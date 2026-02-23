"""Tests for the Oura adapter — normalization of realistic API responses."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from src.wearables.adapters.oura import OuraAdapter
from src.wearables.base import NormalizedDaily, NormalizedSleep
from src.wearables.tests.conftest import TEST_DATE, TEST_USER_ID


@pytest.fixture
def oura_adapter() -> OuraAdapter:
    """Oura adapter with test credentials and no real HTTP client."""
    return OuraAdapter(
        client_id="test_client_id",
        client_secret="test_client_secret",
        personal_token="test_personal_token",
    )


# ---------------------------------------------------------------------------
# Sleep normalization
# ---------------------------------------------------------------------------


class TestOuraSleepNormalization:
    def test_normalize_sleep_returns_normalized_sleep(
        self, oura_adapter: OuraAdapter, oura_sleep_raw: dict
    ) -> None:
        result = oura_adapter.normalize_sleep(oura_sleep_raw)
        assert isinstance(result, NormalizedSleep)
        assert result.source == "oura"

    def test_normalize_sleep_date_from_day_field(
        self, oura_adapter: OuraAdapter, oura_sleep_raw: dict
    ) -> None:
        result = oura_adapter.normalize_sleep(oura_sleep_raw)
        assert result.sleep_date == date(2026, 2, 23)

    def test_normalize_sleep_bedtime_start_parsed(
        self, oura_adapter: OuraAdapter, oura_sleep_raw: dict
    ) -> None:
        result = oura_adapter.normalize_sleep(oura_sleep_raw)
        assert result.sleep_start is not None
        # bedtime_start: "2026-02-22T22:50:00+00:00"
        assert result.sleep_start.year == 2026
        assert result.sleep_start.month == 2
        assert result.sleep_start.day == 22

    def test_normalize_sleep_bedtime_end_parsed(
        self, oura_adapter: OuraAdapter, oura_sleep_raw: dict
    ) -> None:
        result = oura_adapter.normalize_sleep(oura_sleep_raw)
        assert result.sleep_end is not None
        # bedtime_end: "2026-02-23T06:45:00+00:00"
        assert result.sleep_end.day == 23

    def test_normalize_sleep_duration_in_minutes(
        self, oura_adapter: OuraAdapter
    ) -> None:
        raw = {
            "sleep": [{
                "day": "2026-02-23",
                "total_sleep_duration": 25500,   # 425 minutes
                "deep_sleep_duration": 6300,     # 105 minutes
                "rem_sleep_duration": 5400,      # 90 minutes
                "light_sleep_duration": 12600,   # 210 minutes
                "awake_duration": 1200,          # 20 minutes
                "bedtime_start": "2026-02-22T23:00:00+00:00",
                "bedtime_end": "2026-02-23T06:45:00+00:00",
            }],
            "daily_sleep": [],
        }
        result = oura_adapter.normalize_sleep(raw)
        assert result.total_sleep_minutes == 425
        assert result.deep_minutes == 105
        assert result.rem_minutes == 90
        assert result.light_minutes == 210
        assert result.awake_minutes == 20

    def test_normalize_sleep_avg_hrv_from_samples(
        self, oura_adapter: OuraAdapter, oura_sleep_raw: dict
    ) -> None:
        result = oura_adapter.normalize_sleep(oura_sleep_raw)
        # HRV items: [45, 52, 61, 65, 62, 58, 55, 53, 57, 60] → mean = 56.8
        assert result.avg_hrv_ms is not None
        assert 50 < result.avg_hrv_ms < 65

    def test_normalize_sleep_score_from_daily_sleep(
        self, oura_adapter: OuraAdapter, oura_sleep_raw: dict
    ) -> None:
        result = oura_adapter.normalize_sleep(oura_sleep_raw)
        # daily_sleep score = 84
        assert result.sleep_score == 84

    def test_normalize_sleep_skin_temp_deviation(
        self, oura_adapter: OuraAdapter
    ) -> None:
        raw = {
            "sleep": [{
                "day": "2026-02-23",
                "temperature_deviation": 0.08,
                "bedtime_start": "2026-02-22T23:00:00+00:00",
                "bedtime_end": "2026-02-23T06:45:00+00:00",
            }],
            "daily_sleep": [],
        }
        result = oura_adapter.normalize_sleep(raw)
        assert result.avg_skin_temp_deviation_c == pytest.approx(0.08)

    def test_normalize_sleep_builds_hypnogram_from_phases(
        self, oura_adapter: OuraAdapter
    ) -> None:
        raw = {
            "sleep": [{
                "day": "2026-02-23",
                "sleep_phase_5_min": "44333333",  # 8 five-minute buckets
                "bedtime_start": "2026-02-22T23:00:00+00:00",
                "bedtime_end": "2026-02-23T06:45:00+00:00",
            }],
            "daily_sleep": [],
        }
        result = oura_adapter.normalize_sleep(raw)
        assert len(result.hypnogram) == 8
        # phase 4 = awake, phase 3 = rem
        assert result.hypnogram[0]["stage"] == "awake"
        assert result.hypnogram[2]["stage"] == "rem"

    def test_normalize_sleep_selects_longest_session(
        self, oura_adapter: OuraAdapter
    ) -> None:
        """When multiple sleep sessions, pick the one with max total_sleep_duration."""
        raw = {
            "sleep": [
                {
                    "day": "2026-02-23",
                    "total_sleep_duration": 25500,  # longest
                    "bedtime_start": "2026-02-22T23:00:00+00:00",
                    "bedtime_end": "2026-02-23T06:45:00+00:00",
                },
                {
                    "day": "2026-02-23",
                    "total_sleep_duration": 5400,  # short nap
                    "bedtime_start": "2026-02-23T13:00:00+00:00",
                    "bedtime_end": "2026-02-23T14:30:00+00:00",
                },
            ],
            "daily_sleep": [],
        }
        result = oura_adapter.normalize_sleep(raw)
        assert result.total_sleep_minutes == 425

    def test_normalize_sleep_empty_payload(
        self, oura_adapter: OuraAdapter
    ) -> None:
        result = oura_adapter.normalize_sleep({"sleep": [], "daily_sleep": []})
        assert result.source == "oura"
        assert result.total_sleep_minutes is None


# ---------------------------------------------------------------------------
# Daily normalization
# ---------------------------------------------------------------------------


class TestOuraDailyNormalization:
    def test_normalize_daily_returns_normalized_daily(
        self, oura_adapter: OuraAdapter, oura_daily_raw: dict
    ) -> None:
        result = oura_adapter.normalize_daily(oura_daily_raw)
        assert isinstance(result, NormalizedDaily)
        assert result.source == "oura"

    def test_normalize_daily_steps_from_activity(
        self, oura_adapter: OuraAdapter
    ) -> None:
        raw = {
            "daily_activity": [{
                "day": "2026-02-23",
                "steps": 10241,
                "active_calories": 487,
                "total_calories": 2118,
                "medium_activity_time": 62,
            }],
            "daily_readiness": [],
        }
        result = oura_adapter.normalize_daily(raw)
        assert result.steps == 10241
        assert result.active_calories_kcal == 487
        assert result.active_minutes == 62

    def test_normalize_daily_readiness_score(
        self, oura_adapter: OuraAdapter
    ) -> None:
        raw = {
            "daily_activity": [],
            "daily_readiness": [{
                "day": "2026-02-23",
                "score": 84,
                "contributors": {"hrv_balance": 82},
            }],
        }
        result = oura_adapter.normalize_daily(raw)
        assert result.readiness_score == 84

    def test_normalize_daily_date_from_activity(
        self, oura_adapter: OuraAdapter
    ) -> None:
        raw = {
            "daily_activity": [{"day": "2026-02-23", "steps": 9000}],
            "daily_readiness": [],
        }
        result = oura_adapter.normalize_daily(raw)
        assert result.date == date(2026, 2, 23)

    def test_normalize_daily_resting_hr_is_none(
        self, oura_adapter: OuraAdapter
    ) -> None:
        """Oura reports resting HR in sleep data, not daily activity."""
        raw = {
            "daily_activity": [{"day": "2026-02-23", "steps": 9000}],
            "daily_readiness": [],
        }
        result = oura_adapter.normalize_daily(raw)
        assert result.resting_hr_bpm is None

    def test_normalize_daily_extended_metrics_has_oura_scores(
        self, oura_adapter: OuraAdapter
    ) -> None:
        raw = {
            "daily_activity": [{"day": "2026-02-23", "score": 75}],
            "daily_readiness": [{"day": "2026-02-23", "score": 84}],
        }
        result = oura_adapter.normalize_daily(raw)
        assert result.extended_metrics is not None
        assert "oura_readiness_score" in result.extended_metrics
        assert result.extended_metrics["oura_readiness_score"] == 84


# ---------------------------------------------------------------------------
# Auth header builder
# ---------------------------------------------------------------------------


class TestOuraAuthHeaders:
    def test_build_headers_with_token(self, oura_adapter: OuraAdapter) -> None:
        headers = oura_adapter._build_headers("my_token")
        assert headers["Authorization"] == "Bearer my_token"

    def test_build_headers_falls_back_to_personal_token(
        self, oura_adapter: OuraAdapter
    ) -> None:
        headers = oura_adapter._build_headers("")
        assert headers["Authorization"] == "Bearer test_personal_token"


# ---------------------------------------------------------------------------
# Adapter metadata
# ---------------------------------------------------------------------------


class TestOuraAdapterMetadata:
    def test_source_id(self, oura_adapter: OuraAdapter) -> None:
        assert oura_adapter.SOURCE_ID == "oura"

    def test_display_name_contains_oura(self, oura_adapter: OuraAdapter) -> None:
        assert "Oura" in oura_adapter.DISPLAY_NAME


# ---------------------------------------------------------------------------
# HTTP GET integration (mocked)
# ---------------------------------------------------------------------------


class TestOuraHTTPGet:
    @pytest.mark.asyncio
    async def test_get_uses_injected_http_client(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"data": [1, 2, 3]})

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        adapter = OuraAdapter(
            client_id="test",
            client_secret="test",
            http_client=mock_client,
        )

        result = await adapter._get("https://api.ouraring.com/test", {}, "mytoken")
        assert result == {"data": [1, 2, 3]}
        mock_client.get.assert_called_once()
