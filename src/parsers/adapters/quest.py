"""Quest Diagnostics lab report parser.

Quest PDFs share a consistent layout:
  - Header: "Quest Diagnostics" (sometimes "Quest" only)
  - Patient info block: Name, DOB, Specimen ID, Ordering Physician
  - One or more test sections, each with a section header followed by a
    tabular result block.

Typical result line formats:
    Glucose                    95              70-99         mg/dL
    Creatinine                  0.9             0.60-1.35    mg/dL
    eGFR                       >60             >59           mL/min/1.73m2
    Hemoglobin                 14.2  H         13.5-17.5     g/dL
    ANA Screen                 Negative        Negative

Columns (approximate character positions — NOT fixed-width):
    [Test Name]  [Result]  [Flag?]  [Reference Range]  [Units]

Quest also uses these alternative layouts (especially for CBC):
    Test Name       Result   Flag   Reference Interval    Units
    (same tabular but "Reference Interval" header instead of "Reference Range")
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime

from src.parsers.base import BaseParser, MarkerResult, ParseResult, ConfidenceLevel
from src.parsers.confidence import score_marker, compute_overall_confidence
from src.parsers.normalizer import normalize_marker_name, normalize_unit

logger = logging.getLogger("vitalis.parsers.quest")

# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

_QUEST_PATTERNS: list[re.Pattern] = [
    re.compile(r"quest\s+diagnostics", re.IGNORECASE),
    re.compile(r"questdiagnostics\.com", re.IGNORECASE),
    re.compile(r"quest\s+laboratory", re.IGNORECASE),
    re.compile(r"specimen\s+id.*(?:quest|qd)", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Parsing patterns
# ---------------------------------------------------------------------------

# Date patterns used in Quest reports
_DATE_PATTERNS = [
    re.compile(r"date\s+of\s+collection\s*[:\-]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", re.IGNORECASE),
    re.compile(r"collected\s*[:\-]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", re.IGNORECASE),
    re.compile(r"collection\s+date\s*[:\-]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", re.IGNORECASE),
    re.compile(r"date\s+of\s+service\s*[:\-]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", re.IGNORECASE),
    re.compile(r"specimen\s+collected\s*[:\-]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", re.IGNORECASE),
]
_REPORT_DATE_PATTERNS = [
    re.compile(r"report(?:ed)?\s+(?:date)?\s*[:\-]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", re.IGNORECASE),
    re.compile(r"date\s+reported\s*[:\-]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", re.IGNORECASE),
]

_PATIENT_NAME_RE = re.compile(
    r"patient(?:\s+name)?\s*[:\-]?\s*([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)+)",
    re.IGNORECASE,
)
_PROVIDER_RE = re.compile(
    r"(?:ordering\s+)?physician\s*[:\-]?\s*(.+?)(?:\n|$)",
    re.IGNORECASE,
)

# Primary result line regex — handles the typical Quest tabular format.
# Groups: (test_name, result, flag?, ref_range?, units?)
_RESULT_LINE_RE = re.compile(
    r"^"
    r"(?P<name>[A-Za-z][A-Za-z0-9 ,\(\)/'\-\.%]+?)"  # test name (greedy, left anchor)
    r"\s{2,}"                                           # at least 2 spaces (column separator)
    r"(?P<value>[<>≤≥]?\s*\d[\d,\.]*(?:\s*[HLAChlac])?)"  # numeric result (with optional flag)
    r"(?:\s+(?P<flag>[HLAChlac]{1,2}))?"               # separate flag column (optional)
    r"\s+"
    r"(?P<ref>[<>≤≥]?\d[\d,\.]*(?:\s*[-–]\s*[<>≤≥]?\d[\d,\.]*)?|[<>≤≥]\d[\d,\.]*|[A-Za-z]+)?"  # ref range
    r"\s*"
    r"(?P<unit>[a-zA-Z%µ/\^0-9\.]+(?:/[a-zA-Z0-9\^\.µ]+)*)?"  # units
    r"\s*$",
    re.VERBOSE,
)

# Simpler fallback regex for lines where reference range includes text
_RESULT_LINE_SIMPLE_RE = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z0-9 ,\(\)/'\-\.%]{2,}?)\s{2,}"
    r"(?P<value>[<>≤≥~]?\s*[\d,\.]+(?:\s*[HLAChlac])?)"
    r"(?:\s+(?P<flag>[HLAChlac]{1,2}))?"
    r"\s+(?P<rest>.+)$"
)

# Qualitative result line (e.g. "ANA Screen    Negative    Negative")
_QUALITATIVE_RE = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z0-9 ,\(\)/'\-\.%]{2,}?)\s{2,}"
    r"(?P<value>Non-?Reactive|Reactive|Negative|Positive|Detected|Not\s+Detected|Normal|Abnormal|See\s+Note|None\s+Detected)"
    r".*$",
    re.IGNORECASE,
)

# Skip lines that are clearly not result rows
_SKIP_LINE_RE = re.compile(
    r"^\s*$"                         # blank
    r"|^\s*[-=_]{3,}"                # divider lines
    r"|^\s*(?:Test\s+Name|TESTS?\s+ORDERED|Result|Flag|Reference|Units|Page\s+\d)"  # headers
    r"|^\s*(?:Specimen|Collected|Reported|Patient|Physician|NPI|Acct|Lab|Client)"   # meta
    r"|^\s*\*+\s*(?:ABNORMAL|CRITICAL|COMMENT|NOTE|SEE|REFER)"  # annotations
    r"|^\s*\d+\s*$",                 # lone page numbers
    re.IGNORECASE,
)


class QuestParser(BaseParser):
    """Parser for Quest Diagnostics lab reports."""

    PARSER_ID = "quest_v1"
    PRIORITY = 10
    LAB_NAME = "Quest Diagnostics"

    def can_parse(self, text: str, filename: str = "") -> bool:
        """Return True if the text looks like a Quest Diagnostics report."""
        # Check filename hint first
        if "quest" in filename.lower():
            return True
        # Check first 3000 chars of text (the header region)
        sample = text[:3000]
        return any(p.search(sample) for p in _QUEST_PATTERNS)

    def parse(self, text: str, file_bytes: bytes, filename: str = "") -> ParseResult:
        """Parse a Quest Diagnostics PDF."""
        import time
        t0 = time.monotonic()

        warnings: list[str] = []
        markers: list[MarkerResult] = []

        # Extract metadata
        collection_date = _extract_date(text, _DATE_PATTERNS)
        report_date = _extract_date(text, _REPORT_DATE_PATTERNS)
        patient_name = _extract_patient_name(text)
        ordering_provider = _extract_provider(text)

        # Parse markers page by page
        pages = text.split("\f")
        for page_num, page_text in enumerate(pages, start=1):
            page_markers, page_warnings = _parse_page(
                page_text, page_num, format_matched=True
            )
            markers.extend(page_markers)
            warnings.extend(page_warnings)

        # Remove duplicates (same canonical_name) — keep highest confidence
        markers = _deduplicate_markers(markers)

        needs_review = any(m.confidence < 0.70 for m in markers)
        overall_confidence = compute_overall_confidence(markers)

        return ParseResult(
            success=True,
            parser_used=self.PARSER_ID,
            format_detected="Quest Diagnostics",
            confidence=overall_confidence,
            patient_name=patient_name,
            collection_date=collection_date,
            report_date=report_date,
            lab_name="Quest Diagnostics",
            ordering_provider=ordering_provider,
            markers=markers,
            warnings=warnings,
            needs_review=needs_review,
            parse_time_ms=int((time.monotonic() - t0) * 1000),
        )


# ---------------------------------------------------------------------------
# Private parsing helpers
# ---------------------------------------------------------------------------


def _extract_date(text: str, patterns: list[re.Pattern]) -> date | None:
    for pattern in patterns:
        m = pattern.search(text)
        if m:
            raw = m.group(1)
            parsed = _parse_date_str(raw)
            if parsed:
                return parsed
    return None


def _parse_date_str(raw: str) -> date | None:
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y",
                "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _extract_patient_name(text: str) -> str | None:
    m = _PATIENT_NAME_RE.search(text[:2000])
    if m:
        return m.group(1).strip()
    return None


def _extract_provider(text: str) -> str | None:
    m = _PROVIDER_RE.search(text[:2000])
    if m:
        raw = m.group(1).strip()
        # Remove trailing metadata (NPI, ID numbers, etc.)
        raw = re.split(r"\s{2,}|\t|NPI", raw)[0].strip()
        if len(raw) > 3:
            return raw
    return None


def _parse_page(
    page_text: str,
    page_num: int,
    format_matched: bool,
) -> tuple[list[MarkerResult], list[str]]:
    """Extract all marker results from a single page of text."""
    markers: list[MarkerResult] = []
    warnings: list[str] = []

    lines = page_text.splitlines()

    for line in lines:
        # Skip non-result lines early
        if _SKIP_LINE_RE.match(line):
            continue

        stripped = line.strip()
        if len(stripped) < 5:
            continue

        marker = _parse_result_line(stripped, page_num, format_matched)
        if marker is not None:
            markers.append(marker)

    return markers, warnings


def _parse_result_line(
    line: str,
    page_num: int,
    format_matched: bool,
) -> MarkerResult | None:
    """Attempt to parse a single text line into a MarkerResult.

    Returns None if the line doesn't look like a result row.
    """
    # Try qualitative first
    qm = _QUALITATIVE_RE.match(line)
    if qm:
        return _build_qualitative_marker(
            qm.group("name"), qm.group("value"), page_num, format_matched
        )

    # Try primary regex
    m = _RESULT_LINE_RE.match(line)
    if m:
        return _build_numeric_marker(
            name=m.group("name"),
            value_text=m.group("value") or "",
            flag=m.group("flag"),
            ref_text=m.group("ref") or "",
            unit=m.group("unit") or "",
            page_num=page_num,
            format_matched=format_matched,
        )

    # Try simple fallback
    sm = _RESULT_LINE_SIMPLE_RE.match(line)
    if sm:
        rest = sm.group("rest")
        # Split rest into ref and unit by whitespace
        parts = rest.split()
        ref_text = parts[0] if parts else ""
        unit = parts[1] if len(parts) > 1 else ""
        return _build_numeric_marker(
            name=sm.group("name"),
            value_text=sm.group("value") or "",
            flag=sm.group("flag"),
            ref_text=ref_text,
            unit=unit,
            page_num=page_num,
            format_matched=format_matched,
        )

    return None


def _build_numeric_marker(
    name: str,
    value_text: str,
    flag: str | None,
    ref_text: str,
    unit: str,
    page_num: int,
    format_matched: bool,
) -> MarkerResult | None:
    """Build a MarkerResult for a numeric test result."""
    name = name.strip()
    value_text = value_text.strip()

    if not name or not value_text:
        return None

    # Separate embedded flag from value_text (e.g. "5.2 H" or "5.2H")
    detected_flag = flag
    vt_clean = value_text
    if not detected_flag:
        flag_match = re.search(r"\s*([HLAChlac])\s*$", value_text)
        if flag_match:
            detected_flag = flag_match.group(1).upper()
            vt_clean = value_text[: flag_match.start()].strip()

    # Parse numeric value
    value = _safe_float(vt_clean)

    # Parse reference range
    ref_low, ref_high = _parse_reference_range(ref_text)

    # Normalise marker name
    canonical, match_score = normalize_marker_name(name)
    canonical_unit = normalize_unit(unit)

    # Confidence scoring
    conf, reasons = score_marker(
        format_matched=format_matched,
        name_in_dictionary=canonical is not None,
        value_text=vt_clean,
        unit=unit,
        reference_low=ref_low,
        reference_high=ref_high,
        reference_text=ref_text,
    )

    if value is None:
        return None  # can't build a marker without a parseable value

    return MarkerResult(
        canonical_name=canonical or _slugify(name),
        display_name=name,
        value=value,
        value_text=vt_clean,
        unit=unit,
        canonical_unit=canonical_unit,
        reference_low=ref_low,
        reference_high=ref_high,
        reference_text=ref_text,
        flag=detected_flag,
        confidence=conf,
        confidence_reasons=reasons,
        page=page_num,
    )


def _build_qualitative_marker(
    name: str,
    value_text: str,
    page_num: int,
    format_matched: bool,
) -> MarkerResult | None:
    name = name.strip()
    value_text = value_text.strip()
    if not name:
        return None

    canonical, _ = normalize_marker_name(name)
    conf, reasons = score_marker(
        format_matched=format_matched,
        name_in_dictionary=canonical is not None,
        value_text=value_text,
        unit="",
        reference_low=None,
        reference_high=None,
        reference_text="",
    )

    # Use 0.0 as the numeric value for qualitative; value_text carries meaning
    return MarkerResult(
        canonical_name=canonical or _slugify(name),
        display_name=name,
        value=0.0,
        value_text=value_text,
        unit="",
        canonical_unit="",
        confidence=conf,
        confidence_reasons=reasons,
        page=page_num,
    )


def _parse_reference_range(text: str) -> tuple[float | None, float | None]:
    """Parse a reference range string into (low, high).

    Handles:
        "70-99"       → (70, 99)
        "70 - 99"     → (70, 99)
        ">59"         → (59, None)
        "<200"        → (None, 200)
        "0.60-1.35"   → (0.60, 1.35)
        "Negative"    → (None, None)
    """
    if not text:
        return None, None

    text = text.strip()

    # Range with dash
    range_m = re.match(r"([<>≤≥]?\s*[\d,\.]+)\s*[-–]\s*([\d,\.]+)", text)
    if range_m:
        low = _safe_float(range_m.group(1))
        high = _safe_float(range_m.group(2))
        return low, high

    # Greater-than only (e.g. ">59" means low is 59)
    gt_m = re.match(r"[>≥]\s*([\d,\.]+)", text)
    if gt_m:
        return _safe_float(gt_m.group(1)), None

    # Less-than only (e.g. "<200" means high is 200)
    lt_m = re.match(r"[<≤]\s*([\d,\.]+)", text)
    if lt_m:
        return None, _safe_float(lt_m.group(1))

    return None, None


def _safe_float(text: str) -> float | None:
    if not text:
        return None
    text = text.strip()
    for prefix in (">", "<", ">=", "<=", "≥", "≤", "~"):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    text = text.rstrip("HLAChlac").strip()
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _slugify(name: str) -> str:
    """Convert a display name to a snake_case slug for unknown markers."""
    return re.sub(r"\W+", "_", name.lower()).strip("_")


def _deduplicate_markers(markers: list[MarkerResult]) -> list[MarkerResult]:
    """Keep only the highest-confidence result for each canonical_name."""
    seen: dict[str, MarkerResult] = {}
    for m in markers:
        existing = seen.get(m.canonical_name)
        if existing is None or m.confidence > existing.confidence:
            seen[m.canonical_name] = m
    # Preserve original order of first occurrence
    order = {m.canonical_name: i for i, m in enumerate(markers)}
    return sorted(seen.values(), key=lambda m: order.get(m.canonical_name, 0))
