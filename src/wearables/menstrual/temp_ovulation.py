"""Temperature-based ovulation detection for Vitalis.

Uses sustained temperature shifts to detect ovulation retroactively and
predict future fertile windows.  Works best with Oura Ring finger temperature
data, which provides a highly accurate proxy for basal body temperature (BBT).

Algorithm (based on Fertility Awareness Method + clinical BBT guidelines):
1. Compute a pre-shift baseline: mean of temperatures from days 1–5 of the cycle
   (after menstruation ends)
2. Detect a thermal shift: 3+ consecutive days where temperature exceeds the
   baseline by ≥ 0.2°C (configurable in fusion_config.yaml)
3. The day before the first elevated day is marked as the ovulation day
4. Fertile window: 5 days before ovulation day + ovulation day

Privacy: All temperature data is handled with the same elevated privacy controls
as other menstrual data.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta

from src.wearables.config_loader import FusionConfig, get_fusion_config

logger = logging.getLogger("vitalis.wearables.menstrual.temp_ovulation")


@dataclass
class DailyTemperature:
    """Temperature reading for a single day.

    Attributes:
        date:           Calendar date.
        temp_c:         Skin/wrist temperature deviation from baseline in °C.
                        For Oura, this is the ring's deviation metric.
                        For Apple Watch (Series 8+), this is the wrist temp.
        source:         Device source ('oura', 'apple_watch', 'whoop').
        raw_value:      Raw device value before any normalization.
    """

    date: date
    temp_c: float
    source: str
    raw_value: float = 0.0


@dataclass
class OvulationDetectionResult:
    """Result of temperature-based ovulation detection.

    Attributes:
        ovulation_detected:  Whether a thermal shift was confirmed.
        estimated_ovulation_date: Best estimate of when ovulation occurred.
        shift_start_date:    First day temperature rose above threshold.
        pre_shift_baseline:  Mean temperature during follicular phase.
        post_shift_mean:     Mean temperature during luteal phase (after shift).
        temp_shift_c:        Magnitude of the temperature shift.
        confirmation_days:   How many consecutive elevated days were observed.
        fertile_window_start: Estimated start of fertile window.
        fertile_window_end:  Estimated end of fertile window.
        confidence:          0.0–1.0 confidence in the detection.
        notes:               Human-readable explanation.
    """

    ovulation_detected: bool
    estimated_ovulation_date: date | None = None
    shift_start_date: date | None = None
    pre_shift_baseline: float | None = None
    post_shift_mean: float | None = None
    temp_shift_c: float | None = None
    confirmation_days: int = 0
    fertile_window_start: date | None = None
    fertile_window_end: date | None = None
    confidence: float = 0.0
    notes: str = ""


class TempOvulationDetector:
    """Detect ovulation from temperature deviation data.

    Uses the biphasic temperature pattern characteristic of ovulatory cycles:
    - Follicular phase: lower, relatively stable temperatures
    - Luteal phase: temperatures rise 0.2–0.5°C and stay elevated until menstruation

    Usage::

        detector = TempOvulationDetector()
        temps = [DailyTemperature(date=d, temp_c=t, source='oura') for d, t in data]
        result = detector.detect(temps)
        if result.ovulation_detected:
            print(f"Ovulation: {result.estimated_ovulation_date}")
    """

    def __init__(self, config: FusionConfig | None = None) -> None:
        self._config = config or get_fusion_config()

    @property
    def _mc_config(self):
        return self._config.menstrual

    def detect(
        self,
        temperatures: list[DailyTemperature],
        cycle_start_date: date | None = None,
    ) -> OvulationDetectionResult:
        """Detect ovulation from a sequence of daily temperature readings.

        Args:
            temperatures:     Daily temperature readings in chronological order.
            cycle_start_date: First day of the menstrual cycle (period start).
                              Used to compute pre-shift baseline.  If None,
                              uses the first half of the temperature sequence.

        Returns:
            OvulationDetectionResult with detection details.
        """
        mc = self._mc_config
        threshold = mc.temp_shift_threshold_c
        required_days = mc.ovulation_confirmation_days

        if len(temperatures) < required_days + 3:
            return OvulationDetectionResult(
                ovulation_detected=False,
                notes=f"Insufficient data: {len(temperatures)} days (need {required_days + 3}+)",
            )

        # Sort by date
        temps = sorted(temperatures, key=lambda t: t.date)

        # Compute pre-shift baseline
        # Use the first half of readings, or up to day 10 of cycle, whichever is smaller
        if cycle_start_date:
            pre_shift_temps = [
                t for t in temps
                if (t.date - cycle_start_date).days < 10
            ]
        else:
            pre_shift_temps = temps[:max(5, len(temps) // 2)]

        if len(pre_shift_temps) < 3:
            return OvulationDetectionResult(
                ovulation_detected=False,
                notes="Insufficient pre-shift temperature data for baseline",
            )

        baseline = statistics.mean(t.temp_c for t in pre_shift_temps)
        baseline_std = statistics.stdev(t.temp_c for t in pre_shift_temps) if len(pre_shift_temps) > 1 else 0.1

        # More robust threshold: max of config threshold or baseline + 2 std
        effective_threshold = max(threshold, baseline_std * 2)
        shift_threshold = baseline + effective_threshold

        logger.debug(
            "Temp detection: baseline=%.3f°C, std=%.3f, threshold=%.3f°C",
            baseline, baseline_std, shift_threshold,
        )

        # Scan for sustained temperature elevation
        # Only look at temps after the pre-shift period
        post_baseline_temps = [t for t in temps if t not in pre_shift_temps]

        shift_start: date | None = None
        consecutive_elevated = 0
        first_elevated_idx = -1

        for i, temp_reading in enumerate(post_baseline_temps):
            if temp_reading.temp_c >= shift_threshold:
                if consecutive_elevated == 0:
                    first_elevated_idx = i
                consecutive_elevated += 1

                if consecutive_elevated >= required_days:
                    shift_start = post_baseline_temps[first_elevated_idx].date
                    break
            else:
                # Reset on any non-elevated day
                consecutive_elevated = 0
                first_elevated_idx = -1

        if shift_start is None:
            return OvulationDetectionResult(
                ovulation_detected=False,
                pre_shift_baseline=round(baseline, 3),
                notes=(
                    f"No sustained temperature shift detected "
                    f"(threshold: {shift_threshold:.3f}°C, "
                    f"baseline: {baseline:.3f}°C)"
                ),
            )

        # Ovulation occurred the day before the shift started
        estimated_ovulation = shift_start - timedelta(days=1)

        # Compute post-shift mean
        post_shift_temps = [
            t for t in post_baseline_temps if t.date >= shift_start
        ]
        post_shift_mean = (
            statistics.mean(t.temp_c for t in post_shift_temps)
            if post_shift_temps
            else None
        )
        temp_shift = (post_shift_mean - baseline) if post_shift_mean is not None else None

        # Fertile window: 5 days before ovulation through ovulation day
        mc_cfg = self._mc_config
        fertile_start = estimated_ovulation - timedelta(
            days=mc_cfg.fertile_window_days - 1
        )
        fertile_end = estimated_ovulation

        # Confidence based on number of confirmed days and shift magnitude
        magnitude_score = min((temp_shift or 0) / 0.5, 1.0) if temp_shift else 0.5
        duration_score = min(consecutive_elevated / (required_days * 2), 1.0)
        confidence = round((magnitude_score * 0.6) + (duration_score * 0.4), 2)

        logger.info(
            "Ovulation detected: ~%s (shift on %s, +%.3f°C, confidence=%.2f)",
            estimated_ovulation, shift_start, temp_shift or 0, confidence,
        )

        return OvulationDetectionResult(
            ovulation_detected=True,
            estimated_ovulation_date=estimated_ovulation,
            shift_start_date=shift_start,
            pre_shift_baseline=round(baseline, 3),
            post_shift_mean=round(post_shift_mean, 3) if post_shift_mean else None,
            temp_shift_c=round(temp_shift, 3) if temp_shift else None,
            confirmation_days=consecutive_elevated,
            fertile_window_start=fertile_start,
            fertile_window_end=fertile_end,
            confidence=confidence,
            notes=(
                f"Temperature shifted +{temp_shift:.2f}°C above baseline "
                f"(baseline: {baseline:.2f}°C, "
                f"confirmed over {consecutive_elevated} days)"
            ),
        )

    def get_current_phase_temp(
        self,
        temperatures: list[DailyTemperature],
        cycle_start_date: date,
        current_date: date | None = None,
    ) -> tuple[str, float | None]:
        """Determine the current cycle phase from temperature data.

        Args:
            temperatures:     Recent temperature readings.
            cycle_start_date: Start of the current cycle.
            current_date:     Date to evaluate (defaults to today).

        Returns:
            Tuple of (phase_name, current_temp_deviation).
            phase_name: 'menstrual', 'follicular', 'ovulation', 'luteal', 'unknown'
        """
        today = current_date or date.today()
        cycle_day = (today - cycle_start_date).days + 1

        # Get today's temperature
        today_temps = [t for t in temperatures if t.date == today]
        current_temp = today_temps[0].temp_c if today_temps else None

        # Attempt detection to see if we're post-ovulation
        detection = self.detect(temperatures, cycle_start_date)

        if cycle_day <= 5:
            return "menstrual", current_temp
        elif detection.ovulation_detected and detection.estimated_ovulation_date:
            days_post_ov = (today - detection.estimated_ovulation_date).days
            if days_post_ov < 0:
                return "follicular", current_temp
            elif days_post_ov == 0:
                return "ovulation", current_temp
            else:
                return "luteal", current_temp
        else:
            # No detection yet — estimate based on average cycle
            if cycle_day <= 13:
                return "follicular", current_temp
            elif cycle_day <= 15:
                return "ovulation", current_temp
            else:
                return "luteal", current_temp

    @staticmethod
    def compute_follicular_luteal_averages(
        temperatures: list[DailyTemperature],
        ovulation_date: date,
    ) -> tuple[float | None, float | None]:
        """Compute average temperatures for follicular and luteal phases.

        Used to populate menstrual_cycles.avg_bbt_follicular and avg_bbt_luteal.

        Args:
            temperatures:    All daily readings for the cycle.
            ovulation_date:  Detected or estimated ovulation date.

        Returns:
            Tuple of (follicular_avg, luteal_avg) in °C.
        """
        follicular_temps = [
            t.temp_c for t in temperatures if t.date < ovulation_date
        ]
        luteal_temps = [
            t.temp_c for t in temperatures if t.date >= ovulation_date
        ]

        follicular_avg = (
            round(statistics.mean(follicular_temps), 3) if len(follicular_temps) >= 3 else None
        )
        luteal_avg = (
            round(statistics.mean(luteal_temps), 3) if len(luteal_temps) >= 3 else None
        )

        return follicular_avg, luteal_avg
