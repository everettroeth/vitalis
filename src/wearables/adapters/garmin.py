"""Garmin Connect Health API adapter.

Uses OAuth 1.0a (not OAuth2).  Garmin requires a consumer key/secret pair
registered with the Garmin Health API program.

Environment variables:
    GARMIN_CONSUMER_KEY     — OAuth 1.0a consumer key
    GARMIN_CONSUMER_SECRET  — OAuth 1.0a consumer secret

API base: https://healthapi.garmin.com/wellness-api/rest

Endpoints used:
    /dailies              — Daily activity summaries
    /sleeps               — Sleep data
    /activities           — User activities (workouts)
    /epochs               — High-frequency epoch summaries (sub-daily)
    /bodyComps            — Body composition snapshots
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

logger = logging.getLogger("vitalis.wearables.garmin")

_GARMIN_API_BASE = "https://healthapi.garmin.com/wellness-api/rest"
_GARMIN_OAUTH_BASE = "https://connectapi.garmin.com/oauth-service/oauth"

# Activity type mapping: Garmin activity type ID → Vitalis canonical slug
_GARMIN_ACTIVITY_TYPE_MAP: dict[str, str] = {
    "running": "running",
    "cycling": "cycling",
    "lap_swimming": "swimming",
    "open_water_swimming": "swimming",
    "walking": "walking",
    "strength_training": "strength_training",
    "yoga": "yoga",
    "hiit": "hiit",
    "rowing": "rowing",
    "elliptical": "elliptical",
    "stair_climbing": "stair_climbing",
    "hiking": "hiking",
    "indoor_cycling": "indoor_cycling",
    "treadmill_running": "treadmill",
    "cross_country_skiing": "cross_country_skiing",
    "pilates": "pilates",
}


class GarminAdapter(WearableAdapter):
    """Garmin Connect Health API adapter (OAuth 1.0a).

    Handles authentication, data fetching, and normalization for Garmin devices
    including Forerunner, Fenix, Vivoactive, Vivosmart, and Venu series.
    """

    SOURCE_ID = "garmin"
    DISPLAY_NAME = "Garmin Connect"

    def __init__(
        self,
        consumer_key: str | None = None,
        consumer_secret: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize the Garmin adapter.

        Args:
            consumer_key:    OAuth 1.0a consumer key (defaults to GARMIN_CONSUMER_KEY env var).
            consumer_secret: OAuth 1.0a consumer secret (defaults to GARMIN_CONSUMER_SECRET env var).
            http_client:     Optional pre-configured httpx client (useful for testing).
        """
        self._consumer_key = consumer_key or os.environ.get("GARMIN_CONSUMER_KEY", "")
        self._consumer_secret = consumer_secret or os.environ.get("GARMIN_CONSUMER_SECRET", "")
        self._http_client = http_client
        self._config = get_fusion_config()

        if not self._consumer_key or not self._consumer_secret:
            logger.warning(
                "Garmin consumer key/secret not configured. "
                "Set GARMIN_CONSUMER_KEY and GARMIN_CONSUMER_SECRET environment variables."
            )

    # ------------------------------------------------------------------
    # OAuth 1.0a helpers
    # ------------------------------------------------------------------

    def _build_oauth1_headers(
        self, access_token: str, access_token_secret: str, method: str, url: str
    ) -> dict[str, str]:
        """Build OAuth 1.0a Authorization header.

        Uses the authlib OAuth1Auth mechanism.

        Args:
            access_token:        User access token.
            access_token_secret: User access token secret.
            method:              HTTP method (GET, POST, etc.).
            url:                 Full request URL.

        Returns:
            Dict with 'Authorization' header.
        """
        try:
            from authlib.integrations.httpx_client import OAuth1Auth

            auth = OAuth1Auth(
                client_id=self._consumer_key,
                client_secret=self._consumer_secret,
                token=access_token,
                token_secret=access_token_secret,
            )
            # Build a dummy request to extract headers
            import httpx as _httpx

            req = _httpx.Request(method, url)
            signed = auth.auth_flow(req)
            for r in signed:
                return dict(r.headers)
        except ImportError:
            logger.error("authlib is required for Garmin OAuth1. Install with: pip install authlib")
        except Exception as exc:
            logger.error("Failed to build OAuth1 headers: %s", exc)
        return {}

    def _parse_access_token(self, access_token: str) -> tuple[str, str]:
        """Parse the combined 'token:secret' format stored in the database.

        Garmin OAuth 1.0a requires both a token and token_secret.  We store
        them as 'token:::secret' in the access_token_enc column.

        Args:
            access_token: Combined 'token:::secret' string.

        Returns:
            Tuple of (token, secret).
        """
        if ":::" in access_token:
            parts = access_token.split(":::", 1)
            return parts[0], parts[1]
        # Legacy format: assume token only (secret empty)
        return access_token, ""

    # ------------------------------------------------------------------
    # WearableAdapter interface
    # ------------------------------------------------------------------

    async def authenticate(self, user_id: UUID, auth_code: str) -> OAuthTokens:
        """Exchange OAuth 1.0a request token verifier for access tokens.

        In OAuth 1.0a, auth_code is the 'oauth_verifier' from the callback.
        The request token must have been stored before redirect.

        Args:
            user_id:   Internal Vitalis user UUID.
            auth_code: oauth_verifier from Garmin callback (format: 'token:::verifier').

        Returns:
            OAuthTokens with access_token='token:::secret'.
        """
        logger.info("Garmin: authenticating user %s", user_id)

        if ":::" not in auth_code:
            raise ValueError("Garmin auth_code must be 'request_token:::oauth_verifier'")

        request_token, verifier = auth_code.split(":::", 1)

        try:
            from authlib.integrations.httpx_client import AsyncOAuth1Client

            async with AsyncOAuth1Client(
                client_id=self._consumer_key,
                client_secret=self._consumer_secret,
                token=request_token,
                token_secret="",  # not needed for access token exchange
            ) as client:
                resp = await client.fetch_access_token(
                    f"{_GARMIN_OAUTH_BASE}/access_token",
                    verifier=verifier,
                )
                token = resp.get("oauth_token", "")
                secret = resp.get("oauth_token_secret", "")

                return OAuthTokens(
                    access_token=f"{token}:::{secret}",
                    refresh_token=None,  # OAuth 1.0a has no refresh tokens
                    token_type="OAuth1",
                    extra={"oauth_token": token, "oauth_token_secret": secret},
                )
        except ImportError:
            raise ImportError("authlib is required for Garmin OAuth1")

    async def refresh_token(self, user_id: UUID, refresh_token: str) -> OAuthTokens:
        """OAuth 1.0a does not have refresh tokens — access tokens are long-lived.

        This method is a no-op for Garmin; it simply returns the existing
        token unchanged.  Garmin access tokens do not expire.

        Args:
            user_id:       Internal Vitalis user UUID.
            refresh_token: Not used for Garmin (OAuth 1.0a).

        Returns:
            The same OAuthTokens (unchanged).
        """
        logger.debug("Garmin: OAuth1 access tokens don't expire, no refresh needed")
        return OAuthTokens(
            access_token=refresh_token,
            refresh_token=None,
            token_type="OAuth1",
        )

    async def sync_daily(
        self, user_id: UUID, target_date: date, access_token: str
    ) -> RawDevicePayload:
        """Fetch Garmin daily summary for a specific date.

        Uses the /dailies endpoint with uploadStartTimeInSeconds and
        uploadEndTimeInSeconds bounds.

        Args:
            user_id:      Internal Vitalis user UUID.
            target_date:  Date to fetch (user's local date).
            access_token: OAuth 1.0a 'token:::secret'.

        Returns:
            RawDevicePayload with the Garmin daily summary JSON.
        """
        token, secret = self._parse_access_token(access_token)

        # Garmin /dailies uses Unix timestamp bounds for the upload window
        start_ts = int(datetime(target_date.year, target_date.month, target_date.day).timestamp())
        end_ts = start_ts + 86400

        url = f"{_GARMIN_API_BASE}/dailies"
        params = {
            "uploadStartTimeInSeconds": start_ts,
            "uploadEndTimeInSeconds": end_ts,
        }

        raw = await self._get(url, params, token, secret)

        return RawDevicePayload(
            user_id=user_id,
            device_source=self.SOURCE_ID,
            metric_type="daily",
            date=target_date,
            raw_payload=raw,
        )

    async def sync_sleep(
        self, user_id: UUID, target_date: date, access_token: str
    ) -> RawDevicePayload:
        """Fetch Garmin sleep data for a specific night.

        Args:
            user_id:      Internal Vitalis user UUID.
            target_date:  Wake date (morning of sleep period).
            access_token: OAuth 1.0a 'token:::secret'.

        Returns:
            RawDevicePayload with the Garmin sleep JSON.
        """
        token, secret = self._parse_access_token(access_token)

        start_ts = int(
            datetime(target_date.year, target_date.month, target_date.day).timestamp()
        ) - 86400  # look back one day for the sleep start

        url = f"{_GARMIN_API_BASE}/sleeps"
        params = {
            "uploadStartTimeInSeconds": start_ts,
            "uploadEndTimeInSeconds": start_ts + 86400 * 2,
        }

        raw = await self._get(url, params, token, secret)

        return RawDevicePayload(
            user_id=user_id,
            device_source=self.SOURCE_ID,
            metric_type="sleep",
            date=target_date,
            raw_payload=raw,
        )

    async def sync_activities(
        self, user_id: UUID, target_date: date, access_token: str
    ) -> list[RawDevicePayload]:
        """Fetch Garmin activities for a specific date.

        Args:
            user_id:      Internal Vitalis user UUID.
            target_date:  Date to fetch.
            access_token: OAuth 1.0a 'token:::secret'.

        Returns:
            List of RawDevicePayload, one per activity.
        """
        token, secret = self._parse_access_token(access_token)

        start_ts = int(
            datetime(target_date.year, target_date.month, target_date.day).timestamp()
        )
        url = f"{_GARMIN_API_BASE}/activities"
        params = {
            "uploadStartTimeInSeconds": start_ts,
            "uploadEndTimeInSeconds": start_ts + 86400,
        }

        raw = await self._get(url, params, token, secret)
        activities = raw.get("activityList", [])

        return [
            RawDevicePayload(
                user_id=user_id,
                device_source=self.SOURCE_ID,
                metric_type="activity",
                date=target_date,
                raw_payload=act,
            )
            for act in activities
        ]

    async def backfill(
        self,
        user_id: UUID,
        start_date: date,
        end_date: date,
        access_token: str,
    ) -> AsyncIterator[RawDevicePayload]:
        """Iterate over historical Garmin data in 30-day batches.

        Yields daily summaries and sleep records for each day in the range.
        Respects rate_limit_ms from fusion_config.yaml between API calls.

        Args:
            user_id:      Internal Vitalis user UUID.
            start_date:   Earliest date to backfill (inclusive).
            end_date:     Latest date to backfill (inclusive).
            access_token: OAuth 1.0a 'token:::secret'.

        Yields:
            RawDevicePayload for each fetched record.
        """
        import asyncio

        cfg = self._config.backfill
        batch_days = cfg.batch_size_days
        rate_limit_s = cfg.rate_limit_ms / 1000.0

        current = start_date
        while current <= end_date:
            batch_end = min(current + timedelta(days=batch_days - 1), end_date)
            logger.debug(
                "Garmin backfill: %s → %s for user %s", current, batch_end, user_id
            )

            try:
                daily = await self.sync_daily(user_id, current, access_token)
                yield daily
                await asyncio.sleep(rate_limit_s)

                sleep = await self.sync_sleep(user_id, current, access_token)
                yield sleep
                await asyncio.sleep(rate_limit_s)
            except Exception as exc:
                logger.warning(
                    "Garmin backfill error on %s for user %s: %s", current, user_id, exc
                )

            current += timedelta(days=1)

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def normalize_sleep(self, raw: dict) -> NormalizedSleep:
        """Convert Garmin sleep JSON to canonical NormalizedSleep.

        Garmin /sleeps response contains a list; we process the first item.

        Args:
            raw: Garmin sleep API response dict.

        Returns:
            NormalizedSleep in canonical format.
        """
        # Garmin returns {'sleepList': [...]} or a direct dict
        sleep_list = raw.get("sleeps", raw.get("sleepList", []))
        if sleep_list and isinstance(sleep_list, list):
            data = sleep_list[0]
        else:
            data = raw

        user_id_placeholder = UUID("00000000-0000-0000-0000-000000000000")

        # Parse sleep date
        sleep_date_str = data.get("calendarDate") or data.get("sleepStartTimestampLocal", "")
        if sleep_date_str and len(sleep_date_str) >= 10:
            try:
                sleep_date = date.fromisoformat(sleep_date_str[:10])
            except ValueError:
                sleep_date = date.today()
        else:
            sleep_date = date.today()

        # Parse timestamps
        start_ts = data.get("sleepStartTimestampGMT") or data.get("startTimeInSeconds")
        end_ts = data.get("sleepEndTimestampGMT") or data.get("endTimeInSeconds")

        sleep_start = (
            datetime.utcfromtimestamp(int(start_ts)) if start_ts else None
        )
        sleep_end = (
            datetime.utcfromtimestamp(int(end_ts)) if end_ts else None
        )

        # Duration and stages (Garmin uses seconds)
        total_secs = self._safe_int(data.get("sleepTimeSeconds")) or 0
        deep_secs = self._safe_int(data.get("deepSleepSeconds")) or 0
        light_secs = self._safe_int(data.get("lightSleepSeconds")) or 0
        rem_secs = self._safe_int(data.get("remSleepSeconds")) or 0
        awake_secs = self._safe_int(data.get("awakeSleepSeconds")) or 0

        # Build hypnogram from sleep levels if available
        hypnogram = []
        for level in data.get("sleepLevels", []):
            stage_map = {
                "deep": "deep", "light": "light", "rem": "rem",
                "awake": "awake", "n1": "light", "n2": "light", "n3": "deep",
            }
            hypnogram.append({
                "t": level.get("startGMT", 0),
                "stage": stage_map.get(level.get("activityLevel", "").lower(), "light"),
            })

        # Wellness stats
        avg_spo2 = self._safe_float(data.get("averageSpO2Value"))
        avg_rr = self._safe_float(
            data.get("averageRespirationValue") or data.get("averageRespiration")
        )
        avg_hr = self._safe_int(data.get("averageHeartRateValue") or data.get("restingHeartRate"))
        avg_hrv = self._safe_float(data.get("avgSleepStress") or data.get("averageHRV"))

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
            sleep_latency_minutes=self._safe_int(
                (data.get("sleepStartTimestampGMT", 0) or 0) - (data.get("startTimeInSeconds", 0) or 0)
            ),
            sleep_score=self._safe_int(data.get("sleepScore") or data.get("overallSleepScore")),
            avg_hr_bpm=avg_hr,
            avg_hrv_ms=avg_hrv,
            avg_respiratory_rate=avg_rr,
            avg_spo2_pct=avg_spo2,
            hypnogram=hypnogram,
            raw_payload=raw,
        )

    def normalize_daily(self, raw: dict) -> NormalizedDaily:
        """Convert Garmin daily summary JSON to canonical NormalizedDaily.

        Args:
            raw: Garmin /dailies API response dict.

        Returns:
            NormalizedDaily in canonical format.
        """
        # Garmin returns {'dailies': [...]} or {'userDailySummaries': [...]}
        daily_list = raw.get("dailies", raw.get("userDailySummaries", []))
        if daily_list and isinstance(daily_list, list):
            data = daily_list[0]
        else:
            data = raw

        user_id_placeholder = UUID("00000000-0000-0000-0000-000000000000")

        date_str = data.get("calendarDate") or ""
        if date_str:
            try:
                daily_date = date.fromisoformat(date_str[:10])
            except ValueError:
                daily_date = date.today()
        else:
            daily_date = date.today()

        return NormalizedDaily(
            user_id=user_id_placeholder,
            date=daily_date,
            source=self.SOURCE_ID,
            resting_hr_bpm=self._safe_int(data.get("restingHeartRateInBeatsPerMinute")),
            max_hr_bpm=self._safe_int(data.get("maxHeartRateInBeatsPerMinute")),
            hrv_rmssd_ms=self._safe_float(data.get("lastNightAvg5MinHeartRateVariability")),
            steps=self._safe_int(data.get("totalSteps")),
            active_calories_kcal=self._safe_int(data.get("activeKilocalories")),
            total_calories_kcal=self._safe_int(data.get("burnedKilocalories")),
            active_minutes=self._safe_int(data.get("activeTimeInSeconds", 0)) and
                           (self._safe_int(data.get("activeTimeInSeconds", 0)) // 60),
            distance_m=self._safe_int(
                float(data.get("totalDistanceInMeters", 0) or 0)
            ),
            floors_climbed=self._safe_int(data.get("floorsAscended")),
            spo2_avg_pct=self._safe_float(data.get("averageSpo2")),
            respiratory_rate_avg=self._safe_float(
                data.get("averageRespirationValue") or data.get("latestRespirationValue")
            ),
            stress_avg=self._safe_int(data.get("averageStressLevel")),
            readiness_score=None,  # Garmin body battery is proprietary — not fused
            vo2_max_ml_kg_min=self._safe_float(data.get("vo2Max")),
            extended_metrics={
                "body_battery_start": data.get("bodyBatteryChargedValue"),
                "body_battery_end": data.get("bodyBatteryDrainedValue"),
                "moderate_intensity_minutes": data.get("moderateIntensityMinutes"),
                "vigorous_intensity_minutes": data.get("vigorousIntensityMinutes"),
                "avg_waking_respiration": data.get("awakeRespirationValue"),
            },
            raw_payload=raw,
        )

    def normalize_activity(self, raw: dict) -> NormalizedActivity:
        """Convert Garmin activity JSON to canonical NormalizedActivity.

        Args:
            raw: Single Garmin activity dict.

        Returns:
            NormalizedActivity.
        """
        user_id_placeholder = UUID("00000000-0000-0000-0000-000000000000")

        start_ts = raw.get("startTimeInSeconds")
        duration_secs = self._safe_int(raw.get("durationInSeconds"))

        start_time = (
            datetime.utcfromtimestamp(int(start_ts)) if start_ts else None
        )
        end_time = (
            datetime.utcfromtimestamp(int(start_ts) + int(duration_secs or 0))
            if start_ts and duration_secs
            else None
        )

        activity_type_raw = str(raw.get("activityType", "other")).lower()
        activity_type = _GARMIN_ACTIVITY_TYPE_MAP.get(activity_type_raw, "other")

        activity_date = start_time.date() if start_time else date.today()

        return NormalizedActivity(
            user_id=user_id_placeholder,
            activity_date=activity_date,
            source=self.SOURCE_ID,
            source_activity_id=str(raw.get("activityId", "")),
            activity_type=activity_type,
            activity_name=raw.get("activityName"),
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration_secs,
            distance_m=self._safe_float(raw.get("distanceInMeters")),
            calories_kcal=self._safe_int(raw.get("activeKilocalories")),
            avg_hr_bpm=self._safe_int(raw.get("averageHeartRateInBeatsPerMinute")),
            max_hr_bpm=self._safe_int(raw.get("maxHeartRateInBeatsPerMinute")),
            elevation_gain_m=self._safe_float(raw.get("elevationGainInMeters")),
            avg_power_watts=self._safe_int(raw.get("averagePowerInWatts")),
            raw_payload=raw,
        )

    # ------------------------------------------------------------------
    # Private HTTP helper
    # ------------------------------------------------------------------

    async def _get(
        self, url: str, params: dict, token: str, secret: str
    ) -> dict:
        """Make an authenticated GET request to the Garmin Health API.

        Args:
            url:    Full API endpoint URL.
            params: Query parameters.
            token:  OAuth 1.0a access token.
            secret: OAuth 1.0a access token secret.

        Returns:
            JSON response dict.

        Raises:
            httpx.HTTPStatusError: On non-2xx responses.
        """
        try:
            from authlib.integrations.httpx_client import AsyncOAuth1Client

            async with AsyncOAuth1Client(
                client_id=self._consumer_key,
                client_secret=self._consumer_secret,
                token=token,
                token_secret=secret,
            ) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()

        except ImportError:
            raise ImportError("authlib is required for Garmin OAuth1. pip install authlib")
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Garmin API error: %s %s → %d",
                exc.request.method, exc.request.url, exc.response.status_code
            )
            raise
