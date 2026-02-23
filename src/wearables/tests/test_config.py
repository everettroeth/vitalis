"""Tests for fusion_config.yaml loading and validation."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.wearables.config_loader import (
    ConfigValidationError,
    FusionConfig,
    _validate_and_build,
    load_fusion_config,
    reload_fusion_config,
)


class TestConfigLoading:
    """Tests for loading fusion_config.yaml."""

    def test_load_default_config(self, fusion_config: FusionConfig) -> None:
        """The bundled fusion_config.yaml loads without errors."""
        assert fusion_config.version == "1.0"
        assert fusion_config.device_weights
        assert fusion_config.tolerances

    def test_device_weights_are_in_range(self, fusion_config: FusionConfig) -> None:
        """All device weights must be between 0.0 and 1.0."""
        for metric, sources in fusion_config.device_weights.items():
            for source, weight in sources.items():
                assert 0.0 <= weight <= 1.0, (
                    f"Weight out of range: {metric}.{source} = {weight}"
                )

    def test_oura_hrv_highest_weight(self, fusion_config: FusionConfig) -> None:
        """Oura should have the highest HRV weight (0.95)."""
        oura_hrv = fusion_config.device_weight("hrv", "oura")
        garmin_hrv = fusion_config.device_weight("hrv", "garmin")
        apple_hrv = fusion_config.device_weight("hrv", "apple_watch")
        assert oura_hrv > garmin_hrv
        assert oura_hrv > apple_hrv
        assert oura_hrv >= 0.90

    def test_body_battery_excluded_from_fusion(self, fusion_config: FusionConfig) -> None:
        """Proprietary readiness scores should have weight 0.0."""
        for source in ["oura", "garmin", "apple_watch", "whoop"]:
            w = fusion_config.device_weight("body_battery_readiness", source)
            assert w == 0.0, f"body_battery_readiness.{source} should be 0.0"

    def test_sleep_tolerances_configured(self, fusion_config: FusionConfig) -> None:
        """Key sleep tolerances must be set."""
        assert fusion_config.tolerance("sleep_duration_minutes") == 30.0
        assert fusion_config.tolerance("hrv_ms") == 15.0
        assert fusion_config.tolerance("resting_hr_bpm") == 5.0

    def test_sources_for_metric_sorted_by_weight(self, fusion_config: FusionConfig) -> None:
        """sources_for_metric() should return sources highest-weight first."""
        hrv_sources = fusion_config.sources_for_metric("hrv")
        assert hrv_sources[0] == "oura"  # 0.95
        assert len(hrv_sources) >= 3

    def test_primary_source(self, fusion_config: FusionConfig) -> None:
        """primary_source() should return the highest-weight source."""
        assert fusion_config.primary_source("hrv") == "oura"
        assert fusion_config.primary_source("steps") in ("garmin", "apple_watch")

    def test_unknown_metric_returns_zero(self, fusion_config: FusionConfig) -> None:
        """device_weight() on an unknown metric should return 0.0."""
        assert fusion_config.device_weight("nonexistent_metric", "oura") == 0.0

    def test_unknown_source_returns_zero(self, fusion_config: FusionConfig) -> None:
        """device_weight() on an unknown source should return 0.0."""
        assert fusion_config.device_weight("hrv", "fitbit") == 0.0

    def test_sleep_matching_defaults(self, fusion_config: FusionConfig) -> None:
        """Sleep matching config should have sensible defaults."""
        sm = fusion_config.sleep_matching
        assert sm.min_overlap_pct == 60.0
        assert sm.max_start_diff_minutes == 60
        assert sm.sleep_day_cutoff_hour == 18

    def test_readiness_config(self, fusion_config: FusionConfig) -> None:
        """Readiness config should have 5 components summing to 1.0."""
        rs = fusion_config.readiness
        assert rs.enabled
        assert len(rs.components) == 5
        assert abs(rs.total_weight - 1.0) < 0.01

    def test_menstrual_config(self, fusion_config: FusionConfig) -> None:
        """Menstrual config should be properly configured."""
        mc = fusion_config.menstrual
        assert mc.enabled
        assert mc.temp_source_priority[0] == "oura"
        assert mc.min_cycle_days == 21
        assert mc.max_cycle_days == 45

    def test_backfill_config(self, fusion_config: FusionConfig) -> None:
        """Backfill config should have reasonable defaults."""
        bf = fusion_config.backfill
        assert bf.enabled
        assert bf.max_days["garmin"] == 3650
        assert bf.batch_size_days == 30
        assert bf.rate_limit_ms == 500


class TestConfigValidation:
    """Tests for config validation logic."""

    def test_valid_minimal_config(self) -> None:
        """A minimal valid config should load without errors."""
        raw = {
            "version": "1.0",
            "device_weights": {"hrv": {"oura": 0.9, "garmin": 0.7}},
            "tolerances": {"hrv_ms": 15},
        }
        config = _validate_and_build(raw)
        assert config.version == "1.0"

    def test_out_of_range_weight_raises(self) -> None:
        """Weights outside [0.0, 1.0] should raise ConfigValidationError."""
        raw = {
            "version": "1.0",
            "device_weights": {"hrv": {"oura": 1.5}},  # > 1.0
            "tolerances": {},
        }
        with pytest.raises(ConfigValidationError, match="out of range"):
            _validate_and_build(raw)

    def test_non_numeric_weight_raises(self) -> None:
        """Non-numeric weights should raise ConfigValidationError."""
        raw = {
            "version": "1.0",
            "device_weights": {"hrv": {"oura": "best"}},
            "tolerances": {},
        }
        with pytest.raises(ConfigValidationError):
            _validate_and_build(raw)

    def test_missing_device_weights_raises(self) -> None:
        """Empty device_weights section should raise ConfigValidationError."""
        raw = {"version": "1.0", "tolerances": {}}
        with pytest.raises(ConfigValidationError, match="device_weights"):
            _validate_and_build(raw)

    def test_hot_reload(self, tmp_path: Path) -> None:
        """reload_fusion_config() should replace the global singleton."""
        config_content = """
version: "2.0-test"
device_weights:
  hrv:
    oura: 0.95
    garmin: 0.65
tolerances:
  hrv_ms: 15
sleep_matching:
  min_overlap_pct: 60
  max_start_diff_minutes: 60
  sleep_day_cutoff_hour: 18
readiness_score:
  enabled: true
  components: {}
  thresholds:
    thriving: 75
    watch: 50
menstrual_cycle:
  enabled: false
  prediction_model: calendar_only
  temp_source_priority: [oura]
  fertile_window:
    confirmation_days: 3
    predicted_window_days: 6
  cycle_length:
    rolling_average_cycles: 6
    min_cycle_days: 21
    max_cycle_days: 45
backfill:
  enabled: true
  batch_size_days: 30
  rate_limit_ms: 500
"""
        config_file = tmp_path / "fusion_config.yaml"
        config_file.write_text(config_content.strip())

        new_config = reload_fusion_config(path=config_file)
        assert new_config.version == "2.0-test"

    def test_load_nonexistent_file_raises(self) -> None:
        """Loading a nonexistent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_fusion_config(path=Path("/nonexistent/path/config.yaml"))
