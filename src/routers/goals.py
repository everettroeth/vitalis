"""CRUD endpoints for goals and goal alerts."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.dependencies import CurrentUser
from src.models.goals import GoalAlertRead, GoalCreate, GoalRead, GoalUpdate
from src.services.supabase import fetch, fetchrow, get_connection

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("", response_model=list[GoalRead])
async def list_goals(
    user: CurrentUser,
    active_only: bool = Query(default=True),
) -> Any:
    if active_only:
        rows = await fetch(
            "SELECT * FROM goals WHERE user_id = $1 AND is_active = TRUE ORDER BY created_at DESC",
            user.vitalis_user_id,
            user_id=user.vitalis_user_id,
        )
    else:
        rows = await fetch(
            "SELECT * FROM goals WHERE user_id = $1 ORDER BY created_at DESC",
            user.vitalis_user_id,
            user_id=user.vitalis_user_id,
        )
    return [dict(r) for r in rows]


@router.post("", response_model=GoalRead, status_code=201)
async def create_goal(user: CurrentUser, body: GoalCreate) -> Any:
    row = await fetchrow(
        """
        INSERT INTO goals (
            goal_id, user_id, metric_type, biomarker_id, metric_name,
            target_value, target_unit, direction, alert_threshold_low,
            alert_threshold_high, alert_enabled, notes, is_active
        ) VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        RETURNING *
        """,
        user.vitalis_user_id,
        body.metric_type, body.biomarker_id, body.metric_name,
        body.target_value, body.target_unit, body.direction,
        body.alert_threshold_low, body.alert_threshold_high,
        body.alert_enabled, body.notes, body.is_active,
        user_id=user.vitalis_user_id,
    )
    return dict(row)


@router.get("/{goal_id}", response_model=GoalRead)
async def get_goal(goal_id: uuid.UUID, user: CurrentUser) -> Any:
    row = await fetchrow(
        "SELECT * FROM goals WHERE goal_id = $1 AND user_id = $2",
        goal_id, user.vitalis_user_id,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Goal not found")
    return dict(row)


@router.patch("/{goal_id}", response_model=GoalRead)
async def update_goal(
    goal_id: uuid.UUID, user: CurrentUser, body: GoalUpdate
) -> Any:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clauses = []
    params: list[Any] = [goal_id, user.vitalis_user_id]
    for i, (key, value) in enumerate(updates.items(), start=3):
        set_clauses.append(f"{key} = ${i}")
        params.append(value)
    set_clauses.append("updated_at = NOW()")

    row = await fetchrow(
        f"UPDATE goals SET {', '.join(set_clauses)} WHERE goal_id = $1 AND user_id = $2 RETURNING *",
        *params,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Goal not found")
    return dict(row)


@router.delete("/{goal_id}", status_code=204)
async def delete_goal(goal_id: uuid.UUID, user: CurrentUser) -> None:
    async with get_connection(user_id=user.vitalis_user_id) as conn:
        result = await conn.execute(
            "DELETE FROM goals WHERE goal_id = $1 AND user_id = $2",
            goal_id, user.vitalis_user_id,
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Goal not found")


# ---------- Goal Alerts ----------

@router.get("/{goal_id}/alerts", response_model=list[GoalAlertRead])
async def list_alerts(
    goal_id: uuid.UUID,
    user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> Any:
    rows = await fetch(
        """
        SELECT * FROM goal_alerts
        WHERE goal_id = $1 AND user_id = $2
        ORDER BY triggered_at DESC
        LIMIT $3
        """,
        goal_id, user.vitalis_user_id, limit,
        user_id=user.vitalis_user_id,
    )
    return [dict(r) for r in rows]


@router.post("/{goal_id}/alerts/{alert_id}/acknowledge", response_model=GoalAlertRead)
async def acknowledge_alert(
    goal_id: uuid.UUID, alert_id: uuid.UUID, user: CurrentUser
) -> Any:
    row = await fetchrow(
        """
        UPDATE goal_alerts SET acknowledged_at = NOW()
        WHERE alert_id = $1 AND goal_id = $2 AND user_id = $3
        RETURNING *
        """,
        alert_id, goal_id, user.vitalis_user_id,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")
    return dict(row)
