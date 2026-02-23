"""BodySpec DEXA body-composition scan parser.

BodySpec is a mobile DEXA scanning service that visits gyms and corporate
wellness events.  Their PDF reports differ from DexaFit in several ways:

  - Branding as "BodySpec" or "bodyspec.com".
  - Summary page often includes a "Previous Scan" comparison column.
  - Regional table may omit the BMC column.
  - VAT may be labelled "Visceral Fat" rather than "VAT".
  - Bone density section uses "Total Spine" and "Femoral Neck" labels.
  - Date field is labelled "Scan Date: MM/DD/YYYY" in the header.

All mass values in BodySpec reports are in **lbs**.  This adapter converts
them to **grams** for the canonical ``DexaParseResult`` model.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime

from src.parsers.base import BaseParser, ConfidenceLevel, MarkerResult, ParseResult
from src.parsers.dexa_models import (
    DexaBoneDensityResult,
    DexaParseResult,
    DexaRegionResult,
)

logger = logging.getLogger("vitalis.parsers.bodyspec")

_LBS_TO_G: float = 453.59237


def _lbs_to_g(lbs: float) -> float:
    return round(lbs * _LBS_TO_G, 2)


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

_DETECT_PATTERNS: list[re.Pattern] = [
    re.compile(r"bodyspec", re.IGNORECASE),
    re.compile(r"body\s*spec", re.IGNORECASE),
    re.compile(r"bodyspec\.com", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(
    r"(?:scan\s+date|date)\s*[:\-]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
    re.IGNORECASE,
)
_DATE_LONG_RE = re.compile(
    r"(?:scan\s+date|date)\s*[:\-]?\s*"
    r"((?:january|february|march|april|may|june|july|august|september|"
    r"october|november|december)\s+\d{1,2},?\s+\d{4})",
    re.IGNORECASE,
)
_PATIENT_RE = re.compile(
    r"(?:client|name|patient)\s*[:\-]?\s*"
    r"([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)+)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Body composition — BodySpec labels the first data column directly
# ---------------------------------------------------------------------------

# BodySpec uses a 3-column table: Result | Previous | Change
# We capture just the first (current) numeric value on each row.
_FAT_PCT_RE = re.compile(
    r"body\s+fat\s*%?\s*[:\-]?\s*(\d+\.?\d*)\s*%",
    re.IGNORECASE,
)
_FAT_MASS_RE = re.compile(
    r"fat\s+mass\s*[:\-]?\s*(\d+\.?\d*)\s*lbs?",
    re.IGNORECASE,
)
_LEAN_MASS_RE = re.compile(
    r"lean\s+mass\s*[:\-]?\s*(\d+\.?\d*)\s*lbs?",
    re.IGNORECASE,
)
_BONE_MASS_RE = re.compile(
    r"(?:bone\s+mass|bmc|bone\s+mineral)\s*[:\-]?\s*(\d+\.?\d*)\s*lbs?",
    re.IGNORECASE,
)
_TOTAL_MASS_RE = re.compile(
    r"total\s*[:\-]?\s*(\d+\.?\d*)\s*lbs?",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Visceral fat — BodySpec uses "Visceral Fat Mass" and "Visceral Fat Vol"
# ---------------------------------------------------------------------------

_VF_MASS_RE = re.compile(
    r"visceral\s+fat\s+mass\s*[:\-]?\s*(\d+\.?\d*)\s*lbs?",
    re.IGNORECASE,
)
_VF_VOL_RE = re.compile(
    r"visceral\s+fat\s+vol(?:ume)?\s*[:\-]?\s*(\d+\.?\d*)\s*cm[³3]?",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Android / Gynoid
# ---------------------------------------------------------------------------

_ANDROID_RE = re.compile(r"android\s*[:\-]?\s*(\d+\.?\d*)\s*%", re.IGNORECASE)
_GYNOID_RE = re.compile(r"gynoid\s*[:\-]?\s*(\d+\.?\d*)\s*%", re.IGNORECASE)
_AG_RATIO_RE = re.compile(r"ratio\s*[:\-]?\s*(\d+\.?\d*)", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Regional table (BodySpec typically omits BMC column)
# Region  Fat%  Fat(lbs)  Lean(lbs)  Total(lbs)
# ---------------------------------------------------------------------------

_REGION_MAP: dict[str, str] = {
    "left arm": "left_arm",
    "right arm": "right_arm",
    "left leg": "left_leg",
    "right leg": "right_leg",
    "trunk": "trunk",
    "android": "android",
    "gynoid": "gynoid",
    "head": "head",
    "total": "total",
}

_REGION_ROW_RE = re.compile(
    r"^(?P<region>(?:left|right)\s+(?:arm|leg)|trunk|android|gynoid|head|total)"
    r"\s+"
    r"(?P<fat_pct>\d+\.?\d*)\s*%\s+"
    r"(?P<fat_lbs>\d+\.?\d*)\s+"
    r"(?P<lean_lbs>\d+\.?\d*)"
    r"(?:\s+(?P<total_lbs>\d+\.?\d*))?",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Bone density table
# Region  g/cm²  T-Score  Z-Score
# BodySpec uses "Total Spine" and "Femoral Neck"
# ---------------------------------------------------------------------------

_BONE_SITE_MAP: dict[str, str] = {
    "total spine": "lumbar_spine",
    "lumbar spine": "lumbar_spine",
    "lumbar": "lumbar_spine",
    "femoral neck": "femoral_neck",
    "total hip": "total_hip",
    "forearm": "forearm",
    "total body": "total_body",
}

_BONE_ROW_RE = re.compile(
    r"^(?P<site>total\s+spine|lumbar(?:\s+spine)?|femoral(?:\s+neck)?|"
    r"total\s+hip|total\s+body|forearm)"
    r"\s+"
    r"(?P<bmd>\d+\.\d+)"
    r"(?:\s+(?P<t_score>[-+]?\d+\.?\d*))?"
    r"(?:\s+(?P<z_score>[-+]?\d+\.?\d*))?",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Parser class
# ---------------------------------------------------------------------------


class BodySpecParser(BaseParser):
    """Parser for BodySpec DEXA body composition scan reports."""

    PARSER_ID = "bodyspec_v1"
    PRIORITY = 21
    LAB_NAME = "BodySpec"

    def can_parse(self, text: str, filename: str = "") -> bool:
        """Return True if this document looks like a BodySpec report."""
        if "bodyspec" in filename.lower():
            return True
        sample = text[:4000]
        return any(p.search(sample) for p in _DETECT_PATTERNS)

    def parse(self, text: str, file_bytes: bytes, filename: str = "") -> ParseResult:
        """Return a flat ``ParseResult`` for registry compatibility."""
        t0 = time.monotonic()
        structured = self.parse_structured(text)
        markers = _dexa_to_markers(structured)
        return ParseResult(
            success=structured.success,
            parser_used=self.PARSER_ID,
            format_detected=structured.format_detected,
            confidence=structured.confidence,
            patient_name=structured.patient_name,
            collection_date=structured.scan_date,
            lab_name="BodySpec",
            markers=markers,
            warnings=structured.warnings,
            needs_review=structured.needs_review,
            parse_time_ms=int((time.monotonic() - t0) * 1000),
            error=structured.error,
        )

    def parse_structured(self, text: str) -> DexaParseResult:
        """Parse a BodySpec PDF and return a rich ``DexaParseResult``."""
        t0 = time.monotonic()
        warnings: list[str] = []

        try:
            scan_date = _extract_date(text)
            patient_name = _extract_patient_name(text)

            fat_pct = _find_float(_FAT_PCT_RE, text)
            fat_lbs = _find_float(_FAT_MASS_RE, text)
            lean_lbs = _find_float(_LEAN_MASS_RE, text)
            bone_lbs = _find_float(_BONE_MASS_RE, text)
            total_lbs = _find_float(_TOTAL_MASS_RE, text)

            vf_mass_lbs = _find_float(_VF_MASS_RE, text)
            vf_vol = _find_float(_VF_VOL_RE, text)

            android_pct = _find_float(_ANDROID_RE, text)
            gynoid_pct = _find_float(_GYNOID_RE, text)
            ag_ratio = _find_float(_AG_RATIO_RE, text)
            if ag_ratio is None and android_pct and gynoid_pct and gynoid_pct != 0:
                ag_ratio = round(android_pct / gynoid_pct, 3)

            regions = _parse_regions(text)
            bone_density = _parse_bone_density(text)
            alm_g = _compute_alm(regions)

            key_fields = [fat_pct, fat_lbs, lean_lbs, total_lbs]
            filled = sum(1 for f in key_fields if f is not None)
            raw_conf = 0.40 + (filled / len(key_fields)) * 0.50
            if regions:
                raw_conf = min(raw_conf + 0.05, 0.95)
            if bone_density:
                raw_conf = min(raw_conf + 0.05, 0.98)
            confidence = ConfidenceLevel.from_score(raw_conf)
            needs_review = confidence in (ConfidenceLevel.LOW, ConfidenceLevel.UNCERTAIN)

            if fat_pct is None:
                warnings.append("Body fat % not found in report")

            result = DexaParseResult(
                success=True,
                parser_used=self.PARSER_ID,
                format_detected="BodySpec DEXA Body Composition",
                confidence=confidence,
                scan_date=scan_date,
                patient_name=patient_name,
                facility="BodySpec",
                total_body_fat_pct=fat_pct,
                total_fat_mass_g=_lbs_to_g(fat_lbs) if fat_lbs else None,
                total_lean_mass_g=_lbs_to_g(lean_lbs) if lean_lbs else None,
                total_bmc_g=_lbs_to_g(bone_lbs) if bone_lbs else None,
                total_mass_g=_lbs_to_g(total_lbs) if total_lbs else None,
                vat_mass_g=_lbs_to_g(vf_mass_lbs) if vf_mass_lbs else None,
                vat_volume_cm3=vf_vol,
                android_gynoid_ratio=ag_ratio,
                appendicular_lean_mass_g=alm_g,
                regions=regions,
                bone_density=bone_density,
                warnings=warnings,
                needs_review=needs_review,
                parse_time_ms=int((time.monotonic() - t0) * 1000),
            )

        except Exception as exc:
            logger.exception("BodySpecParser raised during parse: %s", exc)
            result = DexaParseResult(
                success=False,
                parser_used=self.PARSER_ID,
                format_detected="BodySpec DEXA Body Composition",
                confidence=ConfidenceLevel.UNCERTAIN,
                warnings=[f"Parser error: {exc}"],
                needs_review=True,
                parse_time_ms=int((time.monotonic() - t0) * 1000),
                error=str(exc),
            )

        return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _find_float(pattern: re.Pattern, text: str) -> float | None:
    m = pattern.search(text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except (ValueError, IndexError):
            pass
    return None


def _extract_date(text: str) -> date | None:
    # Try long month name first
    m = _DATE_LONG_RE.search(text[:3000])
    if m:
        raw = m.group(1)
        for fmt in ("%B %d, %Y", "%B %d %Y"):
            try:
                return datetime.strptime(raw.strip(), fmt).date()
            except ValueError:
                continue
    # Numeric
    m = _DATE_RE.search(text[:3000])
    if m:
        raw = m.group(1)
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw.strip(), fmt).date()
            except ValueError:
                continue
    return None


def _extract_patient_name(text: str) -> str | None:
    m = _PATIENT_RE.search(text[:3000])
    if m:
        name = m.group(1).strip()
        if len(name.split()) >= 2 and len(name) <= 60:
            return name
    return None


def _safe_float(text: str | None) -> float | None:
    if not text:
        return None
    try:
        return float(str(text).replace(",", "").strip())
    except ValueError:
        return None


def _parse_regions(text: str) -> list[DexaRegionResult]:
    results: list[DexaRegionResult] = []
    seen: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        m = _REGION_ROW_RE.match(line)
        if not m:
            continue
        raw = m.group("region").lower().strip()
        canonical = _REGION_MAP.get(raw)
        if canonical is None:
            for key, val in _REGION_MAP.items():
                if raw.startswith(key[:4]):
                    canonical = val
                    break
        if canonical is None or canonical in seen:
            continue
        seen.add(canonical)

        fat_pct = _safe_float(m.group("fat_pct"))
        fat_lbs = _safe_float(m.group("fat_lbs"))
        lean_lbs = _safe_float(m.group("lean_lbs"))
        total_lbs = _safe_float(m.group("total_lbs")) if m.group("total_lbs") else None

        results.append(
            DexaRegionResult(
                region=canonical,
                fat_pct=fat_pct,
                fat_mass_g=_lbs_to_g(fat_lbs) if fat_lbs else None,
                lean_mass_g=_lbs_to_g(lean_lbs) if lean_lbs else None,
                total_mass_g=_lbs_to_g(total_lbs) if total_lbs else None,
                confidence=0.91,
            )
        )
    return results


def _parse_bone_density(text: str) -> list[DexaBoneDensityResult]:
    results: list[DexaBoneDensityResult] = []
    seen: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        m = _BONE_ROW_RE.match(line)
        if not m:
            continue
        raw_site = m.group("site").lower().strip()
        canonical = None
        for key, val in _BONE_SITE_MAP.items():
            if key in raw_site:
                canonical = val
                break
        if canonical is None or canonical in seen:
            continue
        seen.add(canonical)

        bmd = _safe_float(m.group("bmd"))
        t_score = _safe_float(m.group("t_score")) if m.group("t_score") else None
        z_score = _safe_float(m.group("z_score")) if m.group("z_score") else None
        if bmd is None:
            continue

        results.append(
            DexaBoneDensityResult(
                site=canonical,
                bmd_g_cm2=bmd,
                t_score=t_score,
                z_score=z_score,
                confidence=0.92,
            )
        )
    return results


def _compute_alm(regions: list[DexaRegionResult]) -> float | None:
    arm = sum(
        r.lean_mass_g
        for r in regions
        if r.region in ("left_arm", "right_arm") and r.lean_mass_g is not None
    )
    leg = sum(
        r.lean_mass_g
        for r in regions
        if r.region in ("left_leg", "right_leg") and r.lean_mass_g is not None
    )
    if arm == 0 and leg == 0:
        return None
    return round(arm + leg, 2)


_DEXA_MARKER_DEFS: list[tuple[str, str, str, str]] = [
    ("total_body_fat_pct", "body_fat_pct", "Total Body Fat %", "%"),
    ("total_fat_mass_g", "fat_mass", "Fat Mass", "g"),
    ("total_lean_mass_g", "lean_mass", "Lean Mass", "g"),
    ("total_bmc_g", "bone_mineral_content", "Bone Mineral Content", "g"),
    ("total_mass_g", "total_body_mass", "Total Body Mass", "g"),
    ("vat_mass_g", "vat_mass", "Visceral Fat Mass", "g"),
    ("vat_volume_cm3", "vat_volume", "Visceral Fat Volume", "cm³"),
    ("android_gynoid_ratio", "android_gynoid_ratio", "Android/Gynoid Ratio", "ratio"),
    ("appendicular_lean_mass_g", "appendicular_lean_mass", "Appendicular Lean Mass", "g"),
]


def _dexa_to_markers(result: DexaParseResult) -> list[MarkerResult]:
    markers: list[MarkerResult] = []
    for attr, canonical, display, unit in _DEXA_MARKER_DEFS:
        value = getattr(result, attr, None)
        if value is None:
            continue
        markers.append(
            MarkerResult(
                canonical_name=canonical,
                display_name=display,
                value=float(value),
                value_text=str(round(float(value), 2)),
                unit=unit,
                canonical_unit=unit,
                confidence=0.90,
                confidence_reasons=["DEXA scan structured field"],
                page=1,
            )
        )
    for bd in result.bone_density:
        if bd.bmd_g_cm2 is not None:
            markers.append(
                MarkerResult(
                    canonical_name=f"bone_mineral_density_{bd.site}",
                    display_name=f"BMD — {bd.site.replace('_', ' ').title()}",
                    value=bd.bmd_g_cm2,
                    value_text=str(bd.bmd_g_cm2),
                    unit="g/cm²",
                    canonical_unit="g/cm²",
                    confidence=0.90,
                    confidence_reasons=["DEXA scan structured field"],
                    page=1,
                )
            )
    return markers
