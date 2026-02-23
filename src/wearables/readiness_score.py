"""Vitalis proprietary readiness score calculator.

Computes a 0–100 readiness score from fused wearable metrics by comparing
each component to the user's personal rolling baseline.  This is NOT a copy
of any device's proprietary score.

Score formula (from fusion_config.yaml):
    - HRV vs 30-day baseline        (weight: 0.30)
    - Resting HR vs 30-day baseline (weight: 0.20)
    - Sleep quality composite       (weight: 0.25)
    - Sleep consistency             (weight: 0.10)
    - Recovery time                 (weight: 0.15)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Sequence

from src.wearables.base import NormalizedDaily, NormalizedSleep
from src.wearables.config_loader import FusionConfig, ReadinessConfig, get_fusion_config

logger = logging.getLogger("vitalis.wearables.readiness")

# Target sleep duration for quality scoring (minutes)
_OPTIMAL_SLEEP_MINUTES = 450  # 7.5 hours
_MIN_SLEEP_MINUTES = 300      # 5 hours — below this = 0 contribution


@dataclass
class ReadinessComponentScore:
    """Score for a single readiness component.

    Attributes:
        name:        Component identifier (matches config key).
        raw_score:   Raw component score 0.0–1.0 before weighting.
        weighted:    raw_score * weight.
        weight:      Configured weight for this component.
        available:   False if baseline data was insufficient.
        explanation: Human-readable explanation of this component's value.
    """

    name: str
    raw_score: float
    weight: float
    available: bool = True
    explanation: str = ""

    @property
    def weighted(self) -> float:
        return self.raw_score * self.weight if self.available else 0.0


@dataclass
class ReadinessScore:
    """The complete Vitalis readiness score for one user+date.

    Attributes:
        user_id:    Internal Vitalis user UUID string.
        date:       Date of the score.
        score:      Final 0–100 score.
        band:       'thriving', 'watch', or 'concern'.
        components: Per-component breakdown.
        available:  False if there was insufficient data to compute a score.
        computed_at: UTC timestamp.
    """

    user_id: str
    date: date
    score: int
    band: str
    components: list[ReadinessComponentScore] = field(default_factory=list)
    available: bool = True
    computed_at: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Component scorers
# ---------------------------------------------------------------------------


def _sigmoid_score(value: float, mean: float, std: float, higher_is_better: bool = True) -> float:
    """Convert a metric value to a 0.0–1.0 score using a sigmoid function.

    A value equal to the mean returns 0.5.  Values 2 std deviations above
    the mean return ~0.88 (higher_is_better=True) or ~0.12.

    Args:
        value:            The current measurement.
        mean:             Personal baseline mean.
        std:              Personal baseline standard deviation.
        higher_is_better: True if higher values = better readiness (e.g. HRV).
                          False for RHR (lower is better).

    Returns:
        Score between 0.0 and 1.0.
    """
    if std <= 0:
        # No variance in baseline — return 0.5 unless value == mean
        return 0.5 if value == mean else (1.0 if (value > mean) == higher_is_better else 0.0)

    z = (value - mean) / std
    if not higher_is_better:
        z = -z

    # Sigmoid: 1 / (1 + e^(-z * 1.5)) — steepness factor 1.5 feels right
    score = 1.0 / (1.0 + math.exp(-z * 1.5))
    return round(min(max(score, 0.0), 1.0), 4)


def _score_hrv_vs_baseline(
    current_hrv: float | None,
    baseline_values: list[float],
) -> ReadinessComponentScore:
    """Score HRV compared to personal 30-day rolling average.

    Higher HRV = better recovery = higher score.

    Args:
        current_hrv:      Today's fused HRV RMSSD (ms).
        baseline_values:  Last 30 days of HRV readings (excluding today).

    Returns:
        ReadinessComponentScore with raw_score 0.0–1.0.
    """
    component = "hrv_vs_baseline"
    weight = 0.30  # default; overridden by config at call site

    if current_hrv is None:
        return ReadinessComponentScore(
            name=component, raw_score=0.5, weight=weight,
            available=False, explanation="No HRV data available for today",
        )

    if len(baseline_values) < 7:
        return ReadinessComponentScore(
            name=component, raw_score=0.5, weight=weight,
            available=False,
            explanation=f"Insufficient HRV baseline ({len(baseline_values)} days, need 7+)",
        )

    mean = sum(baseline_values) / len(baseline_values)
    variance = sum((v - mean) ** 2 for v in baseline_values) / len(baseline_values)
    std = math.sqrt(variance)

    raw = _sigmoid_score(current_hrv, mean, std, higher_is_better=True)
    pct_vs_baseline = ((current_hrv - mean) / mean * 100) if mean > 0 else 0.0

    return ReadinessComponentScore(
        name=component,
        raw_score=raw,
        weight=weight,
        available=True,
        explanation=(
            f"HRV {current_hrv:.1f}ms vs {mean:.1f}ms baseline "
            f"({pct_vs_baseline:+.1f}%)"
        ),
    )


def _score_rhr_vs_baseline(
    current_rhr: float | None,
    baseline_values: list[float],
) -> ReadinessComponentScore:
    """Score resting HR compared to personal 30-day rolling average.

    Lower RHR = better recovery = higher score.

    Args:
        current_rhr:      Today's fused resting heart rate (bpm).
        baseline_values:  Last 30 days of RHR readings.

    Returns:
        ReadinessComponentScore.
    """
    component = "resting_hr_vs_baseline"
    weight = 0.20

    if current_rhr is None:
        return ReadinessComponentScore(
            name=component, raw_score=0.5, weight=weight,
            available=False, explanation="No resting HR data for today",
        )

    if len(baseline_values) < 7:
        return ReadinessComponentScore(
            name=component, raw_score=0.5, weight=weight,
            available=False,
            explanation=f"Insufficient RHR baseline ({len(baseline_values)} days)",
        )

    mean = sum(baseline_values) / len(baseline_values)
    variance = sum((v - mean) ** 2 for v in baseline_values) / len(baseline_values)
    std = math.sqrt(variance)

    raw = _sigmoid_score(current_rhr, mean, std, higher_is_better=False)
    diff = current_rhr - mean

    return ReadinessComponentScore(
        name=component,
        raw_score=raw,
        weight=weight,
        available=True,
        explanation=(
            f"RHR {current_rhr:.0f}bpm vs {mean:.0f}bpm baseline ({diff:+.1f}bpm)"
        ),
    )


def _score_sleep_quality(
    sleep: NormalizedSleep | None,
) -> ReadinessComponentScore:
    """Score sleep quality using a composite of duration, deep%, and efficiency.

    Composite formula:
        - Duration contribution (50%): linearly scaled vs optimal 7.5h
        - Deep sleep contribution (30%): target ≥ 20% of total sleep
        - Efficiency contribution (20%): target ≥ 85%

    Args:
        sleep: Fused sleep record for last night.

    Returns:
        ReadinessComponentScore.
    """
    component = "sleep_quality"
    weight = 0.25

    if sleep is None or sleep.total_sleep_minutes is None:
        return ReadinessComponentScore(
            name=component, raw_score=0.5, weight=weight,
            available=False, explanation="No sleep data for last night",
        )

    total = sleep.total_sleep_minutes

    # Duration score (0–1): 0 at ≤300min, 1.0 at 450min+
    dur_score = min(max((total - _MIN_SLEEP_MINUTES) / (_OPTIMAL_SLEEP_MINUTES - _MIN_SLEEP_MINUTES), 0.0), 1.0)

    # Deep sleep score
    deep_score = 0.5  # neutral if no data
    if sleep.deep_minutes is not None and total > 0:
        deep_pct = sleep.deep_minutes / total
        deep_score = min(deep_pct / 0.20, 1.0)  # target 20%

    # Efficiency score
    eff_score = 0.5
    if sleep.sleep_efficiency_pct is not None:
        eff = sleep.sleep_efficiency_pct
        eff_score = min(max((eff - 70.0) / 30.0, 0.0), 1.0)  # 70%→0, 100%→1

    composite = (dur_score * 0.50) + (deep_score * 0.30) + (eff_score * 0.20)
    hours = total / 60.0

    return ReadinessComponentScore(
        name=component,
        raw_score=round(composite, 4),
        weight=weight,
        available=True,
        explanation=(
            f"{hours:.1f}h sleep, "
            f"{sleep.deep_minutes or 0}min deep, "
            f"{sleep.sleep_efficiency_pct or 'n/a'}% efficiency"
        ),
    )


def _score_sleep_consistency(
    recent_sleeps: Sequence[NormalizedSleep],
) -> ReadinessComponentScore:
    """Score sleep schedule consistency over the last 7 days.

    Measures variance in sleep start times.  Lower variance = higher score.
    Target: bedtime varies by ≤ 30 minutes on average.

    Args:
        recent_sleeps: Last 7 days of NormalizedSleep records (excluding today).

    Returns:
        ReadinessComponentScore.
    """
    component = "sleep_consistency"
    weight = 0.10

    valid_starts = [
        s.sleep_start for s in recent_sleeps
        if s.sleep_start is not None
    ]

    if len(valid_starts) < 3:
        return ReadinessComponentScore(
            name=component, raw_score=0.5, weight=weight,
            available=False,
            explanation=f"Insufficient sleep history ({len(valid_starts)} nights, need 3+)",
        )

    # Convert to minutes since midnight for variance calculation
    minutes = [t.hour * 60 + t.minute for t in valid_starts]
    mean_min = sum(minutes) / len(minutes)
    variance = sum((m - mean_min) ** 2 for m in minutes) / len(minutes)
    std_min = math.sqrt(variance)

    # Score: 0 std = 1.0, 60min std = 0.0
    raw = max(1.0 - (std_min / 60.0), 0.0)

    return ReadinessComponentScore(
        name=component,
        raw_score=round(raw, 4),
        weight=weight,
        available=True,
        explanation=f"Sleep time variability: ±{std_min:.0f}min over {len(valid_starts)} nights",
    )


def _score_recovery_time(
    days_since_hard_workout: int | None,
) -> ReadinessComponentScore:
    """Score based on time since last high-intensity workout.

    Score ramps from 0.3 (0 days) to 1.0 (3+ days rest).

    Args:
        days_since_hard_workout: Days since last intense session (None if no data).

    Returns:
        ReadinessComponentScore.
    """
    component = "recovery_time"
    weight = 0.15

    if days_since_hard_workout is None:
        return ReadinessComponentScore(
            name=component, raw_score=0.7, weight=weight,
            available=False,
            explanation="No workout history — assuming adequate recovery",
        )

    d = min(days_since_hard_workout, 4)
    # 0 days = 0.3, 1 = 0.5, 2 = 0.75, 3+ = 1.0
    scores = {0: 0.3, 1: 0.5, 2: 0.75, 3: 0.9, 4: 1.0}
    raw = scores.get(d, 1.0)

    explanation = (
        f"{days_since_hard_workout} day(s) since last intense workout"
        if days_since_hard_workout > 0
        else "Intense workout today"
    )

    return ReadinessComponentScore(
        name=component,
        raw_score=raw,
        weight=weight,
        available=True,
        explanation=explanation,
    )


# ---------------------------------------------------------------------------
# Main calculator
# ---------------------------------------------------------------------------


class ReadinessCalculator:
    """Compute the Vitalis readiness score from fused metrics.

    Usage::

        calc = ReadinessCalculator()
        score = calc.compute(
            user_id="...",
            target_date=date.today(),
            today_daily=fused_daily,
            today_sleep=fused_sleep,
            hrv_baseline=[52.1, 48.3, ...],  # last 30 days
            rhr_baseline=[54, 55, ...],
            recent_sleeps=[...],             # last 7 nights
            days_since_hard_workout=2,
        )
        print(score.score, score.band)
    """

    def __init__(self, config: FusionConfig | None = None) -> None:
        self._config = config or get_fusion_config()

    @property
    def _rs_config(self) -> ReadinessConfig:
        return self._config.readiness

    def compute(
        self,
        user_id: str,
        target_date: date,
        today_daily: NormalizedDaily | None,
        today_sleep: NormalizedSleep | None,
        hrv_baseline: list[float] | None = None,
        rhr_baseline: list[float] | None = None,
        recent_sleeps: list[NormalizedSleep] | None = None,
        days_since_hard_workout: int | None = None,
    ) -> ReadinessScore:
        """Compute the Vitalis readiness score.

        Args:
            user_id:                Internal user UUID string.
            target_date:            Date to compute the score for.
            today_daily:            Fused NormalizedDaily for target_date.
            today_sleep:            Fused NormalizedSleep for last night.
            hrv_baseline:           HRV readings for the past 30 days (excluding today).
            rhr_baseline:           RHR readings for the past 30 days (excluding today).
            recent_sleeps:          NormalizedSleep records for last 7 nights.
            days_since_hard_workout: Days since last high-intensity workout.

        Returns:
            ReadinessScore with 0–100 score and component breakdown.
        """
        rs_cfg = self._rs_config

        if not rs_cfg.enabled:
            return ReadinessScore(
                user_id=user_id, date=target_date, score=0,
                band="concern", available=False,
            )

        # Extract today's metrics
        today_hrv = today_daily.hrv_rmssd_ms if today_daily else None
        today_rhr = today_daily.resting_hr_bpm if today_daily else None

        # Look up component weights from config
        weight_map = {c.name: c.weight for c in rs_cfg.components}

        # Score each component
        hrv_component = _score_hrv_vs_baseline(
            today_hrv, hrv_baseline or []
        )
        hrv_component.weight = weight_map.get("hrv_vs_baseline", hrv_component.weight)

        rhr_component = _score_rhr_vs_baseline(
            float(today_rhr) if today_rhr is not None else None,
            [float(v) for v in (rhr_baseline or [])],
        )
        rhr_component.weight = weight_map.get("resting_hr_vs_baseline", rhr_component.weight)

        sleep_q_component = _score_sleep_quality(today_sleep)
        sleep_q_component.weight = weight_map.get("sleep_quality", sleep_q_component.weight)

        sleep_c_component = _score_sleep_consistency(recent_sleeps or [])
        sleep_c_component.weight = weight_map.get("sleep_consistency", sleep_c_component.weight)

        recovery_component = _score_recovery_time(days_since_hard_workout)
        recovery_component.weight = weight_map.get("recovery_time", recovery_component.weight)

        components = [
            hrv_component,
            rhr_component,
            sleep_q_component,
            sleep_c_component,
            recovery_component,
        ]

        # Compute final score, re-normalizing weights for missing components
        available_components = [c for c in components if c.available]
        if not available_components:
            return ReadinessScore(
                user_id=user_id, date=target_date, score=50,
                band="watch", components=components, available=False,
            )

        available_weight_sum = sum(c.weight for c in available_components)
        if available_weight_sum <= 0:
            available_weight_sum = 1.0

        raw_score = sum(
            c.weighted / available_weight_sum * (c.weight / available_weight_sum)
            for c in available_components
        )

        # Simpler and correct: sum weighted scores, re-normalize by available weight
        raw_score = sum(
            c.raw_score * (c.weight / available_weight_sum)
            for c in available_components
        )

        final_score = int(round(raw_score * 100))
        final_score = max(0, min(100, final_score))

        # Determine band
        if final_score >= rs_cfg.thriving_threshold:
            band = "thriving"
        elif final_score >= rs_cfg.watch_threshold:
            band = "watch"
        else:
            band = "concern"

        logger.debug(
            "Readiness score for %s on %s: %d (%s) — "
            "HRV=%.2f RHR=%.2f SleepQ=%.2f SleepC=%.2f Rec=%.2f",
            user_id, target_date, final_score, band,
            hrv_component.raw_score, rhr_component.raw_score,
            sleep_q_component.raw_score, sleep_c_component.raw_score,
            recovery_component.raw_score,
        )

        return ReadinessScore(
            user_id=user_id,
            date=target_date,
            score=final_score,
            band=band,
            components=components,
            available=True,
        )
