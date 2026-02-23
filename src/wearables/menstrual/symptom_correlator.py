"""Symptom correlation engine for menstrual cycle tracking.

Correlates logged symptoms with cycle phase and wearable metrics to
surface patterns like:
- "Your cramps are worst on days 1-2 when your HRV is also lowest"
- "Your sleep quality drops 15% in the luteal phase"
- "Your energy peaks around day 12-14 (follicular phase)"
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

logger = logging.getLogger("vitalis.wearables.menstrual.symptom_correlator")

# Valid symptom keys and their allowed values
SYMPTOM_SCHEMA: dict[str, list[str] | str] = {
    "flow": ["spotting", "light", "medium", "heavy"],
    "cramps": "scale_0_5",
    "mood": ["calm", "happy", "irritable", "anxious", "sad", "emotional"],
    "energy": "scale_1_5",
    "bloating": ["none", "mild", "moderate", "severe"],
    "headache": ["none", "mild", "moderate", "severe"],
    "breast_tenderness": ["none", "mild", "moderate", "severe"],
    "acne": ["none", "mild", "moderate", "severe"],
    "cravings": "scale_0_5",
    "libido": ["low", "normal", "high"],
}

# Phases in order
PHASES = ["menstrual", "follicular", "ovulation", "luteal"]

# Severity maps for ordinal symptoms
_SEVERITY_MAP = {"none": 0, "mild": 1, "moderate": 2, "severe": 3}
_FLOW_MAP = {"spotting": 0.5, "light": 1, "medium": 2, "heavy": 3}
_LIBIDO_MAP = {"low": 0, "normal": 1, "high": 2}


@dataclass
class SymptomLog:
    """A single day's symptom log.

    Attributes:
        date:       Calendar date of the log entry.
        cycle_day:  Day within the cycle (1-indexed).
        phase:      Cycle phase at time of logging.
        symptoms:   Dict of symptom_name → value.
        hrv_ms:     Fused HRV for this day (for correlation).
        rhr_bpm:    Fused resting HR (for correlation).
        sleep_minutes: Total sleep for this night.
    """

    date: date
    cycle_day: int
    phase: str
    symptoms: dict[str, str | int | float]
    hrv_ms: float | None = None
    rhr_bpm: int | None = None
    sleep_minutes: int | None = None


@dataclass
class SymptomInsight:
    """A single generated insight from symptom correlation analysis.

    Attributes:
        insight_id:   Unique identifier for this insight.
        category:     'phase_pattern', 'metric_correlation', 'cycle_day_pattern'.
        title:        Short insight title for display.
        body:         Full insight description.
        metric_a:     Primary metric or symptom.
        metric_b:     Secondary metric or phase.
        correlation:  Strength of correlation (0.0–1.0, or None).
        data_points:  Number of observations used.
        confidence:   Confidence in this insight.
    """

    insight_id: str
    category: str
    title: str
    body: str
    metric_a: str
    metric_b: str = ""
    correlation: float | None = None
    data_points: int = 0
    confidence: float = 0.0


@dataclass
class PhaseSymptomProfile:
    """Aggregated symptom and metric statistics for a single phase.

    Attributes:
        phase:         Phase name.
        avg_symptoms:  Average severity per symptom.
        avg_hrv:       Average HRV during this phase.
        avg_rhr:       Average RHR during this phase.
        avg_sleep:     Average sleep duration during this phase.
        sample_count:  Number of days in this phase across all cycles.
    """

    phase: str
    avg_symptoms: dict[str, float] = field(default_factory=dict)
    avg_hrv: float | None = None
    avg_rhr: float | None = None
    avg_sleep: float | None = None
    sample_count: int = 0


def _symptom_to_numeric(symptom_name: str, value: str | int | float) -> float | None:
    """Convert a symptom value to a comparable numeric score.

    Args:
        symptom_name: Name of the symptom.
        value:        Raw symptom value.

    Returns:
        Numeric score or None if not convertible.
    """
    if isinstance(value, (int, float)):
        return float(value)

    schema = SYMPTOM_SCHEMA.get(symptom_name)
    if schema == "scale_0_5" or schema == "scale_1_5":
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    str_val = str(value).lower()
    if symptom_name == "flow":
        return _FLOW_MAP.get(str_val)
    if symptom_name == "libido":
        return _LIBIDO_MAP.get(str_val)
    return _SEVERITY_MAP.get(str_val)


class SymptomCorrelator:
    """Correlate symptoms with cycle phase and wearable metrics.

    Requires a sufficient history of symptom logs across multiple cycles
    to surface reliable patterns.  Minimum: 2 complete cycles with daily logs.

    Usage::

        correlator = SymptomCorrelator()
        insights = correlator.generate_insights(symptom_logs)
        for insight in insights:
            print(insight.title, insight.body)
    """

    MIN_DATA_POINTS = 7  # minimum days per phase for reliable averages

    def generate_insights(
        self, logs: list[SymptomLog]
    ) -> list[SymptomInsight]:
        """Generate all available insights from symptom logs.

        Args:
            logs: All symptom log entries across cycles.

        Returns:
            List of SymptomInsight ordered by confidence (highest first).
        """
        if len(logs) < self.MIN_DATA_POINTS:
            logger.info(
                "Insufficient symptom data: %d logs (need %d)",
                len(logs), self.MIN_DATA_POINTS,
            )
            return []

        insights: list[SymptomInsight] = []

        # 1. Phase-based symptom patterns
        phase_profiles = self._build_phase_profiles(logs)
        insights.extend(self._phase_symptom_insights(phase_profiles))

        # 2. Symptom ↔ HRV correlations
        insights.extend(self._symptom_metric_correlations(logs, "hrv_ms", "HRV"))

        # 3. Sleep correlations across phases
        insights.extend(self._phase_sleep_insights(phase_profiles))

        # Sort by confidence
        insights.sort(key=lambda i: i.confidence, reverse=True)
        return insights

    def _build_phase_profiles(
        self, logs: list[SymptomLog]
    ) -> dict[str, PhaseSymptomProfile]:
        """Build per-phase aggregated statistics.

        Args:
            logs: All symptom logs.

        Returns:
            Dict of phase_name → PhaseSymptomProfile.
        """
        profiles: dict[str, PhaseSymptomProfile] = {
            phase: PhaseSymptomProfile(phase=phase) for phase in PHASES
        }

        phase_logs: dict[str, list[SymptomLog]] = {p: [] for p in PHASES}
        for log in logs:
            if log.phase in phase_logs:
                phase_logs[log.phase].append(log)

        for phase, phase_log_list in phase_logs.items():
            if not phase_log_list:
                continue

            profile = profiles[phase]
            profile.sample_count = len(phase_log_list)

            # Average each symptom
            symptom_values: dict[str, list[float]] = {}
            for log in phase_log_list:
                for symptom_name, value in log.symptoms.items():
                    num = _symptom_to_numeric(symptom_name, value)
                    if num is not None:
                        if symptom_name not in symptom_values:
                            symptom_values[symptom_name] = []
                        symptom_values[symptom_name].append(num)

            for symptom_name, values in symptom_values.items():
                profile.avg_symptoms[symptom_name] = round(
                    statistics.mean(values), 2
                )

            # Average wearable metrics
            hrv_vals = [l.hrv_ms for l in phase_log_list if l.hrv_ms is not None]
            rhr_vals = [l.rhr_bpm for l in phase_log_list if l.rhr_bpm is not None]
            sleep_vals = [l.sleep_minutes for l in phase_log_list if l.sleep_minutes is not None]

            profile.avg_hrv = round(statistics.mean(hrv_vals), 1) if hrv_vals else None
            profile.avg_rhr = round(statistics.mean(rhr_vals), 1) if rhr_vals else None
            profile.avg_sleep = round(statistics.mean(sleep_vals), 0) if sleep_vals else None

        return profiles

    def _phase_symptom_insights(
        self, profiles: dict[str, PhaseSymptomProfile]
    ) -> list[SymptomInsight]:
        """Surface the strongest per-symptom patterns across phases.

        Args:
            profiles: Phase → profile mapping.

        Returns:
            List of insights about phase-based symptom patterns.
        """
        insights = []

        # Collect all symptoms that have data
        all_symptoms: set[str] = set()
        for p in profiles.values():
            all_symptoms.update(p.avg_symptoms.keys())

        for symptom in all_symptoms:
            phase_scores = {
                phase: p.avg_symptoms[symptom]
                for phase, p in profiles.items()
                if symptom in p.avg_symptoms and p.sample_count >= 3
            }

            if len(phase_scores) < 2:
                continue

            # Find peak phase
            peak_phase = max(phase_scores, key=lambda k: phase_scores[k])
            low_phase = min(phase_scores, key=lambda k: phase_scores[k])
            peak_val = phase_scores[peak_phase]
            low_val = phase_scores[low_phase]

            if peak_val <= 0 or (peak_val - low_val) < 0.3:
                continue  # No meaningful difference

            pct_higher = round(((peak_val - low_val) / max(low_val, 0.1)) * 100)
            confidence = min(
                0.5 + min(sum(p.sample_count for p in profiles.values()) / 60, 0.4),
                0.9,
            )

            insights.append(
                SymptomInsight(
                    insight_id=f"phase_{symptom}",
                    category="phase_pattern",
                    title=f"{symptom.replace('_', ' ').title()} peaks in {peak_phase} phase",
                    body=(
                        f"Your {symptom.replace('_', ' ')} is highest during the "
                        f"{peak_phase} phase ({pct_higher}% higher than {low_phase} phase). "
                        f"This pattern was detected over {sum(p.sample_count for p in profiles.values())} logged days."
                    ),
                    metric_a=symptom,
                    metric_b=peak_phase,
                    data_points=sum(p.sample_count for p in profiles.values()),
                    confidence=confidence,
                )
            )

        return insights

    def _symptom_metric_correlations(
        self,
        logs: list[SymptomLog],
        metric_attr: str,
        metric_display: str,
    ) -> list[SymptomInsight]:
        """Correlate each symptom with a wearable metric using Pearson r.

        Args:
            logs:            All symptom logs.
            metric_attr:     Attribute name on SymptomLog (e.g. 'hrv_ms').
            metric_display:  Human-readable metric name.

        Returns:
            List of correlation insights.
        """
        insights = []

        logs_with_metric = [
            l for l in logs if getattr(l, metric_attr) is not None
        ]
        if len(logs_with_metric) < 10:
            return []

        metric_vals = [getattr(l, metric_attr) for l in logs_with_metric]

        all_symptoms: set[str] = set()
        for l in logs_with_metric:
            all_symptoms.update(l.symptoms.keys())

        for symptom in all_symptoms:
            symptom_vals = []
            paired_metric = []

            for log in logs_with_metric:
                raw_val = log.symptoms.get(symptom)
                if raw_val is None:
                    continue
                num = _symptom_to_numeric(symptom, raw_val)
                if num is not None:
                    symptom_vals.append(num)
                    paired_metric.append(getattr(log, metric_attr))

            if len(symptom_vals) < 10:
                continue

            # Pearson correlation
            r = _pearson_r(symptom_vals, paired_metric)
            if r is None or abs(r) < 0.25:
                continue

            direction = "negatively" if r < 0 else "positively"
            pct = round(abs(r) * 100)
            confidence = min(abs(r) * 0.8 + len(symptom_vals) / 100 * 0.2, 0.9)

            insights.append(
                SymptomInsight(
                    insight_id=f"corr_{symptom}_{metric_attr}",
                    category="metric_correlation",
                    title=f"{symptom.replace('_', ' ').title()} correlates with {metric_display}",
                    body=(
                        f"Your {symptom.replace('_', ' ')} is {direction} correlated with "
                        f"your {metric_display} (r={r:.2f}). "
                        f"On days with {'low' if r < 0 else 'high'} {metric_display}, "
                        f"your {symptom.replace('_', ' ')} tends to be "
                        f"{'higher' if r < 0 else 'higher'} as well."
                    ),
                    metric_a=symptom,
                    metric_b=metric_attr,
                    correlation=round(r, 3),
                    data_points=len(symptom_vals),
                    confidence=round(confidence, 2),
                )
            )

        return insights

    def _phase_sleep_insights(
        self, profiles: dict[str, PhaseSymptomProfile]
    ) -> list[SymptomInsight]:
        """Surface sleep quality differences across cycle phases.

        Args:
            profiles: Phase → profile mapping.

        Returns:
            List of sleep-phase insights.
        """
        insights = []

        sleep_by_phase = {
            phase: p.avg_sleep
            for phase, p in profiles.items()
            if p.avg_sleep is not None and p.sample_count >= 3
        }

        if len(sleep_by_phase) < 2:
            return []

        best_phase = max(sleep_by_phase, key=lambda k: sleep_by_phase[k])
        worst_phase = min(sleep_by_phase, key=lambda k: sleep_by_phase[k])

        best_hours = round((sleep_by_phase[best_phase] or 0) / 60, 1)
        worst_hours = round((sleep_by_phase[worst_phase] or 0) / 60, 1)
        diff_min = round(
            (sleep_by_phase[best_phase] or 0) - (sleep_by_phase[worst_phase] or 0)
        )

        if diff_min < 15:
            return []

        insights.append(
            SymptomInsight(
                insight_id="sleep_phase_pattern",
                category="phase_pattern",
                title=f"Sleep quality varies by cycle phase",
                body=(
                    f"You sleep best in the {best_phase} phase ({best_hours}h avg) "
                    f"and least in the {worst_phase} phase ({worst_hours}h avg). "
                    f"That's a {diff_min}-minute difference. "
                    f"Consider prioritizing sleep hygiene during {worst_phase} phase."
                ),
                metric_a="sleep_minutes",
                metric_b="cycle_phase",
                data_points=sum(p.sample_count for p in profiles.values()),
                confidence=0.7,
            )
        )

        return insights


def _pearson_r(x: list[float], y: list[float]) -> float | None:
    """Compute Pearson correlation coefficient between two lists.

    Args:
        x: First variable.
        y: Second variable.

    Returns:
        Pearson r (-1.0 to 1.0) or None if computation fails.
    """
    if len(x) != len(y) or len(x) < 3:
        return None

    n = len(x)
    mean_x = sum(x) / n
    mean_y = sum(y) / n

    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y)) / n
    std_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x) / n)
    std_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y) / n)

    if std_x == 0 or std_y == 0:
        return None

    return round(cov / (std_x * std_y), 4)


import math
