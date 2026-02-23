"""Pydantic models for manual tracking: supplements, mood, measurements,
menstrual cycles, doctor visits, nutrition, custom metrics, photos, notifications."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import Field

from src.models.base import SoftDeleteMixin, TimestampMixin, VitalisBase


# ---------- Enums ----------

class MeasurementMetric(str, Enum):
    weight = "weight"
    body_fat_pct = "body_fat_pct"
    waist_circumference = "waist_circumference"
    hip_circumference = "hip_circumference"
    chest_circumference = "chest_circumference"
    neck_circumference = "neck_circumference"
    bicep_left = "bicep_left"
    bicep_right = "bicep_right"
    thigh_left = "thigh_left"
    thigh_right = "thigh_right"
    calf_left = "calf_left"
    calf_right = "calf_right"
    blood_pressure_systolic = "blood_pressure_systolic"
    blood_pressure_diastolic = "blood_pressure_diastolic"
    blood_glucose = "blood_glucose"
    body_temperature = "body_temperature"
    height = "height"


class MenstrualPhase(str, Enum):
    menstrual = "menstrual"
    follicular = "follicular"
    ovulatory = "ovulatory"
    luteal = "luteal"


class MealType(str, Enum):
    breakfast = "breakfast"
    lunch = "lunch"
    dinner = "dinner"
    snack = "snack"
    fast = "fast"
    other = "other"


class NotificationType(str, Enum):
    sync_success = "sync_success"
    sync_failure = "sync_failure"
    parse_complete = "parse_complete"
    goal_alert = "goal_alert"
    subscription = "subscription"
    system = "system"


# ---------- Supplements ----------

class SupplementBase(VitalisBase):
    name: str = Field(min_length=1)
    brand: str | None = None
    dose_amount: Decimal | None = Field(default=None, gt=0)
    dose_unit: str | None = None
    frequency: str | None = None
    timing: str | None = None
    started_at: date | None = None
    ended_at: date | None = None
    purpose: str | None = None
    notes: str | None = None


class SupplementCreate(SupplementBase):
    pass


class SupplementUpdate(VitalisBase):
    name: str | None = Field(default=None, min_length=1)
    brand: str | None = None
    dose_amount: Decimal | None = Field(default=None, gt=0)
    dose_unit: str | None = None
    frequency: str | None = None
    timing: str | None = None
    ended_at: date | None = None
    notes: str | None = None


class SupplementRead(SupplementBase, TimestampMixin, SoftDeleteMixin):
    supplement_id: uuid.UUID
    user_id: uuid.UUID


# ---------- Supplement Logs ----------

class SupplementLogCreate(VitalisBase):
    supplement_id: uuid.UUID
    taken_at: datetime
    dose_amount: Decimal | None = None
    dose_unit: str | None = None
    notes: str | None = None


class SupplementLogRead(VitalisBase):
    log_id: uuid.UUID
    supplement_id: uuid.UUID
    user_id: uuid.UUID
    taken_at: datetime
    dose_amount: Decimal | None = None
    dose_unit: str | None = None
    notes: str | None = None
    created_at: datetime


# ---------- Mood Journal ----------

class MoodJournalBase(VitalisBase):
    journal_date: date
    mood_score: int | None = Field(default=None, ge=1, le=5)
    energy_score: int | None = Field(default=None, ge=1, le=5)
    stress_score: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None


class MoodJournalCreate(MoodJournalBase):
    pass


class MoodJournalUpdate(VitalisBase):
    mood_score: int | None = Field(default=None, ge=1, le=5)
    energy_score: int | None = Field(default=None, ge=1, le=5)
    stress_score: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None


class MoodJournalRead(MoodJournalBase, TimestampMixin, SoftDeleteMixin):
    journal_id: uuid.UUID
    user_id: uuid.UUID


# ---------- Measurements ----------

class MeasurementBase(VitalisBase):
    metric: MeasurementMetric
    value: Decimal
    unit: str
    measured_at: datetime
    source: str = "manual"
    notes: str | None = None


class MeasurementCreate(MeasurementBase):
    pass


class MeasurementUpdate(VitalisBase):
    value: Decimal | None = None
    unit: str | None = None
    notes: str | None = None


class MeasurementRead(MeasurementBase, TimestampMixin, SoftDeleteMixin):
    measurement_id: uuid.UUID
    user_id: uuid.UUID


# ---------- Menstrual Cycles ----------

class MenstrualCycleBase(VitalisBase):
    cycle_date: date
    phase: MenstrualPhase | None = None
    flow_intensity: int | None = Field(default=None, ge=0, le=4)
    symptoms: list[str] = Field(default_factory=list)
    notes: str | None = None


class MenstrualCycleCreate(MenstrualCycleBase):
    pass


class MenstrualCycleRead(MenstrualCycleBase):
    cycle_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime


# ---------- Doctor Visits ----------

class DoctorVisitBase(VitalisBase):
    visit_date: date
    provider_name: str | None = None
    specialty: str | None = None
    notes: str | None = None
    follow_up_date: date | None = None


class DoctorVisitCreate(DoctorVisitBase):
    pass


class DoctorVisitUpdate(VitalisBase):
    provider_name: str | None = None
    specialty: str | None = None
    notes: str | None = None
    follow_up_date: date | None = None


class DoctorVisitRead(DoctorVisitBase, TimestampMixin, SoftDeleteMixin):
    visit_id: uuid.UUID
    user_id: uuid.UUID


# ---------- Nutrition Logs ----------

class NutritionLogBase(VitalisBase):
    log_date: date
    meal_type: MealType | None = None
    calories_kcal: int | None = Field(default=None, ge=0)
    protein_g: Decimal | None = None
    carbs_g: Decimal | None = None
    fat_g: Decimal | None = None
    fiber_g: Decimal | None = None
    source: str = "manual"


class NutritionLogCreate(NutritionLogBase):
    raw_data: dict[str, Any] | None = None


class NutritionLogUpdate(VitalisBase):
    meal_type: MealType | None = None
    calories_kcal: int | None = Field(default=None, ge=0)
    protein_g: Decimal | None = None
    carbs_g: Decimal | None = None
    fat_g: Decimal | None = None
    fiber_g: Decimal | None = None


class NutritionLogRead(NutritionLogBase, TimestampMixin, SoftDeleteMixin):
    nutrition_id: uuid.UUID
    user_id: uuid.UUID


# ---------- Custom Metrics ----------

class CustomMetricBase(VitalisBase):
    name: str = Field(min_length=1)
    unit: str | None = None
    data_type: str = "numeric"  # numeric, boolean, text, scale_1_5
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    is_active: bool = True


class CustomMetricCreate(CustomMetricBase):
    pass


class CustomMetricUpdate(VitalisBase):
    name: str | None = Field(default=None, min_length=1)
    unit: str | None = None
    is_active: bool | None = None


class CustomMetricRead(CustomMetricBase):
    metric_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime


class CustomMetricEntryCreate(VitalisBase):
    metric_id: uuid.UUID
    value_numeric: Decimal | None = None
    value_text: str | None = None
    measured_at: datetime
    notes: str | None = None


class CustomMetricEntryRead(VitalisBase):
    entry_id: uuid.UUID
    metric_id: uuid.UUID
    user_id: uuid.UUID
    value_numeric: Decimal | None = None
    value_text: str | None = None
    measured_at: datetime
    notes: str | None = None
    created_at: datetime


# ---------- Photos ----------

class PhotoBase(VitalisBase):
    photo_date: date
    photo_type: str = "other"
    notes: str | None = None
    linked_scan_id: uuid.UUID | None = None


class PhotoCreate(PhotoBase):
    s3_key: str
    s3_thumbnail_key: str | None = None
    file_size_bytes: int = Field(gt=0)


class PhotoRead(PhotoBase, SoftDeleteMixin):
    photo_id: uuid.UUID
    user_id: uuid.UUID
    s3_key: str
    s3_thumbnail_key: str | None = None
    file_size_bytes: int
    created_at: datetime


# ---------- Notifications ----------

class NotificationRead(VitalisBase):
    notification_id: uuid.UUID
    user_id: uuid.UUID
    notification_type: NotificationType
    title: str
    body: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    is_read: bool = False
    read_at: datetime | None = None
    created_at: datetime
    expires_at: datetime | None = None
