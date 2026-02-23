"""Pydantic models for epigenetic tests and organ ages."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import Field

from src.models.base import SoftDeleteMixin, TimestampMixin, VitalisBase


# ---------- Enums ----------

class OrganSystem(str, Enum):
    lung = "lung"
    metabolic = "metabolic"
    heart = "heart"
    liver = "liver"
    kidney = "kidney"
    brain = "brain"
    immune = "immune"
    musculoskeletal = "musculoskeletal"
    hormone = "hormone"
    blood = "blood"
    inflammation = "inflammation"
    skin = "skin"


class AgeDirection(str, Enum):
    younger = "younger"
    older = "older"
    same = "same"


# ---------- Epigenetic Tests ----------

class EpigeneticTestBase(VitalisBase):
    provider: str | None = None
    kit_id: str | None = None
    collected_at: date | None = None
    reported_at: date | None = None
    chronological_age: Decimal | None = Field(default=None, ge=0, le=120)
    biological_age: Decimal | None = Field(default=None, ge=0, le=120)
    pace_score: Decimal | None = Field(default=None, ge=Decimal("0.2"), le=Decimal("3.0"))
    pace_percentile: Decimal | None = Field(default=None, ge=0, le=100)
    telomere_length: Decimal | None = None
    methylation_clock: str | None = None
    document_id: uuid.UUID | None = None


class EpigeneticTestCreate(EpigeneticTestBase):
    raw_data: dict[str, Any] | None = None


class EpigeneticTestUpdate(VitalisBase):
    provider: str | None = None
    chronological_age: Decimal | None = Field(default=None, ge=0, le=120)
    biological_age: Decimal | None = Field(default=None, ge=0, le=120)
    pace_score: Decimal | None = Field(default=None, ge=Decimal("0.2"), le=Decimal("3.0"))
    notes: str | None = None


class EpigeneticTestRead(EpigeneticTestBase, TimestampMixin, SoftDeleteMixin):
    test_id: uuid.UUID
    user_id: uuid.UUID
    raw_data: dict[str, Any] | None = None


# ---------- Organ Ages ----------

class EpigeneticOrganAgeBase(VitalisBase):
    test_id: uuid.UUID
    organ_system: OrganSystem
    biological_age: Decimal
    direction: AgeDirection


class EpigeneticOrganAgeCreate(EpigeneticOrganAgeBase):
    pass


class EpigeneticOrganAgeRead(EpigeneticOrganAgeBase):
    organ_age_id: uuid.UUID
    user_id: uuid.UUID


class EpigeneticOrganAgeEnriched(EpigeneticOrganAgeRead):
    """Enriched view with computed delta from chronological age."""
    chronological_age: Decimal | None = None
    delta_years: Decimal | None = None
