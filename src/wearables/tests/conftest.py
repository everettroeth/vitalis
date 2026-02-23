"""Shared fixtures and mock API responses for wearable fusion engine tests."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from src.wearables.base import NormalizedDaily, NormalizedSleep
from src.wearables.config_loader import FusionConfig, load_fusion_config

# Fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Canonical test user ID
TEST_USER_ID = UUID("12345678-1234-5678-1234-567812345678")
TEST_DATE = date(2026, 2, 23)


# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fusion_config() -> FusionConfig:
    """Load the real fusion config for tests."""
    return load_fusion_config()


# ---------------------------------------------------------------------------
# JSON fixture loaders
# ---------------------------------------------------------------------------


@pytest.fixture
def garmin_sleep_raw() -> dict:
    return json.loads((FIXTURES_DIR / "garmin_sleep.json").read_text())


@pytest.fixture
def garmin_daily_raw() -> dict:
    return json.loads((FIXTURES_DIR / "garmin_daily.json").read_text())


@pytest.fixture
def oura_sleep_raw() -> dict:
    return json.loads((FIXTURES_DIR / "oura_sleep.json").read_text())


@pytest.fixture
def oura_daily_raw() -> dict:
    return json.loads((FIXTURES_DIR / "oura_daily.json").read_text())


@pytest.fixture
def overlapping_sleep_raw() -> dict:
    return json.loads((FIXTURES_DIR / "overlapping_sleep.json").read_text())


@pytest.fixture
def cycle_data() -> dict:
    return json.loads((FIXTURES_DIR / "cycle_data.json").read_text())


# ---------------------------------------------------------------------------
# Normalized data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def normalized_oura_sleep() -> NormalizedSleep:
    """A realistic Oura sleep record."""
    return NormalizedSleep(
        user_id=TEST_USER_ID,
        sleep_date=TEST_DATE,
        source="oura",
        sleep_start=datetime(2026, 2, 22, 23, 0, 0),
        sleep_end=datetime(2026, 2, 23, 6, 45, 0),
        total_sleep_minutes=425,
        rem_minutes=90,
        deep_minutes=105,
        light_minutes=210,
        awake_minutes=20,
        sleep_latency_minutes=8,
        sleep_efficiency_pct=92.0,
        sleep_score=84,
        avg_hrv_ms=58.0,
        avg_hr_bpm=52,
        avg_respiratory_rate=13.9,
        avg_spo2_pct=97.1,
        avg_skin_temp_deviation_c=0.08,
    )


@pytest.fixture
def normalized_garmin_sleep() -> NormalizedSleep:
    """A realistic Garmin sleep record for the same night."""
    return NormalizedSleep(
        user_id=TEST_USER_ID,
        sleep_date=TEST_DATE,
        source="garmin",
        sleep_start=datetime(2026, 2, 22, 23, 15, 0),
        sleep_end=datetime(2026, 2, 23, 6, 40, 0),
        total_sleep_minutes=420,
        rem_minutes=70,
        deep_minutes=90,
        light_minutes=240,
        awake_minutes=20,
        sleep_latency_minutes=10,
        sleep_efficiency_pct=89.0,
        sleep_score=78,
        avg_hrv_ms=52.4,
        avg_hr_bpm=54,
        avg_respiratory_rate=14.8,
        avg_spo2_pct=96.2,
    )


@pytest.fixture
def normalized_oura_daily() -> NormalizedDaily:
    """A realistic Oura daily record."""
    return NormalizedDaily(
        user_id=TEST_USER_ID,
        date=TEST_DATE,
        source="oura",
        resting_hr_bpm=None,  # Oura typically reports from sleep data
        hrv_rmssd_ms=58.0,
        steps=10241,
        active_calories_kcal=487,
        total_calories_kcal=2118,
        active_minutes=62,
        distance_m=8240,
        spo2_avg_pct=97.1,
        respiratory_rate_avg=14.2,
        readiness_score=84,
    )


@pytest.fixture
def normalized_garmin_daily() -> NormalizedDaily:
    """A realistic Garmin daily record for the same day."""
    return NormalizedDaily(
        user_id=TEST_USER_ID,
        date=TEST_DATE,
        source="garmin",
        resting_hr_bpm=51,
        hrv_rmssd_ms=52.4,
        steps=11432,
        active_calories_kcal=542,
        total_calories_kcal=2180,
        active_minutes=72,
        distance_m=9124,
        spo2_avg_pct=97.1,
        respiratory_rate_avg=14.2,
        stress_avg=28,
    )


@pytest.fixture
def conflict_daily_records() -> list[NormalizedDaily]:
    """Two daily records with conflicting HRV (outside tolerance)."""
    oura = NormalizedDaily(
        user_id=TEST_USER_ID,
        date=TEST_DATE,
        source="oura",
        hrv_rmssd_ms=85.0,  # Oura reads 85ms
        resting_hr_bpm=48,
    )
    garmin = NormalizedDaily(
        user_id=TEST_USER_ID,
        date=TEST_DATE,
        source="garmin",
        hrv_rmssd_ms=48.0,  # Garmin reads 48ms — diff=37ms > 15ms tolerance
        resting_hr_bpm=50,
    )
    return [oura, garmin]


# ---------------------------------------------------------------------------
# Mock HTTP clients
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_httpx_client() -> MagicMock:
    """Mock httpx.AsyncClient for testing adapters without real API calls."""
    client = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value={})
    client.get = AsyncMock(return_value=response)
    client.post = AsyncMock(return_value=response)
    return client


# ---------------------------------------------------------------------------
# HRV baseline fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def hrv_baseline_30_days() -> list[float]:
    """30 days of realistic HRV readings."""
    import random
    random.seed(42)
    base = 52.0
    return [base + random.gauss(0, 5) for _ in range(30)]


@pytest.fixture
def rhr_baseline_30_days() -> list[float]:
    """30 days of realistic RHR readings."""
    import random
    random.seed(42)
    base = 53.0
    return [base + random.gauss(0, 2) for _ in range(30)]
