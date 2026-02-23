"""Menstrual cycle prediction engine.

Uses calendar averaging + temperature data to predict:
- Next period start date
- Fertile window
- Current cycle phase

Does NOT assume a 28-day cycle.  Works correctly for irregular cycles,
PCOS, perimenopause, and post-partum patterns.

All predictions use a rolling average of the last 6 cycles (configurable).
"""

from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from uuid import UUID

from src.wearables.config_loader import FusionConfig, get_fusion_config
from src.wearables.menstrual.temp_ovulation import (
    DailyTemperature,
    OvulationDetectionResult,
    TempOvulationDetector,
)

logger = logging.getLogger("vitalis.wearables.menstrual.cycle_tracker")


@dataclass
class CycleRecord:
    """A single historical menstrual cycle.

    Attributes:
        cycle_id:       UUID of the cycle in the database.
        period_start:   First day of menstruation (user-entered ground truth).
        period_end:     Last day of menstruation (optional).
        cycle_length:   Total cycle length in days (start of this cycle to
                        start of next cycle).
        ovulation_date: Detected ovulation date (from temperature data).
        temperatures:   Daily temperature readings for this cycle.
        is_complete:    False if the next period hasn't started yet.
    """

    cycle_id: UUID | None
    period_start: date
    period_end: date | None = None
    cycle_length: int | None = None
    ovulation_date: date | None = None
    temperatures: list[DailyTemperature] = field(default_factory=list)
    is_complete: bool = False


@dataclass
class CyclePrediction:
    """Prediction for the user's next cycle.

    Attributes:
        predicted_period_start: Best estimate for next period start.
        predicted_period_start_early: Lower bound (earlier than expected).
        predicted_period_start_late:  Upper bound (later than expected).
        predicted_ovulation_date: Best estimate for next ovulation.
        fertile_window_start:   Start of fertile window.
        fertile_window_end:     End of fertile window.
        predicted_cycle_length: Predicted length of current/next cycle.
        avg_cycle_length:       Personal rolling average cycle length.
        std_cycle_length:       Standard deviation of cycle lengths.
        cycles_used:            Number of historical cycles used for prediction.
        confidence:             0.0–1.0 overall prediction confidence.
        model_used:             'temperature_assisted', 'calendar_only'.
        current_phase:          Current phase if in an active cycle.
        current_cycle_day:      Day within current cycle (1-indexed).
        is_irregular:           True if cycles vary by > 7 days.
        warnings:               Any flags (very short, very long cycles, etc.).
    """

    predicted_period_start: date | None = None
    predicted_period_start_early: date | None = None
    predicted_period_start_late: date | None = None
    predicted_ovulation_date: date | None = None
    fertile_window_start: date | None = None
    fertile_window_end: date | None = None
    predicted_cycle_length: int | None = None
    avg_cycle_length: float | None = None
    std_cycle_length: float | None = None
    cycles_used: int = 0
    confidence: float = 0.0
    model_used: str = "calendar_only"
    current_phase: str | None = None
    current_cycle_day: int | None = None
    is_irregular: bool = False
    warnings: list[str] = field(default_factory=list)


class CycleTracker:
    """Predict menstrual cycles using calendar averaging and temperature data.

    Usage::

        tracker = CycleTracker()
        prediction = tracker.predict(
            cycles=past_cycles,
            current_cycle_start=date(2026, 2, 1),
            current_temps=temperatures,
        )
        print(prediction.predicted_period_start)
        print(prediction.current_phase)
    """

    def __init__(self, config: FusionConfig | None = None) -> None:
        self._config = config or get_fusion_config()
        self._temp_detector = TempOvulationDetector(self._config)

    @property
    def _mc_config(self):
        return self._config.menstrual

    def predict(
        self,
        cycles: list[CycleRecord],
        current_cycle_start: date | None = None,
        current_temps: list[DailyTemperature] | None = None,
        as_of_date: date | None = None,
    ) -> CyclePrediction:
        """Generate a cycle prediction from historical data.

        Args:
            cycles:               Historical cycle records (oldest first).
            current_cycle_start:  First day of the current (in-progress) cycle.
            current_temps:        Temperature readings for the current cycle.
            as_of_date:           Reference date (defaults to today).

        Returns:
            CyclePrediction with all available prediction fields populated.
        """
        mc = self._mc_config
        today = as_of_date or date.today()

        prediction = CyclePrediction()

        # Filter to complete cycles only (for length averaging)
        complete_cycles = [c for c in cycles if c.is_complete and c.cycle_length is not None]

        # Use last N cycles (configurable rolling window)
        n = mc.rolling_average_cycles
        recent = complete_cycles[-n:] if len(complete_cycles) >= 1 else []
        lengths = [c.cycle_length for c in recent if c.cycle_length is not None]

        prediction.cycles_used = len(lengths)

        if not lengths:
            # No historical data — can't predict
            if current_cycle_start:
                prediction.current_cycle_day = (today - current_cycle_start).days + 1
                prediction.current_phase = "unknown"
            prediction.confidence = 0.1
            prediction.warnings.append("No complete cycles available for prediction")
            return prediction

        # Compute statistics
        avg_length = statistics.mean(lengths)
        std_length = statistics.stdev(lengths) if len(lengths) > 1 else 0.0

        prediction.avg_cycle_length = round(avg_length, 1)
        prediction.std_cycle_length = round(std_length, 1)
        prediction.predicted_cycle_length = round(avg_length)

        # Flag irregular cycles
        prediction.is_irregular = std_length > 7.0

        # Flag abnormal lengths
        for length in lengths:
            if length < mc.min_cycle_days:
                prediction.warnings.append(
                    f"Short cycle detected: {length} days (below {mc.min_cycle_days} day minimum)"
                )
                break
            if length > mc.max_cycle_days:
                prediction.warnings.append(
                    f"Long cycle detected: {length} days (above {mc.max_cycle_days} day maximum)"
                )
                break

        # Anchor: use current_cycle_start if provided, else the last period start
        if current_cycle_start:
            anchor = current_cycle_start
        elif complete_cycles:
            anchor = complete_cycles[-1].period_start
        else:
            return prediction

        # Predict next period
        predicted_start = anchor + timedelta(days=round(avg_length))
        early = anchor + timedelta(days=round(avg_length - std_length))
        late = anchor + timedelta(days=round(avg_length + std_length))

        prediction.predicted_period_start = predicted_start
        prediction.predicted_period_start_early = early
        prediction.predicted_period_start_late = late

        # Ovulation prediction (typically 14 days before next period)
        luteal_length = 14  # Luteal phase is remarkably consistent
        predicted_ov = predicted_start - timedelta(days=luteal_length)
        prediction.predicted_ovulation_date = predicted_ov

        # Fertile window
        fertile_start = predicted_ov - timedelta(days=mc.fertile_window_days - 1)
        prediction.fertile_window_start = fertile_start
        prediction.fertile_window_end = predicted_ov

        # Current phase and cycle day
        if current_cycle_start:
            cycle_day = (today - current_cycle_start).days + 1
            prediction.current_cycle_day = max(1, cycle_day)

            # Temperature-assisted phase detection
            if current_temps and mc.prediction_model == "temperature_assisted":
                ovulation_result = self._temp_detector.detect(
                    current_temps, current_cycle_start
                )
                if ovulation_result.ovulation_detected and ovulation_result.estimated_ovulation_date:
                    # Update predictions with actual detected ovulation
                    actual_ov = ovulation_result.estimated_ovulation_date
                    prediction.predicted_ovulation_date = actual_ov
                    prediction.fertile_window_start = actual_ov - timedelta(
                        days=mc.fertile_window_days - 1
                    )
                    prediction.fertile_window_end = actual_ov
                    prediction.model_used = "temperature_assisted"

                    # Adjust next period prediction
                    prediction.predicted_period_start = actual_ov + timedelta(
                        days=luteal_length
                    )
                    prediction.confidence = min(0.9, 0.6 + ovulation_result.confidence * 0.3)
                else:
                    prediction.model_used = "calendar_only"
            else:
                prediction.model_used = "calendar_only"

            # Determine current phase
            if cycle_day <= 5:
                prediction.current_phase = "menstrual"
            elif prediction.predicted_ovulation_date:
                days_to_ov = (prediction.predicted_ovulation_date - today).days
                if days_to_ov > 1:
                    prediction.current_phase = "follicular"
                elif days_to_ov >= -1:
                    prediction.current_phase = "ovulation"
                else:
                    prediction.current_phase = "luteal"
            else:
                prediction.current_phase = "follicular" if cycle_day < 14 else "luteal"

        # Base confidence on number of cycles + regularity
        data_confidence = min(len(lengths) / mc.rolling_average_cycles, 1.0)
        regularity_confidence = max(0.2, 1.0 - (std_length / 14.0))
        prediction.confidence = round(
            data_confidence * 0.5 + regularity_confidence * 0.5,
            2,
        )

        return prediction

    def compute_cycle_length(
        self, period_start: date, next_period_start: date
    ) -> int:
        """Compute cycle length in days.

        Args:
            period_start:      First day of this cycle.
            next_period_start: First day of the next cycle.

        Returns:
            Cycle length in days.
        """
        return (next_period_start - period_start).days

    def classify_cycle(self, cycle_length: int) -> str:
        """Classify a cycle length as normal, short, or long.

        Args:
            cycle_length: Cycle length in days.

        Returns:
            'normal', 'short', or 'long'.
        """
        mc = self._mc_config
        if cycle_length < mc.min_cycle_days:
            return "short"
        if cycle_length > mc.max_cycle_days:
            return "long"
        return "normal"

    @staticmethod
    def cycle_day_from_start(period_start: date, query_date: date) -> int:
        """Return the cycle day number for a given date.

        Day 1 = first day of period.  Returns negative numbers for dates
        before the period start.

        Args:
            period_start: First day of the cycle.
            query_date:   Date to calculate for.

        Returns:
            Cycle day (1-indexed).
        """
        return (query_date - period_start).days + 1
