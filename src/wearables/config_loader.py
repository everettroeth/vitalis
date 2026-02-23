"""Load, validate, and hot-reload the Vitalis fusion configuration.

The config lives in ``fusion_config.yaml`` alongside this module.  At startup
it is loaded once and cached.  Call ``reload_fusion_config()`` to re-read from
disk after an admin update — no restart required.

Usage::

    from src.wearables.config_loader import get_fusion_config

    config = get_fusion_config()
    hrv_weight = config.device_weight("hrv", "oura")   # 0.95
    tolerance = config.tolerance("hrv_ms")              # 15.0
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("vitalis.wearables.config")

# Path to the YAML file sitting next to this module
_CONFIG_PATH = Path(__file__).parent / "fusion_config.yaml"


# ---------------------------------------------------------------------------
# Typed config sections
# ---------------------------------------------------------------------------


@dataclass
class ReadinessComponent:
    """One component of the Vitalis readiness score formula."""

    name: str
    weight: float
    description: str


@dataclass
class ReadinessConfig:
    """Readiness score computation settings."""

    enabled: bool
    components: list[ReadinessComponent]
    thriving_threshold: int  # ≥ this = thriving
    watch_threshold: int     # ≥ this = watch

    @property
    def total_weight(self) -> float:
        return sum(c.weight for c in self.components)


@dataclass
class SleepMatchingConfig:
    """Settings for matching sleep sessions across devices."""

    min_overlap_pct: float
    max_start_diff_minutes: int
    sleep_day_cutoff_hour: int


@dataclass
class MenstrualCycleConfig:
    """Menstrual cycle tracking settings."""

    enabled: bool
    prediction_model: str
    temp_source_priority: list[str]
    temp_shift_threshold_c: float = 0.2
    ovulation_confirmation_days: int = 3
    fertile_window_days: int = 6
    rolling_average_cycles: int = 6
    min_cycle_days: int = 21
    max_cycle_days: int = 45


@dataclass
class BackfillConfig:
    """Historical backfill settings per device."""

    enabled: bool
    max_days: dict[str, int]
    batch_size_days: int
    rate_limit_ms: int


@dataclass
class FusionConfig:
    """Complete, validated fusion configuration.

    This is the single in-memory representation of fusion_config.yaml.
    All engine, matcher, and scorer components read from this object.

    Attributes:
        version:          Config schema version string.
        device_weights:   Nested dict: metric → source → weight (0.0–1.0).
        tolerances:       Metric tolerance thresholds for conflict detection.
        sleep_matching:   Sleep session matching parameters.
        readiness:        Readiness score computation settings.
        menstrual:        Menstrual cycle tracking settings.
        backfill:         Historical backfill settings.
    """

    version: str
    device_weights: dict[str, dict[str, float]]
    tolerances: dict[str, float]
    sleep_matching: SleepMatchingConfig
    readiness: ReadinessConfig
    menstrual: MenstrualCycleConfig
    backfill: BackfillConfig
    _raw: dict = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def device_weight(self, metric: str, source: str) -> float:
        """Return the fusion weight for a metric+source pair.

        Falls back to 0.0 if the metric or source is not configured,
        which effectively excludes that source from fusion for that metric.

        Args:
            metric: Metric key (e.g. 'hrv', 'sleep_duration').
            source: Device source slug (e.g. 'oura', 'garmin').

        Returns:
            Weight between 0.0 and 1.0.
        """
        return self.device_weights.get(metric, {}).get(source, 0.0)

    def tolerance(self, key: str) -> float:
        """Return the conflict tolerance for a given metric key.

        Args:
            key: Tolerance key from config (e.g. 'hrv_ms', 'steps_count').

        Returns:
            Tolerance value (units depend on metric).
        """
        return self.tolerances.get(key, float("inf"))

    def sources_for_metric(self, metric: str) -> list[str]:
        """Return all configured sources for a metric, sorted by weight descending.

        Sources with weight 0.0 are excluded.

        Args:
            metric: Metric key.

        Returns:
            List of source slugs in descending weight order.
        """
        weights = self.device_weights.get(metric, {})
        return sorted(
            (s for s, w in weights.items() if w > 0.0),
            key=lambda s: weights[s],
            reverse=True,
        )

    def primary_source(self, metric: str) -> str | None:
        """Return the highest-weight source for a metric.

        Args:
            metric: Metric key.

        Returns:
            Source slug or None if no sources configured.
        """
        sources = self.sources_for_metric(metric)
        return sources[0] if sources else None


# ---------------------------------------------------------------------------
# Loader / validation
# ---------------------------------------------------------------------------


class ConfigValidationError(ValueError):
    """Raised when fusion_config.yaml fails validation."""


def _load_yaml(path: Path) -> dict:
    """Read and parse a YAML file.

    Args:
        path: Path to the YAML file.

    Returns:
        Parsed dict.

    Raises:
        FileNotFoundError: If the file does not exist.
        ConfigValidationError: If the YAML is malformed.
    """
    try:
        import yaml  # pyyaml
    except ImportError as exc:
        raise ImportError(
            "pyyaml is required for config loading. Install with: pip install pyyaml"
        ) from exc

    if not path.exists():
        raise FileNotFoundError(f"Fusion config not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        try:
            return yaml.safe_load(fh) or {}
        except yaml.YAMLError as exc:
            raise ConfigValidationError(f"YAML parse error in {path}: {exc}") from exc


def _validate_and_build(raw: dict) -> FusionConfig:
    """Validate the raw YAML dict and construct a FusionConfig.

    Performs structural validation and applies defaults for optional fields.

    Args:
        raw: Parsed YAML dict.

    Returns:
        Validated FusionConfig instance.

    Raises:
        ConfigValidationError: If required fields are missing or invalid.
    """
    errors: list[str] = []

    def _require(d: dict, key: str, section: str) -> Any:
        if key not in d:
            errors.append(f"Missing required key '{key}' in section '{section}'")
            return None
        return d[key]

    version = raw.get("version", "1.0")

    # ── Device weights ──
    device_weights_raw = raw.get("device_weights", {})
    if not device_weights_raw:
        errors.append("'device_weights' section is missing or empty")

    # Validate all weights are in [0.0, 1.0]
    device_weights: dict[str, dict[str, float]] = {}
    for metric, sources in (device_weights_raw or {}).items():
        if not isinstance(sources, dict):
            errors.append(f"device_weights.{metric} must be a mapping of source→weight")
            continue
        device_weights[metric] = {}
        for source, weight in sources.items():
            try:
                w = float(weight)
            except (TypeError, ValueError):
                errors.append(
                    f"device_weights.{metric}.{source} must be a number, got {weight!r}"
                )
                continue
            if not (0.0 <= w <= 1.0):
                errors.append(
                    f"device_weights.{metric}.{source} = {w} is out of range [0.0, 1.0]"
                )
            device_weights[metric][source] = w

    # ── Tolerances ──
    tol_raw = raw.get("tolerances", {})
    tolerances: dict[str, float] = {}
    for key, val in (tol_raw or {}).items():
        try:
            tolerances[key] = float(val)
        except (TypeError, ValueError):
            errors.append(f"tolerances.{key} must be a number, got {val!r}")

    # ── Sleep matching ──
    sm_raw = raw.get("sleep_matching", {})
    sleep_matching = SleepMatchingConfig(
        min_overlap_pct=float(sm_raw.get("min_overlap_pct", 60)),
        max_start_diff_minutes=int(sm_raw.get("max_start_diff_minutes", 60)),
        sleep_day_cutoff_hour=int(sm_raw.get("sleep_day_cutoff_hour", 18)),
    )

    # ── Readiness score ──
    rs_raw = raw.get("readiness_score", {})
    components_raw = rs_raw.get("components", {})
    components: list[ReadinessComponent] = []
    for name, cfg in (components_raw or {}).items():
        if not isinstance(cfg, dict):
            errors.append(f"readiness_score.components.{name} must be a mapping")
            continue
        w = float(cfg.get("weight", 0.0))
        components.append(
            ReadinessComponent(
                name=name,
                weight=w,
                description=cfg.get("description", ""),
            )
        )
    thresholds_raw = rs_raw.get("thresholds", {})
    readiness = ReadinessConfig(
        enabled=bool(rs_raw.get("enabled", True)),
        components=components,
        thriving_threshold=int(thresholds_raw.get("thriving", 75)),
        watch_threshold=int(thresholds_raw.get("watch", 50)),
    )

    # Validate total weight sums to ~1.0 (warn only)
    total_w = readiness.total_weight
    if components and not (0.95 <= total_w <= 1.05):
        logger.warning(
            "Readiness component weights sum to %.3f (expected ~1.0). "
            "Score will be normalized at runtime.",
            total_w,
        )

    # ── Menstrual cycle ──
    mc_raw = raw.get("menstrual_cycle", {})
    fw_raw = mc_raw.get("fertile_window", {})
    cl_raw = mc_raw.get("cycle_length", {})
    menstrual = MenstrualCycleConfig(
        enabled=bool(mc_raw.get("enabled", True)),
        prediction_model=mc_raw.get("prediction_model", "temperature_assisted"),
        temp_source_priority=mc_raw.get(
            "temp_source_priority", ["oura", "apple_watch", "whoop", "garmin"]
        ),
        temp_shift_threshold_c=0.2,
        ovulation_confirmation_days=int(fw_raw.get("confirmation_days", 3)),
        fertile_window_days=int(fw_raw.get("predicted_window_days", 6)),
        rolling_average_cycles=int(cl_raw.get("rolling_average_cycles", 6)),
        min_cycle_days=int(cl_raw.get("min_cycle_days", 21)),
        max_cycle_days=int(cl_raw.get("max_cycle_days", 45)),
    )

    # ── Backfill ──
    bf_raw = raw.get("backfill", {})
    backfill = BackfillConfig(
        enabled=bool(bf_raw.get("enabled", True)),
        max_days={
            "garmin": int(bf_raw.get("garmin_max_days", 3650)),
            "oura": int(bf_raw.get("oura_max_days", 3650)),
            "apple_health": int(bf_raw.get("apple_health_max_days", 3650)),
            "whoop": int(bf_raw.get("whoop_max_days", 3650)),
        },
        batch_size_days=int(bf_raw.get("batch_size_days", 30)),
        rate_limit_ms=int(bf_raw.get("rate_limit_ms", 500)),
    )

    if errors:
        raise ConfigValidationError(
            f"fusion_config.yaml has {len(errors)} validation error(s):\n"
            + "\n".join(f"  • {e}" for e in errors)
        )

    return FusionConfig(
        version=version,
        device_weights=device_weights,
        tolerances=tolerances,
        sleep_matching=sleep_matching,
        readiness=readiness,
        menstrual=menstrual,
        backfill=backfill,
        _raw=raw,
    )


def load_fusion_config(path: Path | None = None) -> FusionConfig:
    """Load and validate the fusion config from disk.

    Args:
        path: Override path to YAML. Uses the bundled fusion_config.yaml by default.

    Returns:
        Validated FusionConfig instance.
    """
    target = path or _CONFIG_PATH
    raw = _load_yaml(target)
    config = _validate_and_build(raw)
    logger.info("Loaded fusion config v%s from %s", config.version, target)
    return config


# ---------------------------------------------------------------------------
# Global singleton with hot-reload support
# ---------------------------------------------------------------------------

_config: FusionConfig | None = None
_config_lock = threading.Lock()


def get_fusion_config() -> FusionConfig:
    """Return the global FusionConfig singleton, loading it on first call.

    Thread-safe.  Use ``reload_fusion_config()`` to refresh after YAML changes.

    Returns:
        The current FusionConfig instance.
    """
    global _config
    if _config is None:
        with _config_lock:
            if _config is None:  # double-checked locking
                _config = load_fusion_config()
    return _config


def reload_fusion_config(path: Path | None = None) -> FusionConfig:
    """Reload the fusion config from disk and replace the global singleton.

    Called by the admin ``PUT /api/v1/admin/fusion-config`` endpoint after
    writing a new config to disk.  If validation fails, the old config is
    retained and the error is re-raised.

    Args:
        path: Override path to YAML. Defaults to bundled fusion_config.yaml.

    Returns:
        The newly loaded FusionConfig.

    Raises:
        ConfigValidationError: If the new config is invalid.
        FileNotFoundError:     If the config file is missing.
    """
    global _config
    new_config = load_fusion_config(path)  # validate before acquiring lock
    with _config_lock:
        old_version = _config.version if _config else "none"
        _config = new_config
    logger.info(
        "Reloaded fusion config: %s → %s",
        old_version,
        new_config.version,
    )
    return new_config
