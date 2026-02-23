"""CRUD endpoints for measurements and custom metrics."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.dependencies import CurrentUser
from src.models.tracking import (
    CustomMetricCreate,
    CustomMetricEntryCreate,
    CustomMetricEntryRead,
    CustomMetricRead,
    MeasurementCreate,
    MeasurementRead,
    MeasurementUpdate,
)
from src.services.supabase import fetch, fetchrow, get_connection

router = APIRouter(prefix="/measurements", tags=["measurements"])


# ---------- Measurements ----------

@router.get("", response_model=list[MeasurementRead])
async def list_measurements(
    user: CurrentUser,
    metric: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=365),
) -> Any:
    conditions = ["user_id = $1", "deleted_at IS NULL"]
    params: list[Any] = [user.vitalis_user_id]
    idx = 2

    if metric:
        conditions.append(f"metric = ${idx}")
        params.append(metric)
        idx += 1

    where = " AND ".join(conditions)
    rows = await fetch(
        f"SELECT * FROM measurements WHERE {where} ORDER BY measured_at DESC LIMIT ${idx}",
        *params, limit,
        user_id=user.vitalis_user_id,
    )
    return [dict(r) for r in rows]


@router.post("", response_model=MeasurementRead, status_code=201)
async def create_measurement(user: CurrentUser, body: MeasurementCreate) -> Any:
    row = await fetchrow(
        """
        INSERT INTO measurements (
            measurement_id, user_id, metric, value, unit, measured_at, source, notes
        ) VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7)
        RETURNING *
        """,
        user.vitalis_user_id,
        body.metric, body.value, body.unit, body.measured_at,
        body.source, body.notes,
        user_id=user.vitalis_user_id,
    )
    return dict(row)


@router.get("/{measurement_id}", response_model=MeasurementRead)
async def get_measurement(measurement_id: uuid.UUID, user: CurrentUser) -> Any:
    row = await fetchrow(
        "SELECT * FROM measurements WHERE measurement_id = $1 AND user_id = $2 AND deleted_at IS NULL",
        measurement_id, user.vitalis_user_id,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Measurement not found")
    return dict(row)


@router.patch("/{measurement_id}", response_model=MeasurementRead)
async def update_measurement(
    measurement_id: uuid.UUID, user: CurrentUser, body: MeasurementUpdate
) -> Any:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clauses = []
    params: list[Any] = [measurement_id, user.vitalis_user_id]
    for i, (key, value) in enumerate(updates.items(), start=3):
        set_clauses.append(f"{key} = ${i}")
        params.append(value)
    set_clauses.append("updated_at = NOW()")

    row = await fetchrow(
        f"""
        UPDATE measurements SET {', '.join(set_clauses)}
        WHERE measurement_id = $1 AND user_id = $2 AND deleted_at IS NULL
        RETURNING *
        """,
        *params,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Measurement not found")
    return dict(row)


@router.delete("/{measurement_id}", status_code=204)
async def delete_measurement(measurement_id: uuid.UUID, user: CurrentUser) -> None:
    async with get_connection(user_id=user.vitalis_user_id) as conn:
        result = await conn.execute(
            """
            UPDATE measurements SET deleted_at = NOW(), updated_at = NOW()
            WHERE measurement_id = $1 AND user_id = $2 AND deleted_at IS NULL
            """,
            measurement_id, user.vitalis_user_id,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Measurement not found")


# ---------- Custom Metrics ----------

@router.get("/custom", response_model=list[CustomMetricRead])
async def list_custom_metrics(user: CurrentUser) -> Any:
    rows = await fetch(
        "SELECT * FROM custom_metrics WHERE user_id = $1 AND is_active = TRUE ORDER BY name",
        user.vitalis_user_id,
        user_id=user.vitalis_user_id,
    )
    return [dict(r) for r in rows]


@router.post("/custom", response_model=CustomMetricRead, status_code=201)
async def create_custom_metric(user: CurrentUser, body: CustomMetricCreate) -> Any:
    row = await fetchrow(
        """
        INSERT INTO custom_metrics (
            metric_id, user_id, name, unit, data_type, min_value, max_value, is_active
        ) VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7)
        RETURNING *
        """,
        user.vitalis_user_id,
        body.name, body.unit, body.data_type, body.min_value, body.max_value, body.is_active,
        user_id=user.vitalis_user_id,
    )
    return dict(row)


@router.post("/custom/{metric_id}/entries", response_model=CustomMetricEntryRead, status_code=201)
async def create_custom_entry(
    metric_id: uuid.UUID, user: CurrentUser, body: CustomMetricEntryCreate
) -> Any:
    row = await fetchrow(
        """
        INSERT INTO custom_metric_entries (
            entry_id, metric_id, user_id, value_numeric, value_text, measured_at, notes
        ) VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        metric_id, user.vitalis_user_id,
        body.value_numeric, body.value_text, body.measured_at, body.notes,
        user_id=user.vitalis_user_id,
    )
    return dict(row)


@router.get("/custom/{metric_id}/entries", response_model=list[CustomMetricEntryRead])
async def list_custom_entries(
    metric_id: uuid.UUID,
    user: CurrentUser,
    limit: int = Query(default=30, ge=1, le=365),
) -> Any:
    rows = await fetch(
        """
        SELECT * FROM custom_metric_entries
        WHERE metric_id = $1 AND user_id = $2
        ORDER BY measured_at DESC
        LIMIT $3
        """,
        metric_id, user.vitalis_user_id, limit,
        user_id=user.vitalis_user_id,
    )
    return [dict(r) for r in rows]
