"""Health check endpoint — public, no auth required."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from src.config import get_settings
from src.services.supabase import get_pool

router = APIRouter(tags=["system"])
logger = logging.getLogger("vitalis.health")


@router.get("/health")
async def health_check() -> dict:
    """Liveness probe. Returns 200 if the API process is up.

    Also performs a lightweight DB connectivity check.
    """
    settings = get_settings()
    db_ok = False
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_ok = True
    except Exception as exc:
        logger.warning("Health check DB probe failed: %s", exc)

    return {
        "status": "healthy" if db_ok else "degraded",
        "version": settings.app_version,
        "environment": settings.environment,
        "database": "connected" if db_ok else "unreachable",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
