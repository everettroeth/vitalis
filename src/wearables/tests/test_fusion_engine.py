"""Tests for the fusion engine — weighted merge and conflict detection."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

import pytest

from src.wearables.base import NormalizedDaily, NormalizedSleep
from src.wearables.config_loader import FusionConfig
from src.wearables.fusion_engine import (
    FusionEngine,
    FusionResult,
    _fuse_metric,
    _weighted_average,
    fuse_daily,
    fuse_sleep,
)
from src.wearables.sleep_matcher import SleepMatchGroup
from src.wearables.tests.conftest import TEST_DATE, TEST_USER_ID


class TestWeightedAverage:
    """Unit tests for the weighted average helper."""

    def test_equal_weights(self) -> None:
        readings = {"a": 100.0, "b": 80.0}
        weights = {"a": 1.0, "b": 1.0}
        result = _weighted_average(readings, weights)
        assert result == pytest.approx(90.0)

    def test_unequal_weights(self) -> None:
        readings = {"oura": 58.0, "garmin": 52.0}
        weights = {"oura": 0.95, "garmin": 0.65}
        result = _weighted_average(readings, weights)
        # oura contributes 95/(95+65) = 59.4% of the result
        expected = (58.0 * 0.95 + 52.0 * 0.65) / (0.95 + 0.65)
        assert result == pytest.approx(expected, rel=0.001)

    def test_zero_weights_falls_back_to_simple_average(self) -> None:
        readings = {"a": 60.0, "b": 40.0}
        weights = {"a": 0.0, "b": 0.0}
        result = _weighted_average(readings, weights)
        assert result == pytest.approx(50.0)

    def test_single_source(self) -> None:
        readings = {"oura": 75.0}
        weights = {"oura": 0.95}
        result = _weighted_average(readings, weights)
        assert result == pytest.approx(75.0)


class TestFuseMetric:
    """Unit tests for single-metric fusion."""

    def test_single_source_no_conflict(self, fusion_config: FusionConfig) -> None:
        result = _fuse_metric("hrv", {"oura": 58.0}, fusion_config, "hrv_ms")
        assert result.fused_value == pytest.approx(58.0)
        assert not result.had_conflict
        assert result.sources_used == ["oura"]

    def test_two_sources_within_tolerance(self, fusion_config: FusionConfig) -> None:
        # Diff = 5ms < 15ms tolerance
        readings = {"oura": 58.0, "garmin": 55.0}
        result = _fuse_metric("hrv", readings, fusion_config, "hrv_ms")
        assert not result.had_conflict
        assert 55.0 < result.fused_value < 58.0  # weighted toward oura
        assert result.fused_value > 56.5  # oura gets more weight

    def test_two_sources_outside_tolerance_conflict(self, fusion_config: FusionConfig) -> None:
        # Diff = 37ms > 15ms tolerance → conflict
        readings = {"oura": 85.0, "garmin": 48.0}
        result = _fuse_metric("hrv", readings, fusion_config, "hrv_ms")
        assert result.had_conflict
        assert result.fused_value == pytest.approx(85.0)  # oura wins (higher weight)
        assert "oura" in result.sources_used
        assert result.conflict_detail

    def test_three_sources_weighted_merge(self, fusion_config: FusionConfig) -> None:
        readings = {"oura": 58.0, "garmin": 52.0, "whoop": 55.0}
        result = _fuse_metric("hrv", readings, fusion_config, "hrv_ms")
        assert not result.had_conflict
        # Result should be weighted toward oura (highest weight)
        assert 52.0 <= result.fused_value <= 58.0
        assert len(result.sources_used) == 3

    def test_zero_weight_source_excluded(self, fusion_config: FusionConfig) -> None:
        # garmin has weight 0.0 for body_battery_readiness
        readings = {"garmin": 75.0}
        result = _fuse_metric("body_battery_readiness", readings, fusion_config)
        # Weight is 0 — falls back to equal weights, returns the value
        assert result.fused_value == pytest.approx(75.0)

    def test_no_tolerance_key_skips_conflict_check(self, fusion_config: FusionConfig) -> None:
        # Very large difference but no tolerance key → no conflict flagged
        readings = {"oura": 1000.0, "garmin": 1.0}
        result = _fuse_metric("calories_burned", readings, fusion_config, None)
        assert not result.had_conflict


class TestFuseDaily:
    """Tests for daily fusion end-to-end."""

    def test_single_source_passthrough(
        self, normalized_oura_daily: NormalizedDaily
    ) -> None:
        fusion_result, fused = fuse_daily(
            TEST_USER_ID, TEST_DATE, [normalized_oura_daily]
        )
        assert fused.source == "oura"
        assert fusion_result.sources_used == ["oura"]

    def test_two_sources_no_conflict(
        self,
        normalized_oura_daily: NormalizedDaily,
        normalized_garmin_daily: NormalizedDaily,
    ) -> None:
        fusion_result, fused = fuse_daily(
            TEST_USER_ID, TEST_DATE,
            [normalized_oura_daily, normalized_garmin_daily],
        )
        assert fused.source == "fused"
        assert set(fusion_result.sources_used) == {"oura", "garmin"}
        assert not fusion_result.conflicts

    def test_conflict_detected_on_hrv(
        self, conflict_daily_records: list[NormalizedDaily]
    ) -> None:
        fusion_result, fused = fuse_daily(
            TEST_USER_ID, TEST_DATE, conflict_daily_records
        )
        # HRV diff = 37ms > 15ms tolerance → conflict
        assert "hrv_rmssd_ms" in fusion_result.conflicts
        # Oura wins (highest weight) → fused value = 85.0
        assert fused.hrv_rmssd_ms == pytest.approx(85.0)

    def test_proprietary_scores_excluded(
        self,
        normalized_oura_daily: NormalizedDaily,
        normalized_garmin_daily: NormalizedDaily,
    ) -> None:
        _, fused = fuse_daily(
            TEST_USER_ID, TEST_DATE,
            [normalized_oura_daily, normalized_garmin_daily],
        )
        assert fused.readiness_score is None
        assert fused.recovery_score is None

    def test_empty_records_raises(self) -> None:
        with pytest.raises(ValueError, match="No daily records"):
            fuse_daily(TEST_USER_ID, TEST_DATE, [])

    def test_fused_steps_is_integer(
        self,
        normalized_oura_daily: NormalizedDaily,
        normalized_garmin_daily: NormalizedDaily,
    ) -> None:
        _, fused = fuse_daily(
            TEST_USER_ID, TEST_DATE,
            [normalized_oura_daily, normalized_garmin_daily],
        )
        assert isinstance(fused.steps, int)

    def test_fusion_metadata_recorded(
        self,
        normalized_oura_daily: NormalizedDaily,
        normalized_garmin_daily: NormalizedDaily,
    ) -> None:
        fusion_result, _ = fuse_daily(
            TEST_USER_ID, TEST_DATE,
            [normalized_oura_daily, normalized_garmin_daily],
        )
        meta = fusion_result.to_metadata_dict()
        assert "sources_used" in meta
        assert "weights_applied" in meta
        assert "fusion_config_version" in meta  # version depends on loaded config


class TestFuseSleep:
    """Tests for sleep fusion end-to-end."""

    def test_single_source_passthrough(
        self, normalized_oura_sleep: NormalizedSleep
    ) -> None:
        group = SleepMatchGroup(sessions=[normalized_oura_sleep])
        result, fused = fuse_sleep(TEST_USER_ID, TEST_DATE, group)
        assert fused.source == "oura"
        assert result.sources_used == ["oura"]

    def test_two_sources_fused(
        self,
        normalized_oura_sleep: NormalizedSleep,
        normalized_garmin_sleep: NormalizedSleep,
    ) -> None:
        group = SleepMatchGroup(
            sessions=[normalized_oura_sleep, normalized_garmin_sleep]
        )
        result, fused = fuse_sleep(TEST_USER_ID, TEST_DATE, group)
        assert fused.source == "fused"
        assert set(result.sources_used) == {"oura", "garmin"}
        # Total sleep: oura=425, garmin=420 — weighted toward oura → ~423
        assert 419 <= fused.total_sleep_minutes <= 426

    def test_sleep_timing_from_primary_source(
        self,
        normalized_oura_sleep: NormalizedSleep,
        normalized_garmin_sleep: NormalizedSleep,
    ) -> None:
        group = SleepMatchGroup(
            sessions=[normalized_oura_sleep, normalized_garmin_sleep]
        )
        _, fused = fuse_sleep(TEST_USER_ID, TEST_DATE, group)
        # Oura is primary (highest weight) — timing should come from oura
        assert fused.sleep_start == normalized_oura_sleep.sleep_start

    def test_empty_group_raises(self) -> None:
        group = SleepMatchGroup(sessions=[])
        with pytest.raises(ValueError, match="Empty sleep match group"):
            fuse_sleep(TEST_USER_ID, TEST_DATE, group)

    def test_fusion_engine_run_sleep(
        self,
        normalized_oura_sleep: NormalizedSleep,
        normalized_garmin_sleep: NormalizedSleep,
        fusion_config: FusionConfig,
    ) -> None:
        engine = FusionEngine(fusion_config)
        results = engine.run_sleep(
            TEST_USER_ID, TEST_DATE,
            [normalized_oura_sleep, normalized_garmin_sleep],
        )
        assert len(results) == 1
        fusion_result, fused = results[0]
        assert fused.source == "fused"
