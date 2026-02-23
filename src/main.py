"""Vitalis API — FastAPI application entry point.

Run locally:
    uvicorn src.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.middleware.clerk_auth import ClerkAuthMiddleware
from src.middleware.rate_limit import RateLimitMiddleware
from src.middleware.security import SecurityHeadersMiddleware
from src.routers import (
    blood_work,
    documents,
    goals,
    health,
    measurements,
    mood_journal,
    parsers,
    supplements,
    users,
    wearables,
    webhooks,
)
from src.services.supabase import close_pool, init_pool

# ---------- Logging ----------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("vitalis")


# ---------- Lifespan ----------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown hooks."""
    settings = get_settings()
    logger.info(
        "Starting Vitalis API v%s [%s]",
        settings.app_version,
        settings.environment,
    )
    await init_pool(settings)
    yield
    await close_pool()
    logger.info("Vitalis API shut down")


# ---------- App factory ----------

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Vitalis API",
        description=(
            "Personal health intelligence platform — unified wearable data, "
            "blood work tracking, AI-powered insights, and more."
        ),
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ---------- Middleware (order matters — outermost first) ----------

    # Security headers on every response
    app.add_middleware(SecurityHeadersMiddleware)

    # Rate limiting
    app.add_middleware(RateLimitMiddleware, settings=settings)

    # Clerk JWT authentication
    app.add_middleware(ClerkAuthMiddleware, settings=settings)

    # CORS — must be the innermost middleware so it can handle preflight
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "Retry-After"],
    )

    # ---------- Health check (outside v1 prefix — always at /health) ----------
    app.include_router(health.router)

    # ---------- Webhooks (outside v1 prefix — Clerk posts to /api/v1/webhooks/clerk) ----------
    app.include_router(webhooks.router, prefix="/api/v1")

    # ---------- API v1 routes ----------
    v1_prefix = "/api/v1"

    app.include_router(users.router, prefix=v1_prefix)
    app.include_router(wearables.router, prefix=v1_prefix)
    app.include_router(blood_work.router, prefix=v1_prefix)
    app.include_router(supplements.router, prefix=v1_prefix)
    app.include_router(mood_journal.router, prefix=v1_prefix)
    app.include_router(goals.router, prefix=v1_prefix)
    app.include_router(measurements.router, prefix=v1_prefix)
    app.include_router(documents.router, prefix=v1_prefix)
    app.include_router(parsers.router, prefix=v1_prefix)

    return app


app = create_app()
