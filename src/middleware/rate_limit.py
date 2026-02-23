"""Simple in-memory sliding-window rate limiter.

For production at scale, replace with Redis-backed rate limiting (e.g. via
``fastapi-limiter`` + Upstash Redis). This in-memory implementation is
sufficient for single-instance deployments and local development.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from src.config import Settings, get_settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP sliding window rate limiter."""

    def __init__(self, app: Any, settings: Settings | None = None) -> None:
        super().__init__(app)
        s = settings or get_settings()
        self._max_requests = s.rate_limit_per_minute
        self._window_seconds = 60
        # ip -> list of timestamps
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _cleanup(self, ip: str, now: float) -> None:
        cutoff = now - self._window_seconds
        self._requests[ip] = [t for t in self._requests[ip] if t > cutoff]

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        ip = self._client_ip(request)
        now = time.monotonic()
        self._cleanup(ip, now)

        if len(self._requests[ip]) >= self._max_requests:
            retry_after = int(self._window_seconds - (now - self._requests[ip][0]))
            return Response(
                content='{"detail":"Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(max(retry_after, 1))},
            )

        self._requests[ip].append(now)

        response = await call_next(request)

        # Inform clients of their remaining budget
        remaining = self._max_requests - len(self._requests[ip])
        response.headers["X-RateLimit-Limit"] = str(self._max_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(remaining, 0))

        return response
