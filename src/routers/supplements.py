"""CRUD endpoints for supplements and supplement logs."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.dependencies import CurrentUser
from src.models.tracking import (
    SupplementCreate,
    SupplementLogCreate,
    SupplementLogRead,
    SupplementRead,
    SupplementUpdate,
)
from src.services.supabase import fetch, fetchrow, get_connection

router = APIRouter(prefix="/supplements", tags=["supplements"])


@router.get("", response_model=list[SupplementRead])
async def list_supplements(
    user: CurrentUser,
    active_only: bool = Query(default=True),
) -> Any:
    if active_only:
        rows = await fetch(
            """
            SELECT * FROM supplements
            WHERE user_id = $1 AND deleted_at IS NULL AND ended_at IS NULL
            ORDER BY name
            """,
            user.vitalis_user_id,
            user_id=user.vitalis_user_id,
        )
    else:
        rows = await fetch(
            """
            SELECT * FROM supplements
            WHERE user_id = $1 AND deleted_at IS NULL
            ORDER BY started_at DESC NULLS LAST
            """,
            user.vitalis_user_id,
            user_id=user.vitalis_user_id,
        )
    return [dict(r) for r in rows]


@router.post("", response_model=SupplementRead, status_code=201)
async def create_supplement(user: CurrentUser, body: SupplementCreate) -> Any:
    row = await fetchrow(
        """
        INSERT INTO supplements (
            supplement_id, user_id, name, brand, dose_amount, dose_unit,
            frequency, timing, started_at, ended_at, purpose, notes
        ) VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        RETURNING *
        """,
        user.vitalis_user_id,
        body.name, body.brand, body.dose_amount, body.dose_unit,
        body.frequency, body.timing, body.started_at, body.ended_at,
        body.purpose, body.notes,
        user_id=user.vitalis_user_id,
    )
    return dict(row)


@router.get("/{supplement_id}", response_model=SupplementRead)
async def get_supplement(supplement_id: uuid.UUID, user: CurrentUser) -> Any:
    row = await fetchrow(
        "SELECT * FROM supplements WHERE supplement_id = $1 AND user_id = $2 AND deleted_at IS NULL",
        supplement_id, user.vitalis_user_id,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Supplement not found")
    return dict(row)


@router.patch("/{supplement_id}", response_model=SupplementRead)
async def update_supplement(
    supplement_id: uuid.UUID, user: CurrentUser, body: SupplementUpdate
) -> Any:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clauses = []
    params: list[Any] = [supplement_id, user.vitalis_user_id]
    for i, (key, value) in enumerate(updates.items(), start=3):
        set_clauses.append(f"{key} = ${i}")
        params.append(value)
    set_clauses.append("updated_at = NOW()")

    row = await fetchrow(
        f"""
        UPDATE supplements SET {', '.join(set_clauses)}
        WHERE supplement_id = $1 AND user_id = $2 AND deleted_at IS NULL
        RETURNING *
        """,
        *params,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Supplement not found")
    return dict(row)


@router.delete("/{supplement_id}", status_code=204)
async def delete_supplement(supplement_id: uuid.UUID, user: CurrentUser) -> None:
    async with get_connection(user_id=user.vitalis_user_id) as conn:
        result = await conn.execute(
            """
            UPDATE supplements SET deleted_at = NOW(), updated_at = NOW()
            WHERE supplement_id = $1 AND user_id = $2 AND deleted_at IS NULL
            """,
            supplement_id, user.vitalis_user_id,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Supplement not found")


# ---------- Supplement Logs ----------

@router.post("/{supplement_id}/logs", response_model=SupplementLogRead, status_code=201)
async def create_log(
    supplement_id: uuid.UUID, user: CurrentUser, body: SupplementLogCreate
) -> Any:
    row = await fetchrow(
        """
        INSERT INTO supplement_logs (
            log_id, supplement_id, user_id, taken_at, dose_amount, dose_unit, notes
        ) VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        supplement_id, user.vitalis_user_id,
        body.taken_at, body.dose_amount, body.dose_unit, body.notes,
        user_id=user.vitalis_user_id,
    )
    return dict(row)


@router.get("/{supplement_id}/logs", response_model=list[SupplementLogRead])
async def list_logs(
    supplement_id: uuid.UUID,
    user: CurrentUser,
    limit: int = Query(default=30, ge=1, le=200),
) -> Any:
    rows = await fetch(
        """
        SELECT * FROM supplement_logs
        WHERE supplement_id = $1 AND user_id = $2
        ORDER BY taken_at DESC
        LIMIT $3
        """,
        supplement_id, user.vitalis_user_id, limit,
        user_id=user.vitalis_user_id,
    )
    return [dict(r) for r in rows]
