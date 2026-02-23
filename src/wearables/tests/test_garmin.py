"""Tests for the Garmin adapter — normalization of realistic API responses."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from src.wearables.adapters.garmin import GarminAdapter
from src.wearables.base import NormalizedDaily, NormalizedSleep, RawDevicePayload
from src.wearables.tests.conftest import TEST_DATE, TEST_USER_ID


@pytest.fixture
def garmin_adapter() -> GarminAdapter:
    """Garmin adapter with test credentials."""
    return GarminAdapter(
        consumer_key="test_key",
        consumer_secret="test_secret",
    )


# ---------------------------------------------------------------------------
# Sleep normalization
# ---------------------------------------------------------------------------


class TestGarminSleepNormalization:
    def test_normalize_sleep_date(
        self, garmin_adapter: GarminAdapter, garmin_sleep_raw: dict
    ) -> None:
        result = garmin_adapter.normalize_sleep(garmin_sleep_raw)
        assert isinstance(result.sleep_date, date)

    def test_normalize_sleep_returns_normalized_sleep(
        self, garmin_adapter: GarminAdapter, garmin_sleep_raw: dict
    ) -> None:
        result = garmin_adapter.normalize_sleep(garmin_sleep_raw)
        assert isinstance(result, NormalizedSleep)
        assert result.source == "garmin"

    def test_normalize_sleep_total_minutes_from_seconds(
        self, garmin_adapter: GarminAdapter
    ) -> None:
        raw = {
            "sleeps": [{
                "calendarDate": "2026-02-23",
                "sleepTimeSeconds": 25200,  # 7 hours
                "deepSleepSeconds": 5400,
                "lightSleepSeconds": 12600,
                "remSleepSeconds": 5400,
                "awakeSleepSeconds": 1800,
            }]
        }
        result = garmin_adapter.normalize_sleep(raw)
        assert result.total_sleep_minutes == 420
        assert result.deep_minutes == 90
        assert result.rem_minutes == 90

    def test_normalize_sleep_timestamps_converted(
        self, garmin_adapter: GarminAdapter
    ) -> None:
        # Unix timestamps for 2026-02-22T23:00:00 UTC and 2026-02-23T06:45:00 UTC
        start_ts = 1771801200  # 2026-02-22 23:00 UTC
        end_ts = 1771829100  # 2026-02-23 06:45 UTC
        raw = {
            "sleeps": [{
                "calendarDate": "2026-02-23",
                "sleepStartTimestampGMT": start_ts,
                "sleepEndTimestampGMT": end_ts,
                "sleepTimeSeconds": 28200,
            }]
        }
        result = garmin_adapter.normalize_sleep(raw)
        assert result.sleep_start is not None
        assert result.sleep_end is not None
        assert result.sleep_start.hour == 23

    def test_normalize_sleep_handles_missing_fields_gracefully(
        self, garmin_adapter: GarminAdapter
    ) -> None:
        # Minimal payload — should not raise
        result = garmin_adapter.normalize_sleep({"sleeps": [{"calendarDate": "2026-02-23"}]})
        assert result.source == "garmin"
        assert result.total_sleep_minutes is None

    def test_normalize_sleep_empty_payload_uses_defaults(
        self, garmin_adapter: GarminAdapter
    ) -> None:
        result = garmin_adapter.normalize_sleep({})
        assert result.source == "garmin"
        assert result.sleep_date is not None  # defaults to today

    def test_normalize_sleep_builds_hypnogram(
        self, garmin_adapter: GarminAdapter
    ) -> None:
        raw = {
            "sleeps": [{
                "calendarDate": "2026-02-23",
                "sleepLevels": [
                    {"startGMT": 1000000, "activityLevel": "deep"},
                    {"startGMT": 1001800, "activityLevel": "rem"},
                    {"startGMT": 1003600, "activityLevel": "light"},
                ],
            }]
        }
        result = garmin_adapter.normalize_sleep(raw)
        assert len(result.hypnogram) == 3
        assert result.hypnogram[0]["stage"] == "deep"
        assert result.hypnogram[1]["stage"] == "rem"

    def test_normalize_sleep_stage_mapping(
        self, garmin_adapter: GarminAdapter
    ) -> None:
        """N1/N2/N3 sleep level notation should map to light/light/deep."""
        raw = {
            "sleeps": [{
                "calendarDate": "2026-02-23",
                "sleepLevels": [
                    {"startGMT": 1000000, "activityLevel": "n1"},
                    {"startGMT": 1000300, "activityLevel": "n2"},
                    {"startGMT": 1000600, "activityLevel": "n3"},
                ],
            }]
        }
        result = garmin_adapter.normalize_sleep(raw)
        stages = [e["stage"] for e in result.hypnogram]
        assert stages == ["light", "light", "deep"]


# ---------------------------------------------------------------------------
# Daily normalization
# ---------------------------------------------------------------------------


class TestGarminDailyNormalization:
    def test_normalize_daily_returns_normalized_daily(
        self, garmin_adapter: GarminAdapter, garmin_daily_raw: dict
    ) -> None:
        result = garmin_adapter.normalize_daily(garmin_daily_raw)
        assert isinstance(result, NormalizedDaily)
        assert result.source == "garmin"

    def test_normalize_daily_steps(
        self, garmin_adapter: GarminAdapter
    ) -> None:
        raw = {
            "dailies": [{
                "calendarDate": "2026-02-23",
                "totalSteps": 11432,
            }]
        }
        result = garmin_adapter.normalize_daily(raw)
        assert result.steps == 11432

    def test_normalize_daily_resting_hr(
        self, garmin_adapter: GarminAdapter
    ) -> None:
        raw = {
            "dailies": [{
                "calendarDate": "2026-02-23",
                "restingHeartRateInBeatsPerMinute": 52,
            }]
        }
        result = garmin_adapter.normalize_daily(raw)
        assert result.resting_hr_bpm == 52

    def test_normalize_daily_active_time_seconds_to_minutes(
        self, garmin_adapter: GarminAdapter
    ) -> None:
        raw = {
            "dailies": [{
                "calendarDate": "2026-02-23",
                "activeTimeInSeconds": 4320,  # 72 minutes
            }]
        }
        result = garmin_adapter.normalize_daily(raw)
        assert result.active_minutes == 72

    def test_normalize_daily_extended_metrics_present(
        self, garmin_adapter: GarminAdapter
    ) -> None:
        raw = {
            "dailies": [{
                "calendarDate": "2026-02-23",
                "bodyBatteryChargedValue": 85,
                "bodyBatteryDrainedValue": 60,
                "moderateIntensityMinutes": 30,
            }]
        }
        result = garmin_adapter.normalize_daily(raw)
        assert result.extended_metrics is not None
        assert result.extended_metrics.get("body_battery_end") == 60

    def test_normalize_daily_handles_userDailySummaries_key(
        self, garmin_adapter: GarminAdapter
    ) -> None:
        raw = {
            "userDailySummaries": [{
                "calendarDate": "2026-02-23",
                "totalSteps": 9000,
            }]
        }
        result = garmin_adapter.normalize_daily(raw)
        assert result.steps == 9000

    def test_normalize_daily_proprietary_score_is_none(
        self, garmin_adapter: GarminAdapter
    ) -> None:
        """Garmin body battery is proprietary — readiness_score must be None."""
        raw = {
            "dailies": [{
                "calendarDate": "2026-02-23",
                "bodyBatteryChargedValue": 90,
            }]
        }
        result = garmin_adapter.normalize_daily(raw)
        assert result.readiness_score is None


# ---------------------------------------------------------------------------
# Token parsing
# ---------------------------------------------------------------------------


class TestGarminTokenParsing:
    def test_parse_combined_token(self, garmin_adapter: GarminAdapter) -> None:
        token, secret = garmin_adapter._parse_access_token("mytoken:::mysecret")
        assert token == "mytoken"
        assert secret == "mysecret"

    def test_parse_legacy_token_no_secret(self, garmin_adapter: GarminAdapter) -> None:
        token, secret = garmin_adapter._parse_access_token("legacytoken")
        assert token == "legacytoken"
        assert secret == ""

    def test_parse_token_with_multiple_colons(self, garmin_adapter: GarminAdapter) -> None:
        # Only splits on first :::
        token, secret = garmin_adapter._parse_access_token("tok:::sec:::extra")
        assert token == "tok"
        assert secret == "sec:::extra"


# ---------------------------------------------------------------------------
# Activity normalization
# ---------------------------------------------------------------------------


class TestGarminActivityNormalization:
    def test_normalize_activity_type_mapping(
        self, garmin_adapter: GarminAdapter
    ) -> None:
        raw = {
            "activityId": 123456,
            "activityName": "Morning Run",
            "activityType": "running",
            "startTimeInSeconds": int(datetime(2026, 2, 23, 7, 0).timestamp()),
            "durationInSeconds": 3600,
            "distanceInMeters": 10000,
            "activeKilocalories": 650,
            "averageHeartRateInBeatsPerMinute": 142,
        }
        result = garmin_adapter.normalize_activity(raw)
        assert result.activity_type == "running"
        assert result.duration_seconds == 3600
        assert result.distance_m == pytest.approx(10000.0)
        assert result.calories_kcal == 650

    def test_normalize_activity_unknown_type_mapped_to_other(
        self, garmin_adapter: GarminAdapter
    ) -> None:
        raw = {
            "activityType": "interpretive_dance",
            "startTimeInSeconds": int(datetime(2026, 2, 23, 7, 0).timestamp()),
        }
        result = garmin_adapter.normalize_activity(raw)
        assert result.activity_type == "other"

    def test_normalize_activity_computes_end_time(
        self, garmin_adapter: GarminAdapter
    ) -> None:
        start_ts = int(datetime(2026, 2, 23, 7, 0).timestamp())
        raw = {
            "startTimeInSeconds": start_ts,
            "durationInSeconds": 1800,  # 30 minutes
        }
        result = garmin_adapter.normalize_activity(raw)
        assert result.end_time is not None
        assert result.start_time is not None
        diff = (result.end_time - result.start_time).total_seconds()
        assert diff == 1800


# ---------------------------------------------------------------------------
# Adapter metadata
# ---------------------------------------------------------------------------


class TestGarminAdapterMetadata:
    def test_source_id(self, garmin_adapter: GarminAdapter) -> None:
        assert garmin_adapter.SOURCE_ID == "garmin"

    def test_display_name(self, garmin_adapter: GarminAdapter) -> None:
        assert "Garmin" in garmin_adapter.DISPLAY_NAME

    def test_needs_token_refresh_no_refresh_token(self) -> None:
        from src.wearables.sync.scheduler import SyncJob
        job = SyncJob(
            user_id=TEST_USER_ID,
            source="garmin",
            access_token="tok:::sec",
            refresh_token=None,
        )
        # OAuth 1.0a — no token refresh needed
        assert not job.needs_token_refresh()
