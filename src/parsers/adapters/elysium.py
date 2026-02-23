"""Elysium Health Index biological age test parser.

Elysium Health (elysiumhealth.com) produces the "Index" biological age test
kit.  Their report is simpler than TruDiagnostic, focusing on:

  - Biological Age (Index score) — their proprietary algorithm
  - Chronological Age
  - Rate of Aging (years of biological aging per calendar year)
  - Cumulative pace interpretation

Report layout:
  - Clean two-page PDF with branded "Elysium Health" header
  - Large headline biological age on page 1
  - Rate of Aging table on page 2
  - "What Your Results Mean" explanatory section

Detection: "Elysium" OR "Index Biological Age" in document.
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

logger = logging.getLogger("vitalis.parsers.elysium")

# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

_DETECT_PATTERNS: list[re.Pattern] = [
    re.compile(r"elysium\s+health", re.IGNORECASE),
    re.compile(r"elysiumhealth\.com", re.IGNORECASE),
    re.compile(r"index\s+biological\s+age", re.IGNORECASE),
    re.compile(r"elysium\s+index", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(
    r"(?:date\s+of\s+collection|collection\s+date|test\s+date|sample\s+date)"
    r"\s*[:\-]?\s*"
    r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}"
    r"|(?:january|february|march|april|may|june|july|august|september|"
    r"october|november|december)\s+\d{1,2},?\s+\d{4})",
    re.IGNORECASE,
)
_PATIENT_RE = re.compile(
    r"(?:name|patient|member)\s*[:\-]?\s*"
    r"([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)+)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Key metrics
# ---------------------------------------------------------------------------

# Biological age — headline value on page 1
_BIO_AGE_RE = re.compile(
    r"biological\s+age\s*[:\-]?\s*(\d+\.?\d*)\s*years?",
    re.IGNORECASE,
)
# "Index Biological Age Test" doesn't repeat "years" — fallback
_BIO_AGE_PLAIN_RE = re.compile(
    r"(?:your\s+)?(?:index\s+)?biological\s+age\s*\n?\s*(\d+\.?\d*)",
    re.IGNORECASE,
)
_CHRON_AGE_RE = re.compile(
    r"chronological\s+age\s*[:\-]?\n?\s*(\d+\.?\d*)",
    re.IGNORECASE,
)
# Rate of aging
_RATE_RE = re.compile(
    r"rate\s+of\s+aging\s*[:\-]?\s*(\d+\.\d+)\s*(?:years?(?:/year)?)?",
    re.IGNORECASE,
)
# Cumulative pace interpretation: "Aging 16% slower than your peers"
_PACE_INTERP_RE = re.compile(
    r"aging\s+(\d+)\s*%\s+(faster|slower)\s+than",
    re.IGNORECASE,
)
# Age delta: "X.X years YOUNGER/OLDER"
_DELTA_RE = re.compile(
    r"(\d+\.?\d*)\s*years?\s+(younger|older)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Parser class
# ---------------------------------------------------------------------------


class ElysiumParser(BaseParser):
    """Parser for Elysium Health Index biological age reports."""

    PARSER_ID = "elysium_v1"
    PRIORITY = 26
    LAB_NAME = "Elysium Health"

    def can_parse(self, text: str, filename: str = "") -> bool:
        """Return True if this looks like an Elysium Health report."""
        name_lower = filename.lower()
        if any(k in name_lower for k in ("elysium", "index_bio_age")):
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
            lab_name="Elysium Health",
            markers=markers,
            warnings=structured.warnings,
            needs_review=structured.needs_review,
            parse_time_ms=int((time.monotonic() - t0) * 1000),
            error=structured.error,
        )

    def parse_structured(self, text: str) -> EpigeneticParseResult:
        """Parse an Elysium Index PDF and return a rich ``EpigeneticParseResult``."""
        t0 = time.monotonic()
        warnings: list[str] = []

        try:
            test_date = _extract_date(text)
            patient_name = _extract_patient_name(text)

            chron_age = _find_float(_CHRON_AGE_RE, text)
            bio_age = _find_float(_BIO_AGE_RE, text)
            if bio_age is None:
                bio_age = _find_float(_BIO_AGE_PLAIN_RE, text)

            rate = _find_float(_RATE_RE, text)
            pace_interp = _extract_pace_interpretation(text)

            clocks: list[EpigeneticClockResult] = []
            if bio_age is not None:
                clocks.append(
                    EpigeneticClockResult(
                        clock_name="elysium_index",
                        value=bio_age,
                        unit="years",
                        description="Elysium Index biological age",
                        confidence=0.95,
                    )
                )
            if rate is not None:
                clocks.append(
                    EpigeneticClockResult(
                        clock_name="elysium_rate",
                        value=rate,
                        unit="rate",
                        description="Elysium rate of aging (years/year)",
                        confidence=0.93,
                    )
                )

            key_fields = [bio_age, chron_age]
            filled = sum(1 for f in key_fields if f is not None)
            raw_conf = 0.40 + (filled / len(key_fields)) * 0.45
            if rate is not None:
                raw_conf = min(raw_conf + 0.05, 0.92)
            confidence = ConfidenceLevel.from_score(raw_conf)
            needs_review = confidence in (ConfidenceLevel.LOW, ConfidenceLevel.UNCERTAIN)

            if bio_age is None:
                warnings.append("Biological age not found in report")
            if chron_age is None:
                warnings.append("Chronological age not found in report")

            result = EpigeneticParseResult(
                success=True,
                parser_used=self.PARSER_ID,
                format_detected="Elysium Health Index Biological Age Test",
                confidence=confidence,
                test_date=test_date,
                patient_name=patient_name,
                provider="Elysium Health",
                chronological_age=chron_age,
                primary_biological_age=bio_age,
                primary_clock_used="elysium_index",
                clocks=clocks,
                pace_of_aging=rate,
                pace_interpretation=pace_interp,
                warnings=warnings,
                needs_review=needs_review,
                parse_time_ms=int((time.monotonic() - t0) * 1000),
            )

        except Exception as exc:
            logger.exception("ElysiumParser raised during parse: %s", exc)
            result = EpigeneticParseResult(
                success=False,
                parser_used=self.PARSER_ID,
                format_detected="Elysium Health Index Biological Age Test",
                confidence=ConfidenceLevel.UNCERTAIN,
                provider="Elysium Health",
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


def _extract_pace_interpretation(text: str) -> str | None:
    """Extract rate-of-aging interpretation sentence."""
    m = _PACE_INTERP_RE.search(text)
    if m:
        pct = m.group(1)
        direction = m.group(2).lower()
        return f"aging {pct}% {direction} than peers"
    # Fallback: "X.X years younger/older"
    m = _DELTA_RE.search(text)
    if m:
        delta = m.group(1)
        direction = m.group(2).lower()
        return f"{delta} years {direction} than chronological age"
    return None


def _epi_to_markers(result: EpigeneticParseResult) -> list[MarkerResult]:
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
                canonical_name="rate_of_aging",
                display_name="Rate of Aging",
                value=result.pace_of_aging,
                value_text=str(result.pace_of_aging),
                unit="rate",
                canonical_unit="rate",
                confidence=conf_val,
                confidence_reasons=["Epigenetic test structured field"],
                page=1,
            )
        )
    return markers
