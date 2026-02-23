"""Clerk JWT verification middleware for FastAPI.

Validates the Bearer token on every request (except public routes),
extracts claims, and sets ``request.state.auth`` with the authenticated
user context that downstream route handlers consume via ``get_current_user``.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
import jwt as pyjwt
from fastapi import Request, Response
from jwt import PyJWKClient
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from src.config import Settings, get_settings
from src.dependencies import AuthContext

logger = logging.getLogger("vitalis.auth")

# Paths that do not require authentication
PUBLIC_PATHS: set[str] = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/v1/webhooks/clerk",
}


def _is_public(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/redoc")


class ClerkAuthMiddleware(BaseHTTPMiddleware):
    """Verify Clerk-issued JWTs and populate request.state.auth."""

    def __init__(self, app: Any, settings: Settings | None = None) -> None:
        super().__init__(app)
        self._settings = settings or get_settings()
        self._jwks_client = PyJWKClient(
            self._settings.clerk_jwks_url,
            cache_keys=True,
            lifespan=3600,
        )

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if _is_public(request.url.path):
            return await call_next(request)

        # OPTIONS requests pass through (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return Response(
                content='{"detail":"Missing or invalid Authorization header"}',
                status_code=401,
                media_type="application/json",
            )

        token = auth_header.removeprefix("Bearer ").strip()

        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            payload = pyjwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                options={"verify_aud": False},  # Clerk tokens use azp, not aud
            )
        except pyjwt.ExpiredSignatureError:
            return Response(
                content='{"detail":"Token expired"}',
                status_code=401,
                media_type="application/json",
            )
        except pyjwt.InvalidTokenError as exc:
            logger.warning("JWT validation failed: %s", exc)
            return Response(
                content='{"detail":"Invalid token"}',
                status_code=401,
                media_type="application/json",
            )

        # Extract Clerk claims
        clerk_user_id: str = payload.get("sub", "")
        email: str | None = payload.get("email")
        session_id: str | None = payload.get("sid")

        # Custom claims set via Clerk session token template
        vitalis_user_id = payload.get("vitalis_user_id")
        account_id = payload.get("account_id")

        request.state.auth = AuthContext(
            user_id=clerk_user_id,
            vitalis_user_id=vitalis_user_id,
            account_id=account_id,
            email=email,
            session_id=session_id,
        )

        return await call_next(request)
