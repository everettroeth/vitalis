"""Confidence scoring logic for the Vitalis parser engine.

Scores are built additively from multiple evidence signals.  Each signal
contributes a fixed weight; the total is capped at 1.0.

Weights (must sum to 1.0):
    format_match        0.30  — adapter recognised the document format
    name_in_dictionary  0.20  — canonical_name resolved via biomarker_dictionary
    value_parseable     0.20  — numeric value cleanly extracted
    unit_recognised     0.15  — unit is known / canonical
    reference_parseable 0.15  — reference range parsed into low/high floats
"""

from __future__ import annotations

from src.parsers.base import ConfidenceLevel, MarkerResult

# ---------------------------------------------------------------------------
# Weight constants
# ---------------------------------------------------------------------------

W_FORMAT_MATCH = 0.30
W_NAME_IN_DICT = 0.20
W_VALUE_PARSED = 0.20
W_UNIT_KNOWN = 0.15
W_REF_PARSED = 0.15

# Set of units we recognise as canonical / well-known.
KNOWN_UNITS: frozenset[str] = frozenset(
    {
        # Concentration
        "mg/dL",
        "g/dL",
        "g/L",
        "mmol/L",
        "µmol/L",
        "umol/L",
        "nmol/L",
        "pmol/L",
        "ng/dL",
        "ng/mL",
        "pg/mL",
        "µg/dL",
        "ug/dL",
        "µg/mL",
        "ug/mL",
        "µIU/mL",
        "uIU/mL",
        "mIU/L",
        "mIU/mL",
        "IU/L",
        "IU/mL",
        "U/L",
        "mU/L",
        # Count / volume
        "10^3/µL",
        "10^3/uL",
        "10^6/µL",
        "10^6/uL",
        "K/µL",
        "K/uL",
        "M/µL",
        "M/uL",
        "cells/µL",
        # Ratios / percent
        "%",
        "ratio",
        "index",
        # Velocity / clearance
        "mL/min/1.73m2",
        "mL/min",
        "mm/hr",
        # Mass per time
        "µg/24hr",
        "mg/24hr",
        # Misc
        "fL",
        "pg",
        "sec",
        "nmol/mg",
    }
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score_marker(
    *,
    format_matched: bool,
    name_in_dictionary: bool,
    value_text: str,
    unit: str,
    reference_low: float | None,
    reference_high: float | None,
    reference_text: str,
) -> tuple[float, list[str]]:
    """Compute a confidence score (0.0–1.0) for a single parsed marker.

    Returns:
        (score, reasons) where ``reasons`` is a list of human-readable
        strings explaining what contributed to (or deducted from) the score.
    """
    score = 0.0
    reasons: list[str] = []

    # 1. Format match
    if format_matched:
        score += W_FORMAT_MATCH
        reasons.append("format matched known lab template (+0.30)")
    else:
        reasons.append("format not recognised — using generic extraction (+0.00)")

    # 2. Name in biomarker dictionary
    if name_in_dictionary:
        score += W_NAME_IN_DICT
        reasons.append("marker name resolved in biomarker dictionary (+0.20)")
    else:
        reasons.append("marker name not found in dictionary (+0.00)")

    # 3. Value parseable as float
    value_clean = _strip_decorations(value_text)
    try:
        float(value_clean.replace(",", ""))
        score += W_VALUE_PARSED
        reasons.append("numeric value cleanly parsed (+0.20)")
    except ValueError:
        # Check for known qualitative values
        qualitative = {
            "non-reactive",
            "reactive",
            "negative",
            "positive",
            "detected",
            "not detected",
            "normal",
            "abnormal",
            "see note",
            "borderline",
        }
        if value_text.strip().lower() in qualitative:
            score += W_VALUE_PARSED * 0.5
            reasons.append("qualitative value recognised (partial credit +0.10)")
        else:
            reasons.append("value could not be parsed as number (+0.00)")

    # 4. Unit recognised
    unit_norm = unit.strip()
    if unit_norm in KNOWN_UNITS or unit_norm.lower() in {u.lower() for u in KNOWN_UNITS}:
        score += W_UNIT_KNOWN
        reasons.append(f"unit '{unit_norm}' is recognised (+0.15)")
    elif unit_norm == "":
        # Some markers are unitless (ratios, ANA titre, etc.)
        score += W_UNIT_KNOWN * 0.5
        reasons.append("no unit present — may be unitless ratio (+0.08)")
    else:
        reasons.append(f"unit '{unit_norm}' not in known set (+0.00)")

    # 5. Reference range parsed
    if reference_low is not None or reference_high is not None:
        score += W_REF_PARSED
        reasons.append("reference range successfully parsed (+0.15)")
    elif reference_text.strip():
        # We have the text but couldn't parse it numerically
        score += W_REF_PARSED * 0.5
        reasons.append("reference text present but not numeric (+0.08)")
    else:
        reasons.append("no reference range found (+0.00)")

    return min(score, 1.0), reasons


def compute_overall_confidence(markers: list[MarkerResult]) -> ConfidenceLevel:
    """Derive the overall ParseResult confidence from all marker scores.

    Strategy: use a weighted combination — median score for stability,
    but penalise heavily if many markers have low confidence.
    """
    if not markers:
        return ConfidenceLevel.UNCERTAIN

    scores = [m.confidence for m in markers]
    scores.sort()

    n = len(scores)
    median = scores[n // 2]

    # Fraction of markers with confidence < 0.5
    low_fraction = sum(1 for s in scores if s < 0.5) / n

    adjusted = median - (low_fraction * 0.2)
    return ConfidenceLevel.from_score(max(adjusted, 0.0))


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _strip_decorations(text: str) -> str:
    """Remove common prefixes/suffixes that prevent float() parsing."""
    text = text.strip()
    for prefix in (">=", "<=", ">", "<", "≥", "≤", "~"):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    # Strip trailing flag letters
    while text and text[-1].upper() in "HLAC":
        text = text[:-1].strip()
    return text
