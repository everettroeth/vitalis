"""Function Health lab report parser.

Function Health (functionhealth.com) provides comprehensive 100+ biomarker
panels with their own PDF report format:
  - Header: "Function Health" branding, logo
  - Results presented in a clean columnar layout
  - Columns: Test | Result | Range | Units | Status
  - Status column: "Optimal", "Borderline", "At Risk", "Normal", etc.
  - Often includes trend data vs. previous results
  - Some panels: Longevity, Metabolic, Hormones, Inflammatory, etc.

The report is typically multi-page with section headers for each panel.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime

from src.parsers.base import BaseParser, MarkerResult, ParseResult
from src.parsers.confidence import score_marker, compute_overall_confidence
from src.parsers.normalizer import normalize_marker_name, normalize_unit

logger = logging.getLogger("vitalis.parsers.function_health")

# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

_FH_PATTERNS: list[re.Pattern] = [
    re.compile(r"function\s+health", re.IGNORECASE),
    re.compile(r"functionhealth\.com", re.IGNORECASE),
    re.compile(r"function\s+health\s+report", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Result patterns
# ---------------------------------------------------------------------------

# Function Health typical row:
#   Glucose    95 mg/dL    70-99    Optimal
#   LDL Cholesterol    105 mg/dL    <100    Borderline
_FH_RESULT_RE = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z0-9 ,\(\)/'\-\.%]{2,}?)"
    r"\s{2,}"
    r"(?P<value>[<>≤≥~]?\s*[\d,\.]+)"
    r"\s*"
    r"(?P<unit>[a-zA-Z%µ/\^0-9\.]+(?:/[a-zA-Z0-9\^\.µ]+)*)?"
    r"\s*"
    r"(?P<ref>[<>≤≥]?\d[\d,\.]*(?:\s*[-–]\s*[<>≤≥]?\d[\d,\.]*)?|[<>≤≥]\d[\d,\.]*)?"
    r"\s*"
    r"(?P<status>Optimal|Borderline|At\s+Risk|Normal|High|Low|Elevated|Deficient)?"
    r".*$",
    re.IGNORECASE,
)

_DATE_RE = re.compile(
    r"(?:report|collected|date)\s*[:\-]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\w+\s+\d{1,2},?\s+\d{4})",
    re.IGNORECASE,
)

_SKIP_RE = re.compile(
    r"^\s*$|^\s*[-=_]{3,}|^\s*(?:Test|Result|Range|Units|Status|Category|Function\s+Health)"
    r"|^\s*Page\s+\d|^\s*\d+\s*$|^\s*Trend",
    re.IGNORECASE,
)


class FunctionHealthParser(BaseParser):
    """Parser for Function Health PDF reports."""

    PARSER_ID = "function_health_v1"
    PRIORITY = 20
    LAB_NAME = "Function Health"

    def can_parse(self, text: str, filename: str = "") -> bool:
        if "function" in filename.lower() and "health" in filename.lower():
            return True
        sample = text[:3000]
        return any(p.search(sample) for p in _FH_PATTERNS)

    def parse(self, text: str, file_bytes: bytes, filename: str = "") -> ParseResult:
        import time
        t0 = time.monotonic()

        warnings: list[str] = []
        markers: list[MarkerResult] = []

        collection_date = _extract_date(text)

        pages = text.split("\f")
        for page_num, page_text in enumerate(pages, start=1):
            for line in page_text.splitlines():
                if _SKIP_RE.match(line):
                    continue
                stripped = line.strip()
                if len(stripped) < 5:
                    continue
                marker = _parse_line(stripped, page_num)
                if marker:
                    markers.append(marker)

        markers = _dedup(markers)
        needs_review = any(m.confidence < 0.70 for m in markers)
        overall = compute_overall_confidence(markers)

        return ParseResult(
            success=True,
            parser_used=self.PARSER_ID,
            format_detected="Function Health",
            confidence=overall,
            collection_date=collection_date,
            lab_name="Function Health",
            markers=markers,
            warnings=warnings,
            needs_review=needs_review,
            parse_time_ms=int((time.monotonic() - t0) * 1000),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_date(text: str) -> date | None:
    m = _DATE_RE.search(text[:2000])
    if not m:
        return None
    raw = m.group(1)
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%B %d, %Y", "%B %d %Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_line(line: str, page_num: int) -> MarkerResult | None:
    m = _FH_RESULT_RE.match(line)
    if not m:
        return None

    name = m.group("name").strip()
    value_text = m.group("value").strip()
    unit = (m.group("unit") or "").strip()
    ref_text = (m.group("ref") or "").strip()

    value = _safe_float(value_text)
    if value is None:
        return None

    ref_low, ref_high = _parse_ref(ref_text)
    canonical, _ = normalize_marker_name(name)
    canonical_unit = normalize_unit(unit)

    conf, reasons = score_marker(
        format_matched=True,
        name_in_dictionary=canonical is not None,
        value_text=value_text,
        unit=unit,
        reference_low=ref_low,
        reference_high=ref_high,
        reference_text=ref_text,
    )

    return MarkerResult(
        canonical_name=canonical or re.sub(r"\W+", "_", name.lower()).strip("_"),
        display_name=name,
        value=value,
        value_text=value_text,
        unit=unit,
        canonical_unit=canonical_unit,
        reference_low=ref_low,
        reference_high=ref_high,
        reference_text=ref_text,
        confidence=conf,
        confidence_reasons=reasons,
        page=page_num,
    )


def _parse_ref(text: str) -> tuple[float | None, float | None]:
    if not text:
        return None, None
    rm = re.match(r"([<>≤≥]?\s*[\d,\.]+)\s*[-–]\s*([\d,\.]+)", text)
    if rm:
        return _safe_float(rm.group(1)), _safe_float(rm.group(2))
    gt = re.match(r"[>≥]\s*([\d,\.]+)", text)
    if gt:
        return _safe_float(gt.group(1)), None
    lt = re.match(r"[<≤]\s*([\d,\.]+)", text)
    if lt:
        return None, _safe_float(lt.group(1))
    return None, None


def _safe_float(text: str) -> float | None:
    text = text.strip()
    for p in (">", "<", ">=", "<=", "≥", "≤", "~"):
        if text.startswith(p):
            text = text[len(p):].strip()
            break
    text = text.rstrip("HLAChlac").strip()
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _dedup(markers: list[MarkerResult]) -> list[MarkerResult]:
    seen: dict[str, MarkerResult] = {}
    for m in markers:
        if m.canonical_name not in seen or m.confidence > seen[m.canonical_name].confidence:
            seen[m.canonical_name] = m
    order = {m.canonical_name: i for i, m in enumerate(markers)}
    return sorted(seen.values(), key=lambda m: order.get(m.canonical_name, 0))
