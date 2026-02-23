"""Whoop API v1 adapter.

Uses OAuth2 for authentication.

Environment variables:
    WHOOP_CLIENT_ID     — OAuth2 client ID
    WHOOP_CLIENT_SECRET — OAuth2 client secret

API base: https://api.prod.whoop.com/developer

Endpoints used:
    /v1/cycle          — Recovery cycles
    /v1/recovery       — Recovery scores
    /v1/sleep          — Sleep data
    /v1/workout        — Workout sessions
    /v1/user/measurement/body — Body measurements
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta
from typing import AsyncIterator
from uuid import UUID

import httpx

from src.wearables.base import (
    NormalizedActivity,
    NormalizedDaily,
    NormalizedSleep,
    OAuthTokens,
    RawDevicePayload,
    WearableAdapter,
)
from src.wearables.config_loader import get_fusion_config

logger = logging.getLogger("vitalis.wearables.whoop")

_WHOOP_API_BASE = "https://api.prod.whoop.com/developer"
_WHOOP_TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
_WHOOP_AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"

# Whoop sport type ID → Vitalis canonical activity type
_WHOOP_SPORT_MAP: dict[int, str] = {
    -1: "other",
    0: "other",
    1: "running",
    16: "cycling",
    17: "swimming",
    63: "walking",
    45: "strength_training",
    63: "hiit",
    44: "yoga",
    37: "rowing",
    49: "elliptical",
    62: "stair_climbing",
    32: "hiking",
    71: "indoor_cycling",
}


class WhoopAdapter(WearableAdapter):
    """Whoop API v1 adapter.

    Whoop focuses on strain, recovery, and HRV tracking.  It provides
    detailed HRV data and a strong sleep staging algorithm.
    """

    SOURCE_ID = "whoop"
    DISPLAY_NAME = "Whoop"

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize the Whoop adapter.

        Args:
            client_id:     OAuth2 client ID (WHOOP_CLIENT_ID env var).
            client_secret: OAuth2 client secret (WHOOP_CLIENT_SECRET env var).
            http_client:   Optional pre-configured httpx client (for testing).
        """
        self._client_id = client_id or os.environ.get("WHOOP_CLIENT_ID", "")
        self._client_secret = client_secret or os.environ.get("WHOOP_CLIENT_SECRET", "")
        self._http_client = http_client
        self._config = get_fusion_config()

    # ------------------------------------------------------------------
    # WearableAdapter interface
    # ------------------------------------------------------------------

    async def authenticate(self, user_id: UUID, auth_code: str) -> OAuthTokens:
        """Exchange Whoop OAuth2 authorization code for tokens.

        Args:
            user_id:   Internal Vitalis user UUID.
            auth_code: Authorization code from Whoop OAuth2 callback.

        Returns:
            OAuthTokens.
        """
        logger.info("Whoop: authenticating user %s", user_id)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                _WHOOP_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": auth_code,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            data = response.json()

        expires_in = data.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        return OAuthTokens(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=expires_at,
            token_type=data.get("token_type", "Bearer"),
        )

    async def refresh_token(self, user_id: UUID, refresh_token: str) -> OAuthTokens:
        """Refresh a Whoop OAuth2 access token.

        Args:
            user_id:       Internal Vitalis user UUID.
            refresh_token: Current refresh token.

        Returns:
            New OAuthTokens.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                _WHOOP_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            data = response.json()

        expires_in = data.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        return OAuthTokens(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", refresh_token),
            expires_at=expires_at,
        )

    async def sync_daily(
        self, user_id: UUID, target_date: date, access_token: str
    ) -> RawDevicePayload:
        """Fetch Whoop recovery cycle data for a date.

        Whoop organizes data around "cycles" (one per day), each containing
        recovery and strain scores.

        Args:
            user_id:      Internal Vitalis user UUID.
            target_date:  Date to fetch.
            access_token: Bearer token.

        Returns:
            RawDevicePayload.
        """
        date_str = target_date.isoformat()
        next_day = (target_date + timedelta(days=1)).isoformat()

        recovery = await self._get(
            f"{_WHOOP_API_BASE}/v1/recovery",
            params={"start": f"{date_str}T00:00:00.000Z", "end": f"{next_day}T00:00:00.000Z"},
            access_token=access_token,
        )
        cycle = await self._get(
            f"{_WHOOP_API_BASE}/v1/cycle",
            params={"start": f"{date_str}T00:00:00.000Z", "end": f"{next_day}T00:00:00.000Z"},
            access_token=access_token,
        )

        combined = {
            "recovery": recovery.get("records", recovery.get("data", [])),
            "cycle": cycle.get("records", cycle.get("data", [])),
        }

        return RawDevicePayload(
            user_id=user_id,
            device_source=self.SOURCE_ID,
            metric_type="daily",
            date=target_date,
            raw_payload=combined,
        )

    async def sync_sleep(
        self, user_id: UUID, target_date: date, access_token: str
    ) -> RawDevicePayload:
        """Fetch Whoop sleep data for a specific night.

        Args:
            user_id:      Internal Vitalis user UUID.
            target_date:  Wake date.
            access_token: Bearer token.

        Returns:
            RawDevicePayload.
        """
        start_str = (target_date - timedelta(days=1)).isoformat()
        end_str = (target_date + timedelta(days=1)).isoformat()

        data = await self._get(
            f"{_WHOOP_API_BASE}/v1/sleep",
            params={
                "start": f"{start_str}T12:00:00.000Z",
                "end": f"{end_str}T12:00:00.000Z",
            },
            access_token=access_token,
        )

        return RawDevicePayload(
            user_id=user_id,
            device_source=self.SOURCE_ID,
            metric_type="sleep",
            date=target_date,
            raw_payload=data,
        )

    async def sync_activities(
        self, user_id: UUID, target_date: date, access_token: str
    ) -> list[RawDevicePayload]:
        """Fetch Whoop workout sessions for a date.

        Args:
            user_id:      Internal Vitalis user UUID.
            target_date:  Date to fetch.
            access_token: Bearer token.

        Returns:
            List of RawDevicePayload.
        """
        date_str = target_date.isoformat()
        next_day = (target_date + timedelta(days=1)).isoformat()

        data = await self._get(
            f"{_WHOOP_API_BASE}/v1/workout",
            params={
                "start": f"{date_str}T00:00:00.000Z",
                "end": f"{next_day}T00:00:00.000Z",
            },
            access_token=access_token,
        )

        records = data.get("records", data.get("data", []))
        return [
            RawDevicePayload(
                user_id=user_id,
                device_source=self.SOURCE_ID,
                metric_type="activity",
                date=target_date,
                raw_payload=workout,
            )
            for workout in records
        ]

    async def backfill(
        self,
        user_id: UUID,
        start_date: date,
        end_date: date,
        access_token: str,
    ) -> AsyncIterator[RawDevicePayload]:
        """Iterate over historical Whoop data.

        Args:
            user_id:      Internal Vitalis user UUID.
            start_date:   Earliest date.
            end_date:     Latest date.
            access_token: Bearer token.

        Yields:
            RawDevicePayload for each day.
        """
        import asyncio

        cfg = self._config.backfill
        rate_limit_s = cfg.rate_limit_ms / 1000.0
        current = start_date

        while current <= end_date:
            try:
                daily = await self.sync_daily(user_id, current, access_token)
                yield daily
                await asyncio.sleep(rate_limit_s)

                sleep = await self.sync_sleep(user_id, current, access_token)
                yield sleep
                await asyncio.sleep(rate_limit_s)

            except Exception as exc:
                logger.warning(
                    "Whoop backfill error on %s for user %s: %s", current, user_id, exc
                )

            current += timedelta(days=1)

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def normalize_sleep(self, raw: dict) -> NormalizedSleep:
        """Convert Whoop sleep JSON to canonical NormalizedSleep.

        Args:
            raw: Whoop /v1/sleep response dict.

        Returns:
            NormalizedSleep.
        """
        user_id_placeholder = UUID("00000000-0000-0000-0000-000000000000")

        records = raw.get("records", raw.get("data", [raw]))
        if not records:
            return NormalizedSleep(
                user_id=user_id_placeholder,
                sleep_date=date.today(),
                source=self.SOURCE_ID,
                raw_payload=raw,
            )

        # Use the longest sleep record
        data = max(records, key=lambda r: r.get("score", {}).get("total_in_bed_time_milli", 0) or 0)

        score = data.get("score", {})
        start_str = data.get("start")
        end_str = data.get("end")

        sleep_start = self._parse_iso_datetime(start_str)
        sleep_end = self._parse_iso_datetime(end_str)

        # Date = wake date
        sleep_date = sleep_end.date() if sleep_end else date.today()

        # Whoop reports times in milliseconds
        def _ms_to_min(ms: int | None) -> int | None:
            return ms // 60000 if ms is not None else None

        total_ms = score.get("total_sleep_time_milli")
        rem_ms = score.get("rem_sleep_time_milli")
        slow_ms = score.get("slow_wave_sleep_time_milli")  # deep
        awake_ms = score.get("total_awake_time_milli")
        light_ms = score.get("light_sleep_time_milli")
        latency_ms = score.get("sleep_latency_milli")

        # Calculate light if not provided directly
        if light_ms is None and total_ms is not None and rem_ms is not None and slow_ms is not None:
            light_ms = max(
                0,
                int(total_ms or 0) - int(rem_ms or 0) - int(slow_ms or 0) - int(awake_ms or 0)
            )

        return NormalizedSleep(
            user_id=user_id_placeholder,
            sleep_date=sleep_date,
            source=self.SOURCE_ID,
            sleep_start=sleep_start,
            sleep_end=sleep_end,
            total_sleep_minutes=_ms_to_min(total_ms),
            rem_minutes=_ms_to_min(rem_ms),
            deep_minutes=_ms_to_min(slow_ms),
            light_minutes=_ms_to_min(light_ms),
            awake_minutes=_ms_to_min(awake_ms),
            sleep_latency_minutes=_ms_to_min(latency_ms),
            sleep_efficiency_pct=self._safe_float(score.get("sleep_efficiency_percentage")),
            sleep_score=self._safe_int(score.get("quality_duration_score")),
            avg_hr_bpm=self._safe_int(score.get("avg_heart_rate")),
            avg_hrv_ms=self._safe_float(score.get("rmssd")),
            avg_respiratory_rate=self._safe_float(score.get("respiratory_rate")),
            raw_payload=raw,
        )

    def normalize_daily(self, raw: dict) -> NormalizedDaily:
        """Convert Whoop recovery + cycle JSON to canonical NormalizedDaily.

        Args:
            raw: Combined {'recovery': [...], 'cycle': [...]} dict.

        Returns:
            NormalizedDaily.
        """
        user_id_placeholder = UUID("00000000-0000-0000-0000-000000000000")

        recoveries = raw.get("recovery", [])
        cycles = raw.get("cycle", [])

        rec = recoveries[0] if recoveries else {}
        cyc = cycles[0] if cycles else {}

        rec_score = rec.get("score", {})
        cyc_score = cyc.get("score", {})

        date_str = rec.get("created_at") or cyc.get("created_at") or ""
        try:
            daily_date = datetime.fromisoformat(date_str[:10]).date() if date_str else date.today()
        except ValueError:
            daily_date = date.today()

        return NormalizedDaily(
            user_id=user_id_placeholder,
            date=daily_date,
            source=self.SOURCE_ID,
            resting_hr_bpm=self._safe_int(rec_score.get("resting_heart_rate")),
            hrv_rmssd_ms=self._safe_float(rec_score.get("hrv_rmssd_milli")),
            respiratory_rate_avg=self._safe_float(rec_score.get("respiratory_rate")),
            skin_temp_deviation_c=self._safe_float(rec_score.get("skin_temp_celsius")),
            recovery_score=self._safe_int(rec_score.get("recovery_score")),
            readiness_score=None,  # Whoop strain is proprietary — not fused
            extended_metrics={
                "whoop_recovery_score": rec_score.get("recovery_score"),
                "whoop_strain": cyc_score.get("strain"),
                "whoop_kilojoule": cyc_score.get("kilojoule"),
                "whoop_max_hr": cyc_score.get("max_heart_rate"),
                "whoop_avg_hr": cyc_score.get("average_heart_rate"),
            },
            raw_payload=raw,
        )

    # ------------------------------------------------------------------
    # Private HTTP helper
    # ------------------------------------------------------------------

    async def _get(
        self, url: str, params: dict, access_token: str
    ) -> dict:
        """Make an authenticated GET request to the Whoop API.

        Args:
            url:          Full endpoint URL.
            params:       Query parameters.
            access_token: Bearer token.

        Returns:
            JSON response dict.
        """
        headers = {"Authorization": f"Bearer {access_token}"}

        if self._http_client:
            response = await self._http_client.get(url, params=params, headers=headers)
        else:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, headers=headers)

        response.raise_for_status()
        return response.json()
