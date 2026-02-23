"""CRUD endpoints for mood journal entries."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.dependencies import CurrentUser
from src.models.tracking import MoodJournalCreate, MoodJournalRead, MoodJournalUpdate
from src.services.supabase import fetch, fetchrow, get_connection

router = APIRouter(prefix="/mood-journal", tags=["mood journal"])


@router.get("", response_model=list[MoodJournalRead])
async def list_entries(
    user: CurrentUser,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=365),
) -> Any:
    conditions = ["user_id = $1", "deleted_at IS NULL"]
    params: list[Any] = [user.vitalis_user_id]
    idx = 2

    if start_date:
        conditions.append(f"journal_date >= ${idx}")
        params.append(start_date)
        idx += 1
    if end_date:
        conditions.append(f"journal_date <= ${idx}")
        params.append(end_date)
        idx += 1

    where = " AND ".join(conditions)
    rows = await fetch(
        f"SELECT * FROM mood_journal WHERE {where} ORDER BY journal_date DESC LIMIT ${idx}",
        *params, limit,
        user_id=user.vitalis_user_id,
    )
    return [dict(r) for r in rows]


@router.post("", response_model=MoodJournalRead, status_code=201)
async def create_entry(user: CurrentUser, body: MoodJournalCreate) -> Any:
    row = await fetchrow(
        """
        INSERT INTO mood_journal (
            journal_id, user_id, journal_date, mood_score, energy_score, stress_score, notes
        ) VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6)
        ON CONFLICT (user_id, journal_date) DO UPDATE SET
            mood_score = EXCLUDED.mood_score,
            energy_score = EXCLUDED.energy_score,
            stress_score = EXCLUDED.stress_score,
            notes = EXCLUDED.notes,
            updated_at = NOW()
        RETURNING *
        """,
        user.vitalis_user_id,
        body.journal_date, body.mood_score, body.energy_score,
        body.stress_score, body.notes,
        user_id=user.vitalis_user_id,
    )
    return dict(row)


@router.get("/{journal_id}", response_model=MoodJournalRead)
async def get_entry(journal_id: uuid.UUID, user: CurrentUser) -> Any:
    row = await fetchrow(
        "SELECT * FROM mood_journal WHERE journal_id = $1 AND user_id = $2 AND deleted_at IS NULL",
        journal_id, user.vitalis_user_id,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return dict(row)


@router.patch("/{journal_id}", response_model=MoodJournalRead)
async def update_entry(
    journal_id: uuid.UUID, user: CurrentUser, body: MoodJournalUpdate
) -> Any:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clauses = []
    params: list[Any] = [journal_id, user.vitalis_user_id]
    for i, (key, value) in enumerate(updates.items(), start=3):
        set_clauses.append(f"{key} = ${i}")
        params.append(value)
    set_clauses.append("updated_at = NOW()")

    row = await fetchrow(
        f"""
        UPDATE mood_journal SET {', '.join(set_clauses)}
        WHERE journal_id = $1 AND user_id = $2 AND deleted_at IS NULL
        RETURNING *
        """,
        *params,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return dict(row)


@router.delete("/{journal_id}", status_code=204)
async def delete_entry(journal_id: uuid.UUID, user: CurrentUser) -> None:
    async with get_connection(user_id=user.vitalis_user_id) as conn:
        result = await conn.execute(
            """
            UPDATE mood_journal SET deleted_at = NOW(), updated_at = NOW()
            WHERE journal_id = $1 AND user_id = $2 AND deleted_at IS NULL
            """,
            journal_id, user.vitalis_user_id,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Journal entry not found")
