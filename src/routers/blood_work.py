"""CRUD endpoints for blood panels, blood markers, and biomarker dictionary lookups."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.dependencies import CurrentUser
from src.models.blood_work import (
    BiomarkerDictionaryRead,
    BloodMarkerCreate,
    BloodMarkerRead,
    BloodMarkerUpdate,
    BloodPanelCreate,
    BloodPanelRead,
    BloodPanelUpdate,
)
from src.services.supabase import fetch, fetchrow, get_connection

router = APIRouter(prefix="/blood-work", tags=["blood work"])


# ---------- Blood Panels ----------

@router.get("/panels", response_model=list[BloodPanelRead])
async def list_panels(
    user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> Any:
    rows = await fetch(
        """
        SELECT * FROM blood_panels
        WHERE user_id = $1 AND deleted_at IS NULL
        ORDER BY collected_at DESC NULLS LAST
        LIMIT $2
        """,
        user.vitalis_user_id, limit,
        user_id=user.vitalis_user_id,
    )
    return [dict(r) for r in rows]


@router.post("/panels", response_model=BloodPanelRead, status_code=201)
async def create_panel(user: CurrentUser, body: BloodPanelCreate) -> Any:
    row = await fetchrow(
        """
        INSERT INTO blood_panels (
            panel_id, user_id, lab_name, lab_provider, panel_name,
            collected_at, reported_at, fasting, specimen_id, document_id, notes
        ) VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING *
        """,
        user.vitalis_user_id,
        body.lab_name, body.lab_provider, body.panel_name,
        body.collected_at, body.reported_at, body.fasting,
        body.specimen_id, body.document_id, body.notes,
        user_id=user.vitalis_user_id,
    )
    return dict(row)


@router.get("/panels/{panel_id}", response_model=BloodPanelRead)
async def get_panel(panel_id: uuid.UUID, user: CurrentUser) -> Any:
    row = await fetchrow(
        "SELECT * FROM blood_panels WHERE panel_id = $1 AND user_id = $2 AND deleted_at IS NULL",
        panel_id, user.vitalis_user_id,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Panel not found")
    return dict(row)


@router.patch("/panels/{panel_id}", response_model=BloodPanelRead)
async def update_panel(
    panel_id: uuid.UUID, user: CurrentUser, body: BloodPanelUpdate
) -> Any:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clauses = []
    params: list[Any] = [panel_id, user.vitalis_user_id]
    for i, (key, value) in enumerate(updates.items(), start=3):
        set_clauses.append(f"{key} = ${i}")
        params.append(value)
    set_clauses.append("updated_at = NOW()")

    row = await fetchrow(
        f"""
        UPDATE blood_panels SET {', '.join(set_clauses)}
        WHERE panel_id = $1 AND user_id = $2 AND deleted_at IS NULL
        RETURNING *
        """,
        *params,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Panel not found")
    return dict(row)


@router.delete("/panels/{panel_id}", status_code=204)
async def delete_panel(panel_id: uuid.UUID, user: CurrentUser) -> None:
    """Soft-delete a blood panel."""
    async with get_connection(user_id=user.vitalis_user_id) as conn:
        result = await conn.execute(
            """
            UPDATE blood_panels SET deleted_at = NOW(), updated_at = NOW()
            WHERE panel_id = $1 AND user_id = $2 AND deleted_at IS NULL
            """,
            panel_id, user.vitalis_user_id,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Panel not found")


# ---------- Blood Markers ----------

@router.get("/panels/{panel_id}/markers", response_model=list[BloodMarkerRead])
async def list_markers(panel_id: uuid.UUID, user: CurrentUser) -> Any:
    rows = await fetch(
        """
        SELECT * FROM blood_markers
        WHERE panel_id = $1 AND user_id = $2
        ORDER BY raw_name
        """,
        panel_id, user.vitalis_user_id,
        user_id=user.vitalis_user_id,
    )
    return [dict(r) for r in rows]


@router.post("/markers", response_model=BloodMarkerRead, status_code=201)
async def create_marker(user: CurrentUser, body: BloodMarkerCreate) -> Any:
    row = await fetchrow(
        """
        INSERT INTO blood_markers (
            marker_id, user_id, panel_id, biomarker_id, collected_at,
            raw_name, sub_panel, value_numeric, value_text, unit,
            value_canonical, ref_range_low, ref_range_high, ref_range_text,
            flag, in_range, optimal_low, optimal_high, lab_code, parse_confidence
        ) VALUES (
            gen_random_uuid(), $1, $2, $3, $4,
            $5, $6, $7, $8, $9,
            $10, $11, $12, $13,
            $14, $15, $16, $17, $18, $19
        ) RETURNING *
        """,
        user.vitalis_user_id,
        body.panel_id, body.biomarker_id, body.collected_at,
        body.raw_name, body.sub_panel, body.value_numeric, body.value_text, body.unit,
        body.value_canonical, body.ref_range_low, body.ref_range_high, body.ref_range_text,
        body.flag, body.in_range, body.optimal_low, body.optimal_high,
        body.lab_code, body.parse_confidence,
        user_id=user.vitalis_user_id,
    )
    return dict(row)


@router.patch("/markers/{marker_id}", response_model=BloodMarkerRead)
async def update_marker(
    marker_id: uuid.UUID, user: CurrentUser, body: BloodMarkerUpdate
) -> Any:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clauses = []
    params: list[Any] = [marker_id, user.vitalis_user_id]
    for i, (key, value) in enumerate(updates.items(), start=3):
        set_clauses.append(f"{key} = ${i}")
        params.append(value)
    set_clauses.append("updated_at = NOW()")

    row = await fetchrow(
        f"""
        UPDATE blood_markers SET {', '.join(set_clauses)}
        WHERE marker_id = $1 AND user_id = $2
        RETURNING *
        """,
        *params,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Marker not found")
    return dict(row)


# ---------- Biomarker trend (across panels) ----------

@router.get("/markers/trend/{biomarker_id}", response_model=list[BloodMarkerRead])
async def get_marker_trend(
    biomarker_id: uuid.UUID,
    user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> Any:
    """Get historical values for a single biomarker across all panels."""
    rows = await fetch(
        """
        SELECT * FROM blood_markers
        WHERE user_id = $1 AND biomarker_id = $2
        ORDER BY collected_at DESC
        LIMIT $3
        """,
        user.vitalis_user_id, biomarker_id, limit,
        user_id=user.vitalis_user_id,
    )
    return [dict(r) for r in rows]


# ---------- Biomarker Dictionary (public read-only) ----------

@router.get("/biomarkers", response_model=list[BiomarkerDictionaryRead])
async def list_biomarkers(
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> Any:
    """Search the canonical biomarker dictionary. No auth required for reads."""
    conditions = []
    params: list[Any] = []
    idx = 1

    if category:
        conditions.append(f"category = ${idx}")
        params.append(category)
        idx += 1
    if search:
        conditions.append(f"(display_name ILIKE ${idx} OR aliases @> ARRAY[lower(${idx})])")
        params.append(f"%{search}%")
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = await fetch(
        f"SELECT * FROM biomarker_dictionary {where} ORDER BY category, sort_order LIMIT ${idx}",
        *params, limit,
    )
    return [dict(r) for r in rows]
