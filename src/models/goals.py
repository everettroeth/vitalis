"""Pydantic models for goals, goal alerts, and insights."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import Field

from src.models.base import TimestampMixin, VitalisBase


# ---------- Enums ----------

class GoalDirection(str, Enum):
    minimize = "minimize"
    maximize = "maximize"
    target = "target"


class GoalMetricType(str, Enum):
    blood_marker = "blood_marker"
    measurement = "measurement"
    wearable = "wearable"
    custom = "custom"


class InsightType(str, Enum):
    correlation = "correlation"
    anomaly = "anomaly"
    trend = "trend"
    goal_progress = "goal_progress"
    recommendation = "recommendation"


# ---------- Goals ----------

class GoalBase(VitalisBase):
    metric_type: GoalMetricType
    biomarker_id: uuid.UUID | None = None
    metric_name: str
    target_value: Decimal | None = None
    target_unit: str | None = None
    direction: GoalDirection = GoalDirection.target
    alert_threshold_low: Decimal | None = None
    alert_threshold_high: Decimal | None = None
    alert_enabled: bool = True
    notes: str | None = None
    is_active: bool = True


class GoalCreate(GoalBase):
    pass


class GoalUpdate(VitalisBase):
    target_value: Decimal | None = None
    target_unit: str | None = None
    direction: GoalDirection | None = None
    alert_threshold_low: Decimal | None = None
    alert_threshold_high: Decimal | None = None
    alert_enabled: bool | None = None
    notes: str | None = None
    is_active: bool | None = None


class GoalRead(GoalBase, TimestampMixin):
    goal_id: uuid.UUID
    user_id: uuid.UUID


# ---------- Goal Alerts ----------

class GoalAlertRead(VitalisBase):
    alert_id: uuid.UUID
    goal_id: uuid.UUID
    user_id: uuid.UUID
    triggered_at: datetime
    trigger_value: Decimal | None = None
    message: str | None = None
    acknowledged_at: datetime | None = None


# ---------- Insights ----------

class InsightRead(VitalisBase):
    insight_id: uuid.UUID
    user_id: uuid.UUID
    insight_type: InsightType
    title: str
    body: str
    metric_a: str | None = None
    metric_b: str | None = None
    correlation_r: Decimal | None = None
    p_value: Decimal | None = None
    data_points: int | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    is_dismissed: bool = False
    dismissed_at: datetime | None = None
    created_at: datetime
