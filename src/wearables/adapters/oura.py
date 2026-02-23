"""Oura Ring API v2 adapter.

Supports both OAuth2 (for multi-user SaaS) and personal access tokens
(for single-user / development use).

Environment variables:
    OURA_CLIENT_ID      — OAuth2 client ID
    OURA_CLIENT_SECRET  — OAuth2 client secret
    OURA_PERSONAL_TOKEN — Personal access token (skips OAuth2 for dev)

API base: https://api.ouraring.com

Endpoints used:
    /v2/usercollection/daily_sleep      — Nightly sleep summary
    /v2/usercollection/sleep            — Detailed sleep stages
    /v2/usercollection/daily_activity   — Daily step/calorie summary
    /v2/usercollection/heartrate        — Continuous heart rate
    /v2/usercollection/daily_readiness  — Oura readiness score (proprietary)
    /v2/usercollection/ring_configuration — Device info
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

logger = logging.getLogger("vitalis.wearables.oura")

_OURA_API_BASE = "https://api.ouraring.com"
_OURA_TOKEN_URL = "https://api.ouraring.com/oauth/token"
_OURA_AUTH_URL = "https://cloud.ouraring.com/oauth/authorize"


class OuraAdapter(WearableAdapter):
    """Oura Ring API v2 adapter.

    Oura is one of the gold-standard sources for HRV, sleep staging, and
    skin temperature data.  The ring's finger-based PPG provides the most
    accurate consumer-grade readings for these metrics.

    Supports:
    - OAuth2 authorization code flow (for SaaS multi-user)
    - Personal access token (for dev / single-user)
    - Temperature deviation tracking (used for menstrual cycle prediction)
    """

    SOURCE_ID = "oura"
    DISPLAY_NAME = "Oura Ring"

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        personal_token: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize the Oura adapter.

        Args:
            client_id:      OAuth2 client ID (OURA_CLIENT_ID env var).
            client_secret:  OAuth2 client secret (OURA_CLIENT_SECRET env var).
            personal_token: Personal access token for single-user use.
            http_client:    Optional pre-configured httpx client (for testing).
        """
        self._client_id = client_id or os.environ.get("OURA_CLIENT_ID", "")
        self._client_secret = client_secret or os.environ.get("OURA_CLIENT_SECRET", "")
        self._personal_token = personal_token or os.environ.get("OURA_PERSONAL_TOKEN", "")
        self._http_client = http_client
        self._config = get_fusion_config()

    # ------------------------------------------------------------------
    # WearableAdapter interface
    # ------------------------------------------------------------------

    async def authenticate(self, user_id: UUID, auth_code: str) -> OAuthTokens:
        """Exchange OAuth2 authorization code for access + refresh tokens.

        Args:
            user_id:   Internal Vitalis user UUID.
            auth_code: Authorization code from Oura OAuth2 callback.

        Returns:
            OAuthTokens with access_token, refresh_token, and expiry.
        """
        logger.info("Oura: authenticating user %s", user_id)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                _OURA_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": auth_code,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
            response.raise_for_status()
            data = response.json()

        expires_in = data.get("expires_in", 3600)
        expires_at = datetime.utcnow().replace(microsecond=0)
        from datetime import timedelta as _td

        expires_at = expires_at + _td(seconds=expires_in)

        return OAuthTokens(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=expires_at,
            token_type=data.get("token_type", "Bearer"),
        )

    async def refresh_token(self, user_id: UUID, refresh_token: str) -> OAuthTokens:
        """Refresh an expired Oura OAuth2 access token.

        Args:
            user_id:       Internal Vitalis user UUID.
            refresh_token: Current refresh token.

        Returns:
            New OAuthTokens.
        """
        logger.info("Oura: refreshing token for user %s", user_id)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                _OURA_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
            response.raise_for_status()
            data = response.json()

        expires_in = data.get("expires_in", 3600)
        from datetime import timedelta as _td

        expires_at = datetime.utcnow() + _td(seconds=expires_in)

        return OAuthTokens(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", refresh_token),
            expires_at=expires_at,
        )

    async def sync_daily(
        self, user_id: UUID, target_date: date, access_token: str
    ) -> RawDevicePayload:
        """Fetch Oura daily activity summary for a date.

        Combines daily_activity and daily_readiness data.

        Args:
            user_id:      Internal Vitalis user UUID.
            target_date:  Date to fetch.
            access_token: OAuth2 Bearer token (or personal token).

        Returns:
            RawDevicePayload with combined Oura daily JSON.
        """
        date_str = target_date.isoformat()
        activity = await self._get(
            f"{_OURA_API_BASE}/v2/usercollection/daily_activity",
            params={"start_date": date_str, "end_date": date_str},
            access_token=access_token,
        )
        readiness = await self._get(
            f"{_OURA_API_BASE}/v2/usercollection/daily_readiness",
            params={"start_date": date_str, "end_date": date_str},
            access_token=access_token,
        )

        combined = {
            "daily_activity": activity.get("data", []),
            "daily_readiness": readiness.get("data", []),
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
        """Fetch Oura sleep data for a specific night.

        Combines /sleep (detailed stages) and /daily_sleep (summary).

        Args:
            user_id:      Internal Vitalis user UUID.
            target_date:  Wake date (morning of the sleep period).
            access_token: Bearer token.

        Returns:
            RawDevicePayload with Oura sleep JSON.
        """
        date_str = target_date.isoformat()
        start_str = (target_date - timedelta(days=1)).isoformat()

        sleep_detail = await self._get(
            f"{_OURA_API_BASE}/v2/usercollection/sleep",
            params={"start_date": start_str, "end_date": date_str},
            access_token=access_token,
        )
        sleep_summary = await self._get(
            f"{_OURA_API_BASE}/v2/usercollection/daily_sleep",
            params={"start_date": date_str, "end_date": date_str},
            access_token=access_token,
        )

        combined = {
            "sleep": sleep_detail.get("data", []),
            "daily_sleep": sleep_summary.get("data", []),
        }

        return RawDevicePayload(
            user_id=user_id,
            device_source=self.SOURCE_ID,
            metric_type="sleep",
            date=target_date,
            raw_payload=combined,
        )

    async def sync_activities(
        self, user_id: UUID, target_date: date, access_token: str
    ) -> list[RawDevicePayload]:
        """Oura does not track individual workouts; returns empty list.

        Oura focuses on recovery metrics, not activity tracking.

        Returns:
            Empty list.
        """
        logger.debug("Oura: activity tracking not supported, returning empty list")
        return []

    async def sync_temperature(
        self, user_id: UUID, target_date: date, access_token: str
    ) -> RawDevicePayload | None:
        """Fetch Oura skin temperature deviation for menstrual cycle tracking.

        Temperature data is the most accurate consumer-grade proxy for BBT
        (basal body temperature) and is used for ovulation detection.

        Args:
            user_id:      Internal Vitalis user UUID.
            target_date:  Date to fetch.
            access_token: Bearer token.

        Returns:
            RawDevicePayload with temperature data.
        """
        date_str = target_date.isoformat()
        start_str = (target_date - timedelta(days=1)).isoformat()

        try:
            data = await self._get(
                f"{_OURA_API_BASE}/v2/usercollection/daily_spo2",
                params={"start_date": start_str, "end_date": date_str},
                access_token=access_token,
            )
            return RawDevicePayload(
                user_id=user_id,
                device_source=self.SOURCE_ID,
                metric_type="temperature",
                date=target_date,
                raw_payload=data,
            )
        except Exception as exc:
            logger.warning("Oura temperature fetch failed: %s", exc)
            return None

    async def backfill(
        self,
        user_id: UUID,
        start_date: date,
        end_date: date,
        access_token: str,
    ) -> AsyncIterator[RawDevicePayload]:
        """Iterate over historical Oura data.

        Oura's API supports up to 30-day windows per request.

        Args:
            user_id:      Internal Vitalis user UUID.
            start_date:   Earliest date (inclusive).
            end_date:     Latest date (inclusive).
            access_token: Bearer token.

        Yields:
            RawDevicePayload for each batch.
        """
        import asyncio

        cfg = self._config.backfill
        batch_days = cfg.batch_size_days
        rate_limit_s = cfg.rate_limit_ms / 1000.0

        current = start_date
        while current <= end_date:
            batch_end = min(current + timedelta(days=batch_days - 1), end_date)

            try:
                daily = await self.sync_daily(user_id, current, access_token)
                yield daily
                await asyncio.sleep(rate_limit_s)

                sleep = await self.sync_sleep(user_id, current, access_token)
                yield sleep
                await asyncio.sleep(rate_limit_s)

            except Exception as exc:
                logger.warning(
                    "Oura backfill error on %s for user %s: %s", current, user_id, exc
                )

            current = batch_end + timedelta(days=1)

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def normalize_sleep(self, raw: dict) -> NormalizedSleep:
        """Convert Oura sleep JSON to canonical NormalizedSleep.

        Uses the detailed /sleep endpoint data when available, falling back
        to /daily_sleep summary.

        Args:
            raw: Combined {'sleep': [...], 'daily_sleep': [...]} dict.

        Returns:
            NormalizedSleep in canonical format.
        """
        user_id_placeholder = UUID("00000000-0000-0000-0000-000000000000")

        # Prefer detailed sleep data
        sleep_sessions = raw.get("sleep", [])
        daily_sleeps = raw.get("daily_sleep", [])

        # Find the primary (longest) sleep session
        session = {}
        if sleep_sessions:
            session = max(
                sleep_sessions,
                key=lambda s: s.get("total_sleep_duration", 0) or 0,
            )

        daily = daily_sleeps[0] if daily_sleeps else {}

        sleep_date_str = session.get("day") or daily.get("day") or ""
        try:
            sleep_date = date.fromisoformat(sleep_date_str) if sleep_date_str else date.today()
        except ValueError:
            sleep_date = date.today()

        sleep_start = self._parse_iso_datetime(session.get("bedtime_start"))
        sleep_end = self._parse_iso_datetime(session.get("bedtime_end"))

        # Oura returns durations in seconds
        total_secs = self._safe_int(session.get("total_sleep_duration"))
        rem_secs = self._safe_int(session.get("rem_sleep_duration"))
        deep_secs = self._safe_int(session.get("deep_sleep_duration"))
        light_secs = self._safe_int(session.get("light_sleep_duration"))
        awake_secs = self._safe_int(session.get("awake_duration"))
        latency_secs = self._safe_int(session.get("sleep_latency"))

        # HRV
        hrv_samples = session.get("hrv", {}).get("items", [])
        avg_hrv = (
            sum(hrv_samples) / len(hrv_samples)
            if hrv_samples
            else None
        )

        # Build hypnogram from Oura sleep phases
        hypnogram = []
        sleep_phases = session.get("sleep_phase_5_min", "")
        if sleep_phases and sleep_start:
            phase_map = {"1": "deep", "2": "light", "3": "rem", "4": "awake", "w": "awake"}
            for i, phase_char in enumerate(sleep_phases):
                hypnogram.append({
                    "t": int(sleep_start.timestamp()) + i * 300,  # 5-min buckets
                    "stage": phase_map.get(phase_char, "light"),
                })

        return NormalizedSleep(
            user_id=user_id_placeholder,
            sleep_date=sleep_date,
            source=self.SOURCE_ID,
            sleep_start=sleep_start,
            sleep_end=sleep_end,
            total_sleep_minutes=total_secs // 60 if total_secs else None,
            rem_minutes=rem_secs // 60 if rem_secs else None,
            deep_minutes=deep_secs // 60 if deep_secs else None,
            light_minutes=light_secs // 60 if light_secs else None,
            awake_minutes=awake_secs // 60 if awake_secs else None,
            sleep_latency_minutes=latency_secs // 60 if latency_secs else None,
            sleep_efficiency_pct=self._safe_float(session.get("sleep_efficiency_percentage")),
            sleep_score=self._safe_int(daily.get("score") or session.get("score")),
            interruptions=self._safe_int(session.get("restless_periods")),
            avg_hr_bpm=self._safe_int(session.get("lowest_heart_rate")),
            avg_hrv_ms=avg_hrv,
            avg_respiratory_rate=self._safe_float(
                session.get("average_breath") or session.get("breathing_regularity")
            ),
            avg_spo2_pct=self._safe_float(session.get("average_hrv")),
            avg_skin_temp_deviation_c=self._safe_float(
                session.get("skin_temperature_delta")
                or session.get("temperature_deviation")
            ),
            hypnogram=hypnogram,
            raw_payload=raw,
        )

    def normalize_daily(self, raw: dict) -> NormalizedDaily:
        """Convert Oura daily activity+readiness JSON to canonical NormalizedDaily.

        Args:
            raw: Combined {'daily_activity': [...], 'daily_readiness': [...]} dict.

        Returns:
            NormalizedDaily in canonical format.
        """
        user_id_placeholder = UUID("00000000-0000-0000-0000-000000000000")

        activities = raw.get("daily_activity", [])
        readinesses = raw.get("daily_readiness", [])

        act = activities[0] if activities else {}
        rdns = readinesses[0] if readinesses else {}

        date_str = act.get("day") or rdns.get("day") or ""
        try:
            daily_date = date.fromisoformat(date_str) if date_str else date.today()
        except ValueError:
            daily_date = date.today()

        contributors = rdns.get("contributors", {})

        return NormalizedDaily(
            user_id=user_id_placeholder,
            date=daily_date,
            source=self.SOURCE_ID,
            resting_hr_bpm=None,  # Oura reports this in sleep data, not daily
            hrv_rmssd_ms=self._safe_float(contributors.get("hrv_balance")),
            steps=self._safe_int(act.get("steps")),
            active_calories_kcal=self._safe_int(act.get("active_calories")),
            total_calories_kcal=self._safe_int(act.get("total_calories")),
            active_minutes=self._safe_int(act.get("medium_activity_time")),
            distance_m=self._safe_int(act.get("equivalent_walking_distance")),
            spo2_avg_pct=self._safe_float(act.get("average_met_minutes")),
            respiratory_rate_avg=self._safe_float(
                contributors.get("recovery_index")
            ),
            readiness_score=self._safe_int(rdns.get("score")),
            extended_metrics={
                "oura_readiness_score": rdns.get("score"),
                "oura_activity_score": act.get("score"),
                "high_activity_time": act.get("high_activity_time"),
                "resting_time": act.get("resting_time"),
            },
            raw_payload=raw,
        )

    # ------------------------------------------------------------------
    # Private HTTP helper
    # ------------------------------------------------------------------

    def _build_headers(self, access_token: str) -> dict[str, str]:
        """Build authorization headers for Oura API requests.

        Args:
            access_token: Bearer token or personal access token.

        Returns:
            Authorization headers dict.
        """
        token = access_token or self._personal_token
        return {"Authorization": f"Bearer {token}"}

    async def _get(
        self, url: str, params: dict, access_token: str
    ) -> dict:
        """Make an authenticated GET request to the Oura API.

        Args:
            url:          Full endpoint URL.
            params:       Query parameters.
            access_token: Bearer token.

        Returns:
            JSON response dict.

        Raises:
            httpx.HTTPStatusError: On non-2xx responses.
        """
        headers = self._build_headers(access_token)

        if self._http_client:
            response = await self._http_client.get(url, params=params, headers=headers)
        else:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, headers=headers)

        response.raise_for_status()
        return response.json()
