"""CRUD endpoints for wearable data: daily summaries, sleep, activities, connected devices."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.dependencies import CurrentUser
from src.models.wearables import (
    ConnectedDeviceCreate,
    ConnectedDeviceRead,
    ConnectedDeviceUpdate,
    WearableActivityCreate,
    WearableActivityRead,
    WearableDailyCreate,
    WearableDailyRead,
    WearableDailyUpdate,
    WearableSleepCreate,
    WearableSleepRead,
)
from src.services.supabase import fetch, fetchrow, get_connection

router = APIRouter(prefix="/wearables", tags=["wearables"])


# ---------- Connected Devices ----------

@router.get("/devices", response_model=list[ConnectedDeviceRead])
async def list_devices(user: CurrentUser) -> Any:
    rows = await fetch(
        "SELECT * FROM connected_devices WHERE user_id = $1 ORDER BY created_at DESC",
        user.vitalis_user_id,
        user_id=user.vitalis_user_id,
    )
    return [dict(r) for r in rows]


@router.post("/devices", response_model=ConnectedDeviceRead, status_code=201)
async def create_device(user: CurrentUser, body: ConnectedDeviceCreate) -> Any:
    row = await fetchrow(
        """
        INSERT INTO connected_devices (device_id, user_id, source, display_name, external_user_id, scope, is_active)
        VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        user.vitalis_user_id,
        body.source,
        body.display_name,
        body.external_user_id,
        body.scope,
        body.is_active,
        user_id=user.vitalis_user_id,
    )
    return dict(row)


@router.patch("/devices/{device_id}", response_model=ConnectedDeviceRead)
async def update_device(
    device_id: uuid.UUID, user: CurrentUser, body: ConnectedDeviceUpdate
) -> Any:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clauses = []
    params: list[Any] = [user.vitalis_user_id, device_id]
    for i, (key, value) in enumerate(updates.items(), start=3):
        set_clauses.append(f"{key} = ${i}")
        params.append(value)
    set_clauses.append("updated_at = NOW()")

    row = await fetchrow(
        f"UPDATE connected_devices SET {', '.join(set_clauses)} WHERE user_id = $1 AND device_id = $2 RETURNING *",
        *params,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Device not found")
    return dict(row)


@router.delete("/devices/{device_id}", status_code=204)
async def delete_device(device_id: uuid.UUID, user: CurrentUser) -> None:
    async with get_connection(user_id=user.vitalis_user_id) as conn:
        result = await conn.execute(
            "DELETE FROM connected_devices WHERE device_id = $1 AND user_id = $2",
            device_id, user.vitalis_user_id,
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Device not found")


# ---------- Wearable Daily ----------

@router.get("/daily", response_model=list[WearableDailyRead])
async def list_daily(
    user: CurrentUser,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    source: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=365),
) -> Any:
    conditions = ["user_id = $1"]
    params: list[Any] = [user.vitalis_user_id]
    idx = 2

    if start_date:
        conditions.append(f"date >= ${idx}")
        params.append(start_date)
        idx += 1
    if end_date:
        conditions.append(f"date <= ${idx}")
        params.append(end_date)
        idx += 1
    if source:
        conditions.append(f"source = ${idx}")
        params.append(source)
        idx += 1

    conditions.append(f"LIMIT ${idx}")
    params.append(limit)

    where = " AND ".join(conditions[:-1])  # exclude LIMIT from WHERE
    query = f"SELECT * FROM wearable_daily WHERE {where} ORDER BY date DESC LIMIT ${idx}"

    rows = await fetch(query, *params, user_id=user.vitalis_user_id)
    return [dict(r) for r in rows]


@router.post("/daily", response_model=WearableDailyRead, status_code=201)
async def create_daily(user: CurrentUser, body: WearableDailyCreate) -> Any:
    data = body.model_dump(exclude_unset=True)
    data["user_id"] = user.vitalis_user_id
    data["daily_id"] = uuid.uuid4()

    columns = ", ".join(data.keys())
    placeholders = ", ".join(f"${i}" for i in range(1, len(data) + 1))

    row = await fetchrow(
        f"INSERT INTO wearable_daily ({columns}) VALUES ({placeholders}) RETURNING *",
        *data.values(),
        user_id=user.vitalis_user_id,
    )
    return dict(row)


@router.get("/daily/{daily_id}", response_model=WearableDailyRead)
async def get_daily(daily_id: uuid.UUID, user: CurrentUser) -> Any:
    row = await fetchrow(
        "SELECT * FROM wearable_daily WHERE daily_id = $1 AND user_id = $2",
        daily_id, user.vitalis_user_id,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Daily record not found")
    return dict(row)


# ---------- Wearable Sleep ----------

@router.get("/sleep", response_model=list[WearableSleepRead])
async def list_sleep(
    user: CurrentUser,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=365),
) -> Any:
    conditions = ["user_id = $1"]
    params: list[Any] = [user.vitalis_user_id]
    idx = 2

    if start_date:
        conditions.append(f"sleep_date >= ${idx}")
        params.append(start_date)
        idx += 1
    if end_date:
        conditions.append(f"sleep_date <= ${idx}")
        params.append(end_date)
        idx += 1

    where = " AND ".join(conditions)
    rows = await fetch(
        f"SELECT * FROM wearable_sleep WHERE {where} ORDER BY sleep_date DESC LIMIT ${idx}",
        *params, limit,
        user_id=user.vitalis_user_id,
    )
    return [dict(r) for r in rows]


@router.post("/sleep", response_model=WearableSleepRead, status_code=201)
async def create_sleep(user: CurrentUser, body: WearableSleepCreate) -> Any:
    data = body.model_dump(exclude_unset=True)
    data["user_id"] = user.vitalis_user_id
    data["sleep_id"] = uuid.uuid4()

    columns = ", ".join(data.keys())
    placeholders = ", ".join(f"${i}" for i in range(1, len(data) + 1))

    row = await fetchrow(
        f"INSERT INTO wearable_sleep ({columns}) VALUES ({placeholders}) RETURNING *",
        *data.values(),
        user_id=user.vitalis_user_id,
    )
    return dict(row)


# ---------- Wearable Activities ----------

@router.get("/activities", response_model=list[WearableActivityRead])
async def list_activities(
    user: CurrentUser,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    activity_type: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=200),
) -> Any:
    conditions = ["user_id = $1"]
    params: list[Any] = [user.vitalis_user_id]
    idx = 2

    if start_date:
        conditions.append(f"activity_date >= ${idx}")
        params.append(start_date)
        idx += 1
    if end_date:
        conditions.append(f"activity_date <= ${idx}")
        params.append(end_date)
        idx += 1
    if activity_type:
        conditions.append(f"activity_type = ${idx}")
        params.append(activity_type)
        idx += 1

    where = " AND ".join(conditions)
    rows = await fetch(
        f"SELECT * FROM wearable_activities WHERE {where} ORDER BY activity_date DESC LIMIT ${idx}",
        *params, limit,
        user_id=user.vitalis_user_id,
    )
    return [dict(r) for r in rows]


@router.post("/activities", response_model=WearableActivityRead, status_code=201)
async def create_activity(user: CurrentUser, body: WearableActivityCreate) -> Any:
    data = body.model_dump(exclude_unset=True)
    data["user_id"] = user.vitalis_user_id
    data["activity_id"] = uuid.uuid4()

    columns = ", ".join(data.keys())
    placeholders = ", ".join(f"${i}" for i in range(1, len(data) + 1))

    row = await fetchrow(
        f"INSERT INTO wearable_activities ({columns}) VALUES ({placeholders}) RETURNING *",
        *data.values(),
        user_id=user.vitalis_user_id,
    )
    return dict(row)
