"""Vitalis Wearable Data Fusion Engine.

This package handles multi-device wearable data ingestion, normalization,
conflict resolution via weighted fusion, and the Vitalis proprietary
readiness score.

Subpackages:
    adapters/  — Device-specific API adapters (Garmin, Oura, Apple Health, Whoop)
    menstrual/ — Cycle tracking, temperature-based ovulation detection, symptom correlation
    sync/      — Background sync scheduler, historical backfill, deduplication

Core modules:
    base            — WearableAdapter ABC and canonical data models
    fusion_engine   — Weighted multi-source data fusion
    config_loader   — Load/validate/hot-reload fusion_config.yaml
    readiness_score — Vitalis proprietary readiness score
    sleep_matcher   — Cross-device sleep session matching
"""

from src.wearables.base import (
    NormalizedActivity,
    NormalizedDaily,
    NormalizedSleep,
    OAuthTokens,
    RawDevicePayload,
    WearableAdapter,
)
from src.wearables.config_loader import FusionConfig, get_fusion_config

__all__ = [
    "WearableAdapter",
    "NormalizedSleep",
    "NormalizedDaily",
    "NormalizedActivity",
    "OAuthTokens",
    "RawDevicePayload",
    "FusionConfig",
    "get_fusion_config",
]
