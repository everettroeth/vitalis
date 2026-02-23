"""File upload and document management endpoints (Cloudflare R2)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form

from src.config import get_settings
from src.dependencies import CurrentUser
from src.models.documents import DocumentRead, DocumentType, DocumentUpdate
from src.services.r2 import delete_file, generate_presigned_url, upload_file
from src.services.supabase import fetch, fetchrow, get_connection

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentRead, status_code=201)
async def upload_document(
    user: CurrentUser,
    file: UploadFile = File(...),
    document_type: DocumentType = Form(default=DocumentType.other),
    provider_name: str | None = Form(default=None),
) -> Any:
    """Upload a file (PDF, image) to R2 and create a document record.

    Max file size: 50 MB. Allowed types: PDF, JPEG, PNG, WebP.
    """
    settings = get_settings()

    # Validate content type
    content_type = file.content_type or "application/octet-stream"
    if content_type not in settings.allowed_upload_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{content_type}' not allowed. Accepted: {settings.allowed_upload_types}",
        )

    # Read file data
    file_data = await file.read()
    if len(file_data) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {settings.max_upload_size_bytes // (1024*1024)} MB",
        )

    filename = file.filename or "upload"

    # Upload to R2
    s3_key, file_hash, file_size = await upload_file(
        user_id=user.vitalis_user_id,
        file_data=file_data,
        filename=filename,
        content_type=content_type,
    )

    # Check for duplicate upload
    existing = await fetchrow(
        """
        SELECT document_id FROM documents
        WHERE user_id = $1 AND file_hash = $2 AND deleted_at IS NULL
        """,
        user.vitalis_user_id, file_hash,
        user_id=user.vitalis_user_id,
    )
    if existing:
        # Clean up the R2 upload since we already have this file
        await delete_file(s3_key)
        raise HTTPException(
            status_code=409,
            detail="This file has already been uploaded",
        )

    # Create document record
    row = await fetchrow(
        """
        INSERT INTO documents (
            document_id, user_id, document_type, provider_name,
            original_filename, s3_key, file_hash, file_size_bytes, mime_type
        ) VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING *
        """,
        user.vitalis_user_id,
        document_type, provider_name,
        filename, s3_key, file_hash, file_size, content_type,
        user_id=user.vitalis_user_id,
    )
    return dict(row)


@router.get("", response_model=list[DocumentRead])
async def list_documents(
    user: CurrentUser,
    document_type: DocumentType | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> Any:
    if document_type:
        rows = await fetch(
            """
            SELECT * FROM documents
            WHERE user_id = $1 AND document_type = $2 AND deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT $3
            """,
            user.vitalis_user_id, document_type, limit,
            user_id=user.vitalis_user_id,
        )
    else:
        rows = await fetch(
            """
            SELECT * FROM documents
            WHERE user_id = $1 AND deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT $2
            """,
            user.vitalis_user_id, limit,
            user_id=user.vitalis_user_id,
        )
    return [dict(r) for r in rows]


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(document_id: uuid.UUID, user: CurrentUser) -> Any:
    row = await fetchrow(
        "SELECT * FROM documents WHERE document_id = $1 AND user_id = $2 AND deleted_at IS NULL",
        document_id, user.vitalis_user_id,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    return dict(row)


@router.get("/{document_id}/download-url")
async def get_download_url(document_id: uuid.UUID, user: CurrentUser) -> dict:
    """Generate a time-limited presigned URL to download the file."""
    row = await fetchrow(
        "SELECT s3_key FROM documents WHERE document_id = $1 AND user_id = $2 AND deleted_at IS NULL",
        document_id, user.vitalis_user_id,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    url = await generate_presigned_url(row["s3_key"])
    return {"url": url, "expires_in": 3600}


@router.patch("/{document_id}", response_model=DocumentRead)
async def update_document(
    document_id: uuid.UUID, user: CurrentUser, body: DocumentUpdate
) -> Any:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clauses = []
    params: list[Any] = [document_id, user.vitalis_user_id]
    for i, (key, value) in enumerate(updates.items(), start=3):
        set_clauses.append(f"{key} = ${i}")
        params.append(value)
    set_clauses.append("updated_at = NOW()")

    row = await fetchrow(
        f"""
        UPDATE documents SET {', '.join(set_clauses)}
        WHERE document_id = $1 AND user_id = $2 AND deleted_at IS NULL
        RETURNING *
        """,
        *params,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    return dict(row)


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: uuid.UUID, user: CurrentUser) -> None:
    """Soft-delete document record. R2 file cleaned up by background job."""
    async with get_connection(user_id=user.vitalis_user_id) as conn:
        result = await conn.execute(
            """
            UPDATE documents SET deleted_at = NOW(), updated_at = NOW()
            WHERE document_id = $1 AND user_id = $2 AND deleted_at IS NULL
            """,
            document_id, user.vitalis_user_id,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Document not found")
