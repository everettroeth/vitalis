"""TruDiagnostic epigenetic aging test parser.

TruDiagnostic (trudiagnostic.com) is the largest consumer epigenetic testing
company.  Their TruAge™ Complete report includes:

  - Overall biological age (TruAge — a composite of multiple clocks)
  - Individual methylation clock ages: Horvath, Hannum, PhenoAge, GrimAge
  - DunedinPACE score (pace of aging rate — not an age estimate)
  - Organ-system biological ages: immune, cardiovascular, liver, kidney,
    brain, lung, metabolic, musculoskeletal, hormonal, blood, inflammatory
  - Telomere length (kb) and age-adjusted percentile

PDF layout (pdfplumber text extraction):
  - Page 1: Patient header + biological age summary + DunedinPACE
  - Page 2: Methylation clock breakdown
  - Page 3: Organ system ages table
  - Page 4: Telomere section (some reports)

Detection: "TruDiagnostic" OR "TruAge" must appear in the document.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime

from src.parsers.base import BaseParser, ConfidenceLevel, MarkerResult, ParseResult
from src.parsers.epi_models import (
    EpigeneticClockResult,
    EpigeneticParseResult,
    OrganAgeResult,
)

logger = logging.getLogger("vitalis.parsers.trudiagnostic")

# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

_DETECT_PATTERNS: list[re.Pattern] = [
    re.compile(r"trudiagnostic", re.IGNORECASE),
    re.compile(r"truage", re.IGNORECASE),
    re.compile(r"tru\s+age", re.IGNORECASE),
    re.compile(r"trudiagnostic\.com", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(
    r"(?:collection\s+date|date\s+of\s+collection|test\s+date|sample\s+date)"
    r"\s*[:\-]?\s*"
    r"((?:january|february|march|april|may|june|july|august|september|"
    r"october|november|december)\s+\d{1,2},?\s+\d{4}"
    r"|\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
    re.IGNORECASE,
)
_PATIENT_RE = re.compile(
    r"(?:patient\s+name|name|patient)\s*[:\-]?\s*"
    r"([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)+)",
    re.IGNORECASE,
)
_KIT_RE = re.compile(r"kit\s*(?:id|#|number)?\s*[:\-]?\s*([\w\-]+)", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Primary biological age
# ---------------------------------------------------------------------------

_TRUAGE_RE = re.compile(
    r"(?:your\s+truage|truage|biological\s+age)\s*(?:\([^)]*\))?\s*[:\-]?\s*(\d+\.?\d*)\s*years?",
    re.IGNORECASE,
)
_CHRON_AGE_RE = re.compile(
    r"chronological\s+age\s*[:\-]?\s*(\d+\.?\d*)\s*years?",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Individual methylation clocks
# Pattern: "<Clock Name>  XX.X years  <delta>"
# ---------------------------------------------------------------------------

_CLOCK_TABLE_ROW_RE = re.compile(
    r"^(?P<name>Horvath(?:\s+Clock)?|Hannum(?:\s+Clock)?|"
    r"PhenoAge|Pheno\s+Age|GrimAge|Grim\s+Age|DunedinPACE|Dunedin\s*PACE)"
    r"\s+"
    r"(?P<value>\d+\.?\d*)"
    r"(?:\s+years?)?",
    re.IGNORECASE,
)

# Standalone DunedinPACE (may appear outside the clock table)
_DUNEDINPACE_RE = re.compile(
    r"dunedinpace\s+(?:score\s*[:\-]?)?\s*(\d+\.\d+)",
    re.IGNORECASE,
)
_PACE_INTERP_RE = re.compile(
    r"(?:you\s+are\s+aging|aging)\s+(\d+)\s*%\s+(faster|slower)\s+than\s+average",
    re.IGNORECASE,
)
_PACE_PERCENTILE_RE = re.compile(
    r"percentile\s*[:\-]?\s*(\d+)(?:st|nd|rd|th)?",
    re.IGNORECASE,
)

# Clock name → canonical slug
_CLOCK_CANONICAL: dict[str, str] = {
    "horvath": "horvath",
    "horvath clock": "horvath",
    "hannum": "hannum",
    "hannum clock": "hannum",
    "phenoage": "phenoage",
    "pheno age": "phenoage",
    "grimage": "grimage",
    "grim age": "grimage",
    "dunedinpace": "dunedinpace",
    "dunedin pace": "dunedinpace",
}

# ---------------------------------------------------------------------------
# Organ system ages table
# "Immune System   35.2   -6.8 yrs   Younger"
# ---------------------------------------------------------------------------

_ORGAN_SYSTEM_MAP: dict[str, str] = {
    "immune": "immune",
    "immune system": "immune",
    "cardiovascular": "heart",
    "heart": "heart",
    "cardiac": "heart",
    "liver": "liver",
    "hepatic": "liver",
    "kidney": "kidney",
    "renal": "kidney",
    "brain": "brain",
    "brain/cognitive": "brain",
    "cognitive": "brain",
    "neurological": "brain",
    "lung": "lung",
    "pulmonary": "lung",
    "lung/pulmonary": "lung",
    "respiratory": "lung",
    "metabolic": "metabolic",
    "musculoskeletal": "musculoskeletal",
    "muscle": "musculoskeletal",
    "hormonal": "hormone",
    "hormonal/endocrine": "hormone",
    "endocrine": "hormone",
    "blood": "blood",
    "blood/hematopoietic": "blood",
    "hematopoietic": "blood",
    "inflammation": "inflammation",
    "inflammatory": "inflammation",
}

_ORGAN_ROW_RE = re.compile(
    r"^(?P<organ>immune(?:\s+system)?|cardiovascular|heart|liver|hepatic|"
    r"kidney|renal|brain(?:/cognitive)?|cognitive|neurological|"
    r"lung(?:/pulmonary)?|pulmonary|respiratory|metabolic|musculoskeletal|"
    r"muscle|hormonal(?:/endocrine)?|endocrine|blood(?:/hematopoietic)?|"
    r"hematopoietic|inflamma(?:tion|tory))"
    r"\s+"
    r"(?P<bio_age>\d+\.?\d*)"
    r"(?:\s+(?P<delta>[-+]?\d+\.?\d*)\s*yrs?)?"
    r"(?:\s+(?P<direction>younger|older|same))?",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Telomere
# ---------------------------------------------------------------------------

_TELO_LENGTH_RE = re.compile(
    r"(?:telomere\s+)?length\s*[:\-]?\s*(\d+\.?\d*)\s*kb",
    re.IGNORECASE,
)
_TELO_PCT_RE = re.compile(
    r"percentile\s*[:\-]?\s*(\d+)(?:st|nd|rd|th)?(?:\s+percentile)?",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Parser class
# ---------------------------------------------------------------------------


class TruDiagnosticParser(BaseParser):
    """Parser for TruDiagnostic TruAge™ epigenetic aging reports."""

    PARSER_ID = "trudiagnostic_v1"
    PRIORITY = 25
    LAB_NAME = "TruDiagnostic"

    def can_parse(self, text: str, filename: str = "") -> bool:
        """Return True if this looks like a TruDiagnostic report."""
        name_lower = filename.lower()
        if any(k in name_lower for k in ("trudiagnostic", "truage", "tru_age")):
            return True
        sample = text[:4000]
        return any(p.search(sample) for p in _DETECT_PATTERNS)

    def parse(self, text: str, file_bytes: bytes, filename: str = "") -> ParseResult:
        """Return a flat ``ParseResult`` for registry compatibility."""
        t0 = time.monotonic()
        structured = self.parse_structured(text)
        markers = _epi_to_markers(structured)
        return ParseResult(
            success=structured.success,
            parser_used=self.PARSER_ID,
            format_detected=structured.format_detected,
            confidence=structured.confidence,
            patient_name=structured.patient_name,
            collection_date=structured.test_date,
            lab_name="TruDiagnostic",
            markers=markers,
            warnings=structured.warnings,
            needs_review=structured.needs_review,
            parse_time_ms=int((time.monotonic() - t0) * 1000),
            error=structured.error,
        )

    def parse_structured(self, text: str) -> EpigeneticParseResult:
        """Parse a TruDiagnostic PDF and return a rich ``EpigeneticParseResult``."""
        t0 = time.monotonic()
        warnings: list[str] = []

        try:
            test_date = _extract_date(text)
            patient_name = _extract_patient_name(text)

            chron_age = _find_float(_CHRON_AGE_RE, text)
            bio_age = _find_float(_TRUAGE_RE, text)

            clocks = _parse_clocks(text)
            organ_ages = _parse_organ_ages(text, chron_age)
            pace, pace_interp = _parse_pace(text)
            pace_pct = _parse_pace_percentile(text)
            telo_len, telo_pct = _parse_telomere(text)

            # If DunedinPACE already added via clock table, avoid duplication
            has_dunedinpace = any(c.clock_name == "dunedinpace" for c in clocks)
            if pace is not None and not has_dunedinpace:
                clocks.append(
                    EpigeneticClockResult(
                        clock_name="dunedinpace",
                        value=pace,
                        unit="rate",
                        description=pace_interp,
                        confidence=0.95,
                    )
                )

            # Confidence
            key_fields = [bio_age, chron_age, pace]
            filled = sum(1 for f in key_fields if f is not None)
            raw_conf = 0.40 + (filled / len(key_fields)) * 0.40
            if clocks:
                raw_conf = min(raw_conf + 0.08, 0.92)
            if organ_ages:
                raw_conf = min(raw_conf + 0.08, 0.97)
            confidence = ConfidenceLevel.from_score(raw_conf)
            needs_review = confidence in (ConfidenceLevel.LOW, ConfidenceLevel.UNCERTAIN)

            if bio_age is None:
                warnings.append("Primary biological age not found")
            if chron_age is None:
                warnings.append("Chronological age not found")

            result = EpigeneticParseResult(
                success=True,
                parser_used=self.PARSER_ID,
                format_detected="TruDiagnostic TruAge™ Epigenetic Test",
                confidence=confidence,
                test_date=test_date,
                patient_name=patient_name,
                provider="TruDiagnostic",
                chronological_age=chron_age,
                primary_biological_age=bio_age,
                primary_clock_used="truage",
                clocks=clocks,
                organ_ages=organ_ages,
                pace_of_aging=pace,
                pace_interpretation=pace_interp,
                telomere_length=telo_len,
                telomere_percentile=telo_pct if telo_pct else pace_pct,
                warnings=warnings,
                needs_review=needs_review,
                parse_time_ms=int((time.monotonic() - t0) * 1000),
            )

        except Exception as exc:
            logger.exception("TruDiagnosticParser raised during parse: %s", exc)
            result = EpigeneticParseResult(
                success=False,
                parser_used=self.PARSER_ID,
                format_detected="TruDiagnostic TruAge™ Epigenetic Test",
                confidence=ConfidenceLevel.UNCERTAIN,
                provider="TruDiagnostic",
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
    m = _DATE_RE.search(text[:4000])
    if not m:
        return None
    raw = m.group(1).strip()
    for fmt in (
        "%B %d, %Y",
        "%B %d %Y",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%m-%d-%Y",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(raw, fmt).date()
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


def _parse_clocks(text: str) -> list[EpigeneticClockResult]:
    """Extract individual methylation clock values from the report."""
    results: list[EpigeneticClockResult] = []
    seen: set[str] = set()

    for line in text.splitlines():
        line = line.strip()
        m = _CLOCK_TABLE_ROW_RE.match(line)
        if not m:
            continue
        raw_name = m.group("name").lower().strip()
        canonical = _CLOCK_CANONICAL.get(raw_name)
        if canonical is None:
            # Prefix match
            for key, val in _CLOCK_CANONICAL.items():
                if raw_name.startswith(key[:4]):
                    canonical = val
                    break
        if canonical is None or canonical in seen:
            continue
        seen.add(canonical)

        try:
            value = float(m.group("value").replace(",", ""))
        except ValueError:
            continue

        unit = "rate" if canonical == "dunedinpace" else "years"
        results.append(
            EpigeneticClockResult(
                clock_name=canonical,
                value=value,
                unit=unit,
                confidence=0.93,
            )
        )

    return results


def _parse_organ_ages(
    text: str, chron_age: float | None
) -> list[OrganAgeResult]:
    """Extract organ-system biological ages."""
    results: list[OrganAgeResult] = []
    seen: set[str] = set()

    for line in text.splitlines():
        line = line.strip()
        m = _ORGAN_ROW_RE.match(line)
        if not m:
            continue

        raw_organ = m.group("organ").lower().strip()
        canonical = _ORGAN_SYSTEM_MAP.get(raw_organ)
        if canonical is None:
            for key, val in _ORGAN_SYSTEM_MAP.items():
                if raw_organ.startswith(key[:4]):
                    canonical = val
                    break
        if canonical is None or canonical in seen:
            continue
        seen.add(canonical)

        try:
            bio_age = float(m.group("bio_age").replace(",", ""))
        except (ValueError, TypeError):
            continue

        # Compute delta
        if m.group("delta"):
            try:
                delta = float(m.group("delta"))
            except ValueError:
                delta = bio_age - (chron_age or bio_age)
        else:
            delta = bio_age - (chron_age or bio_age)

        results.append(
            OrganAgeResult(
                organ_system=canonical,
                biological_age=bio_age,
                chronological_age=chron_age or bio_age,
                delta_years=round(delta, 2),
                confidence=0.91,
            )
        )

    return results


def _parse_pace(text: str) -> tuple[float | None, str | None]:
    """Extract DunedinPACE value and interpretation text."""
    pace = _find_float(_DUNEDINPACE_RE, text)
    interp: str | None = None

    m = _PACE_INTERP_RE.search(text)
    if m:
        pct_val = m.group(1)
        direction = m.group(2).lower()
        interp = f"aging {pct_val}% {direction} than average"

    return pace, interp


def _parse_pace_percentile(text: str) -> int | None:
    """Extract percentile value for DunedinPACE."""
    # Look for the percentile in the DunedinPACE section
    pace_section_re = re.compile(
        r"(?:dunedinpace|pace\s+of\s+aging).*?percentile\s*[:\-]?\s*(\d+)",
        re.IGNORECASE | re.DOTALL,
    )
    m = pace_section_re.search(text[:6000])
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return None


def _parse_telomere(text: str) -> tuple[float | None, int | None]:
    """Extract telomere length (kb) and age-adjusted percentile."""
    # Find telomere section
    telo_section_re = re.compile(
        r"telomere.{0,200}?length\s*[:\-]?\s*(\d+\.?\d*)\s*kb",
        re.IGNORECASE | re.DOTALL,
    )
    length: float | None = None
    percentile: int | None = None

    m = telo_section_re.search(text)
    if m:
        try:
            length = float(m.group(1))
        except ValueError:
            pass

    if length is None:
        length = _find_float(_TELO_LENGTH_RE, text)

    # Find percentile near "telomere" keyword
    telo_pct_re = re.compile(
        r"telomere.{0,300}?(\d+)(?:st|nd|rd|th)?\s+percentile",
        re.IGNORECASE | re.DOTALL,
    )
    m = telo_pct_re.search(text)
    if m:
        try:
            percentile = int(m.group(1))
        except ValueError:
            pass

    return length, percentile


# ---------------------------------------------------------------------------
# Convert EpigeneticParseResult → flat MarkerResult list
# ---------------------------------------------------------------------------

def _epi_to_markers(result: EpigeneticParseResult) -> list[MarkerResult]:
    """Flatten an EpigeneticParseResult into MarkerResult objects."""
    markers: list[MarkerResult] = []
    conf_val = 0.90

    if result.primary_biological_age is not None:
        markers.append(
            MarkerResult(
                canonical_name="biological_age",
                display_name="Biological Age",
                value=result.primary_biological_age,
                value_text=str(result.primary_biological_age),
                unit="years",
                canonical_unit="years",
                confidence=conf_val,
                confidence_reasons=["Epigenetic test structured field"],
                page=1,
            )
        )
    if result.chronological_age is not None:
        markers.append(
            MarkerResult(
                canonical_name="chronological_age",
                display_name="Chronological Age",
                value=result.chronological_age,
                value_text=str(result.chronological_age),
                unit="years",
                canonical_unit="years",
                confidence=conf_val,
                confidence_reasons=["Epigenetic test structured field"],
                page=1,
            )
        )
    if result.pace_of_aging is not None:
        markers.append(
            MarkerResult(
                canonical_name="dunedinpace",
                display_name="DunedinPACE",
                value=result.pace_of_aging,
                value_text=str(result.pace_of_aging),
                unit="rate",
                canonical_unit="rate",
                confidence=conf_val,
                confidence_reasons=["Epigenetic test structured field"],
                page=1,
            )
        )
    if result.telomere_length is not None:
        markers.append(
            MarkerResult(
                canonical_name="telomere_length",
                display_name="Telomere Length",
                value=result.telomere_length,
                value_text=str(result.telomere_length),
                unit="kb",
                canonical_unit="kb",
                confidence=conf_val,
                confidence_reasons=["Epigenetic test structured field"],
                page=1,
            )
        )
    # Individual clocks
    for clock in result.clocks:
        if clock.clock_name == "dunedinpace":
            continue  # already added above
        markers.append(
            MarkerResult(
                canonical_name=f"{clock.clock_name}_age",
                display_name=f"{clock.clock_name.title()} Clock Age",
                value=clock.value,
                value_text=str(clock.value),
                unit=clock.unit,
                canonical_unit=clock.unit,
                confidence=clock.confidence,
                confidence_reasons=["Methylation clock value"],
                page=1,
            )
        )

    return markers
