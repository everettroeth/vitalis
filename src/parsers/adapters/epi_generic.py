"""Generic epigenetic / biological age test parser.

Fallback adapter for providers not covered by the specific TruDiagnostic or
Elysium parsers, including:

  - myDNAge (IntelliAge.com / EpiAging)
  - GlycanAge
  - Blueprint Biomarkers (blueprint.bryanjohnson.com)
  - GrimAge-only clinical reports
  - Any document mentioning "biological age", "methylation age",
    "epigenetic age", or DNA methylation clocks.

Detection strategy:
  - Requires at least 2 epigenetic vocabulary signals (see _DETECT_PATTERNS).
  - Registered at priority 41 — after specific parsers (25, 26) and before
    the generic AI catch-all.

Extracted metrics (best-effort):
  - Biological age and chronological age
  - Any named clock values (Horvath, Hannum, PhenoAge, GrimAge, DunedinPACE)
  - Pace of aging rate
  - Telomere length
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
)

logger = logging.getLogger("vitalis.parsers.epi_generic")

# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

_DETECT_PATTERNS: list[re.Pattern] = [
    re.compile(r"biological\s+age", re.IGNORECASE),
    re.compile(r"methylation\s+age", re.IGNORECASE),
    re.compile(r"epigenetic\s+age", re.IGNORECASE),
    re.compile(r"dna\s+methylation", re.IGNORECASE),
    re.compile(r"pace\s+of\s+aging", re.IGNORECASE),
    re.compile(r"dunedinpace", re.IGNORECASE),
    re.compile(r"horvath\s+clock", re.IGNORECASE),
    re.compile(r"grimage", re.IGNORECASE),
    re.compile(r"glycanage", re.IGNORECASE),
    re.compile(r"mydnage", re.IGNORECASE),
    re.compile(r"blueprint\s+biomarkers", re.IGNORECASE),
]

_MIN_SIGNAL_COUNT = 2

# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(
    r"(?:collection\s+date|test\s+date|sample\s+date|date\s+of\s+collection|"
    r"report\s+date)\s*[:\-]?\s*"
    r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}"
    r"|(?:january|february|march|april|may|june|july|august|september|"
    r"october|november|december)\s+\d{1,2},?\s+\d{4})",
    re.IGNORECASE,
)
_PATIENT_RE = re.compile(
    r"(?:patient|name|subject|client)\s*[:\-]?\s*"
    r"([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)+)",
    re.IGNORECASE,
)
_PROVIDER_RE = re.compile(
    r"(?:provider|company|lab|test\s+by)\s*[:\-]?\s*(.+?)(?:\n|$)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Biological age — liberal patterns
# ---------------------------------------------------------------------------

_BIO_AGE_RE = re.compile(
    r"(?:biological|epigenetic|methylation|dna)\s+age\s*[:\-]?\s*"
    r"(\d+\.?\d*)\s*years?",
    re.IGNORECASE,
)
_BIO_AGE_PLAIN_RE = re.compile(
    r"(?:biological|epigenetic|methylation)\s+age\s*\n?\s*(\d+\.?\d*)",
    re.IGNORECASE,
)
_CHRON_AGE_RE = re.compile(
    r"chronological\s+age\s*[:\-]?\n?\s*(\d+\.?\d*)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Clock patterns — liberal
# ---------------------------------------------------------------------------

_CLOCK_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"horvath(?:\s+clock)?\s*[:\-]?\s*(\d+\.?\d*)\s*years?", re.IGNORECASE), "horvath", "years"),
    (re.compile(r"hannum(?:\s+clock)?\s*[:\-]?\s*(\d+\.?\d*)\s*years?", re.IGNORECASE), "hannum", "years"),
    (re.compile(r"pheno\s*age\s*[:\-]?\s*(\d+\.?\d*)\s*years?", re.IGNORECASE), "phenoage", "years"),
    (re.compile(r"grim\s*age\s*[:\-]?\s*(\d+\.?\d*)\s*years?", re.IGNORECASE), "grimage", "years"),
    (re.compile(r"dunedinpace\s*(?:score)?\s*[:\-]?\s*(\d+\.\d+)", re.IGNORECASE), "dunedinpace", "rate"),
    (re.compile(r"mydnage\s*[:\-]?\s*(\d+\.?\d*)\s*years?", re.IGNORECASE), "mydnage", "years"),
    (re.compile(r"glycanage\s*[:\-]?\s*(\d+\.?\d*)\s*years?", re.IGNORECASE), "glycanage", "years"),
]

# ---------------------------------------------------------------------------
# Pace of aging
# ---------------------------------------------------------------------------

_PACE_RE = re.compile(
    r"(?:pace|rate)\s+of\s+aging\s*[:\-]?\s*(\d+\.\d+)",
    re.IGNORECASE,
)
_PACE_INTERP_RE = re.compile(
    r"aging\s+(\d+)\s*%\s+(faster|slower)\s+than",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Telomere
# ---------------------------------------------------------------------------

_TELO_LEN_RE = re.compile(
    r"telomere\s+(?:length)?\s*[:\-]?\s*(\d+\.?\d*)\s*kb",
    re.IGNORECASE,
)
_TELO_PCT_RE = re.compile(
    r"telomere.{0,100}?(\d+)(?:st|nd|rd|th)?\s+percentile",
    re.IGNORECASE | re.DOTALL,
)


# ---------------------------------------------------------------------------
# Parser class
# ---------------------------------------------------------------------------


class EpigeneticGenericParser(BaseParser):
    """Generic fallback parser for myDNAge, GlycanAge, Blueprint, and unknown
    epigenetic test formats."""

    PARSER_ID = "epi_generic_v1"
    PRIORITY = 41
    LAB_NAME = "Epigenetic Test (Generic)"

    def can_parse(self, text: str, filename: str = "") -> bool:
        """Return True if the document contains sufficient epigenetic vocabulary."""
        name_lower = filename.lower()
        if any(k in name_lower for k in ("epigenetic", "biological_age", "bio_age",
                                          "mydnage", "glycanage", "truage")):
            return True
        sample = text[:5000]
        signals = sum(1 for p in _DETECT_PATTERNS if p.search(sample))
        return signals >= _MIN_SIGNAL_COUNT

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
            lab_name=structured.provider or "Epigenetic Test",
            markers=markers,
            warnings=structured.warnings,
            needs_review=structured.needs_review,
            parse_time_ms=int((time.monotonic() - t0) * 1000),
            error=structured.error,
        )

    def parse_structured(self, text: str) -> EpigeneticParseResult:
        """Parse a generic epigenetic test and return an ``EpigeneticParseResult``."""
        t0 = time.monotonic()
        warnings: list[str] = []

        try:
            test_date = _extract_date(text)
            patient_name = _extract_patient_name(text)
            provider = _detect_provider(text)

            bio_age = _find_float(_BIO_AGE_RE, text)
            if bio_age is None:
                bio_age = _find_float(_BIO_AGE_PLAIN_RE, text)
            chron_age = _find_float(_CHRON_AGE_RE, text)

            clocks = _extract_clocks(text)
            pace = _find_float(_PACE_RE, text)
            pace_interp = _extract_pace_interpretation(text)
            telo_len = _find_float(_TELO_LEN_RE, text)
            telo_pct = _extract_telo_percentile(text)

            # If DunedinPACE not in clocks table but found standalone
            has_pace = any(c.clock_name == "dunedinpace" for c in clocks)
            if pace is not None and not has_pace:
                clocks.append(
                    EpigeneticClockResult(
                        clock_name="dunedinpace",
                        value=pace,
                        unit="rate",
                        description=pace_interp,
                        confidence=0.75,
                    )
                )

            # Primary clock: use first non-pace clock if bio_age not explicit
            primary_clock: str | None = None
            if clocks:
                for c in clocks:
                    if c.unit == "years":
                        primary_clock = c.clock_name
                        if bio_age is None:
                            bio_age = c.value
                        break

            format_str = _detect_format_name(text, provider)

            key_fields = [bio_age, chron_age]
            filled = sum(1 for f in key_fields if f is not None)
            raw_conf = 0.30 + (filled / len(key_fields)) * 0.35
            if clocks:
                raw_conf = min(raw_conf + 0.10, 0.78)
            if telo_len is not None:
                raw_conf = min(raw_conf + 0.05, 0.80)
            confidence = ConfidenceLevel.from_score(raw_conf)
            needs_review = confidence in (ConfidenceLevel.LOW, ConfidenceLevel.UNCERTAIN)

            if bio_age is None:
                warnings.append("No biological age found — verify this is an epigenetic report")

            result = EpigeneticParseResult(
                success=True,
                parser_used=self.PARSER_ID,
                format_detected=format_str,
                confidence=confidence,
                test_date=test_date,
                patient_name=patient_name,
                provider=provider,
                chronological_age=chron_age,
                primary_biological_age=bio_age,
                primary_clock_used=primary_clock,
                clocks=clocks,
                pace_of_aging=pace,
                pace_interpretation=pace_interp,
                telomere_length=telo_len,
                telomere_percentile=telo_pct,
                warnings=warnings,
                needs_review=needs_review,
                parse_time_ms=int((time.monotonic() - t0) * 1000),
            )

        except Exception as exc:
            logger.exception("EpigeneticGenericParser raised during parse: %s", exc)
            result = EpigeneticParseResult(
                success=False,
                parser_used=self.PARSER_ID,
                format_detected="Epigenetic Test (Generic)",
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


def _detect_provider(text: str) -> str | None:
    """Identify the provider from known brand names in the text."""
    sample = text[:4000].lower()
    if "trudiagnostic" in sample or "truage" in sample:
        return "TruDiagnostic"
    if "elysium" in sample:
        return "Elysium Health"
    if "mydnage" in sample or "epigenomics" in sample:
        return "myDNAge"
    if "glycanage" in sample:
        return "GlycanAge"
    if "blueprint biomarkers" in sample or "bryan johnson" in sample:
        return "Blueprint Biomarkers"
    m = _PROVIDER_RE.search(text[:3000])
    if m:
        prov = m.group(1).strip()
        if 2 < len(prov) < 60:
            return prov
    return None


def _detect_format_name(text: str, provider: str | None) -> str:
    if provider:
        return f"{provider} Epigenetic Test"
    sample = text[:3000].lower()
    if "methylation" in sample:
        return "DNA Methylation Epigenetic Test (Generic)"
    return "Biological Age Test (Generic)"


def _extract_clocks(text: str) -> list[EpigeneticClockResult]:
    results: list[EpigeneticClockResult] = []
    seen: set[str] = set()
    for pattern, canonical, unit in _CLOCK_PATTERNS:
        if canonical in seen:
            continue
        m = pattern.search(text)
        if m:
            try:
                value = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            seen.add(canonical)
            results.append(
                EpigeneticClockResult(
                    clock_name=canonical,
                    value=value,
                    unit=unit,
                    confidence=0.72,
                )
            )
    return results


def _extract_pace_interpretation(text: str) -> str | None:
    m = _PACE_INTERP_RE.search(text)
    if m:
        return f"aging {m.group(1)}% {m.group(2).lower()} than average"
    return None


def _extract_telo_percentile(text: str) -> int | None:
    m = _TELO_PCT_RE.search(text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return None


def _epi_to_markers(result: EpigeneticParseResult) -> list[MarkerResult]:
    markers: list[MarkerResult] = []
    conf_val = 0.75  # generic parser: slightly lower baseline

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
                confidence_reasons=["Generic epigenetic extraction"],
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
                confidence_reasons=["Generic epigenetic extraction"],
                page=1,
            )
        )
    if result.pace_of_aging is not None:
        markers.append(
            MarkerResult(
                canonical_name="pace_of_aging",
                display_name="Pace of Aging",
                value=result.pace_of_aging,
                value_text=str(result.pace_of_aging),
                unit="rate",
                canonical_unit="rate",
                confidence=conf_val,
                confidence_reasons=["Generic epigenetic extraction"],
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
                confidence_reasons=["Generic epigenetic extraction"],
                page=1,
            )
        )
    for clock in result.clocks:
        if clock.clock_name in ("dunedinpace", "elysium_rate"):
            continue
        markers.append(
            MarkerResult(
                canonical_name=f"{clock.clock_name}_age",
                display_name=f"{clock.clock_name.replace('_', ' ').title()} Age",
                value=clock.value,
                value_text=str(clock.value),
                unit=clock.unit,
                canonical_unit=clock.unit,
                confidence=clock.confidence,
                confidence_reasons=["Methylation clock generic extraction"],
                page=1,
            )
        )
    return markers
