"""Tests for the confidence scoring module."""

from __future__ import annotations

import pytest

from src.parsers.base import ConfidenceLevel, MarkerResult
from src.parsers.confidence import (
    score_marker,
    compute_overall_confidence,
    KNOWN_UNITS,
)


# ---------------------------------------------------------------------------
# score_marker
# ---------------------------------------------------------------------------


class TestScoreMarker:
    def test_perfect_score(self):
        """All signals present → score should be 1.0."""
        score, reasons = score_marker(
            format_matched=True,
            name_in_dictionary=True,
            value_text="95",
            unit="mg/dL",
            reference_low=70.0,
            reference_high=99.0,
            reference_text="70-99",
        )
        assert score == pytest.approx(1.0, abs=0.01)
        assert len(reasons) == 5

    def test_no_format_match_reduces_score(self):
        score, _ = score_marker(
            format_matched=False,
            name_in_dictionary=True,
            value_text="95",
            unit="mg/dL",
            reference_low=70.0,
            reference_high=99.0,
            reference_text="70-99",
        )
        # Missing format match = -0.30 from max
        assert score == pytest.approx(0.70, abs=0.01)

    def test_name_not_in_dictionary(self):
        score, _ = score_marker(
            format_matched=True,
            name_in_dictionary=False,
            value_text="95",
            unit="mg/dL",
            reference_low=70.0,
            reference_high=99.0,
            reference_text="70-99",
        )
        assert score == pytest.approx(0.80, abs=0.01)

    def test_unparseable_value_penalised(self):
        score, reasons = score_marker(
            format_matched=True,
            name_in_dictionary=True,
            value_text="PENDING",
            unit="mg/dL",
            reference_low=70.0,
            reference_high=99.0,
            reference_text="70-99",
        )
        # No value credit
        assert score == pytest.approx(0.80, abs=0.01)
        assert any("could not be parsed" in r for r in reasons)

    def test_qualitative_value_partial_credit(self):
        score, reasons = score_marker(
            format_matched=True,
            name_in_dictionary=True,
            value_text="Negative",
            unit="",
            reference_low=None,
            reference_high=None,
            reference_text="",
        )
        # Qualitative gets 0.5 × W_VALUE_PARSED = 0.10
        # No unit, no ref → also deducted
        # format(0.30) + dict(0.20) + qual(0.10) + no_unit(0.08) + no_ref(0.00)
        assert score == pytest.approx(0.68, abs=0.05)

    def test_unknown_unit_penalised(self):
        score, reasons = score_marker(
            format_matched=True,
            name_in_dictionary=True,
            value_text="95",
            unit="widgets",
            reference_low=70.0,
            reference_high=99.0,
            reference_text="70-99",
        )
        assert score == pytest.approx(0.85, abs=0.01)
        assert any("not in known set" in r for r in reasons)

    def test_no_reference_range_penalised(self):
        score, _ = score_marker(
            format_matched=True,
            name_in_dictionary=True,
            value_text="95",
            unit="mg/dL",
            reference_low=None,
            reference_high=None,
            reference_text="",
        )
        assert score == pytest.approx(0.85, abs=0.01)

    def test_ref_text_present_partial_credit(self):
        score, reasons = score_marker(
            format_matched=True,
            name_in_dictionary=True,
            value_text="95",
            unit="mg/dL",
            reference_low=None,
            reference_high=None,
            reference_text="See Note",
        )
        assert score == pytest.approx(0.925, abs=0.01)
        assert any("text present but not numeric" in r for r in reasons)

    def test_score_capped_at_1(self):
        """Score must never exceed 1.0."""
        score, _ = score_marker(
            format_matched=True,
            name_in_dictionary=True,
            value_text="42",
            unit="mg/dL",
            reference_low=20.0,
            reference_high=80.0,
            reference_text="20-80",
        )
        assert score <= 1.0

    def test_score_non_negative(self):
        score, _ = score_marker(
            format_matched=False,
            name_in_dictionary=False,
            value_text="GARBAGE",
            unit="??",
            reference_low=None,
            reference_high=None,
            reference_text="",
        )
        assert score >= 0.0


# ---------------------------------------------------------------------------
# ConfidenceLevel.from_score
# ---------------------------------------------------------------------------


class TestConfidenceLevelFromScore:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (0.95, ConfidenceLevel.HIGH),
            (0.90, ConfidenceLevel.HIGH),
            (0.85, ConfidenceLevel.MEDIUM),
            (0.70, ConfidenceLevel.MEDIUM),
            (0.65, ConfidenceLevel.LOW),
            (0.50, ConfidenceLevel.LOW),
            (0.49, ConfidenceLevel.UNCERTAIN),
            (0.0, ConfidenceLevel.UNCERTAIN),
        ],
    )
    def test_bands(self, score: float, expected: ConfidenceLevel):
        assert ConfidenceLevel.from_score(score) == expected


# ---------------------------------------------------------------------------
# compute_overall_confidence
# ---------------------------------------------------------------------------


class TestComputeOverallConfidence:
    def _make_marker(self, confidence: float) -> MarkerResult:
        return MarkerResult(
            canonical_name="glucose",
            display_name="Glucose",
            value=95.0,
            value_text="95",
            unit="mg/dL",
            confidence=confidence,
        )

    def test_all_high_confidence(self):
        markers = [self._make_marker(0.95) for _ in range(5)]
        result = compute_overall_confidence(markers)
        assert result == ConfidenceLevel.HIGH

    def test_all_low_confidence(self):
        markers = [self._make_marker(0.40) for _ in range(5)]
        result = compute_overall_confidence(markers)
        assert result == ConfidenceLevel.UNCERTAIN

    def test_mixed_confidence_penalised(self):
        # 50% markers < 0.5 should penalise the score
        markers = (
            [self._make_marker(0.95) for _ in range(5)]
            + [self._make_marker(0.30) for _ in range(5)]
        )
        result = compute_overall_confidence(markers)
        # Should be at most MEDIUM due to penalty
        assert result in (ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW)

    def test_empty_markers(self):
        result = compute_overall_confidence([])
        assert result == ConfidenceLevel.UNCERTAIN

    def test_single_marker(self):
        markers = [self._make_marker(0.92)]
        result = compute_overall_confidence(markers)
        assert result == ConfidenceLevel.HIGH


# ---------------------------------------------------------------------------
# KNOWN_UNITS completeness
# ---------------------------------------------------------------------------


def test_known_units_includes_common():
    assert "mg/dL" in KNOWN_UNITS
    assert "g/dL" in KNOWN_UNITS
    assert "10^3/µL" in KNOWN_UNITS
    assert "mIU/L" in KNOWN_UNITS
    assert "%" in KNOWN_UNITS
    assert "U/L" in KNOWN_UNITS
