"""Shared FastAPI dependencies injected into route handlers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from src.config import Settings, get_settings


@dataclass(frozen=True)
class AuthContext:
    """Authenticated user context extracted from Clerk JWT."""

    user_id: str  # Clerk user ID (e.g. "user_2x...")
    vitalis_user_id: uuid.UUID | None = None  # Our internal UUID, resolved after provisioning
    account_id: uuid.UUID | None = None
    email: str | None = None
    session_id: str | None = None


async def get_current_user(request: Request) -> AuthContext:
    """Extract the authenticated user from the request state.

    The Clerk auth middleware sets ``request.state.auth`` before routes run.
    """
    auth: AuthContext | None = getattr(request.state, "auth", None)
    if auth is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Not authenticated")
    return auth


# Annotated shortcuts for route signatures
CurrentUser = Annotated[AuthContext, Depends(get_current_user)]
AppSettings = Annotated[Settings, Depends(get_settings)]
