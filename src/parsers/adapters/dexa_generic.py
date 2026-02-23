"""Generic DEXA scan parser — fallback for Hologic, GE Lunar, and hospital formats.

Hospital and clinic DEXA reports (produced by Hologic Horizon, GE Lunar
Prodigy, Norland, etc.) vary widely in layout and terminology.  This adapter
uses a liberal set of patterns to extract the most common DEXA metrics
without relying on specific brand formatting.

Detection strategy:
  - Looks for DEXA-specific vocabulary: "bone mineral density", "t-score",
    "z-score", "lean mass", "fat mass", "body composition", "dual-energy",
    "dxa", "dexa".
  - Returns True for any document that plausibly contains DEXA output.

Because this is a catch-all, it is registered at priority 40 — after the
specific DexaFit (20) and BodySpec (21) parsers.

Unit handling:
  - Reports from US machines are usually in lbs; metric machines use kg.
  - The adapter detects the unit on each line and converts to grams.
  - BMD is always in g/cm² regardless of machine locale.
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

logger = logging.getLogger("vitalis.parsers.dexa_generic")

_LBS_TO_G: float = 453.59237
_KG_TO_G: float = 1_000.0


def _to_grams(value: float, unit: str) -> float:
    """Convert *value* to grams based on detected *unit* string."""
    u = unit.lower().strip()
    if "kg" in u:
        return round(value * _KG_TO_G, 2)
    if "lb" in u:
        return round(value * _LBS_TO_G, 2)
    if "g" in u:
        return round(value, 2)
    # Default: assume grams
    return round(value, 2)


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

_DETECT_PATTERNS: list[re.Pattern] = [
    re.compile(r"bone\s+mineral\s+density", re.IGNORECASE),
    re.compile(r"t[‐\-]score", re.IGNORECASE),
    re.compile(r"dual[‐\-]energy\s+x[‐\-]ray", re.IGNORECASE),
    re.compile(r"\bDXA\b|\bDEXA\b", re.IGNORECASE),
    re.compile(r"hologic", re.IGNORECASE),
    re.compile(r"ge\s+lunar", re.IGNORECASE),
    re.compile(r"body\s+composition\s+analysis", re.IGNORECASE),
]

# Require at least 2 DEXA signals before claiming ownership
_MIN_SIGNAL_COUNT = 2

# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(
    r"(?:scan\s+date|date\s+of\s+exam|exam\s+date|study\s+date)\s*[:\-]?\s*"
    r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
    re.IGNORECASE,
)
_DATE_LONG_RE = re.compile(
    r"(?:january|february|march|april|may|june|july|august|"
    r"september|october|november|december)\s+\d{1,2},?\s+\d{4}",
    re.IGNORECASE,
)
_PATIENT_RE = re.compile(
    r"(?:patient|name|subject)\s*[:\-]?\s*"
    r"([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)+)",
    re.IGNORECASE,
)
_FACILITY_RE = re.compile(
    r"(?:facility|site|location|institution)\s*[:\-]?\s*(.+?)(?:\n|$)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Liberal body-composition patterns
# ---------------------------------------------------------------------------

_FAT_PCT_RE = re.compile(
    r"(?:total\s+)?(?:body\s+)?fat\s+%\s*[:\-]?\s*(\d+\.?\d*)\s*%?",
    re.IGNORECASE,
)
_FAT_MASS_RE = re.compile(
    r"fat\s+(?:mass|tissue)\s*[:\-]?\s*(\d+\.?\d*)\s*(lbs?|kg|g)\b",
    re.IGNORECASE,
)
_LEAN_MASS_RE = re.compile(
    r"lean\s+(?:mass|tissue)\s*[:\-]?\s*(\d+\.?\d*)\s*(lbs?|kg|g)\b",
    re.IGNORECASE,
)
_BMC_RE = re.compile(
    r"(?:bone\s+mineral\s+content|bmc)\s*[:\-]?\s*(\d+\.?\d*)\s*(lbs?|kg|g)\b",
    re.IGNORECASE,
)
_TOTAL_MASS_RE = re.compile(
    r"total\s+(?:mass|weight)\s*[:\-]?\s*(\d+\.?\d*)\s*(lbs?|kg|g)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# VAT patterns
# ---------------------------------------------------------------------------

_VAT_MASS_RE = re.compile(
    r"visceral\s+(?:adipose\s+)?(?:tissue\s+|fat\s+)?(?:mass)?\s*[:\-]?\s*"
    r"(\d+\.?\d*)\s*(lbs?|kg|g)\b",
    re.IGNORECASE,
)
_VAT_VOL_RE = re.compile(
    r"visceral\s+(?:adipose\s+)?(?:tissue\s+|fat\s+)?(?:vol(?:ume)?)?\s*[:\-]?\s*"
    r"(\d+\.?\d*)\s*cm[³3]?",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Android / Gynoid
# ---------------------------------------------------------------------------

_ANDROID_RE = re.compile(r"android\s*[:\-]?\s*(\d+\.?\d*)\s*%", re.IGNORECASE)
_GYNOID_RE = re.compile(r"gynoid\s*[:\-]?\s*(\d+\.?\d*)\s*%", re.IGNORECASE)
_AG_RATIO_RE = re.compile(
    r"(?:a(?:ndroid)?\s*/\s*g(?:ynoid)?|a\s*:\s*g)\s*ratio\s*[:\-]?\s*(\d+\.?\d*)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Regional table — very liberal matching
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
    "arms": "arms",
    "legs": "legs",
    "pelvis": "trunk",
    "ribs": "trunk",
    "spine region": "lumbar_spine",
}

_REGION_ROW_RE = re.compile(
    r"^(?P<region>(?:left|right)\s+(?:arm|leg)|trunk|android|gynoid|head|"
    r"total|arms|legs|pelvis|ribs)\s+"
    r"(?P<fat_pct>\d+\.?\d*)\s*%\s+"
    r"(?P<fat>\d+\.?\d*)\s+(?P<fat_unit>lbs?|kg|g)\s+"
    r"(?P<lean>\d+\.?\d*)\s+(?P<lean_unit>lbs?|kg|g)"
    r"(?:\s+(?P<total>\d+\.?\d*)\s+(?P<total_unit>lbs?|kg|g))?",
    re.IGNORECASE,
)

# Alternative: fat and lean without explicit unit on each column
_REGION_ROW_UNITLESS_RE = re.compile(
    r"^(?P<region>(?:left|right)\s+(?:arm|leg)|trunk|android|gynoid|head|"
    r"total|arms|legs)\s+"
    r"(?P<fat_pct>\d+\.?\d*)\s*%\s+"
    r"(?P<fat>\d+\.?\d*)\s+"
    r"(?P<lean>\d+\.?\d*)"
    r"(?:\s+(?P<bmc>\d+\.?\d*))?"
    r"(?:\s+(?P<total>\d+\.?\d*))?",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Bone density table
# ---------------------------------------------------------------------------

_BONE_SITE_MAP: dict[str, str] = {
    "lumbar spine": "lumbar_spine",
    "lumbar": "lumbar_spine",
    "l1-l4": "lumbar_spine",
    "l1 l4": "lumbar_spine",
    "total spine": "lumbar_spine",
    "spine": "lumbar_spine",
    "femoral neck": "femoral_neck",
    "neck": "femoral_neck",
    "total hip": "total_hip",
    "hip": "total_hip",
    "forearm": "forearm",
    "radius": "forearm",
    "total body": "total_body",
    "whole body": "total_body",
}

_BONE_ROW_RE = re.compile(
    r"^(?P<site>(?:lumbar|total)\s+spine|l1[-–]l4|l1\s+l4|"
    r"femoral(?:\s+neck)?|total\s+hip|total\s+body|whole\s+body|"
    r"forearm|radius|spine|hip|neck)\s+"
    r"(?P<bmd>\d+\.\d+)"
    r"(?:\s+(?P<t_score>[-+]?\d+\.?\d*))?"
    r"(?:\s+(?P<z_score>[-+]?\d+\.?\d*))?",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Parser class
# ---------------------------------------------------------------------------


class DexaGenericParser(BaseParser):
    """Generic fallback parser for Hologic, GE Lunar, and unknown DEXA formats."""

    PARSER_ID = "dexa_generic_v1"
    PRIORITY = 40
    LAB_NAME = "DEXA (Generic)"

    def can_parse(self, text: str, filename: str = "") -> bool:
        """Return True if the document contains sufficient DEXA vocabulary."""
        # Filename hint
        name_lower = filename.lower()
        if any(k in name_lower for k in ("dexa", "dxa", "bone_density", "body_comp")):
            return True
        sample = text[:5000]
        signals = sum(1 for p in _DETECT_PATTERNS if p.search(sample))
        return signals >= _MIN_SIGNAL_COUNT

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
            lab_name=structured.facility or "DEXA Scan",
            markers=markers,
            warnings=structured.warnings,
            needs_review=structured.needs_review,
            parse_time_ms=int((time.monotonic() - t0) * 1000),
            error=structured.error,
        )

    def parse_structured(self, text: str) -> DexaParseResult:
        """Parse a generic DEXA report and return a ``DexaParseResult``."""
        t0 = time.monotonic()
        warnings: list[str] = []

        try:
            scan_date = _extract_date(text)
            patient_name = _extract_patient_name(text)
            facility = _extract_facility(text)

            fat_pct = _find_float_any(_FAT_PCT_RE, text)
            fat_mass_raw = _find_float_unit(_FAT_MASS_RE, text)
            lean_mass_raw = _find_float_unit(_LEAN_MASS_RE, text)
            bmc_raw = _find_float_unit(_BMC_RE, text)
            total_raw = _find_float_unit(_TOTAL_MASS_RE, text)
            vat_mass_raw = _find_float_unit(_VAT_MASS_RE, text)
            vat_vol = _find_float_any(_VAT_VOL_RE, text)

            android_pct = _find_float_any(_ANDROID_RE, text)
            gynoid_pct = _find_float_any(_GYNOID_RE, text)
            ag_ratio = _find_float_any(_AG_RATIO_RE, text)
            if ag_ratio is None and android_pct and gynoid_pct and gynoid_pct != 0:
                ag_ratio = round(android_pct / gynoid_pct, 3)

            regions = _parse_regions(text)
            bone_density = _parse_bone_density(text)
            alm_g = _compute_alm(regions)

            # Detect format string
            format_str = _detect_format_name(text)

            key_fields = [fat_pct, fat_mass_raw, lean_mass_raw, total_raw]
            filled = sum(1 for f in key_fields if f is not None)
            # Generic parser has lower baseline confidence
            raw_conf = 0.30 + (filled / len(key_fields)) * 0.40
            if regions:
                raw_conf = min(raw_conf + 0.08, 0.85)
            if bone_density:
                raw_conf = min(raw_conf + 0.08, 0.88)
            confidence = ConfidenceLevel.from_score(raw_conf)
            needs_review = confidence in (ConfidenceLevel.LOW, ConfidenceLevel.UNCERTAIN)

            if fat_pct is None and fat_mass_raw is None:
                warnings.append("No body fat data found — verify this is a DEXA report")

            result = DexaParseResult(
                success=True,
                parser_used=self.PARSER_ID,
                format_detected=format_str,
                confidence=confidence,
                scan_date=scan_date,
                patient_name=patient_name,
                facility=facility,
                total_body_fat_pct=fat_pct,
                total_fat_mass_g=(
                    _to_grams(fat_mass_raw[0], fat_mass_raw[1])
                    if fat_mass_raw else None
                ),
                total_lean_mass_g=(
                    _to_grams(lean_mass_raw[0], lean_mass_raw[1])
                    if lean_mass_raw else None
                ),
                total_bmc_g=(
                    _to_grams(bmc_raw[0], bmc_raw[1])
                    if bmc_raw else None
                ),
                total_mass_g=(
                    _to_grams(total_raw[0], total_raw[1])
                    if total_raw else None
                ),
                vat_mass_g=(
                    _to_grams(vat_mass_raw[0], vat_mass_raw[1])
                    if vat_mass_raw else None
                ),
                vat_volume_cm3=vat_vol,
                android_gynoid_ratio=ag_ratio,
                appendicular_lean_mass_g=alm_g,
                regions=regions,
                bone_density=bone_density,
                warnings=warnings,
                needs_review=needs_review,
                parse_time_ms=int((time.monotonic() - t0) * 1000),
            )

        except Exception as exc:
            logger.exception("DexaGenericParser raised during parse: %s", exc)
            result = DexaParseResult(
                success=False,
                parser_used=self.PARSER_ID,
                format_detected="DEXA Scan (Generic)",
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


def _find_float_any(pattern: re.Pattern, text: str) -> float | None:
    """Return the first captured float group from *pattern*."""
    m = pattern.search(text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except (ValueError, IndexError):
            pass
    return None


def _find_float_unit(
    pattern: re.Pattern, text: str
) -> tuple[float, str] | None:
    """Return (value, unit_str) for a pattern with two capture groups."""
    m = pattern.search(text)
    if m:
        try:
            return float(m.group(1).replace(",", "")), m.group(2)
        except (ValueError, IndexError):
            pass
    return None


def _detect_format_name(text: str) -> str:
    """Return a human-readable format name based on brand signals."""
    sample = text[:3000].lower()
    if "hologic" in sample:
        return "Hologic DEXA Body Composition"
    if "ge lunar" in sample or "lunar prodigy" in sample:
        return "GE Lunar DEXA Body Composition"
    if "norland" in sample:
        return "Norland DEXA Body Composition"
    return "DEXA Body Composition (Generic)"


def _extract_date(text: str) -> date | None:
    m = _DATE_LONG_RE.search(text[:3000])
    if m:
        raw = m.group(0)
        for fmt in ("%B %d, %Y", "%B %d %Y"):
            try:
                return datetime.strptime(raw.strip(), fmt).date()
            except ValueError:
                continue
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


def _extract_facility(text: str) -> str | None:
    m = _FACILITY_RE.search(text[:3000])
    if m:
        fac = m.group(1).strip()
        if 3 < len(fac) < 80:
            return fac
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

        # Try unit-explicit pattern first
        m = _REGION_ROW_RE.match(line)
        if m:
            raw = m.group("region").lower().strip()
            canonical = _REGION_MAP.get(raw)
            if canonical and canonical not in seen:
                seen.add(canonical)
                fat = _safe_float(m.group("fat"))
                lean = _safe_float(m.group("lean"))
                total = _safe_float(m.group("total")) if m.group("total") else None
                results.append(
                    DexaRegionResult(
                        region=canonical,
                        fat_pct=_safe_float(m.group("fat_pct")),
                        fat_mass_g=_to_grams(fat, m.group("fat_unit")) if fat else None,
                        lean_mass_g=_to_grams(lean, m.group("lean_unit")) if lean else None,
                        total_mass_g=(
                            _to_grams(total, m.group("total_unit"))
                            if total and m.group("total_unit") else None
                        ),
                        confidence=0.78,
                    )
                )
            continue

        # Unitless fallback
        m = _REGION_ROW_UNITLESS_RE.match(line)
        if m:
            raw = m.group("region").lower().strip()
            canonical = _REGION_MAP.get(raw)
            if canonical and canonical not in seen:
                seen.add(canonical)
                fat = _safe_float(m.group("fat"))
                lean = _safe_float(m.group("lean"))
                bmc = _safe_float(m.group("bmc")) if m.group("bmc") else None
                total = _safe_float(m.group("total")) if m.group("total") else None
                # Can't determine unit — store as-is with warning baked in
                results.append(
                    DexaRegionResult(
                        region=canonical,
                        fat_pct=_safe_float(m.group("fat_pct")),
                        fat_mass_g=_lbs_to_g(fat) if fat else None,
                        lean_mass_g=_lbs_to_g(lean) if lean else None,
                        bmc_g=_lbs_to_g(bmc) if bmc else None,
                        total_mass_g=_lbs_to_g(total) if total else None,
                        confidence=0.65,
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
            if key in raw_site or raw_site.startswith(key[:4]):
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
                confidence=0.80,
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
    ("vat_mass_g", "vat_mass", "Visceral Adipose Tissue Mass", "g"),
    ("vat_volume_cm3", "vat_volume", "Visceral Adipose Tissue Volume", "cm³"),
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
                confidence=result.confidence.value != "uncertain" and 0.80 or 0.50,
                confidence_reasons=["DEXA scan generic extraction"],
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
                    confidence=0.80,
                    confidence_reasons=["DEXA scan generic extraction"],
                    page=1,
                )
            )
    return markers
