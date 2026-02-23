"""Tests for the Vitalis readiness score calculator."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import patch

import pytest

from src.wearables.base import NormalizedDaily, NormalizedSleep
from src.wearables.config_loader import FusionConfig
from src.wearables.readiness_score import (
    ReadinessCalculator,
    ReadinessComponentScore,
    ReadinessScore,
    _score_hrv_vs_baseline,
    _score_recovery_time,
    _score_rhr_vs_baseline,
    _score_sleep_consistency,
    _score_sleep_quality,
    _sigmoid_score,
)
from src.wearables.tests.conftest import TEST_DATE, TEST_USER_ID


# ---------------------------------------------------------------------------
# Unit tests: sigmoid score
# ---------------------------------------------------------------------------


class TestSigmoidScore:
    def test_mean_value_returns_half(self) -> None:
        score = _sigmoid_score(52.0, 52.0, 5.0, higher_is_better=True)
        assert score == pytest.approx(0.5)

    def test_above_mean_higher_is_better_above_half(self) -> None:
        score = _sigmoid_score(62.0, 52.0, 5.0, higher_is_better=True)
        assert score > 0.5

    def test_below_mean_higher_is_better_below_half(self) -> None:
        score = _sigmoid_score(42.0, 52.0, 5.0, higher_is_better=True)
        assert score < 0.5

    def test_above_mean_lower_is_better_below_half(self) -> None:
        # RHR: higher is worse
        score = _sigmoid_score(62.0, 52.0, 5.0, higher_is_better=False)
        assert score < 0.5

    def test_zero_std_returns_half_at_mean(self) -> None:
        score = _sigmoid_score(52.0, 52.0, 0.0, higher_is_better=True)
        assert score == pytest.approx(0.5)

    def test_score_bounded_0_to_1(self) -> None:
        # Very extreme values should still be within bounds
        assert 0.0 <= _sigmoid_score(200.0, 52.0, 5.0) <= 1.0
        assert 0.0 <= _sigmoid_score(-200.0, 52.0, 5.0) <= 1.0


# ---------------------------------------------------------------------------
# Unit tests: component scorers
# ---------------------------------------------------------------------------


class TestHRVScorer:
    def test_no_hrv_data_returns_unavailable(self) -> None:
        result = _score_hrv_vs_baseline(None, [50.0] * 30)
        assert not result.available

    def test_insufficient_baseline_returns_unavailable(self) -> None:
        result = _score_hrv_vs_baseline(58.0, [50.0] * 5)
        assert not result.available

    def test_hrv_above_baseline_scores_well(
        self, hrv_baseline_30_days: list[float]
    ) -> None:
        mean = sum(hrv_baseline_30_days) / len(hrv_baseline_30_days)
        result = _score_hrv_vs_baseline(mean + 15.0, hrv_baseline_30_days)
        assert result.available
        assert result.raw_score > 0.5

    def test_hrv_below_baseline_scores_poorly(
        self, hrv_baseline_30_days: list[float]
    ) -> None:
        mean = sum(hrv_baseline_30_days) / len(hrv_baseline_30_days)
        result = _score_hrv_vs_baseline(mean - 15.0, hrv_baseline_30_days)
        assert result.available
        assert result.raw_score < 0.5

    def test_explanation_mentions_baseline(
        self, hrv_baseline_30_days: list[float]
    ) -> None:
        result = _score_hrv_vs_baseline(52.0, hrv_baseline_30_days)
        assert "baseline" in result.explanation.lower()


class TestRHRScorer:
    def test_rhr_at_baseline_returns_half(
        self, rhr_baseline_30_days: list[float]
    ) -> None:
        mean = sum(rhr_baseline_30_days) / len(rhr_baseline_30_days)
        result = _score_rhr_vs_baseline(mean, rhr_baseline_30_days)
        assert result.available
        assert result.raw_score == pytest.approx(0.5, abs=0.05)

    def test_rhr_below_baseline_scores_well(
        self, rhr_baseline_30_days: list[float]
    ) -> None:
        mean = sum(rhr_baseline_30_days) / len(rhr_baseline_30_days)
        result = _score_rhr_vs_baseline(mean - 5.0, rhr_baseline_30_days)
        assert result.raw_score > 0.5

    def test_rhr_above_baseline_scores_poorly(
        self, rhr_baseline_30_days: list[float]
    ) -> None:
        mean = sum(rhr_baseline_30_days) / len(rhr_baseline_30_days)
        result = _score_rhr_vs_baseline(mean + 10.0, rhr_baseline_30_days)
        assert result.raw_score < 0.5


class TestSleepQualityScorer:
    def test_no_sleep_returns_unavailable(self) -> None:
        result = _score_sleep_quality(None)
        assert not result.available

    def test_optimal_sleep_scores_near_perfect(self) -> None:
        sleep = NormalizedSleep(
            user_id=TEST_USER_ID, sleep_date=TEST_DATE, source="oura",
            total_sleep_minutes=450,  # 7.5h
            deep_minutes=100,        # 22% of 450 > 20% target
            sleep_efficiency_pct=95.0,
        )
        result = _score_sleep_quality(sleep)
        assert result.available
        assert result.raw_score > 0.85

    def test_minimal_sleep_scores_low(self) -> None:
        sleep = NormalizedSleep(
            user_id=TEST_USER_ID, sleep_date=TEST_DATE, source="oura",
            total_sleep_minutes=300,  # exactly 5h (minimum threshold)
            deep_minutes=20,
            sleep_efficiency_pct=72.0,
        )
        result = _score_sleep_quality(sleep)
        assert result.available
        assert result.raw_score < 0.4

    def test_good_sleep_with_no_stage_data(self) -> None:
        sleep = NormalizedSleep(
            user_id=TEST_USER_ID, sleep_date=TEST_DATE, source="garmin",
            total_sleep_minutes=420,
            deep_minutes=None,
            sleep_efficiency_pct=None,
        )
        result = _score_sleep_quality(sleep)
        assert result.available  # still computes even without stage data


class TestSleepConsistencyScorer:
    def test_perfect_consistency_scores_one(self) -> None:
        sleeps = [
            NormalizedSleep(
                user_id=TEST_USER_ID, sleep_date=date(2026, 2, d), source="oura",
                sleep_start=datetime(2026, 2, d, 23, 0),
            )
            for d in range(15, 22)  # 7 nights, all at 23:00
        ]
        result = _score_sleep_consistency(sleeps)
        assert result.available
        assert result.raw_score == pytest.approx(1.0)

    def test_inconsistent_schedule_scores_low(self) -> None:
        starts = [22, 23, 1, 0, 23, 2, 22]  # varies by hours
        sleeps = [
            NormalizedSleep(
                user_id=TEST_USER_ID,
                sleep_date=date(2026, 2, i + 15),
                source="oura",
                sleep_start=datetime(2026, 2, i + 15 if h < 18 else i + 14, h % 24, 0),
            )
            for i, h in enumerate(starts)
        ]
        result = _score_sleep_consistency(sleeps)
        assert result.available
        assert result.raw_score < 0.6

    def test_insufficient_history_returns_unavailable(self) -> None:
        sleeps = [
            NormalizedSleep(
                user_id=TEST_USER_ID, sleep_date=TEST_DATE, source="oura",
                sleep_start=datetime(2026, 2, 22, 23, 0),
            )
        ]
        result = _score_sleep_consistency(sleeps)
        assert not result.available


class TestRecoveryTimeScorer:
    def test_no_workout_data_returns_neutral(self) -> None:
        result = _score_recovery_time(None)
        # No data → assume adequate recovery → not fully unavailable but moderate
        assert not result.available  # available=False but neutral score
        assert result.raw_score == pytest.approx(0.7)

    def test_workout_today_scores_low(self) -> None:
        result = _score_recovery_time(0)
        assert result.raw_score == pytest.approx(0.3)

    def test_three_days_rest_scores_high(self) -> None:
        result = _score_recovery_time(3)
        assert result.raw_score >= 0.9

    def test_more_than_four_days_caps_at_max(self) -> None:
        result_4 = _score_recovery_time(4)
        result_7 = _score_recovery_time(7)
        assert result_4.raw_score == result_7.raw_score


# ---------------------------------------------------------------------------
# Integration tests: ReadinessCalculator
# ---------------------------------------------------------------------------


class TestReadinessCalculator:
    def test_all_data_available_produces_valid_score(
        self,
        fusion_config: FusionConfig,
        normalized_oura_daily: NormalizedDaily,
        normalized_oura_sleep: NormalizedSleep,
        hrv_baseline_30_days: list[float],
        rhr_baseline_30_days: list[float],
    ) -> None:
        calc = ReadinessCalculator(fusion_config)
        # Create 7 recent sleeps
        recent_sleeps = [
            NormalizedSleep(
                user_id=TEST_USER_ID,
                sleep_date=date(2026, 2, d),
                source="oura",
                sleep_start=datetime(2026, 2, d, 23, 0),
                total_sleep_minutes=420,
            )
            for d in range(16, 23)
        ]
        score = calc.compute(
            user_id=str(TEST_USER_ID),
            target_date=TEST_DATE,
            today_daily=normalized_oura_daily,
            today_sleep=normalized_oura_sleep,
            hrv_baseline=hrv_baseline_30_days,
            rhr_baseline=rhr_baseline_30_days,
            recent_sleeps=recent_sleeps,
            days_since_hard_workout=2,
        )
        assert score.available
        assert 0 <= score.score <= 100
        assert score.band in ("thriving", "watch", "concern")
        assert len(score.components) == 5

    def test_score_in_thriving_band_when_metrics_excellent(
        self,
        fusion_config: FusionConfig,
    ) -> None:
        calc = ReadinessCalculator(fusion_config)
        # HRV well above baseline → excellent score
        baseline = [45.0] * 30  # low baseline
        today_daily = NormalizedDaily(
            user_id=TEST_USER_ID, date=TEST_DATE, source="oura",
            hrv_rmssd_ms=90.0,  # 2x baseline
            resting_hr_bpm=45,
        )
        today_sleep = NormalizedSleep(
            user_id=TEST_USER_ID, sleep_date=TEST_DATE, source="oura",
            total_sleep_minutes=450,
            deep_minutes=100,
            sleep_efficiency_pct=95.0,
            sleep_start=datetime(2026, 2, 22, 23, 0),
        )
        recent_sleeps = [
            NormalizedSleep(
                user_id=TEST_USER_ID, sleep_date=date(2026, 2, d), source="oura",
                sleep_start=datetime(2026, 2, d, 23, 0), total_sleep_minutes=450,
            )
            for d in range(16, 23)
        ]
        score = calc.compute(
            user_id=str(TEST_USER_ID),
            target_date=TEST_DATE,
            today_daily=today_daily,
            today_sleep=today_sleep,
            hrv_baseline=baseline,
            rhr_baseline=[58.0] * 30,
            recent_sleeps=recent_sleeps,
            days_since_hard_workout=3,
        )
        assert score.band == "thriving"
        assert score.score >= 75

    def test_score_in_concern_band_when_metrics_poor(
        self,
        fusion_config: FusionConfig,
    ) -> None:
        calc = ReadinessCalculator(fusion_config)
        baseline = [70.0] * 30  # high baseline
        today_daily = NormalizedDaily(
            user_id=TEST_USER_ID, date=TEST_DATE, source="oura",
            hrv_rmssd_ms=25.0,  # far below baseline
            resting_hr_bpm=72,  # very elevated
        )
        today_sleep = NormalizedSleep(
            user_id=TEST_USER_ID, sleep_date=TEST_DATE, source="oura",
            total_sleep_minutes=300,  # minimum
            deep_minutes=20,
            sleep_efficiency_pct=71.0,
        )
        score = calc.compute(
            user_id=str(TEST_USER_ID),
            target_date=TEST_DATE,
            today_daily=today_daily,
            today_sleep=today_sleep,
            hrv_baseline=baseline,
            rhr_baseline=[48.0] * 30,
            recent_sleeps=[],
            days_since_hard_workout=0,
        )
        assert score.band == "concern"
        assert score.score < 50

    def test_no_baseline_data_produces_score_with_unavailable_components(
        self, fusion_config: FusionConfig, normalized_oura_daily: NormalizedDaily
    ) -> None:
        calc = ReadinessCalculator(fusion_config)
        score = calc.compute(
            user_id=str(TEST_USER_ID),
            target_date=TEST_DATE,
            today_daily=normalized_oura_daily,
            today_sleep=None,
            hrv_baseline=None,
            rhr_baseline=None,
            recent_sleeps=None,
            days_since_hard_workout=None,
        )
        # Should still return a score (graceful degradation)
        assert isinstance(score.score, int)
        # Some components should be unavailable
        unavailable = [c for c in score.components if not c.available]
        assert len(unavailable) > 0

    def test_completely_no_data_returns_score_50_watch(
        self, fusion_config: FusionConfig
    ) -> None:
        calc = ReadinessCalculator(fusion_config)
        score = calc.compute(
            user_id=str(TEST_USER_ID),
            target_date=TEST_DATE,
            today_daily=None,
            today_sleep=None,
            hrv_baseline=None,
            rhr_baseline=None,
            recent_sleeps=None,
            days_since_hard_workout=None,
        )
        # All components unavailable → fallback
        assert score.score == 50
        assert not score.available

    def test_readiness_disabled_returns_unavailable(
        self, fusion_config: FusionConfig, normalized_oura_daily: NormalizedDaily
    ) -> None:
        import dataclasses
        disabled_config = dataclasses.replace(
            fusion_config,
            readiness=dataclasses.replace(fusion_config.readiness, enabled=False),
        )
        calc = ReadinessCalculator(disabled_config)
        score = calc.compute(
            user_id=str(TEST_USER_ID),
            target_date=TEST_DATE,
            today_daily=normalized_oura_daily,
            today_sleep=None,
        )
        assert not score.available
        assert score.score == 0
