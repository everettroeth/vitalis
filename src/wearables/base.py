"""Base classes and canonical data models for the Vitalis wearable fusion engine.

Every device adapter must subclass WearableAdapter and return the canonical
NormalizedSleep / NormalizedDaily / NormalizedActivity models.  These types
are the single source of truth consumed by the fusion engine, database writer,
and API layer.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import AsyncIterator
from uuid import UUID

logger = logging.getLogger("vitalis.wearables")


# ---------------------------------------------------------------------------
# OAuth / Auth tokens
# ---------------------------------------------------------------------------


@dataclass
class OAuthTokens:
    """OAuth token pair returned after authentication or refresh.

    Attributes:
        access_token:  Bearer token for API calls.
        refresh_token: Long-lived token used to obtain a new access_token.
        expires_at:    UTC datetime when the access_token expires.
        token_type:    Token type, typically "Bearer".
        scope:         Granted OAuth scopes.
        extra:         Any additional fields returned by the provider (e.g. user_id).
    """

    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    token_type: str = "Bearer"
    scope: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Raw device payload
# ---------------------------------------------------------------------------


@dataclass
class RawDevicePayload:
    """Raw, un-normalized payload from a device API.

    Stored verbatim in raw_device_data before normalization.  Never modified —
    this is the permanent source of truth for reprocessing.

    Attributes:
        user_id:       Internal Vitalis user UUID.
        device_source: Provider slug ('garmin', 'oura', 'apple_health', 'whoop').
        metric_type:   Category of data ('sleep', 'daily', 'activity', 'cycle').
        date:          The calendar date this data belongs to (user's local date).
        raw_payload:   Exact JSON-serializable API response.
        ingested_at:   UTC timestamp of ingestion.
    """

    user_id: UUID
    device_source: str
    metric_type: str
    date: date
    raw_payload: dict
    ingested_at: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Canonical / Normalized models
# ---------------------------------------------------------------------------


@dataclass
class NormalizedSleep:
    """Canonical sleep record derived from any device source.

    All fields use metric units and UTC timestamps.  Device-specific
    fields are stored in ``extended_metrics``.

    Attributes:
        user_id:              Internal Vitalis user UUID.
        sleep_date:           Date sleep ended (morning of), user's local date.
        source:               Provider slug.
        sleep_start:          UTC timestamp when sleep began.
        sleep_end:            UTC timestamp when sleep ended.
        total_sleep_minutes:  Total sleep duration in minutes.
        rem_minutes:          REM stage duration.
        deep_minutes:         Deep / slow-wave sleep duration.
        light_minutes:        Light sleep duration.
        awake_minutes:        Time awake during sleep period.
        sleep_latency_minutes: Time to fall asleep.
        sleep_efficiency_pct: Sleep efficiency (sleep / time_in_bed * 100).
        sleep_score:          Device-reported sleep quality score (0–100).
        interruptions:        Number of wake events.
        avg_hr_bpm:           Average heart rate during sleep.
        min_hr_bpm:           Minimum heart rate during sleep.
        avg_hrv_ms:           Average RMSSD during sleep (ms).
        avg_respiratory_rate: Average breaths per minute during sleep.
        avg_spo2_pct:         Average blood oxygen saturation.
        avg_skin_temp_deviation_c: Skin temperature deviation from baseline (°C).
        hypnogram:            List of {t: epoch_sec, stage: str} dicts.
        extended_metrics:     Device-specific non-canonical fields.
        raw_payload:          Original API response for audit/reprocessing.
    """

    user_id: UUID
    sleep_date: date
    source: str
    sleep_start: datetime | None = None
    sleep_end: datetime | None = None
    total_sleep_minutes: int | None = None
    rem_minutes: int | None = None
    deep_minutes: int | None = None
    light_minutes: int | None = None
    awake_minutes: int | None = None
    sleep_latency_minutes: int | None = None
    sleep_efficiency_pct: float | None = None
    sleep_score: int | None = None
    interruptions: int | None = None
    avg_hr_bpm: int | None = None
    min_hr_bpm: int | None = None
    avg_hrv_ms: float | None = None
    avg_respiratory_rate: float | None = None
    avg_spo2_pct: float | None = None
    avg_skin_temp_deviation_c: float | None = None
    hypnogram: list[dict] = field(default_factory=list)
    extended_metrics: dict = field(default_factory=dict)
    raw_payload: dict = field(default_factory=dict)


@dataclass
class NormalizedDaily:
    """Canonical daily summary record derived from any device source.

    Attributes:
        user_id:                   Internal Vitalis user UUID.
        date:                      Calendar date (user's local date).
        source:                    Provider slug.
        resting_hr_bpm:            Resting heart rate.
        max_hr_bpm:                Maximum heart rate.
        hrv_rmssd_ms:              HRV RMSSD in milliseconds.
        steps:                     Step count.
        active_calories_kcal:      Active calorie burn.
        total_calories_kcal:       Total daily calorie burn (TDEE).
        active_minutes:            Minutes of moderate+ activity.
        distance_m:                Distance traveled in meters.
        floors_climbed:            Floors climbed.
        spo2_avg_pct:              Average blood oxygen saturation.
        spo2_min_pct:              Minimum blood oxygen saturation.
        respiratory_rate_avg:      Average respiratory rate (brpm).
        stress_avg:                Average stress score (0–100).
        skin_temp_deviation_c:     Skin temperature deviation from baseline.
        readiness_score:           Device proprietary readiness score (NOT fused).
        recovery_score:            Device proprietary recovery score (NOT fused).
        vo2_max_ml_kg_min:         VO2 max estimate.
        extended_metrics:          Non-canonical device-specific fields.
        raw_payload:               Original API response.
    """

    user_id: UUID
    date: date
    source: str
    resting_hr_bpm: int | None = None
    max_hr_bpm: int | None = None
    hrv_rmssd_ms: float | None = None
    steps: int | None = None
    active_calories_kcal: int | None = None
    total_calories_kcal: int | None = None
    active_minutes: int | None = None
    distance_m: int | None = None
    floors_climbed: int | None = None
    spo2_avg_pct: float | None = None
    spo2_min_pct: float | None = None
    respiratory_rate_avg: float | None = None
    stress_avg: int | None = None
    skin_temp_deviation_c: float | None = None
    readiness_score: int | None = None
    recovery_score: int | None = None
    vo2_max_ml_kg_min: float | None = None
    extended_metrics: dict = field(default_factory=dict)
    raw_payload: dict = field(default_factory=dict)


@dataclass
class NormalizedActivity:
    """Canonical activity / workout record.

    Attributes:
        user_id:              Internal Vitalis user UUID.
        activity_date:        Date of activity start (user's local date).
        source:               Provider slug.
        source_activity_id:   External ID for idempotent re-sync.
        activity_type:        Canonical activity type slug.
        activity_name:        Human-readable name from device.
        start_time:           UTC start timestamp.
        end_time:             UTC end timestamp.
        duration_seconds:     Duration in seconds.
        distance_m:           Distance in meters.
        calories_kcal:        Calories burned.
        avg_hr_bpm:           Average heart rate.
        max_hr_bpm:           Maximum heart rate.
        elevation_gain_m:     Elevation gain in meters.
        avg_power_watts:      Average power output.
        extended_metrics:     Non-canonical fields.
        raw_payload:          Original API response.
    """

    user_id: UUID
    activity_date: date
    source: str
    source_activity_id: str | None = None
    activity_type: str = "other"
    activity_name: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_seconds: int | None = None
    distance_m: float | None = None
    calories_kcal: int | None = None
    avg_hr_bpm: int | None = None
    max_hr_bpm: int | None = None
    elevation_gain_m: float | None = None
    avg_power_watts: int | None = None
    extended_metrics: dict = field(default_factory=dict)
    raw_payload: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Abstract base adapter
# ---------------------------------------------------------------------------


class WearableAdapter(ABC):
    """Abstract base class for all wearable device adapters.

    Each device adapter implements this interface to provide a uniform
    surface for the fusion engine and sync scheduler.

    Subclasses must implement:
        - authenticate()
        - refresh_token()
        - sync_daily()
        - sync_sleep()
        - sync_activities()
        - backfill()
        - normalize_sleep()
        - normalize_daily()

    Optional overrides (return None by default):
        - sync_menstrual()
        - sync_temperature()
    """

    #: Unique slug matching data_sources.source_id (e.g. 'garmin', 'oura').
    SOURCE_ID: str = "unknown"

    #: Human-readable name for logging and UI.
    DISPLAY_NAME: str = "Unknown Device"

    @abstractmethod
    async def authenticate(self, user_id: UUID, auth_code: str) -> OAuthTokens:
        """Exchange OAuth code for access + refresh tokens.

        Args:
            user_id:   Internal Vitalis user UUID.
            auth_code: Authorization code from OAuth callback.

        Returns:
            OAuthTokens with access_token, refresh_token, and expiry.
        """

    @abstractmethod
    async def refresh_token(self, user_id: UUID, refresh_token: str) -> OAuthTokens:
        """Refresh an expired access token.

        Args:
            user_id:       Internal Vitalis user UUID.
            refresh_token: Current refresh token from connected_devices table.

        Returns:
            New OAuthTokens.
        """

    @abstractmethod
    async def sync_daily(
        self, user_id: UUID, target_date: date, access_token: str
    ) -> RawDevicePayload:
        """Fetch the daily summary for a given date.

        Args:
            user_id:      Internal Vitalis user UUID.
            target_date:  Date to fetch (user's local date).
            access_token: Valid OAuth access token.

        Returns:
            RawDevicePayload with the API response.
        """

    @abstractmethod
    async def sync_sleep(
        self, user_id: UUID, target_date: date, access_token: str
    ) -> RawDevicePayload:
        """Fetch sleep data for a given night.

        The date convention is the wake date (morning of) — consistent with
        how wearable_sleep.sleep_date is defined in the schema.

        Args:
            user_id:      Internal Vitalis user UUID.
            target_date:  Wake date (morning of the sleep period).
            access_token: Valid OAuth access token.

        Returns:
            RawDevicePayload with sleep API response.
        """

    @abstractmethod
    async def sync_activities(
        self, user_id: UUID, target_date: date, access_token: str
    ) -> list[RawDevicePayload]:
        """Fetch activities/workouts for a given date.

        Args:
            user_id:      Internal Vitalis user UUID.
            target_date:  Date to fetch.
            access_token: Valid OAuth access token.

        Returns:
            List of RawDevicePayload, one per activity.
        """

    @abstractmethod
    async def backfill(
        self,
        user_id: UUID,
        start_date: date,
        end_date: date,
        access_token: str,
    ) -> AsyncIterator[RawDevicePayload]:
        """Iterate over historical data in batches.

        Yields RawDevicePayload for each day between start_date and end_date.
        Implementations must respect rate limits from fusion_config.yaml.

        Args:
            user_id:      Internal Vitalis user UUID.
            start_date:   Earliest date to backfill (inclusive).
            end_date:     Latest date to backfill (inclusive).
            access_token: Valid OAuth access token.

        Yields:
            RawDevicePayload for each fetched record.
        """

    @abstractmethod
    def normalize_sleep(self, raw: dict) -> NormalizedSleep:
        """Convert device-specific sleep JSON to canonical NormalizedSleep.

        This is a pure function — no I/O, no side effects.  Must handle
        missing or null fields gracefully.

        Args:
            raw: Device-specific API response dict.

        Returns:
            NormalizedSleep in canonical format.
        """

    @abstractmethod
    def normalize_daily(self, raw: dict) -> NormalizedDaily:
        """Convert device-specific daily JSON to canonical NormalizedDaily.

        This is a pure function — no I/O, no side effects.

        Args:
            raw: Device-specific API response dict.

        Returns:
            NormalizedDaily in canonical format.
        """

    # ------------------------------------------------------------------
    # Optional overrides — return None by default (not all devices support)
    # ------------------------------------------------------------------

    async def sync_menstrual(
        self, user_id: UUID, target_date: date, access_token: str
    ) -> RawDevicePayload | None:
        """Fetch menstrual/cycle data if the device supports it.

        Override in adapters that have cycle tracking (e.g. Apple Watch).
        Default returns None.

        Args:
            user_id:      Internal Vitalis user UUID.
            target_date:  Date to fetch.
            access_token: Valid OAuth access token.

        Returns:
            RawDevicePayload or None if not supported.
        """
        return None

    async def sync_temperature(
        self, user_id: UUID, target_date: date, access_token: str
    ) -> RawDevicePayload | None:
        """Fetch body/skin temperature data if the device supports it.

        Override in adapters that have temperature sensors (Oura, Apple Series 8+).
        Default returns None.

        Args:
            user_id:      Internal Vitalis user UUID.
            target_date:  Date to fetch.
            access_token: Valid OAuth access token.

        Returns:
            RawDevicePayload or None if not supported.
        """
        return None

    # ------------------------------------------------------------------
    # Shared helpers — available to all adapters
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_int(value: object) -> int | None:
        """Safely coerce a value to int, returning None on failure."""
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_float(value: object) -> float | None:
        """Safely coerce a value to float, returning None on failure."""
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_iso_datetime(value: str | None) -> datetime | None:
        """Parse an ISO-8601 datetime string to UTC datetime.

        Handles both naive (assumed UTC) and timezone-aware strings.
        Returns None if the value is None or unparseable.
        """
        if not value:
            return None
        from datetime import timezone

        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            # Convert to UTC if tz-aware, leave naive as-is (assumed UTC)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except (ValueError, AttributeError):
            logger.warning("Could not parse datetime string: %r", value)
            return None
