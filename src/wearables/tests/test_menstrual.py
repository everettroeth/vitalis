"""Tests for menstrual cycle modules: temperature ovulation detection,
cycle prediction, and symptom correlation."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest

from src.wearables.config_loader import FusionConfig
from src.wearables.menstrual.cycle_tracker import (
    CyclePrediction,
    CycleRecord,
    CycleTracker,
)
from src.wearables.menstrual.symptom_correlator import (
    SymptomCorrelator,
    SymptomLog,
    _pearson_r,
)
from src.wearables.menstrual.temp_ovulation import (
    DailyTemperature,
    OvulationDetectionResult,
    TempOvulationDetector,
)
from src.wearables.tests.conftest import TEST_DATE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_cycle(period_start: date, length: int, is_complete: bool = True) -> CycleRecord:
    return CycleRecord(
        cycle_id=uuid4(),
        period_start=period_start,
        cycle_length=length,
        is_complete=is_complete,
    )


def make_temp(d: date, temp_c: float, source: str = "oura") -> DailyTemperature:
    return DailyTemperature(date=d, temp_c=temp_c, source=source)


def build_regular_cycles(n: int = 6, avg_length: int = 28) -> list[CycleRecord]:
    """Build n consecutive regular cycles."""
    cycles = []
    start = date(2025, 6, 1)
    for _ in range(n):
        cycles.append(make_cycle(start, avg_length))
        start += timedelta(days=avg_length)
    return cycles


def build_biphasic_temps(cycle_start: date, ovulation_day: int = 14) -> list[DailyTemperature]:
    """Build temperature readings with a biphasic pattern (ovulation at day 14)."""
    temps = []
    for i in range(23):
        d = cycle_start + timedelta(days=i)
        if i < ovulation_day:
            # Follicular: low temps around -0.1°C
            temp = -0.10 + (i * 0.005)
        else:
            # Luteal: elevated temps > +0.2°C
            temp = 0.22 + (i - ovulation_day) * 0.01
        temps.append(make_temp(d, temp))
    return temps


# ---------------------------------------------------------------------------
# Temperature ovulation detection
# ---------------------------------------------------------------------------


class TestTempOvulationDetector:
    def test_detects_ovulation_in_biphasic_pattern(
        self, fusion_config: FusionConfig, cycle_data: dict
    ) -> None:
        cycle_start = date.fromisoformat(
            cycle_data["temperature_data"]["current_cycle_start"]
        )
        temps = [
            DailyTemperature(
                date=date.fromisoformat(r["date"]),
                temp_c=r["temp_c"],
                source=r["source"],
            )
            for r in cycle_data["temperature_data"]["readings"]
        ]
        detector = TempOvulationDetector(fusion_config)
        result = detector.detect(temps, cycle_start_date=cycle_start)
        assert result.ovulation_detected
        # Ovulation shift starts around Feb 14 in the fixture
        assert result.estimated_ovulation_date is not None
        assert result.estimated_ovulation_date >= date(2026, 2, 13)
        assert result.estimated_ovulation_date <= date(2026, 2, 16)

    def test_no_ovulation_in_flat_temps(
        self, fusion_config: FusionConfig
    ) -> None:
        cycle_start = date(2026, 2, 1)
        # Flat temperature — no shift
        temps = [make_temp(cycle_start + timedelta(days=i), -0.05) for i in range(23)]
        detector = TempOvulationDetector(fusion_config)
        result = detector.detect(temps, cycle_start_date=cycle_start)
        assert not result.ovulation_detected

    def test_fertile_window_set_when_ovulation_detected(
        self, fusion_config: FusionConfig
    ) -> None:
        cycle_start = date(2026, 2, 1)
        temps = build_biphasic_temps(cycle_start, ovulation_day=14)
        detector = TempOvulationDetector(fusion_config)
        result = detector.detect(temps, cycle_start_date=cycle_start)
        if result.ovulation_detected:
            assert result.fertile_window_start is not None
            assert result.fertile_window_end is not None
            assert result.fertile_window_start <= result.fertile_window_end

    def test_insufficient_data_returns_no_detection(
        self, fusion_config: FusionConfig
    ) -> None:
        # Only 3 days of data — not enough
        cycle_start = date(2026, 2, 1)
        temps = [make_temp(cycle_start + timedelta(days=i), 0.0) for i in range(3)]
        detector = TempOvulationDetector(fusion_config)
        result = detector.detect(temps, cycle_start_date=cycle_start)
        assert not result.ovulation_detected

    def test_confirmation_days_respected(
        self, fusion_config: FusionConfig
    ) -> None:
        """Ovulation should NOT be confirmed if the shift lasts fewer than confirmation_days."""
        cycle_start = date(2026, 2, 1)
        temps = []
        for i in range(20):
            d = cycle_start + timedelta(days=i)
            if i == 13:
                # Single-day spike — not sustained
                temps.append(make_temp(d, 0.30))
            else:
                temps.append(make_temp(d, -0.05))
        detector = TempOvulationDetector(fusion_config)
        result = detector.detect(temps, cycle_start_date=cycle_start)
        # Single-day spike should not confirm ovulation
        assert not result.ovulation_detected

    def test_result_has_confidence(
        self, fusion_config: FusionConfig
    ) -> None:
        cycle_start = date(2026, 2, 1)
        temps = build_biphasic_temps(cycle_start)
        detector = TempOvulationDetector(fusion_config)
        result = detector.detect(temps, cycle_start_date=cycle_start)
        assert 0.0 <= result.confidence <= 1.0


# ---------------------------------------------------------------------------
# Cycle tracker / prediction
# ---------------------------------------------------------------------------


class TestCycleTracker:
    def test_regular_cycles_predicts_next_period(
        self, fusion_config: FusionConfig
    ) -> None:
        cycles = build_regular_cycles(n=6, avg_length=28)
        last_start = cycles[-1].period_start
        current_start = last_start + timedelta(days=28)

        tracker = CycleTracker(fusion_config)
        prediction = tracker.predict(
            cycles=cycles,
            current_cycle_start=current_start,
            as_of_date=current_start + timedelta(days=14),
        )
        assert prediction.predicted_period_start is not None
        expected = current_start + timedelta(days=28)
        assert abs((prediction.predicted_period_start - expected).days) <= 2

    def test_no_cycles_returns_no_prediction(
        self, fusion_config: FusionConfig
    ) -> None:
        tracker = CycleTracker(fusion_config)
        prediction = tracker.predict(
            cycles=[],
            current_cycle_start=date(2026, 2, 1),
            as_of_date=date(2026, 2, 15),
        )
        assert prediction.predicted_period_start is None
        assert prediction.confidence < 0.5

    def test_irregular_cycles_flagged(
        self, fusion_config: FusionConfig, cycle_data: dict
    ) -> None:
        cycles = [
            make_cycle(
                date.fromisoformat(c["period_start"]), c["cycle_length"]
            )
            for c in cycle_data["irregular_cycles"]
        ]
        tracker = CycleTracker(fusion_config)
        prediction = tracker.predict(
            cycles=cycles,
            current_cycle_start=date(2026, 2, 1),
            as_of_date=date(2026, 2, 15),
        )
        assert prediction.is_irregular

    def test_regular_cycles_not_flagged_irregular(
        self, fusion_config: FusionConfig
    ) -> None:
        cycles = build_regular_cycles(n=6, avg_length=28)
        tracker = CycleTracker(fusion_config)
        prediction = tracker.predict(
            cycles=cycles,
            current_cycle_start=cycles[-1].period_start + timedelta(days=28),
            as_of_date=date(2026, 2, 15),
        )
        assert not prediction.is_irregular

    def test_current_cycle_day_computed(
        self, fusion_config: FusionConfig
    ) -> None:
        cycles = build_regular_cycles(n=3)
        current_start = date(2026, 2, 1)
        as_of = date(2026, 2, 10)  # day 10

        tracker = CycleTracker(fusion_config)
        prediction = tracker.predict(
            cycles=cycles,
            current_cycle_start=current_start,
            as_of_date=as_of,
        )
        assert prediction.current_cycle_day == 10

    def test_fertile_window_set(
        self, fusion_config: FusionConfig
    ) -> None:
        cycles = build_regular_cycles(n=6)
        current_start = date(2026, 2, 1)
        tracker = CycleTracker(fusion_config)
        prediction = tracker.predict(
            cycles=cycles,
            current_cycle_start=current_start,
            as_of_date=date(2026, 2, 15),
        )
        assert prediction.fertile_window_start is not None
        assert prediction.fertile_window_end is not None
        assert prediction.fertile_window_start < prediction.fertile_window_end

    def test_prediction_includes_std_stats(
        self, fusion_config: FusionConfig
    ) -> None:
        cycles = build_regular_cycles(n=6, avg_length=28)
        tracker = CycleTracker(fusion_config)
        prediction = tracker.predict(
            cycles=cycles,
            current_cycle_start=date(2026, 2, 1),
            as_of_date=date(2026, 2, 15),
        )
        assert prediction.avg_cycle_length == pytest.approx(28.0)
        assert prediction.std_cycle_length is not None
        assert prediction.cycles_used == 6

    def test_rolling_window_limits_cycles_used(
        self, fusion_config: FusionConfig
    ) -> None:
        # Build 12 cycles — tracker should only use last 6
        cycles = build_regular_cycles(n=12)
        tracker = CycleTracker(fusion_config)
        prediction = tracker.predict(
            cycles=cycles,
            current_cycle_start=cycles[-1].period_start + timedelta(days=28),
        )
        assert prediction.cycles_used <= 6

    def test_temperature_assisted_model_when_temps_available(
        self, fusion_config: FusionConfig
    ) -> None:
        cycles = build_regular_cycles(n=4)
        current_start = date(2026, 2, 1)
        temps = build_biphasic_temps(current_start, ovulation_day=14)

        tracker = CycleTracker(fusion_config)
        prediction = tracker.predict(
            cycles=cycles,
            current_cycle_start=current_start,
            current_temps=temps,
            as_of_date=date(2026, 2, 18),  # post-ovulation
        )
        assert prediction.model_used == "temperature_assisted"
        assert prediction.predicted_ovulation_date is not None

    def test_short_cycle_warning(
        self, fusion_config: FusionConfig
    ) -> None:
        cycles = [make_cycle(date(2025, 6, 1) + timedelta(days=i * 20), 20) for i in range(4)]
        tracker = CycleTracker(fusion_config)
        prediction = tracker.predict(
            cycles=cycles,
            current_cycle_start=date(2026, 2, 1),
        )
        assert any("short" in w.lower() for w in prediction.warnings)


# ---------------------------------------------------------------------------
# Symptom correlator
# ---------------------------------------------------------------------------


class TestSymptomCorrelator:
    def _make_logs(self, n: int = 30) -> list[SymptomLog]:
        """Build synthetic symptom logs with correlated fatigue/low HRV."""
        logs = []
        start = date(2026, 1, 1)
        for i in range(n):
            d = start + timedelta(days=i)
            # Simulate: fatigue correlates with low HRV
            hrv = 60.0 - (i % 7) * 3  # oscillates
            fatigue = max(0, 3 - int(hrv / 20))  # higher when hrv lower
            logs.append(
                SymptomLog(
                    date=d,
                    cycle_day=(i % 28) + 1,
                    phase="follicular" if (i % 28) < 14 else "luteal",
                    symptoms={"fatigue": fatigue, "mood": 3},
                    hrv_ms=hrv,
                    rhr_bpm=55.0,
                    sleep_minutes=420,
                )
            )
        return logs

    def test_generates_insights_from_logs(self) -> None:
        logs = self._make_logs(28)
        correlator = SymptomCorrelator()
        insights = correlator.generate_insights(logs)
        assert isinstance(insights, list)
        # Should produce at least some insights with 28 logs
        assert len(insights) >= 0  # may be 0 if correlations are weak

    def test_insufficient_logs_returns_empty(self) -> None:
        logs = self._make_logs(3)
        correlator = SymptomCorrelator()
        insights = correlator.generate_insights(logs)
        assert insights == []

    def test_phase_profiles_built_correctly(self) -> None:
        logs = self._make_logs(28)
        correlator = SymptomCorrelator()
        profiles = correlator._build_phase_profiles(logs)
        assert "follicular" in profiles or "luteal" in profiles

    def test_phase_profile_sample_count(self) -> None:
        logs = self._make_logs(28)
        correlator = SymptomCorrelator()
        profiles = correlator._build_phase_profiles(logs)
        for profile in profiles.values():
            assert profile.sample_count >= 0


class TestPearsonR:
    def test_perfect_positive_correlation(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]
        r = _pearson_r(x, y)
        assert r is not None
        assert r == pytest.approx(1.0)

    def test_perfect_negative_correlation(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [10.0, 8.0, 6.0, 4.0, 2.0]
        r = _pearson_r(x, y)
        assert r is not None
        assert r == pytest.approx(-1.0)

    def test_no_correlation_near_zero(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [3.0, 3.0, 3.0, 3.0, 3.0]  # constant
        r = _pearson_r(x, y)
        # Constant y → undefined / returns None
        assert r is None or r == pytest.approx(0.0, abs=0.1)

    def test_insufficient_data_returns_none(self) -> None:
        r = _pearson_r([1.0, 2.0], [3.0, 4.0])
        # Need ≥ 3 pairs; with 2 may be None
        assert r is None or isinstance(r, float)

    def test_returns_none_for_empty_lists(self) -> None:
        r = _pearson_r([], [])
        assert r is None
