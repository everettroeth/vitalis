"""DexaFit DEXA body-composition scan parser.

DexaFit is the largest consumer DEXA scan provider in the US.  Their
standardised PDF reports produced by pdfplumber share a consistent layout:

  Header:  "DexaFit" brand, patient info block (name, date, age, height,
           weight, BMI).
  Section 1 — Total Body Composition:  fat %, fat mass (lbs), lean mass
           (lbs), BMC (lbs), total mass (lbs).
  Section 2 — Visceral Adipose Tissue: VAT mass (lbs), VAT volume (cm³).
  Section 3 — Android / Gynoid:  android fat %, gynoid fat %, A/G ratio.
  Section 4 — Regional Breakdown (table):  Left Arm, Right Arm, Left Leg,
           Right Leg, Trunk, Android, Gynoid — each with fat %, fat (lbs),
           lean (lbs), BMC (lbs), total (lbs).
  Section 5 — Bone Mineral Density (table):  Lumbar Spine, Femoral Neck,
           Total Hip — each with BMD (g/cm²), T-Score, Z-Score.

All mass values in DexaFit reports are in **lbs**.  This adapter converts
them to **grams** (1 lb = 453.59237 g) for the canonical ``DexaParseResult``
model.

The adapter also implements the standard ``BaseParser`` interface so it
integrates with the routing registry and returns a flat ``ParseResult``
alongside the richer ``DexaParseResult``.
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

logger = logging.getLogger("vitalis.parsers.dexafit")

# ---------------------------------------------------------------------------
# Unit conversion
# ---------------------------------------------------------------------------

_LBS_TO_G: float = 453.59237


def _lbs_to_g(lbs: float) -> float:
    return round(lbs * _LBS_TO_G, 2)


# ---------------------------------------------------------------------------
# Format detection patterns
# ---------------------------------------------------------------------------

_DETECT_PATTERNS: list[re.Pattern] = [
    re.compile(r"dexafit", re.IGNORECASE),
    re.compile(r"dexa\s*fit", re.IGNORECASE),
    re.compile(r"dexafit\.com", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Metadata patterns
# ---------------------------------------------------------------------------

_DATE_PATTERNS: list[re.Pattern] = [
    re.compile(
        r"(?:scan\s+date|date)\s*[:\-]?\s*"
        r"(\w+\s+\d{1,2},?\s+\d{4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:scan\s+date|date)\s*[:\-]?\s*"
        r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:january|february|march|april|may|june|july|august|september|"
        r"october|november|december)\s+\d{1,2},?\s+\d{4}",
        re.IGNORECASE,
    ),
]

_PATIENT_RE = re.compile(
    r"(?:name|patient|client)\s*[:\-]?\s*"
    r"([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)+)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Total body composition patterns
# ---------------------------------------------------------------------------

_TOTAL_FAT_PCT_RE = re.compile(
    r"total\s+body\s+fat\s*%?\s*[:\-]?\s*(\d+\.?\d*)\s*%",
    re.IGNORECASE,
)
_FAT_MASS_LBS_RE = re.compile(
    r"(?:total\s+)?fat\s+mass\s*[:\-]?\s*(\d+\.?\d*)\s*lbs?",
    re.IGNORECASE,
)
_LEAN_MASS_LBS_RE = re.compile(
    r"lean\s+mass\s*[:\-]?\s*(\d+\.?\d*)\s*lbs?",
    re.IGNORECASE,
)
_BMC_LBS_RE = re.compile(
    r"(?:bone\s+mineral\s+content|bmc)\s*[\(\)a-z\s]*[:\-]?\s*(\d+\.?\d*)\s*lbs?",
    re.IGNORECASE,
)
_TOTAL_MASS_LBS_RE = re.compile(
    r"total\s+mass\s*[:\-]?\s*(\d+\.?\d*)\s*lbs?",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Visceral adipose tissue patterns
# ---------------------------------------------------------------------------

_VAT_MASS_RE = re.compile(
    r"(?:vat|visceral(?:\s+adipose)?(?:\s+tissue)?|visceral\s+fat)\s+"
    r"(?:mass)?\s*[:\-]?\s*(\d+\.?\d*)\s*lbs?",
    re.IGNORECASE,
)
_VAT_VOL_RE = re.compile(
    r"(?:vat|visceral(?:\s+adipose)?(?:\s+tissue)?|visceral\s+fat)\s+"
    r"(?:vol(?:ume)?)?\s*[:\-]?\s*(\d+\.?\d*)\s*cm[³3]",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Android / Gynoid patterns
# ---------------------------------------------------------------------------

_ANDROID_PCT_RE = re.compile(
    r"android\s+fat\s*%?\s*[:\-]?\s*(\d+\.?\d*)\s*%",
    re.IGNORECASE,
)
_GYNOID_PCT_RE = re.compile(
    r"gynoid\s+fat\s*%?\s*[:\-]?\s*(\d+\.?\d*)\s*%",
    re.IGNORECASE,
)
_AG_RATIO_RE = re.compile(
    r"(?:android\s*/\s*gynoid|a\s*/\s*g)\s*ratio\s*[:\-]?\s*(\d+\.?\d*)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Regional table row pattern
# Region  Fat%  Fat(lbs)  Lean(lbs)  BMC(lbs)  Total(lbs)
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
}

_REGION_ROW_RE = re.compile(
    r"^(?P<region>(?:left|right)\s+(?:arm|leg)|trunk|android|gynoid|head|total|arms|legs)"
    r"\s+"
    r"(?P<fat_pct>\d+\.?\d*)\s*%\s+"
    r"(?P<fat_lbs>\d+\.?\d*)\s+"
    r"(?P<lean_lbs>\d+\.?\d*)"
    r"(?:\s+(?P<bmc_lbs>\d+\.?\d*))?"
    r"(?:\s+(?P<total_lbs>\d+\.?\d*))?",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Bone density table row pattern
# Site  BMD(g/cm²)  T-Score  Z-Score
# ---------------------------------------------------------------------------

_BONE_SITE_MAP: dict[str, str] = {
    "lumbar spine": "lumbar_spine",
    "lumbar": "lumbar_spine",
    "l1-l4": "lumbar_spine",
    "l1 l4": "lumbar_spine",
    "femoral neck": "femoral_neck",
    "femoral": "femoral_neck",
    "total hip": "total_hip",
    "total body": "total_body",
    "forearm": "forearm",
    "radius": "forearm",
}

_BONE_ROW_RE = re.compile(
    r"^(?P<site>lumbar(?:\s+spine)?(?:\s+\([lL]1[-–][lL]4\))?|"
    r"femoral(?:\s+neck)?|total\s+hip|total\s+body|forearm|radius)"
    r"\s+"
    r"(?P<bmd>\d+\.\d+)"
    r"(?:\s+(?P<t_score>[-+]?\d+\.?\d*))?"
    r"(?:\s+(?P<z_score>[-+]?\d+\.?\d*))?",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Parser class
# ---------------------------------------------------------------------------


class DexaFitParser(BaseParser):
    """Parser for DexaFit body composition DEXA scan reports."""

    PARSER_ID = "dexafit_v1"
    PRIORITY = 20
    LAB_NAME = "DexaFit"

    # ------------------------------------------------------------------
    # BaseParser interface
    # ------------------------------------------------------------------

    def can_parse(self, text: str, filename: str = "") -> bool:
        """Return True if this document looks like a DexaFit report."""
        if "dexafit" in filename.lower():
            return True
        sample = text[:4000]
        return any(p.search(sample) for p in _DETECT_PATTERNS)

    def parse(self, text: str, file_bytes: bytes, filename: str = "") -> ParseResult:
        """Parse a DexaFit PDF and return a flat ``ParseResult``.

        The DEXA metrics are emitted as ``MarkerResult`` objects so the
        standard registry and database writer can handle them.  For the full
        structured result, call ``parse_structured()`` directly.
        """
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
            lab_name="DexaFit",
            markers=markers,
            warnings=structured.warnings,
            needs_review=structured.needs_review,
            parse_time_ms=int((time.monotonic() - t0) * 1000),
            error=structured.error,
        )

    # ------------------------------------------------------------------
    # Structured parse — primary entry point
    # ------------------------------------------------------------------

    def parse_structured(self, text: str) -> DexaParseResult:
        """Parse a DexaFit PDF and return a rich ``DexaParseResult``.

        Args:
            text: Full extracted PDF text from ``pdf_utils.extract_text``.

        Returns:
            ``DexaParseResult`` with all detected fields populated.
        """
        t0 = time.monotonic()
        warnings: list[str] = []

        try:
            scan_date = _extract_date(text)
            patient_name = _extract_patient_name(text)

            total_fat_pct = _find_float(_TOTAL_FAT_PCT_RE, text)
            fat_mass_lbs = _find_float(_FAT_MASS_LBS_RE, text)
            lean_mass_lbs = _find_float(_LEAN_MASS_LBS_RE, text)
            bmc_lbs = _find_float(_BMC_LBS_RE, text)
            total_mass_lbs = _find_float(_TOTAL_MASS_LBS_RE, text)

            vat_mass_lbs = _find_float(_VAT_MASS_RE, text)
            vat_vol_cm3 = _find_float(_VAT_VOL_RE, text)

            android_pct = _find_float(_ANDROID_PCT_RE, text)
            gynoid_pct = _find_float(_GYNOID_PCT_RE, text)
            ag_ratio = _find_float(_AG_RATIO_RE, text)

            # If A/G ratio not explicit, compute from android/gynoid pct
            if ag_ratio is None and android_pct and gynoid_pct and gynoid_pct != 0:
                ag_ratio = round(android_pct / gynoid_pct, 3)

            regions = _parse_regions(text)
            bone_density = _parse_bone_density(text)

            # Compute appendicular lean mass (arms + legs lean)
            alm_g = _compute_alm(regions)

            # Confidence: how many key fields did we get?
            key_fields = [
                total_fat_pct,
                fat_mass_lbs,
                lean_mass_lbs,
                total_mass_lbs,
            ]
            filled = sum(1 for f in key_fields if f is not None)
            raw_conf = 0.40 + (filled / len(key_fields)) * 0.50  # 0.40–0.90
            if regions:
                raw_conf = min(raw_conf + 0.05, 0.95)
            if bone_density:
                raw_conf = min(raw_conf + 0.05, 0.98)
            confidence = ConfidenceLevel.from_score(raw_conf)
            needs_review = confidence in (ConfidenceLevel.LOW, ConfidenceLevel.UNCERTAIN)

            if total_fat_pct is None:
                warnings.append("Total body fat % not found in report")
            if fat_mass_lbs is None and lean_mass_lbs is None:
                warnings.append("No mass measurements found — check PDF layout")

            result = DexaParseResult(
                success=True,
                parser_used=self.PARSER_ID,
                format_detected="DexaFit DEXA Body Composition",
                confidence=confidence,
                scan_date=scan_date,
                patient_name=patient_name,
                facility="DexaFit",
                total_body_fat_pct=total_fat_pct,
                total_fat_mass_g=_lbs_to_g(fat_mass_lbs) if fat_mass_lbs else None,
                total_lean_mass_g=_lbs_to_g(lean_mass_lbs) if lean_mass_lbs else None,
                total_bmc_g=_lbs_to_g(bmc_lbs) if bmc_lbs else None,
                total_mass_g=_lbs_to_g(total_mass_lbs) if total_mass_lbs else None,
                vat_mass_g=_lbs_to_g(vat_mass_lbs) if vat_mass_lbs else None,
                vat_volume_cm3=vat_vol_cm3,
                android_gynoid_ratio=ag_ratio,
                appendicular_lean_mass_g=alm_g,
                regions=regions,
                bone_density=bone_density,
                warnings=warnings,
                needs_review=needs_review,
                parse_time_ms=int((time.monotonic() - t0) * 1000),
            )

        except Exception as exc:
            logger.exception("DexaFitParser raised during parse: %s", exc)
            result = DexaParseResult(
                success=False,
                parser_used=self.PARSER_ID,
                format_detected="DexaFit DEXA Body Composition",
                confidence=ConfidenceLevel.UNCERTAIN,
                warnings=[f"Parser error: {exc}"],
                needs_review=True,
                parse_time_ms=int((time.monotonic() - t0) * 1000),
                error=str(exc),
            )

        return result


# ---------------------------------------------------------------------------
# Private extraction helpers
# ---------------------------------------------------------------------------


def _find_float(pattern: re.Pattern, text: str) -> float | None:
    """Return the first float captured by *pattern* in *text*, or None."""
    m = pattern.search(text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except (ValueError, IndexError):
            pass
    return None


def _extract_date(text: str) -> date | None:
    """Extract scan date from report text."""
    # Named month format: "January 15, 2024" or "January 15 2024"
    month_re = re.compile(
        r"(january|february|march|april|may|june|july|august|september|"
        r"october|november|december)\s+(\d{1,2}),?\s+(\d{4})",
        re.IGNORECASE,
    )
    m = month_re.search(text[:3000])
    if m:
        try:
            return datetime.strptime(
                f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y"
            ).date()
        except ValueError:
            pass

    # Numeric format: MM/DD/YYYY or MM-DD-YYYY
    for pat in _DATE_PATTERNS[1:]:
        m = pat.search(text[:3000])
        if m:
            raw = m.group(1) if m.lastindex else m.group(0)
            for fmt in ("%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(raw.strip(), fmt).date()
                except ValueError:
                    continue
    return None


def _extract_patient_name(text: str) -> str | None:
    """Extract patient / client name from header block."""
    m = _PATIENT_RE.search(text[:3000])
    if m:
        name = m.group(1).strip()
        # Filter out obvious false positives (facility names etc.)
        if len(name.split()) >= 2 and len(name) <= 60:
            return name
    return None


def _parse_regions(text: str) -> list[DexaRegionResult]:
    """Parse the regional body composition table."""
    results: list[DexaRegionResult] = []
    seen: set[str] = set()

    for line in text.splitlines():
        line = line.strip()
        m = _REGION_ROW_RE.match(line)
        if not m:
            continue

        raw_region = m.group("region").lower().strip()
        canonical = _REGION_MAP.get(raw_region)
        if canonical is None:
            # Try prefix match
            for key, val in _REGION_MAP.items():
                if raw_region.startswith(key[:4]):
                    canonical = val
                    break
        if canonical is None or canonical in seen:
            continue
        seen.add(canonical)

        fat_pct = _safe_float(m.group("fat_pct"))
        fat_lbs = _safe_float(m.group("fat_lbs"))
        lean_lbs = _safe_float(m.group("lean_lbs"))
        bmc_lbs = _safe_float(m.group("bmc_lbs")) if m.group("bmc_lbs") else None
        total_lbs = _safe_float(m.group("total_lbs")) if m.group("total_lbs") else None

        results.append(
            DexaRegionResult(
                region=canonical,
                fat_pct=fat_pct,
                fat_mass_g=_lbs_to_g(fat_lbs) if fat_lbs else None,
                lean_mass_g=_lbs_to_g(lean_lbs) if lean_lbs else None,
                bmc_g=_lbs_to_g(bmc_lbs) if bmc_lbs else None,
                total_mass_g=_lbs_to_g(total_lbs) if total_lbs else None,
                confidence=0.92,
            )
        )

    return results


def _parse_bone_density(text: str) -> list[DexaBoneDensityResult]:
    """Parse the bone mineral density table."""
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
                confidence=0.93,
            )
        )

    return results


def _compute_alm(regions: list[DexaRegionResult]) -> float | None:
    """Compute appendicular lean mass from regional data (arms + legs)."""
    arm_lean = sum(
        r.lean_mass_g
        for r in regions
        if r.region in ("left_arm", "right_arm") and r.lean_mass_g is not None
    )
    leg_lean = sum(
        r.lean_mass_g
        for r in regions
        if r.region in ("left_leg", "right_leg") and r.lean_mass_g is not None
    )
    if arm_lean == 0 and leg_lean == 0:
        return None
    return round(arm_lean + leg_lean, 2)


def _safe_float(text: str | None) -> float | None:
    if not text:
        return None
    try:
        return float(str(text).replace(",", "").strip())
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Convert DexaParseResult → flat list of MarkerResult
# ---------------------------------------------------------------------------

_DEXA_MARKER_DEFS: list[tuple[str, str, str, str]] = [
    # (field_attr, canonical_name, display_name, unit)
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
    """Convert a DexaParseResult into a flat list of MarkerResult objects."""
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

    # Emit bone density BMD values as markers
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
