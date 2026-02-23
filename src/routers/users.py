"""User and account management endpoints."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from src.dependencies import CurrentUser
from src.models.users import (
    AccountRead,
    AccountUpdate,
    UserPreferencesRead,
    UserPreferencesUpdate,
    UserRead,
    UserUpdate,
)
from src.services.supabase import fetch, fetchrow, execute, get_connection

router = APIRouter(prefix="/users", tags=["users"])


# ---------- Current User (me) ----------

@router.get("/me", response_model=UserRead)
async def get_current_user_profile(user: CurrentUser) -> Any:
    """Get the authenticated user's profile."""
    row = await fetchrow(
        "SELECT * FROM users WHERE user_id = $1 AND deleted_at IS NULL",
        user.vitalis_user_id,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)


@router.patch("/me", response_model=UserRead)
async def update_current_user(user: CurrentUser, body: UserUpdate) -> Any:
    """Update the authenticated user's profile."""
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clauses = []
    params: list[Any] = []
    for i, (key, value) in enumerate(updates.items(), start=2):
        set_clauses.append(f"{key} = ${i}")
        params.append(value)

    set_clauses.append("updated_at = NOW()")
    query = f"UPDATE users SET {', '.join(set_clauses)} WHERE user_id = $1 AND deleted_at IS NULL RETURNING *"

    row = await fetchrow(
        query, user.vitalis_user_id, *params,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)


# ---------- Account ----------

@router.get("/me/account", response_model=AccountRead)
async def get_account(user: CurrentUser) -> Any:
    """Get the user's account (billing entity)."""
    row = await fetchrow(
        """
        SELECT a.* FROM accounts a
        JOIN users u ON u.account_id = a.account_id
        WHERE u.user_id = $1 AND u.deleted_at IS NULL
        """,
        user.vitalis_user_id,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Account not found")
    return dict(row)


@router.patch("/me/account", response_model=AccountRead)
async def update_account(user: CurrentUser, body: AccountUpdate) -> Any:
    """Update account settings (admin only in future; currently self-service)."""
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clauses = []
    params: list[Any] = []
    for i, (key, value) in enumerate(updates.items(), start=2):
        set_clauses.append(f"{key} = ${i}")
        params.append(value)

    set_clauses.append("updated_at = NOW()")

    row = await fetchrow(
        f"""
        UPDATE accounts SET {', '.join(set_clauses)}
        WHERE account_id = (SELECT account_id FROM users WHERE user_id = $1 AND deleted_at IS NULL)
        RETURNING *
        """,
        user.vitalis_user_id, *params,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Account not found")
    return dict(row)


# ---------- Preferences ----------

@router.get("/me/preferences", response_model=UserPreferencesRead)
async def get_preferences(user: CurrentUser) -> Any:
    row = await fetchrow(
        "SELECT * FROM user_preferences WHERE user_id = $1",
        user.vitalis_user_id,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Preferences not found")
    return dict(row)


@router.patch("/me/preferences", response_model=UserPreferencesRead)
async def update_preferences(user: CurrentUser, body: UserPreferencesUpdate) -> Any:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clauses = []
    params: list[Any] = []
    for i, (key, value) in enumerate(updates.items(), start=2):
        set_clauses.append(f"{key} = ${i}")
        params.append(value)

    set_clauses.append("updated_at = NOW()")

    row = await fetchrow(
        f"UPDATE user_preferences SET {', '.join(set_clauses)} WHERE user_id = $1 RETURNING *",
        user.vitalis_user_id, *params,
        user_id=user.vitalis_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Preferences not found")
    return dict(row)
