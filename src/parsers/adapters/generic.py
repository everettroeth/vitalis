"""Generic AI-powered fallback parser.

Used when no format-specific adapter claims the document.  This parser:
  1. Applies heuristic regex extraction to pull any lines that look like
     lab results (catches ~80% of formats without AI).
  2. For remaining unmatched documents, calls an LLM (Claude claude-haiku-4-5-20251001 by default)
     to extract structured data from the raw text.

All results from this parser are marked LOW or UNCERTAIN confidence
and flagged for human review.  This is the safety net — it should handle
Blueprint Bryan Johnson reports, DEXA printouts, hospital discharge summaries,
and any other format we haven't seen before.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import date
from typing import Any

from src.parsers.base import BaseParser, ConfidenceLevel, MarkerResult, ParseResult
from src.parsers.confidence import score_marker, compute_overall_confidence
from src.parsers.normalizer import normalize_marker_name, normalize_unit

logger = logging.getLogger("vitalis.parsers.generic")

# ---------------------------------------------------------------------------
# Heuristic extraction — catches many unknown formats without LLM
# ---------------------------------------------------------------------------

# Any line with a number that could be a lab value
_HEURISTIC_RE = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z0-9 ,\(\)/'\-\.%]{3,40}?)"
    r"\s{2,}"
    r"(?P<value>[<>≤≥~]?\s*[\d,\.]+(?:\s*[HLAChlac])?)"
    r"(?:\s+(?P<flag>[HLAChlac]{1,2}))?"
    r"\s*"
    r"(?P<rest>.*)$"
)

_SKIP_RE = re.compile(
    r"^\s*$|^\s*[-=_*#]{3,}|^\s*\d+\s*$|^\s*Page\s+\d",
    re.IGNORECASE,
)

# LLM prompt template
_EXTRACT_PROMPT = """\
You are a medical data extraction assistant. Extract all lab test results from the following text.

For each result, output a JSON object with these exact fields:
- name: test name as written (string)
- value: numeric result as a float (if qualitative like "Negative", use null)
- value_text: original result text (string)
- unit: measurement unit (string, empty if none)
- reference_range: reference range as written (string, empty if none)
- flag: "H" for high, "L" for low, "A" for abnormal, "C" for critical, null otherwise

Output ONLY a JSON array of objects, one per lab result. No explanation, no markdown.
If there are no lab results, output an empty array [].

Text:
{text}
"""


class GenericAIParser(BaseParser):
    """AI-powered fallback parser for unknown lab report formats.

    Priority is highest (99) so it is always tried last.
    can_parse() always returns True — this is the catch-all.
    """

    PARSER_ID = "generic_ai"
    PRIORITY = 99
    LAB_NAME = "Unknown"

    def __init__(self, use_llm: bool | None = None) -> None:
        """Initialise the parser.

        Args:
            use_llm: Whether to use the LLM fallback when heuristics fail.
                     Defaults to True if ANTHROPIC_API_KEY is set.
        """
        if use_llm is None:
            self._use_llm = bool(os.environ.get("ANTHROPIC_API_KEY"))
        else:
            self._use_llm = use_llm

    def can_parse(self, text: str, filename: str = "") -> bool:
        """Always returns True — this is the catch-all adapter."""
        return True

    def parse(self, text: str, file_bytes: bytes, filename: str = "") -> ParseResult:
        import time
        t0 = time.monotonic()

        warnings = ["Generic AI parser used — result needs human review"]
        markers: list[MarkerResult] = []

        # Step 1: Heuristic extraction
        h_markers, h_warnings = _heuristic_extract(text)
        warnings.extend(h_warnings)

        if h_markers:
            logger.info(
                "Generic heuristic extracted %d markers from %s",
                len(h_markers),
                filename or "<unnamed>",
            )
            markers = h_markers
        elif self._use_llm:
            # Step 2: LLM extraction
            logger.info("Attempting LLM extraction for %s", filename or "<unnamed>")
            llm_markers, llm_warnings = _llm_extract(text)
            markers = llm_markers
            warnings.extend(llm_warnings)
        else:
            warnings.append("LLM extraction disabled — no ANTHROPIC_API_KEY found")

        needs_review = True  # always True for generic parser
        overall = compute_overall_confidence(markers) if markers else ConfidenceLevel.UNCERTAIN

        return ParseResult(
            success=len(markers) > 0,
            parser_used=self.PARSER_ID,
            format_detected="Unknown (Generic)",
            confidence=overall,
            markers=markers,
            warnings=warnings,
            needs_review=needs_review,
            parse_time_ms=int((time.monotonic() - t0) * 1000),
            error=None if markers else "No markers could be extracted",
        )


# ---------------------------------------------------------------------------
# Heuristic extraction
# ---------------------------------------------------------------------------


def _heuristic_extract(text: str) -> tuple[list[MarkerResult], list[str]]:
    """Apply broad regex patterns to extract lab results from any format."""
    markers: list[MarkerResult] = []
    warnings: list[str] = []

    pages = text.split("\f")
    for page_num, page_text in enumerate(pages, start=1):
        for line in page_text.splitlines():
            if _SKIP_RE.match(line):
                continue
            stripped = line.strip()
            if len(stripped) < 8:
                continue

            m = _HEURISTIC_RE.match(stripped)
            if not m:
                continue

            name = m.group("name").strip()
            value_text = m.group("value").strip()
            flag = m.group("flag")
            rest = (m.group("rest") or "").strip()

            # Skip lines where the "name" is too short or looks like a number
            if len(name) < 3 or re.match(r"^\d", name):
                continue

            value = _safe_float(value_text)
            if value is None:
                continue

            # Try to parse unit and ref from rest
            unit, ref_text = _parse_rest(rest)
            ref_low, ref_high = _parse_ref(ref_text)
            canonical, _ = normalize_marker_name(name)
            canonical_unit = normalize_unit(unit)

            # Detect embedded flag in value_text
            if not flag:
                fm = re.search(r"\s*([HLAChlac])\s*$", value_text)
                if fm:
                    flag = fm.group(1).upper()
                    value_text = value_text[: fm.start()].strip()

            conf, reasons = score_marker(
                format_matched=False,  # unknown format
                name_in_dictionary=canonical is not None,
                value_text=value_text,
                unit=unit,
                reference_low=ref_low,
                reference_high=ref_high,
                reference_text=ref_text,
            )

            markers.append(
                MarkerResult(
                    canonical_name=canonical or _slugify(name),
                    display_name=name,
                    value=value,
                    value_text=value_text,
                    unit=unit,
                    canonical_unit=canonical_unit,
                    reference_low=ref_low,
                    reference_high=ref_high,
                    reference_text=ref_text,
                    flag=flag,
                    confidence=conf,
                    confidence_reasons=reasons,
                    page=page_num,
                )
            )

    # Deduplicate
    seen: dict[str, MarkerResult] = {}
    for marker in markers:
        if marker.canonical_name not in seen or marker.confidence > seen[marker.canonical_name].confidence:
            seen[marker.canonical_name] = marker

    return list(seen.values()), warnings


def _parse_rest(rest: str) -> tuple[str, str]:
    """Parse 'rest' of a line into (unit, ref_text).

    Heuristic: if the first token looks like a unit (contains alpha + /),
    treat it as unit and remainder as ref.  Otherwise everything is ref.
    """
    parts = rest.split()
    if not parts:
        return "", ""

    unit_pattern = re.compile(r"^[a-zA-Z%µ][a-zA-Z0-9%µ/\^\.]*$")
    if unit_pattern.match(parts[0]):
        unit = parts[0]
        ref_text = " ".join(parts[1:])
    else:
        unit = ""
        ref_text = rest

    return unit, ref_text


# ---------------------------------------------------------------------------
# LLM extraction
# ---------------------------------------------------------------------------


def _llm_extract(text: str) -> tuple[list[MarkerResult], list[str]]:
    """Call Claude claude-haiku-4-5-20251001 to extract lab results from freeform text."""
    warnings: list[str] = []

    try:
        import anthropic  # type: ignore[import]
    except ImportError:
        warnings.append("anthropic SDK not installed — LLM extraction unavailable")
        return [], warnings

    # Truncate text to stay within token limits (~6000 chars ≈ ~2000 tokens)
    truncated = text[:6000]
    if len(text) > 6000:
        warnings.append(
            f"Document truncated from {len(text)} to 6000 chars for LLM extraction"
        )

    prompt = _EXTRACT_PROMPT.format(text=truncated)

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_response = response.content[0].text.strip()
    except Exception as exc:
        warnings.append(f"LLM extraction failed: {exc}")
        return [], warnings

    # Parse JSON response
    try:
        items = json.loads(raw_response)
    except json.JSONDecodeError:
        # Try to find JSON array in the response
        json_match = re.search(r"\[.*\]", raw_response, re.DOTALL)
        if json_match:
            try:
                items = json.loads(json_match.group())
            except json.JSONDecodeError:
                warnings.append("LLM returned invalid JSON")
                return [], warnings
        else:
            warnings.append("LLM response did not contain valid JSON")
            return [], warnings

    markers: list[MarkerResult] = []
    for item in items:
        marker = _item_to_marker(item)
        if marker:
            markers.append(marker)

    logger.info("LLM extracted %d markers", len(markers))
    return markers, warnings


def _item_to_marker(item: dict[str, Any]) -> MarkerResult | None:
    """Convert a raw LLM-extracted dict to a MarkerResult."""
    try:
        name = str(item.get("name", "")).strip()
        value_text = str(item.get("value_text", "")).strip()
        unit = str(item.get("unit", "")).strip()
        ref_text = str(item.get("reference_range", "")).strip()
        flag = item.get("flag")

        if not name:
            return None

        # value can be null for qualitative results
        raw_value = item.get("value")
        if raw_value is None:
            # Try parsing from value_text
            value = _safe_float(value_text)
        else:
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                value = None

        if value is None:
            # Still create marker for qualitative results
            value = 0.0

        ref_low, ref_high = _parse_ref(ref_text)
        canonical, _ = normalize_marker_name(name)
        canonical_unit = normalize_unit(unit)

        conf, reasons = score_marker(
            format_matched=False,
            name_in_dictionary=canonical is not None,
            value_text=value_text or str(raw_value or ""),
            unit=unit,
            reference_low=ref_low,
            reference_high=ref_high,
            reference_text=ref_text,
        )

        return MarkerResult(
            canonical_name=canonical or _slugify(name),
            display_name=name,
            value=value,
            value_text=value_text,
            unit=unit,
            canonical_unit=canonical_unit,
            reference_low=ref_low,
            reference_high=ref_high,
            reference_text=ref_text,
            flag=flag,
            confidence=conf,
            confidence_reasons=reasons,
            page=1,
        )
    except Exception as exc:
        logger.warning("Failed to convert LLM item to marker: %s — %s", item, exc)
        return None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


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
