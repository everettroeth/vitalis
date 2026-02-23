"""Labcorp (Laboratory Corporation of America) lab report parser.

Labcorp PDFs have these distinguishing features:
  - Header contains "Laboratory Corporation of America", "Labcorp",
    or "LabCorp" within the first few hundred characters.
  - May include "FINAL REPORT" watermark text.
  - Patient info block: Name, DOB, Sex, Specimen ID, Date of Collection.
  - Column ordering slightly different from Quest:
        Test Name    Value    Flag    Units    Reference Interval

  Typical result rows:
      Total Cholesterol     185          mg/dL    <200
      HDL Cholesterol        55          mg/dL    >40
      LDL Cholesterol       105    H     mg/dL    <100
      Triglycerides         120          mg/dL    <150

  Notes:
    - "Reference Interval" column may be last, unlike Quest where it comes
      before Units.
    - Some tests have inline reference ranges: "40-59" or "<200".
    - Flagged values: "H", "L", "A" or "C" (critical) in Flag column.
    - Multi-page reports common for comprehensive panels.
    - Some Labcorp PDFs emit results inside a bordered table; pdfplumber
      usually flattens these correctly.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime

from src.parsers.base import BaseParser, MarkerResult, ParseResult, ConfidenceLevel
from src.parsers.confidence import score_marker, compute_overall_confidence
from src.parsers.normalizer import normalize_marker_name, normalize_unit

logger = logging.getLogger("vitalis.parsers.labcorp")

# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

_LABCORP_PATTERNS: list[re.Pattern] = [
    re.compile(r"laboratory\s+corporation\s+of\s+america", re.IGNORECASE),
    re.compile(r"labcorp", re.IGNORECASE),
    re.compile(r"lab\s*corp", re.IGNORECASE),
    re.compile(r"lca\s+patient", re.IGNORECASE),
    re.compile(r"labcorp\.com", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Date / metadata patterns
# ---------------------------------------------------------------------------

_DATE_PATTERNS = [
    re.compile(r"date\s+of\s+collection\s*[:\-]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", re.IGNORECASE),
    re.compile(r"collected\s*[:\-]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", re.IGNORECASE),
    re.compile(r"specimen\s+received\s*[:\-]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", re.IGNORECASE),
    re.compile(r"date\s+of\s+service\s*[:\-]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", re.IGNORECASE),
]
_REPORT_DATE_PATTERNS = [
    re.compile(r"date\s+reported\s*[:\-]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", re.IGNORECASE),
    re.compile(r"reported\s*[:\-]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", re.IGNORECASE),
    re.compile(r"report\s+date\s*[:\-]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", re.IGNORECASE),
]

_PATIENT_NAME_RE = re.compile(
    r"patient(?:\s+name)?\s*[:\-]?\s*([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)+)",
    re.IGNORECASE,
)
_PROVIDER_RE = re.compile(
    r"(?:ordering\s+)?(?:physician|provider|clinician)\s*[:\-]?\s*(.+?)(?:\n|$)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Result line patterns
# ---------------------------------------------------------------------------

# Primary Labcorp format:
#   Test Name    Value    Flag    Units    Reference Interval
# OR
#   Test Name    Value    Units   Flag    Reference Interval
#
# The key difference from Quest: Units often come BEFORE Reference Interval.
_RESULT_LINE_RE = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z0-9 ,\(\)/'\-\.%]{2,}?)"
    r"\s{2,}"
    r"(?P<value>[<>≤≥]?\s*[\d,\.]+(?:\s*[HLAChlac])?)"
    r"(?:\s+(?P<flag>[HLAChlac]{1,2}))?"
    r"\s+"
    r"(?P<unit>[a-zA-Z%µ/\^0-9\.]+(?:/[a-zA-Z0-9\^\.µ]+)*)?"
    r"\s*"
    r"(?P<ref>[<>≤≥]?\d[\d,\.]*(?:\s*[-–]\s*[<>≤≥]?\d[\d,\.]*)?|[<>≤≥]\d[\d,\.]*)?"
    r"\s*$",
    re.VERBOSE,
)

# Qualitative result line
_QUALITATIVE_RE = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z0-9 ,\(\)/'\-\.%]{2,}?)\s{2,}"
    r"(?P<value>Non-?Reactive|Reactive|Negative|Positive|Detected|Not\s+Detected|Normal|Abnormal|See\s+Note|None\s+Detected)"
    r".*$",
    re.IGNORECASE,
)

# Skip header / divider / metadata lines
_SKIP_LINE_RE = re.compile(
    r"^\s*$"
    r"|^\s*[-=_*]{3,}"
    r"|^\s*(?:Test\s+Name|TESTS?\s+ORDERED|Test\s+Result|Value|Flag|Reference|Units|Page\s+\d)"
    r"|^\s*(?:Specimen|Collected|Reported|Patient|Physician|NPI|Acct|Lab|Client|FINAL\s+REPORT|LabCorp)"
    r"|^\s*\*+\s*"
    r"|^\s*\d+\s*$"
    r"|^\s*(?:Continued|Refer\s+to|See\s+Note|Note\s*:)",
    re.IGNORECASE,
)


class LabcorpParser(BaseParser):
    """Parser for Labcorp (Laboratory Corporation of America) lab reports."""

    PARSER_ID = "labcorp_v1"
    PRIORITY = 10
    LAB_NAME = "Labcorp"

    def can_parse(self, text: str, filename: str = "") -> bool:
        if "labcorp" in filename.lower():
            return True
        sample = text[:3000]
        return any(p.search(sample) for p in _LABCORP_PATTERNS)

    def parse(self, text: str, file_bytes: bytes, filename: str = "") -> ParseResult:
        import time
        t0 = time.monotonic()

        warnings: list[str] = []
        markers: list[MarkerResult] = []

        collection_date = _extract_date(text, _DATE_PATTERNS)
        report_date = _extract_date(text, _REPORT_DATE_PATTERNS)
        patient_name = _extract_patient_name(text)
        ordering_provider = _extract_provider(text)

        pages = text.split("\f")
        for page_num, page_text in enumerate(pages, start=1):
            page_markers, page_warnings = _parse_page(
                page_text, page_num, format_matched=True
            )
            markers.extend(page_markers)
            warnings.extend(page_warnings)

        markers = _deduplicate_markers(markers)
        needs_review = any(m.confidence < 0.70 for m in markers)
        overall_confidence = compute_overall_confidence(markers)

        return ParseResult(
            success=True,
            parser_used=self.PARSER_ID,
            format_detected="Labcorp",
            confidence=overall_confidence,
            patient_name=patient_name,
            collection_date=collection_date,
            report_date=report_date,
            lab_name="Labcorp",
            ordering_provider=ordering_provider,
            markers=markers,
            warnings=warnings,
            needs_review=needs_review,
            parse_time_ms=int((time.monotonic() - t0) * 1000),
        )


# ---------------------------------------------------------------------------
# Private helpers (mostly shared with quest.py pattern — kept separate
# for independent evolution of each parser)
# ---------------------------------------------------------------------------


def _extract_date(text: str, patterns: list[re.Pattern]) -> date | None:
    for p in patterns:
        m = p.search(text)
        if m:
            parsed = _parse_date_str(m.group(1))
            if parsed:
                return parsed
    return None


def _parse_date_str(raw: str) -> date | None:
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y",
                "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _extract_patient_name(text: str) -> str | None:
    m = _PATIENT_NAME_RE.search(text[:2000])
    return m.group(1).strip() if m else None


def _extract_provider(text: str) -> str | None:
    m = _PROVIDER_RE.search(text[:2000])
    if m:
        raw = re.split(r"\s{2,}|\t", m.group(1).strip())[0].strip()
        return raw if len(raw) > 3 else None
    return None


def _parse_page(
    page_text: str, page_num: int, format_matched: bool
) -> tuple[list[MarkerResult], list[str]]:
    markers: list[MarkerResult] = []
    warnings: list[str] = []

    for line in page_text.splitlines():
        if _SKIP_LINE_RE.match(line):
            continue
        stripped = line.strip()
        if len(stripped) < 5:
            continue
        marker = _parse_result_line(stripped, page_num, format_matched)
        if marker:
            markers.append(marker)

    return markers, warnings


def _parse_result_line(
    line: str, page_num: int, format_matched: bool
) -> MarkerResult | None:
    qm = _QUALITATIVE_RE.match(line)
    if qm:
        return _build_qualitative(qm.group("name"), qm.group("value"), page_num, format_matched)

    m = _RESULT_LINE_RE.match(line)
    if m:
        return _build_numeric(
            name=m.group("name"),
            value_text=m.group("value") or "",
            flag=m.group("flag"),
            unit=m.group("unit") or "",
            ref_text=m.group("ref") or "",
            page_num=page_num,
            format_matched=format_matched,
        )
    return None


def _build_numeric(
    name: str,
    value_text: str,
    flag: str | None,
    unit: str,
    ref_text: str,
    page_num: int,
    format_matched: bool,
) -> MarkerResult | None:
    name = name.strip()
    value_text = value_text.strip()
    if not name or not value_text:
        return None

    detected_flag = flag
    vt_clean = value_text
    if not detected_flag:
        fm = re.search(r"\s*([HLAChlac])\s*$", value_text)
        if fm:
            detected_flag = fm.group(1).upper()
            vt_clean = value_text[: fm.start()].strip()

    value = _safe_float(vt_clean)
    if value is None:
        return None

    ref_low, ref_high = _parse_ref(ref_text)
    canonical, _ = normalize_marker_name(name)
    canonical_unit = normalize_unit(unit)

    conf, reasons = score_marker(
        format_matched=format_matched,
        name_in_dictionary=canonical is not None,
        value_text=vt_clean,
        unit=unit,
        reference_low=ref_low,
        reference_high=ref_high,
        reference_text=ref_text,
    )

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


def _build_qualitative(
    name: str, value_text: str, page_num: int, format_matched: bool
) -> MarkerResult | None:
    name = name.strip()
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
    return MarkerResult(
        canonical_name=canonical or _slugify(name),
        display_name=name,
        value=0.0,
        value_text=value_text.strip(),
        unit="",
        canonical_unit="",
        confidence=conf,
        confidence_reasons=reasons,
        page=page_num,
    )


def _parse_ref(text: str) -> tuple[float | None, float | None]:
    if not text:
        return None, None
    text = text.strip()
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
    if not text:
        return None
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


def _slugify(name: str) -> str:
    return re.sub(r"\W+", "_", name.lower()).strip("_")


def _deduplicate_markers(markers: list[MarkerResult]) -> list[MarkerResult]:
    seen: dict[str, MarkerResult] = {}
    for m in markers:
        existing = seen.get(m.canonical_name)
        if existing is None or m.confidence > existing.confidence:
            seen[m.canonical_name] = m
    order = {m.canonical_name: i for i, m in enumerate(markers)}
    return sorted(seen.values(), key=lambda m: order.get(m.canonical_name, 0))
