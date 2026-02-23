"""Pydantic models for wearable data: daily summaries, sleep, activities, connected devices."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import Field

from src.models.base import SoftDeleteMixin, TimestampMixin, VitalisBase


# ---------- Connected Devices ----------

class ConnectedDeviceBase(VitalisBase):
    source: str = Field(max_length=50)
    display_name: str | None = None
    external_user_id: str | None = None
    scope: list[str] | None = None
    is_active: bool = True


class ConnectedDeviceCreate(ConnectedDeviceBase):
    pass


class ConnectedDeviceUpdate(VitalisBase):
    display_name: str | None = None
    is_active: bool | None = None


class ConnectedDeviceRead(ConnectedDeviceBase, TimestampMixin):
    device_id: uuid.UUID
    user_id: uuid.UUID
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    last_sync_error: str | None = None
    sync_cursor: dict[str, Any] = Field(default_factory=dict)


# ---------- Wearable Daily ----------

class WearableDailyBase(VitalisBase):
    date: date
    source: str
    resting_hr_bpm: int | None = Field(default=None, ge=20, le=300)
    max_hr_bpm: int | None = Field(default=None, ge=20, le=300)
    hrv_rmssd_ms: Decimal | None = Field(default=None, ge=1, le=300)
    steps: int | None = Field(default=None, ge=0, le=100000)
    active_calories_kcal: int | None = None
    total_calories_kcal: int | None = None
    active_minutes: int | None = Field(default=None, ge=0, le=1440)
    moderate_intensity_minutes: int | None = None
    vigorous_intensity_minutes: int | None = None
    distance_m: int | None = None
    floors_climbed: int | None = None
    spo2_avg_pct: Decimal | None = Field(default=None, ge=70, le=100)
    spo2_min_pct: Decimal | None = None
    respiratory_rate_avg: Decimal | None = Field(default=None, ge=4, le=60)
    stress_avg: int | None = Field(default=None, ge=0, le=100)
    body_battery_start: int | None = None
    body_battery_end: int | None = None
    readiness_score: int | None = None
    recovery_score: int | None = None
    skin_temp_deviation_c: Decimal | None = None
    vo2_max_ml_kg_min: Decimal | None = Field(default=None, ge=10, le=100)
    extended_metrics: dict[str, Any] = Field(default_factory=dict)


class WearableDailyCreate(WearableDailyBase):
    raw_data: dict[str, Any] | None = None


class WearableDailyUpdate(VitalisBase):
    resting_hr_bpm: int | None = Field(default=None, ge=20, le=300)
    max_hr_bpm: int | None = Field(default=None, ge=20, le=300)
    hrv_rmssd_ms: Decimal | None = Field(default=None, ge=1, le=300)
    steps: int | None = Field(default=None, ge=0, le=100000)
    active_calories_kcal: int | None = None
    total_calories_kcal: int | None = None
    extended_metrics: dict[str, Any] | None = None


class WearableDailyRead(WearableDailyBase, TimestampMixin):
    daily_id: uuid.UUID
    user_id: uuid.UUID
    raw_s3_key: str | None = None


# ---------- Wearable Sleep ----------

class WearableSleepBase(VitalisBase):
    sleep_date: date
    source: str
    sleep_start: datetime | None = None
    sleep_end: datetime | None = None
    total_sleep_minutes: int | None = Field(default=None, ge=0, le=1440)
    rem_minutes: int | None = Field(default=None, ge=0, le=720)
    deep_minutes: int | None = None
    light_minutes: int | None = None
    awake_minutes: int | None = None
    sleep_latency_minutes: int | None = Field(default=None, ge=0, le=240)
    sleep_efficiency_pct: Decimal | None = Field(default=None, ge=0, le=100)
    sleep_score: int | None = Field(default=None, ge=0, le=100)
    interruptions: int | None = None
    avg_hr_bpm: int | None = Field(default=None, ge=20, le=200)
    min_hr_bpm: int | None = None
    avg_hrv_ms: Decimal | None = None
    avg_respiratory_rate: Decimal | None = None
    avg_spo2_pct: Decimal | None = None
    avg_skin_temp_deviation_c: Decimal | None = None
    hypnogram: list[dict[str, Any]] | None = None


class WearableSleepCreate(WearableSleepBase):
    raw_data: dict[str, Any] | None = None


class WearableSleepUpdate(VitalisBase):
    total_sleep_minutes: int | None = Field(default=None, ge=0, le=1440)
    sleep_score: int | None = Field(default=None, ge=0, le=100)


class WearableSleepRead(WearableSleepBase, TimestampMixin):
    sleep_id: uuid.UUID
    user_id: uuid.UUID
    raw_s3_key: str | None = None


# ---------- Wearable Activities ----------

class WearableActivityBase(VitalisBase):
    activity_date: date
    source: str
    source_activity_id: str | None = None
    activity_type: str
    activity_name: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_seconds: int | None = Field(default=None, ge=0)
    distance_m: Decimal | None = None
    calories_kcal: int | None = None
    avg_hr_bpm: int | None = Field(default=None, ge=20, le=300)
    max_hr_bpm: int | None = None
    hr_zone_1_seconds: int | None = None
    hr_zone_2_seconds: int | None = None
    hr_zone_3_seconds: int | None = None
    hr_zone_4_seconds: int | None = None
    hr_zone_5_seconds: int | None = None
    avg_pace_sec_per_km: Decimal | None = None
    avg_speed_kmh: Decimal | None = None
    elevation_gain_m: Decimal | None = None
    avg_power_watts: int | None = None
    normalized_power_watts: int | None = None
    training_stress_score: Decimal | None = None
    training_effect_aerobic: Decimal | None = Field(default=None, ge=0, le=5)
    training_effect_anaerobic: Decimal | None = None
    vo2_max_ml_kg_min: Decimal | None = None
    notes: str | None = None


class WearableActivityCreate(WearableActivityBase):
    raw_data: dict[str, Any] | None = None


class WearableActivityRead(WearableActivityBase, TimestampMixin):
    activity_id: uuid.UUID
    user_id: uuid.UUID
    raw_s3_key: str | None = None
