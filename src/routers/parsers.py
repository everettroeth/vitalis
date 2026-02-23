"""Lab PDF parser API endpoints.

Endpoints:
    POST /documents/upload           — Upload PDF, parse immediately, return result
    GET  /documents/{id}/parse-result — Retrieve stored parse result for a document
    POST /documents/{id}/confirm      — User confirms or corrects parsed values
    POST /documents/{id}/reparse      — Force re-parse a previously uploaded document
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form

from src.config import get_settings
from src.dependencies import CurrentUser
from src.models.documents import DocumentType, ParseStatus
from src.parsers import parse_document
from src.parsers.base import ConfidenceLevel, MarkerResult, ParseResult
from src.services.r2 import delete_file, upload_file
from src.services.supabase import fetch, fetchrow, get_connection

logger = logging.getLogger("vitalis.routers.parsers")

router = APIRouter(prefix="/documents", tags=["parsers"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

from pydantic import BaseModel, Field


class MarkerConfirmation(BaseModel):
    """User-supplied correction for a single parsed marker."""

    canonical_name: str
    value: float | None = None
    unit: str | None = None
    flag: str | None = None
    confirmed: bool = True
    notes: str | None = None


class ParseConfirmRequest(BaseModel):
    """Body for the confirm endpoint."""

    collection_date: str | None = None      # ISO date string YYYY-MM-DD
    lab_name: str | None = None
    markers: list[MarkerConfirmation] = Field(default_factory=list)
    notes: str | None = None


class ParseResultResponse(BaseModel):
    """Serialised parse result returned to the client."""

    document_id: uuid.UUID
    parse_status: str
    parser_used: str | None
    format_detected: str | None
    confidence: str | None
    collection_date: str | None
    lab_name: str | None
    ordering_provider: str | None
    markers: list[dict]
    warnings: list[str]
    needs_review: bool
    pages: int
    parse_time_ms: int
    error: str | None


# ---------------------------------------------------------------------------
# POST /documents/upload
# ---------------------------------------------------------------------------


@router.post("/upload/parse", response_model=ParseResultResponse, status_code=201)
async def upload_and_parse(
    user: CurrentUser,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_type: DocumentType = Form(default=DocumentType.blood_work),
    provider_name: str | None = Form(default=None),
) -> Any:
    """Upload a lab PDF, parse it immediately, and return structured results.

    - Validates file type and size
    - Uploads to R2
    - Parses synchronously (< 3s for most PDFs)
    - Stores parse result in the ``documents`` table
    - Returns the full parse result including all extracted markers

    The caller should check ``confidence`` and ``needs_review`` to decide
    whether to show the user a confirmation UI.
    """
    settings = get_settings()

    # --- Validate file ---
    content_type = file.content_type or "application/octet-stream"
    if content_type not in settings.allowed_upload_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{content_type}' not allowed. Accepted: {settings.allowed_upload_types}",
        )

    file_data = await file.read()
    if len(file_data) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max: {settings.max_upload_size_bytes // (1024 * 1024)} MB",
        )

    filename = file.filename or "upload.pdf"

    # --- Upload to R2 ---
    s3_key, file_hash, file_size = await upload_file(
        user_id=user.vitalis_user_id,
        file_data=file_data,
        filename=filename,
        content_type=content_type,
    )

    # --- Duplicate check ---
    existing = await fetchrow(
        """
        SELECT document_id, parse_status, parse_result
        FROM documents
        WHERE user_id = $1 AND file_hash = $2 AND deleted_at IS NULL
        """,
        user.vitalis_user_id,
        file_hash,
        user_id=user.vitalis_user_id,
    )
    if existing:
        await delete_file(s3_key)
        raise HTTPException(
            status_code=409,
            detail="This file has already been uploaded",
        )

    # --- Parse PDF ---
    logger.info("Parsing %s for user %s", filename, user.vitalis_user_id)
    result: ParseResult = parse_document(file_data, filename)

    # --- Persist document record + parse result ---
    parse_result_json = result.to_dict()
    # Exclude raw_text from stored JSON (can be large)
    parse_result_json.pop("raw_text", None)

    doc_row = await fetchrow(
        """
        INSERT INTO documents (
            document_id, user_id, document_type, provider_name,
            original_filename, s3_key, file_hash, file_size_bytes, mime_type,
            parse_status, parse_confidence, parse_result, parsed_at
        ) VALUES (
            gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, $8,
            $9, $10, $11::jsonb, NOW()
        )
        RETURNING document_id, parse_status
        """,
        user.vitalis_user_id,
        document_type,
        provider_name or result.lab_name,
        filename,
        s3_key,
        file_hash,
        file_size,
        content_type,
        ParseStatus.completed if result.success else ParseStatus.failed,
        float(
            sum(m.confidence for m in result.markers) / len(result.markers)
        )
        if result.markers
        else None,
        __import__("json").dumps(parse_result_json),
        user_id=user.vitalis_user_id,
    )

    # --- Optionally persist markers to blood_panels / blood_markers ---
    if result.success and result.markers and not result.needs_review:
        background_tasks.add_task(
            _persist_blood_work,
            user_id=user.vitalis_user_id,
            document_id=doc_row["document_id"],
            parse_result=result,
        )

    return ParseResultResponse(
        document_id=doc_row["document_id"],
        parse_status=doc_row["parse_status"],
        parser_used=result.parser_used,
        format_detected=result.format_detected,
        confidence=result.confidence.value,
        collection_date=result.collection_date.isoformat()
        if result.collection_date
        else None,
        lab_name=result.lab_name,
        ordering_provider=result.ordering_provider,
        markers=[m.to_dict() for m in result.markers],
        warnings=result.warnings,
        needs_review=result.needs_review,
        pages=result.pages,
        parse_time_ms=result.parse_time_ms,
        error=result.error,
    )


# ---------------------------------------------------------------------------
# GET /documents/{id}/parse-result
# ---------------------------------------------------------------------------


@router.get("/{document_id}/parse-result", response_model=ParseResultResponse)
async def get_parse_result(document_id: uuid.UUID, user: CurrentUser) -> Any:
    """Retrieve the stored parse result for a previously uploaded document."""
    row = await fetchrow(
        """
        SELECT document_id, parse_status, parse_result, error_message
        FROM documents
        WHERE document_id = $1 AND user_id = $2 AND deleted_at IS NULL
        """,
        document_id,
        user.vitalis_user_id,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    if row["parse_result"] is None:
        raise HTTPException(
            status_code=404,
            detail="No parse result available — document may still be processing",
        )

    pr = row["parse_result"]
    return ParseResultResponse(
        document_id=row["document_id"],
        parse_status=row["parse_status"],
        parser_used=pr.get("parser_used"),
        format_detected=pr.get("format_detected"),
        confidence=pr.get("confidence"),
        collection_date=pr.get("collection_date"),
        lab_name=pr.get("lab_name"),
        ordering_provider=pr.get("ordering_provider"),
        markers=pr.get("markers", []),
        warnings=pr.get("warnings", []),
        needs_review=pr.get("needs_review", True),
        pages=pr.get("pages", 0),
        parse_time_ms=pr.get("parse_time_ms", 0),
        error=row.get("error_message"),
    )


# ---------------------------------------------------------------------------
# POST /documents/{id}/confirm
# ---------------------------------------------------------------------------


@router.post("/{document_id}/confirm", status_code=200)
async def confirm_parse_result(
    document_id: uuid.UUID,
    user: CurrentUser,
    body: ParseConfirmRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """User confirms or corrects a parse result.

    - Updates the document's parse_status to 'confirmed'
    - Applies any marker corrections to the stored parse_result JSON
    - Triggers background task to write blood_panels + blood_markers rows
    """
    # Fetch existing document + parse result
    row = await fetchrow(
        """
        SELECT document_id, parse_status, parse_result
        FROM documents
        WHERE document_id = $1 AND user_id = $2 AND deleted_at IS NULL
        """,
        document_id,
        user.vitalis_user_id,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    if row["parse_status"] in (ParseStatus.confirmed,):
        raise HTTPException(
            status_code=409,
            detail="Document has already been confirmed",
        )

    parse_result = dict(row["parse_result"] or {})

    # Apply corrections
    corrections_applied = 0
    if body.markers:
        markers = parse_result.get("markers", [])
        for correction in body.markers:
            for marker in markers:
                if marker.get("canonical_name") == correction.canonical_name:
                    if correction.value is not None:
                        marker["value"] = correction.value
                    if correction.unit is not None:
                        marker["unit"] = correction.unit
                    if correction.flag is not None:
                        marker["flag"] = correction.flag
                    marker["user_confirmed"] = True
                    corrections_applied += 1

    if body.collection_date:
        parse_result["collection_date"] = body.collection_date
    if body.lab_name:
        parse_result["lab_name"] = body.lab_name

    # Update document record
    async with get_connection(user_id=user.vitalis_user_id) as conn:
        await conn.execute(
            """
            UPDATE documents SET
                parse_status = $3,
                parse_result = $4::jsonb,
                confirmed_at = NOW(),
                confirmed_by = $2,
                updated_at = NOW()
            WHERE document_id = $1 AND user_id = $2
            """,
            document_id,
            user.vitalis_user_id,
            ParseStatus.confirmed,
            __import__("json").dumps(parse_result),
        )

    # Persist blood work in background
    background_tasks.add_task(
        _persist_blood_work_from_json,
        user_id=user.vitalis_user_id,
        document_id=document_id,
        parse_result_json=parse_result,
    )

    return {
        "status": "confirmed",
        "document_id": str(document_id),
        "corrections_applied": corrections_applied,
    }


# ---------------------------------------------------------------------------
# POST /documents/{id}/reparse
# ---------------------------------------------------------------------------


@router.post("/{document_id}/reparse", response_model=ParseResultResponse)
async def reparse_document(
    document_id: uuid.UUID,
    user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> Any:
    """Force a re-parse of a previously uploaded document.

    Downloads the file from R2 and runs the parser again.  Useful when
    the parser engine has been improved and you want fresh results.
    """
    import boto3

    row = await fetchrow(
        "SELECT s3_key, original_filename FROM documents WHERE document_id = $1 AND user_id = $2 AND deleted_at IS NULL",
        document_id,
        user.vitalis_user_id,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    settings = get_settings()
    from src.services.r2 import _get_client

    client = _get_client(settings)
    try:
        obj = client.get_object(Bucket=settings.r2_bucket_name, Key=row["s3_key"])
        file_data = obj["Body"].read()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch file from storage: {exc}")

    filename = row["original_filename"] or "document.pdf"
    result = parse_document(file_data, filename)

    parse_result_json = result.to_dict()
    parse_result_json.pop("raw_text", None)

    async with get_connection(user_id=user.vitalis_user_id) as conn:
        await conn.execute(
            """
            UPDATE documents SET
                parse_status = $3,
                parse_confidence = $4,
                parse_result = $5::jsonb,
                parsed_at = NOW(),
                confirmed_at = NULL,
                updated_at = NOW()
            WHERE document_id = $1 AND user_id = $2
            """,
            document_id,
            user.vitalis_user_id,
            ParseStatus.completed if result.success else ParseStatus.failed,
            float(sum(m.confidence for m in result.markers) / len(result.markers))
            if result.markers
            else None,
            __import__("json").dumps(parse_result_json),
        )

    return ParseResultResponse(
        document_id=document_id,
        parse_status=ParseStatus.completed if result.success else ParseStatus.failed,
        parser_used=result.parser_used,
        format_detected=result.format_detected,
        confidence=result.confidence.value,
        collection_date=result.collection_date.isoformat() if result.collection_date else None,
        lab_name=result.lab_name,
        ordering_provider=result.ordering_provider,
        markers=[m.to_dict() for m in result.markers],
        warnings=result.warnings,
        needs_review=result.needs_review,
        pages=result.pages,
        parse_time_ms=result.parse_time_ms,
        error=result.error,
    )


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------


async def _persist_blood_work(
    *,
    user_id: uuid.UUID,
    document_id: uuid.UUID,
    parse_result: ParseResult,
) -> None:
    """Write blood_panels and blood_markers rows from a ParseResult."""
    import json

    try:
        async with get_connection(user_id=user_id) as conn:
            # Create blood_panel
            panel_id = uuid.uuid4()
            await conn.execute(
                """
                INSERT INTO blood_panels (
                    panel_id, user_id, document_id, lab_name, panel_name,
                    collection_date, ordering_provider, source
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT DO NOTHING
                """,
                panel_id,
                user_id,
                document_id,
                parse_result.lab_name,
                parse_result.format_detected,
                parse_result.collection_date,
                parse_result.ordering_provider,
                _lab_name_to_source(parse_result.lab_name),
            )

            # Insert markers
            for marker in parse_result.markers:
                await conn.execute(
                    """
                    INSERT INTO blood_markers (
                        marker_id, panel_id, user_id, biomarker_key,
                        value_number, value_text, unit, flag,
                        reference_low, reference_high, reference_text,
                        confidence_score, page_number
                    ) VALUES (
                        gen_random_uuid(), $1, $2, $3,
                        $4, $5, $6, $7,
                        $8, $9, $10,
                        $11, $12
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    panel_id,
                    user_id,
                    marker.canonical_name,
                    marker.value,
                    marker.value_text,
                    marker.canonical_unit or marker.unit,
                    marker.flag,
                    marker.reference_low,
                    marker.reference_high,
                    marker.reference_text,
                    marker.confidence,
                    marker.page,
                )

        logger.info(
            "Persisted %d markers for document %s",
            len(parse_result.markers),
            document_id,
        )

        # Update document to link to blood panel
        async with get_connection(user_id=user_id) as conn:
            await conn.execute(
                """
                UPDATE documents SET
                    linked_record_id = $3,
                    linked_record_type = 'blood_panel',
                    updated_at = NOW()
                WHERE document_id = $1 AND user_id = $2
                """,
                document_id,
                user_id,
                panel_id,
            )

    except Exception as exc:
        logger.exception("Failed to persist blood work for document %s: %s", document_id, exc)


async def _persist_blood_work_from_json(
    *,
    user_id: uuid.UUID,
    document_id: uuid.UUID,
    parse_result_json: dict,
) -> None:
    """Rebuild a ParseResult from stored JSON and persist blood work."""
    from src.parsers.base import MarkerResult, ParseResult, ConfidenceLevel
    from datetime import date

    markers = []
    for m in parse_result_json.get("markers", []):
        markers.append(
            MarkerResult(
                canonical_name=m.get("canonical_name", ""),
                display_name=m.get("display_name", ""),
                value=m.get("value", 0.0),
                value_text=m.get("value_text", ""),
                unit=m.get("unit", ""),
                canonical_unit=m.get("canonical_unit", ""),
                reference_low=m.get("reference_low"),
                reference_high=m.get("reference_high"),
                reference_text=m.get("reference_text", ""),
                flag=m.get("flag"),
                confidence=m.get("confidence", 0.5),
                page=m.get("page", 1),
            )
        )

    cd_raw = parse_result_json.get("collection_date")
    collection_date = date.fromisoformat(cd_raw) if cd_raw else None

    pr = ParseResult(
        success=True,
        parser_used=parse_result_json.get("parser_used", "unknown"),
        format_detected=parse_result_json.get("format_detected", "Unknown"),
        confidence=ConfidenceLevel(parse_result_json.get("confidence", "medium")),
        lab_name=parse_result_json.get("lab_name"),
        collection_date=collection_date,
        ordering_provider=parse_result_json.get("ordering_provider"),
        markers=markers,
    )
    await _persist_blood_work(
        user_id=user_id,
        document_id=document_id,
        parse_result=pr,
    )


def _lab_name_to_source(lab_name: str | None) -> str:
    """Map a lab name to the data_source enum value."""
    if not lab_name:
        return "other"
    lower = lab_name.lower()
    if "quest" in lower:
        return "quest"
    if "labcorp" in lower or "laboratory corporation" in lower:
        return "labcorp"
    return "other"
