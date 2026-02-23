"""Core Wearable Data Fusion Engine.

For a given user + date, gathers all raw_device_data readings, applies
weighted averaging with conflict detection, and writes canonical fused
records to wearable_daily / wearable_sleep.

All fusion parameters (weights, tolerances) are read from fusion_config.yaml
via the config_loader module — no hardcoded values here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from uuid import UUID

from src.wearables.base import NormalizedDaily, NormalizedSleep
from src.wearables.config_loader import FusionConfig, get_fusion_config
from src.wearables.sleep_matcher import SleepMatchGroup, SleepMatcher

logger = logging.getLogger("vitalis.wearables.fusion")


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class MetricFusionResult:
    """Result of fusing a single metric across multiple device sources.

    Attributes:
        metric:         Canonical metric name.
        fused_value:    The weighted-average (or primary) value.
        sources_used:   Sources whose readings contributed to the fusion.
        weights_applied: Normalized weights used for each source.
        had_conflict:   True if sources disagreed beyond the tolerance.
        conflict_detail: Per-source readings that caused the conflict.
        confidence:     0.0–1.0 overall confidence in the fused value.
    """

    metric: str
    fused_value: float | None
    sources_used: list[str] = field(default_factory=list)
    weights_applied: dict[str, float] = field(default_factory=dict)
    had_conflict: bool = False
    conflict_detail: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


@dataclass
class FusionResult:
    """Complete fusion result for one user+date+metric_group.

    Attributes:
        user_id:        Internal Vitalis user UUID.
        date:           Calendar date fused.
        metric_group:   'daily', 'sleep', or 'activity'.
        metrics:        Dict of metric_name → MetricFusionResult.
        sources_used:   All device sources that contributed data.
        conflicts:      Metrics that had conflicts (> tolerance).
        fusion_config_version: Config version used to produce this result.
        computed_at:    UTC timestamp of computation.
    """

    user_id: UUID
    date: date
    metric_group: str
    metrics: dict[str, MetricFusionResult] = field(default_factory=dict)
    sources_used: list[str] = field(default_factory=list)
    conflicts: dict[str, Any] = field(default_factory=dict)
    fusion_config_version: str = "1.0"
    computed_at: datetime = field(default_factory=datetime.utcnow)

    def to_metadata_dict(self) -> dict:
        """Serialize to the format stored in fusion_metadata table."""
        return {
            "sources_used": self.sources_used,
            "weights_applied": {
                k: v.weights_applied for k, v in self.metrics.items()
            },
            "conflicts": self.conflicts or None,
            "fusion_config_version": self.fusion_config_version,
        }


# ---------------------------------------------------------------------------
# Fusion helpers
# ---------------------------------------------------------------------------


def _weighted_average(readings: dict[str, float], weights: dict[str, float]) -> float:
    """Compute a weighted average of readings.

    Args:
        readings: source → value.
        weights:  source → weight (need not sum to 1).

    Returns:
        Weighted average value.
    """
    total_weight = sum(weights.get(src, 0.0) for src in readings)
    if total_weight == 0.0:
        # Fall back to simple average
        return sum(readings.values()) / len(readings)
    return (
        sum(val * weights.get(src, 0.0) for src, val in readings.items())
        / total_weight
    )


def _fuse_metric(
    metric: str,
    readings: dict[str, float],
    config: FusionConfig,
    tolerance_key: str | None = None,
) -> MetricFusionResult:
    """Fuse a single metric across multiple device sources.

    Algorithm:
    1. Get configured weights for each source.
    2. Filter out sources with weight = 0.
    3. If only one source remains: return it directly (no fusion needed).
    4. Check if all values are within tolerance of each other.
    5. If within tolerance: compute weighted average.
    6. If outside tolerance (conflict): use primary (highest-weight) source,
       flag conflict, record all readings.

    Args:
        metric:        Canonical metric name (key into device_weights).
        readings:      source → value dict (only sources that reported a value).
        config:        Loaded FusionConfig.
        tolerance_key: Key in config.tolerances (e.g. 'hrv_ms'). If None,
                       conflict detection is skipped.

    Returns:
        MetricFusionResult.
    """
    if not readings:
        return MetricFusionResult(metric=metric, fused_value=None, confidence=0.0)

    # Get weights for each contributing source
    weights = {src: config.device_weight(metric, src) for src in readings}

    # Filter out sources with zero weight
    active = {src: val for src, val in readings.items() if weights.get(src, 0.0) > 0.0}
    active_weights = {src: weights[src] for src in active}

    if not active:
        # All sources have zero weight — fall through with equal weights
        active = readings
        active_weights = {src: 1.0 for src in readings}

    if len(active) == 1:
        src = next(iter(active))
        return MetricFusionResult(
            metric=metric,
            fused_value=active[src],
            sources_used=[src],
            weights_applied={src: 1.0},
            had_conflict=False,
            confidence=active_weights[src],
        )

    # Normalize weights
    total = sum(active_weights.values())
    normalized = {src: w / total for src, w in active_weights.items()}

    # Conflict detection
    had_conflict = False
    conflict_detail: dict[str, Any] = {}

    if tolerance_key is not None:
        tolerance = config.tolerance(tolerance_key)
        min_val = min(active.values())
        max_val = max(active.values())
        diff = max_val - min_val

        if diff > tolerance:
            had_conflict = True
            # Identify the primary source (highest weight)
            primary_src = max(active_weights, key=lambda s: active_weights[s])
            conflict_detail = {
                src: val for src, val in active.items()
            }
            conflict_detail["diff"] = round(diff, 4)
            conflict_detail["tolerance"] = tolerance
            conflict_detail["primary_used"] = primary_src

            logger.info(
                "Fusion conflict on %s: diff=%.2f > tolerance=%.2f. Using %s (weight=%.2f)",
                metric, diff, tolerance, primary_src, active_weights[primary_src],
            )

            # Use primary source when conflict detected
            return MetricFusionResult(
                metric=metric,
                fused_value=active[primary_src],
                sources_used=[primary_src],
                weights_applied={primary_src: 1.0},
                had_conflict=True,
                conflict_detail=conflict_detail,
                confidence=active_weights[primary_src] * 0.8,  # penalty for conflict
            )

    # No conflict — compute weighted average
    fused = _weighted_average(active, active_weights)
    confidence = sum(normalized[src] * active_weights[src] for src in active) / max(
        sum(active_weights.values()), 1.0
    )

    return MetricFusionResult(
        metric=metric,
        fused_value=round(fused, 4),
        sources_used=list(active.keys()),
        weights_applied=normalized,
        had_conflict=False,
        confidence=min(confidence, 1.0),
    )


# ---------------------------------------------------------------------------
# Daily fusion
# ---------------------------------------------------------------------------


# Mapping of NormalizedDaily field → (fusion metric key, tolerance key)
_DAILY_METRIC_MAP: list[tuple[str, str, str | None]] = [
    ("resting_hr_bpm", "resting_heart_rate", "resting_hr_bpm"),
    ("hrv_rmssd_ms", "hrv", "hrv_ms"),
    ("steps", "steps", "steps_count"),
    ("active_calories_kcal", "calories_burned", None),
    ("total_calories_kcal", "calories_burned", None),
    ("spo2_avg_pct", "spo2", "spo2_pct"),
    ("respiratory_rate_avg", "respiratory_rate", "respiratory_rate_brpm"),
    ("skin_temp_deviation_c", "skin_temperature", "skin_temp_celsius"),
]


def fuse_daily(
    user_id: UUID,
    target_date: date,
    records: list[NormalizedDaily],
    config: FusionConfig | None = None,
) -> tuple[FusionResult, NormalizedDaily]:
    """Fuse daily summary records from multiple devices into a single canonical record.

    Args:
        user_id:     Internal Vitalis user UUID.
        target_date: Date being fused.
        records:     List of NormalizedDaily from different device sources.
        config:      FusionConfig (loaded from singleton if None).

    Returns:
        Tuple of (FusionResult with metadata, NormalizedDaily with fused values).
    """
    cfg = config or get_fusion_config()

    if not records:
        raise ValueError(f"No daily records to fuse for {user_id} on {target_date}")

    if len(records) == 1:
        # Single source — no fusion needed, return as-is with metadata
        result = FusionResult(
            user_id=user_id,
            date=target_date,
            metric_group="daily",
            sources_used=[records[0].source],
            fusion_config_version=cfg.version,
        )
        return result, records[0]

    sources_used = list({r.source for r in records})
    fusion_result = FusionResult(
        user_id=user_id,
        date=target_date,
        metric_group="daily",
        sources_used=sources_used,
        fusion_config_version=cfg.version,
    )

    # Build fused NormalizedDaily
    fused = NormalizedDaily(user_id=user_id, date=target_date, source="fused")

    for field_name, metric_key, tol_key in _DAILY_METRIC_MAP:
        # Collect non-None readings from all sources
        readings: dict[str, float] = {}
        for rec in records:
            val = getattr(rec, field_name, None)
            if val is not None:
                readings[rec.source] = float(val)

        if not readings:
            continue

        metric_result = _fuse_metric(metric_key, readings, cfg, tol_key)
        fusion_result.metrics[field_name] = metric_result

        if metric_result.fused_value is not None:
            # Preserve integer fields as integers
            if field_name in ("resting_hr_bpm", "max_hr_bpm", "steps",
                               "active_calories_kcal", "total_calories_kcal",
                               "active_minutes", "distance_m", "floors_climbed",
                               "stress_avg"):
                setattr(fused, field_name, int(round(metric_result.fused_value)))
            else:
                setattr(fused, field_name, metric_result.fused_value)

        if metric_result.had_conflict:
            fusion_result.conflicts[field_name] = metric_result.conflict_detail

    # Proprietary scores are NOT fused — excluded by weight=0 in config
    # Keep the highest-weight device's score for display purposes only
    fused.readiness_score = None
    fused.recovery_score = None

    logger.info(
        "Fused daily for %s on %s: %d sources, %d conflicts",
        user_id, target_date, len(sources_used), len(fusion_result.conflicts),
    )

    return fusion_result, fused


# ---------------------------------------------------------------------------
# Sleep fusion
# ---------------------------------------------------------------------------


# Mapping of NormalizedSleep field → (fusion metric key, tolerance key)
_SLEEP_METRIC_MAP: list[tuple[str, str, str | None]] = [
    ("total_sleep_minutes", "sleep_duration", "sleep_duration_minutes"),
    ("rem_minutes", "sleep_stages", "sleep_stage_minutes"),
    ("deep_minutes", "sleep_stages", "sleep_stage_minutes"),
    ("light_minutes", "sleep_stages", "sleep_stage_minutes"),
    ("awake_minutes", "sleep_stages", "sleep_stage_minutes"),
    ("avg_hrv_ms", "hrv", "hrv_ms"),
    ("avg_hr_bpm", "resting_heart_rate", "resting_hr_bpm"),
    ("avg_spo2_pct", "spo2", "spo2_pct"),
    ("avg_respiratory_rate", "respiratory_rate", "respiratory_rate_brpm"),
    ("avg_skin_temp_deviation_c", "skin_temperature", "skin_temp_celsius"),
]


def fuse_sleep(
    user_id: UUID,
    target_date: date,
    match_group: SleepMatchGroup,
    config: FusionConfig | None = None,
) -> tuple[FusionResult, NormalizedSleep]:
    """Fuse sleep sessions from a matched group into a single canonical record.

    Args:
        user_id:     Internal Vitalis user UUID.
        target_date: Sleep date (morning of wake, user's local date).
        match_group: SleepMatchGroup from SleepMatcher.
        config:      FusionConfig (loaded from singleton if None).

    Returns:
        Tuple of (FusionResult with metadata, NormalizedSleep with fused values).
    """
    cfg = config or get_fusion_config()
    sessions = match_group.sessions

    if not sessions:
        raise ValueError(f"Empty sleep match group for {user_id} on {target_date}")

    if len(sessions) == 1:
        result = FusionResult(
            user_id=user_id,
            date=target_date,
            metric_group="sleep",
            sources_used=[sessions[0].source],
            fusion_config_version=cfg.version,
        )
        return result, sessions[0]

    sources_used = [s.source for s in sessions]
    fusion_result = FusionResult(
        user_id=user_id,
        date=target_date,
        metric_group="sleep",
        sources_used=sources_used,
        fusion_config_version=cfg.version,
    )

    # Build fused NormalizedSleep
    fused = NormalizedSleep(
        user_id=user_id,
        sleep_date=target_date,
        source="fused",
    )

    # Use the primary source's timing data for sleep_start/sleep_end
    sleep_dur_weights = cfg.device_weights.get("sleep_duration", {})
    primary = SleepMatcher.select_primary(match_group, sleep_dur_weights)
    if primary:
        fused.sleep_start = primary.sleep_start
        fused.sleep_end = primary.sleep_end

    for field_name, metric_key, tol_key in _SLEEP_METRIC_MAP:
        readings: dict[str, float] = {}
        for session in sessions:
            val = getattr(session, field_name, None)
            if val is not None:
                readings[session.source] = float(val)

        if not readings:
            continue

        metric_result = _fuse_metric(metric_key, readings, cfg, tol_key)
        fusion_result.metrics[field_name] = metric_result

        if metric_result.fused_value is not None:
            if field_name in ("total_sleep_minutes", "rem_minutes", "deep_minutes",
                               "light_minutes", "awake_minutes", "sleep_latency_minutes",
                               "interruptions", "avg_hr_bpm", "min_hr_bpm"):
                setattr(fused, field_name, int(round(metric_result.fused_value)))
            else:
                setattr(fused, field_name, metric_result.fused_value)

        if metric_result.had_conflict:
            fusion_result.conflicts[field_name] = metric_result.conflict_detail

    # sleep_efficiency and sleep_score: use primary source
    if primary:
        fused.sleep_efficiency_pct = primary.sleep_efficiency_pct
        fused.sleep_score = primary.sleep_score
        fused.hypnogram = primary.hypnogram

    logger.info(
        "Fused sleep for %s on %s: %d sources, %d conflicts",
        user_id, target_date, len(sources_used), len(fusion_result.conflicts),
    )

    return fusion_result, fused


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


class FusionEngine:
    """Orchestrates the full fusion pipeline for a user+date.

    Usage::

        engine = FusionEngine()
        daily_result, fused_daily = await engine.run_daily(user_id, date, records)
        sleep_result, fused_sleep = await engine.run_sleep(user_id, date, sleep_sessions)
    """

    def __init__(self, config: FusionConfig | None = None) -> None:
        self._config = config or get_fusion_config()
        self._sleep_matcher = SleepMatcher(self._config)

    def run_daily(
        self,
        user_id: UUID,
        target_date: date,
        records: list[NormalizedDaily],
    ) -> tuple[FusionResult, NormalizedDaily]:
        """Run daily fusion for a user+date.

        Args:
            user_id:     Internal Vitalis user UUID.
            target_date: Date to fuse.
            records:     NormalizedDaily records from all available devices.

        Returns:
            (FusionResult, NormalizedDaily) tuple.
        """
        return fuse_daily(user_id, target_date, records, self._config)

    def run_sleep(
        self,
        user_id: UUID,
        target_date: date,
        sessions: list[NormalizedSleep],
    ) -> list[tuple[FusionResult, NormalizedSleep]]:
        """Run sleep fusion for a user+date.

        Matches sessions across devices, then fuses each matched group.

        Args:
            user_id:     Internal Vitalis user UUID.
            target_date: Sleep date.
            sessions:    NormalizedSleep sessions from all devices.

        Returns:
            List of (FusionResult, NormalizedSleep) tuples, one per matched group.
        """
        groups = self._sleep_matcher.match_for_date(sessions, target_date)
        results = []
        for group in groups:
            fusion_result, fused = fuse_sleep(user_id, target_date, group, self._config)
            results.append((fusion_result, fused))
        return results
