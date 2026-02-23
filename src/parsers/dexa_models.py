"""Data models for DEXA body composition scan parse results.

These types are distinct from the standard ``ParseResult`` / ``MarkerResult``
used for blood labs.  DEXA reports expose rich regional and bone-density
structure that doesn't map cleanly to a flat marker list.

The ``DexaParseResult`` is the primary return type from DEXA adapters'
``parse_structured()`` method.  Each adapter also implements ``parse()``
(returning a flat ``ParseResult``) so the standard registry can route and
store DEXA documents alongside lab panels.

Unit conventions
----------------
All mass values are in **grams** (g).  Adapters converting from lbs should
use ``_LBS_TO_G = 453.59237``.  Volume is in cubic centimetres (cm³).
BMD is in g/cm².  Fat percent is stored as a float in the range [0, 100].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from src.parsers.base import ConfidenceLevel


# ---------------------------------------------------------------------------
# Region result
# ---------------------------------------------------------------------------


@dataclass
class DexaRegionResult:
    """Body composition measurements for a single anatomical region.

    Attributes:
        region:       Canonical region slug.  One of: ``"total"``,
                      ``"left_arm"``, ``"right_arm"``, ``"left_leg"``,
                      ``"right_leg"``, ``"trunk"``, ``"android"``,
                      ``"gynoid"``, ``"head"``.
        fat_pct:      Regional fat as a percent of regional total mass.
        fat_mass_g:   Fat mass in grams.
        lean_mass_g:  Lean (muscle + organ) mass in grams.
        bmc_g:        Bone mineral content in grams.
        total_mass_g: Sum of fat + lean + BMC for this region, in grams.
        confidence:   0.0–1.0 per-region extraction confidence.
    """

    region: str
    fat_pct: float | None = None
    fat_mass_g: float | None = None
    lean_mass_g: float | None = None
    bmc_g: float | None = None
    total_mass_g: float | None = None
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return {
            "region": self.region,
            "fat_pct": self.fat_pct,
            "fat_mass_g": self.fat_mass_g,
            "lean_mass_g": self.lean_mass_g,
            "bmc_g": self.bmc_g,
            "total_mass_g": self.total_mass_g,
            "confidence": round(self.confidence, 4),
        }


# ---------------------------------------------------------------------------
# Bone density result
# ---------------------------------------------------------------------------


@dataclass
class DexaBoneDensityResult:
    """Bone mineral density measurement for a single skeletal site.

    Attributes:
        site:       Canonical site slug.  One of: ``"lumbar_spine"``,
                    ``"femoral_neck"``, ``"total_hip"``, ``"forearm"``,
                    ``"total_body"``.
        bmd_g_cm2:  Bone mineral density in g/cm².
        t_score:    Comparison to peak young-adult bone density (SD units).
        z_score:    Comparison to age-matched reference (SD units).
        confidence: 0.0–1.0 per-site extraction confidence.
    """

    site: str
    bmd_g_cm2: float | None = None
    t_score: float | None = None
    z_score: float | None = None
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return {
            "site": self.site,
            "bmd_g_cm2": self.bmd_g_cm2,
            "t_score": self.t_score,
            "z_score": self.z_score,
            "confidence": round(self.confidence, 4),
        }


# ---------------------------------------------------------------------------
# Top-level DEXA parse result
# ---------------------------------------------------------------------------


@dataclass
class DexaParseResult:
    """Top-level result returned by any DEXA scan parser adapter.

    Attributes:
        success:         Whether parsing completed without a fatal error.
        parser_used:     Adapter identifier, e.g. ``"dexafit_v1"``.
        format_detected: Human-readable description of the detected format.
        confidence:      Overall extraction confidence.
        scan_date:       Date the scan was performed.
        patient_name:    Patient full name (PII — not stored server-side).
        facility:        Scanning facility name.

        total_body_fat_pct:        Whole-body fat as % of total mass.
        total_fat_mass_g:          Whole-body fat mass in grams.
        total_lean_mass_g:         Whole-body lean mass in grams.
        total_bmc_g:               Whole-body bone mineral content in grams.
        total_mass_g:              DEXA-measured total body mass in grams.

        vat_mass_g:                Visceral adipose tissue mass in grams.
        vat_volume_cm3:            Visceral adipose tissue volume in cm³.
        android_gynoid_ratio:      Android fat % / Gynoid fat %.
        fat_mass_index:            Fat mass (kg) / height² (m²).
        lean_mass_index:           Lean mass (kg) / height² (m²).
        appendicular_lean_mass_g:  Arms + legs lean mass (ALM) in grams.

        regions:      Regional body composition breakdown.
        bone_density: Bone mineral density by skeletal site.

        warnings:      Non-fatal issues encountered during parsing.
        needs_review:  True when confidence is LOW or UNCERTAIN.
        raw_text:      Full extracted PDF text (omitted from to_dict).
        parse_time_ms: Wall-clock parsing time.
        error:         Fatal error message if success is False.
    """

    success: bool
    parser_used: str
    format_detected: str
    confidence: ConfidenceLevel

    scan_date: date | None = None
    patient_name: str | None = None
    facility: str | None = None

    # Total body composition
    total_body_fat_pct: float | None = None
    total_fat_mass_g: float | None = None
    total_lean_mass_g: float | None = None
    total_bmc_g: float | None = None
    total_mass_g: float | None = None

    # Special metrics
    vat_mass_g: float | None = None
    vat_volume_cm3: float | None = None
    android_gynoid_ratio: float | None = None
    fat_mass_index: float | None = None
    lean_mass_index: float | None = None
    appendicular_lean_mass_g: float | None = None

    # Structured breakdowns
    regions: list[DexaRegionResult] = field(default_factory=list)
    bone_density: list[DexaBoneDensityResult] = field(default_factory=list)

    warnings: list[str] = field(default_factory=list)
    needs_review: bool = False
    raw_text: str = ""
    parse_time_ms: int = 0
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "parser_used": self.parser_used,
            "format_detected": self.format_detected,
            "confidence": self.confidence.value,
            "scan_date": self.scan_date.isoformat() if self.scan_date else None,
            "patient_name": self.patient_name,
            "facility": self.facility,
            "total_body_fat_pct": self.total_body_fat_pct,
            "total_fat_mass_g": self.total_fat_mass_g,
            "total_lean_mass_g": self.total_lean_mass_g,
            "total_bmc_g": self.total_bmc_g,
            "total_mass_g": self.total_mass_g,
            "vat_mass_g": self.vat_mass_g,
            "vat_volume_cm3": self.vat_volume_cm3,
            "android_gynoid_ratio": self.android_gynoid_ratio,
            "fat_mass_index": self.fat_mass_index,
            "lean_mass_index": self.lean_mass_index,
            "appendicular_lean_mass_g": self.appendicular_lean_mass_g,
            "regions": [r.to_dict() for r in self.regions],
            "bone_density": [b.to_dict() for b in self.bone_density],
            "warnings": self.warnings,
            "needs_review": self.needs_review,
            "parse_time_ms": self.parse_time_ms,
            "error": self.error,
            # raw_text intentionally omitted from default serialisation
        }
