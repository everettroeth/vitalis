"""Pydantic models for DEXA scans: scan header, regions, bone density."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import Field

from src.models.base import SoftDeleteMixin, TimestampMixin, VitalisBase


# ---------- Enums ----------

class DexaRegion(str, Enum):
    total = "total"
    arms = "arms"
    arm_right = "arm_right"
    arm_left = "arm_left"
    legs = "legs"
    leg_right = "leg_right"
    leg_left = "leg_left"
    trunk = "trunk"
    android = "android"
    gynoid = "gynoid"
    head = "head"


class BoneDensityRegion(str, Enum):
    total_body = "total_body"
    lumbar_spine = "lumbar_spine"
    left_hip = "left_hip"
    right_hip = "right_hip"
    femoral_neck = "femoral_neck"
    forearm = "forearm"


# ---------- DEXA Scans ----------

class DexaScanBase(VitalisBase):
    provider: str | None = None
    scan_date: date
    age_at_scan: Decimal | None = None
    height_in: Decimal | None = None
    height_cm: Decimal | None = None
    weight_lbs: Decimal | None = None
    weight_kg: Decimal | None = None
    total_mass_lbs: Decimal | None = None
    total_mass_kg: Decimal | None = None
    total_fat_lbs: Decimal | None = None
    total_fat_kg: Decimal | None = None
    total_lean_lbs: Decimal | None = None
    total_lean_kg: Decimal | None = None
    total_bmc_lbs: Decimal | None = None
    total_bmc_kg: Decimal | None = None
    total_body_fat_pct: Decimal | None = Field(default=None, ge=1, le=80)
    visceral_fat_lbs: Decimal | None = None
    visceral_fat_kg: Decimal | None = None
    visceral_fat_in3: Decimal | None = None
    visceral_fat_cm3: Decimal | None = None
    android_gynoid_ratio: Decimal | None = None
    document_id: uuid.UUID | None = None
    notes: str | None = None


class DexaScanCreate(DexaScanBase):
    pass


class DexaScanUpdate(VitalisBase):
    provider: str | None = None
    scan_date: date | None = None
    notes: str | None = None
    total_body_fat_pct: Decimal | None = Field(default=None, ge=1, le=80)
    total_fat_kg: Decimal | None = None
    total_lean_kg: Decimal | None = None


class DexaScanRead(DexaScanBase, TimestampMixin, SoftDeleteMixin):
    scan_id: uuid.UUID
    user_id: uuid.UUID


# ---------- DEXA Regions ----------

class DexaRegionBase(VitalisBase):
    scan_id: uuid.UUID
    region: DexaRegion
    body_fat_pct: Decimal | None = Field(default=None, ge=0, le=100)
    fat_lbs: Decimal | None = None
    lean_lbs: Decimal | None = None
    bmc_lbs: Decimal | None = None
    total_mass_lbs: Decimal | None = None


class DexaRegionCreate(DexaRegionBase):
    pass


class DexaRegionRead(DexaRegionBase):
    region_id: uuid.UUID
    user_id: uuid.UUID


# ---------- DEXA Bone Density ----------

class DexaBoneDensityBase(VitalisBase):
    scan_id: uuid.UUID
    region: BoneDensityRegion
    bmd_g_cm2: Decimal | None = Field(default=None, gt=0)
    t_score: Decimal | None = None
    z_score: Decimal | None = None


class DexaBoneDensityCreate(DexaBoneDensityBase):
    pass


class DexaBoneDensityRead(DexaBoneDensityBase):
    density_id: uuid.UUID
    user_id: uuid.UUID
