"""Pydantic models for fitness: exercise dictionary, lifting sessions, sets."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from src.models.base import SoftDeleteMixin, TimestampMixin, VitalisBase


# ---------- Exercise Dictionary (read-only reference) ----------

class ExerciseDictionaryRead(VitalisBase):
    exercise_id: uuid.UUID
    canonical_name: str
    display_name: str
    aliases: list[str] = Field(default_factory=list)
    primary_muscle: str | None = None
    secondary_muscles: list[str] = Field(default_factory=list)
    equipment: str | None = None
    category: str | None = None
    created_at: datetime


# ---------- Lifting Sessions ----------

class LiftingSessionBase(VitalisBase):
    session_date: date
    source: str = "manual"
    source_session_id: str | None = None
    name: str | None = None
    duration_seconds: int | None = Field(default=None, ge=0, le=86400)
    notes: str | None = None


class LiftingSessionCreate(LiftingSessionBase):
    pass


class LiftingSessionUpdate(VitalisBase):
    name: str | None = None
    duration_seconds: int | None = Field(default=None, ge=0, le=86400)
    notes: str | None = None


class LiftingSessionRead(LiftingSessionBase, TimestampMixin, SoftDeleteMixin):
    session_id: uuid.UUID
    user_id: uuid.UUID


# ---------- Lifting Sets ----------

class LiftingSetBase(VitalisBase):
    session_id: uuid.UUID
    exercise_id: uuid.UUID | None = None
    raw_exercise_name: str | None = None
    exercise_order: int = Field(default=1, ge=1)
    set_number: int = Field(default=1, ge=1)
    weight_lbs: Decimal | None = Field(default=None, ge=0, le=2000)
    weight_kg: Decimal | None = Field(default=None, ge=0, le=910)
    reps: int = Field(ge=1, le=999)
    rpe: Decimal | None = Field(default=None, ge=0, le=10)
    is_warmup: bool = False
    notes: str | None = None


class LiftingSetCreate(LiftingSetBase):
    pass


class LiftingSetUpdate(VitalisBase):
    weight_lbs: Decimal | None = Field(default=None, ge=0, le=2000)
    weight_kg: Decimal | None = Field(default=None, ge=0, le=910)
    reps: int | None = Field(default=None, ge=1, le=999)
    rpe: Decimal | None = Field(default=None, ge=0, le=10)
    is_warmup: bool | None = None
    notes: str | None = None


class LiftingSetRead(LiftingSetBase):
    set_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
