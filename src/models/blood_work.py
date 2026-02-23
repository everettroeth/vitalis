"""Pydantic models for lab work: blood panels, markers, biomarker dictionary, ranges."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import Field

from src.models.base import SoftDeleteMixin, TimestampMixin, VitalisBase


# ---------- Enums ----------

class BiomarkerCategory(str, Enum):
    metabolic = "metabolic"
    lipids = "lipids"
    thyroid = "thyroid"
    hormones = "hormones"
    vitamins = "vitamins"
    minerals = "minerals"
    inflammation = "inflammation"
    liver = "liver"
    kidney = "kidney"
    cbc = "cbc"
    cardiac = "cardiac"
    immune = "immune"
    cancer_markers = "cancer_markers"
    other = "other"


class MarkerFlag(str, Enum):
    H = "H"
    L = "L"
    HH = "HH"
    LL = "LL"
    ABNORMAL = "ABNORMAL"
    CRITICAL = "CRITICAL"


# ---------- Biomarker Dictionary (read-only reference) ----------

class BiomarkerDictionaryRead(VitalisBase):
    biomarker_id: uuid.UUID
    canonical_name: str
    display_name: str
    category: BiomarkerCategory
    subcategory: str | None = None
    canonical_unit: str
    common_units: list[str] = Field(default_factory=list)
    loinc_code: str | None = None
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)
    sex_specific_ranges: bool = False
    optimal_low_male: Decimal | None = None
    optimal_high_male: Decimal | None = None
    optimal_low_female: Decimal | None = None
    optimal_high_female: Decimal | None = None
    optimal_low: Decimal | None = None
    optimal_high: Decimal | None = None
    normal_low: Decimal | None = None
    normal_high: Decimal | None = None
    is_qualitative: bool = False
    sort_order: int | None = None


# ---------- Biomarker Ranges ----------

class BiomarkerRangeRead(VitalisBase):
    range_id: uuid.UUID
    biomarker_id: uuid.UUID
    sex: str | None = None
    age_low: int | None = None
    age_high: int | None = None
    optimal_low: Decimal | None = None
    optimal_high: Decimal | None = None
    normal_low: Decimal | None = None
    normal_high: Decimal | None = None
    source: str | None = None


# ---------- Blood Panels ----------

class BloodPanelBase(VitalisBase):
    lab_name: str | None = None
    lab_provider: str | None = None
    panel_name: str | None = None
    collected_at: datetime | None = None
    reported_at: datetime | None = None
    fasting: bool | None = None
    specimen_id: str | None = None
    document_id: uuid.UUID | None = None
    notes: str | None = None


class BloodPanelCreate(BloodPanelBase):
    pass


class BloodPanelUpdate(VitalisBase):
    lab_name: str | None = None
    lab_provider: str | None = None
    panel_name: str | None = None
    collected_at: datetime | None = None
    fasting: bool | None = None
    notes: str | None = None


class BloodPanelRead(BloodPanelBase, TimestampMixin, SoftDeleteMixin):
    panel_id: uuid.UUID
    user_id: uuid.UUID


# ---------- Blood Markers ----------

class BloodMarkerBase(VitalisBase):
    panel_id: uuid.UUID
    biomarker_id: uuid.UUID | None = None
    collected_at: datetime | None = None
    raw_name: str
    sub_panel: str | None = None
    value_numeric: Decimal | None = None
    value_text: str | None = None
    unit: str | None = None
    value_canonical: Decimal | None = None
    ref_range_low: Decimal | None = None
    ref_range_high: Decimal | None = None
    ref_range_text: str | None = None
    flag: MarkerFlag | None = None
    in_range: bool | None = None
    optimal_low: Decimal | None = None
    optimal_high: Decimal | None = None
    lab_code: str | None = None
    parse_confidence: Decimal | None = Field(default=None, ge=0, le=1)


class BloodMarkerCreate(BloodMarkerBase):
    pass


class BloodMarkerUpdate(VitalisBase):
    biomarker_id: uuid.UUID | None = None
    value_numeric: Decimal | None = None
    value_text: str | None = None
    unit: str | None = None
    value_canonical: Decimal | None = None
    flag: MarkerFlag | None = None
    in_range: bool | None = None


class BloodMarkerRead(BloodMarkerBase, TimestampMixin):
    marker_id: uuid.UUID
    user_id: uuid.UUID
