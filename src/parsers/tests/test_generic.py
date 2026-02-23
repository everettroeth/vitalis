"""Tests for the generic AI fallback parser."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.parsers.adapters.generic import GenericAIParser, _heuristic_extract
from src.parsers.base import ConfidenceLevel
from src.parsers.tests.conftest import GENERIC_LAB_TEXT, FAKE_PDF_BYTES


@pytest.fixture
def parser() -> GenericAIParser:
    """Generic parser with LLM disabled by default in tests."""
    return GenericAIParser(use_llm=False)


# ---------------------------------------------------------------------------
# can_parse — always True
# ---------------------------------------------------------------------------


def test_can_parse_always_true(parser: GenericAIParser):
    assert parser.can_parse("anything") is True
    assert parser.can_parse("") is True
    assert parser.can_parse("Quest Diagnostics blah blah") is True


# ---------------------------------------------------------------------------
# Heuristic extraction
# ---------------------------------------------------------------------------


class TestHeuristicExtract:
    def test_extracts_glucose(self):
        markers, warnings = _heuristic_extract(GENERIC_LAB_TEXT)
        glucose = next((m for m in markers if m.canonical_name == "glucose"), None)
        assert glucose is not None
        assert glucose.value == pytest.approx(92.0)
        assert glucose.unit == "mg/dL"

    def test_extracts_hba1c(self):
        markers, _ = _heuristic_extract(GENERIC_LAB_TEXT)
        hba1c = next((m for m in markers if m.canonical_name == "hba1c"), None)
        assert hba1c is not None
        assert hba1c.value == pytest.approx(5.4)

    def test_extracts_vitamin_d(self):
        markers, _ = _heuristic_extract(GENERIC_LAB_TEXT)
        vd = next((m for m in markers if m.canonical_name == "vitamin_d_25oh"), None)
        assert vd is not None
        assert vd.value == pytest.approx(42.0)

    def test_extracts_ferritin(self):
        markers, _ = _heuristic_extract(GENERIC_LAB_TEXT)
        ferritin = next((m for m in markers if m.canonical_name == "ferritin"), None)
        assert ferritin is not None
        assert ferritin.value == pytest.approx(85.0)

    def test_extracts_hscrp(self):
        markers, _ = _heuristic_extract(GENERIC_LAB_TEXT)
        crp = next((m for m in markers if m.canonical_name == "hs_crp"), None)
        assert crp is not None
        assert crp.value == pytest.approx(0.8)

    def test_no_duplicates(self):
        markers, _ = _heuristic_extract(GENERIC_LAB_TEXT)
        names = [m.canonical_name for m in markers]
        assert len(names) == len(set(names))

    def test_empty_text_returns_empty(self):
        markers, _ = _heuristic_extract("")
        assert markers == []

    def test_does_not_extract_header_lines(self):
        text = "ACME LAB\nPatient: John\nCollection Date: 01/01/2024\n\nGlucose  92  mg/dL  70-99"
        markers, _ = _heuristic_extract(text)
        # Should only find Glucose, not header lines
        names = [m.canonical_name for m in markers]
        assert "glucose" in names
        # Headers should not appear as markers
        assert "acme_lab" not in names


# ---------------------------------------------------------------------------
# parse — full integration (no LLM)
# ---------------------------------------------------------------------------


class TestGenericParse:
    def test_parse_returns_result(self, parser: GenericAIParser):
        result = parser.parse(GENERIC_LAB_TEXT, FAKE_PDF_BYTES)
        assert result is not None
        assert result.parser_used == "generic_ai"

    def test_needs_review_always_true(self, parser: GenericAIParser):
        result = parser.parse(GENERIC_LAB_TEXT, FAKE_PDF_BYTES)
        assert result.needs_review is True

    def test_contains_review_warning(self, parser: GenericAIParser):
        result = parser.parse(GENERIC_LAB_TEXT, FAKE_PDF_BYTES)
        assert any("review" in w.lower() for w in result.warnings)

    def test_format_detected_is_unknown(self, parser: GenericAIParser):
        result = parser.parse(GENERIC_LAB_TEXT, FAKE_PDF_BYTES)
        assert "Unknown" in result.format_detected

    def test_markers_extracted_by_heuristic(self, parser: GenericAIParser):
        result = parser.parse(GENERIC_LAB_TEXT, FAKE_PDF_BYTES)
        assert result.success is True
        assert len(result.markers) >= 5

    def test_confidence_low_or_uncertain(self, parser: GenericAIParser):
        result = parser.parse(GENERIC_LAB_TEXT, FAKE_PDF_BYTES)
        assert result.confidence in (
            ConfidenceLevel.LOW,
            ConfidenceLevel.MEDIUM,
            ConfidenceLevel.UNCERTAIN,
        )

    def test_completely_empty_text_fails(self, parser: GenericAIParser):
        result = parser.parse("", FAKE_PDF_BYTES)
        assert result.success is False


# ---------------------------------------------------------------------------
# LLM extraction (mocked)
# ---------------------------------------------------------------------------


class TestLLMExtraction:
    def test_llm_called_when_heuristic_fails(self):
        parser = GenericAIParser(use_llm=True)

        llm_response = [
            {
                "name": "Glucose",
                "value": 95.0,
                "value_text": "95",
                "unit": "mg/dL",
                "reference_range": "70-99",
                "flag": None,
            }
        ]

        with patch("src.parsers.adapters.generic._llm_extract") as mock_llm:
            mock_llm.return_value = (
                [],  # will be called, return empty to test second call
                ["LLM would be called"],
            )
            # Patch heuristic to return nothing
            with patch("src.parsers.adapters.generic._heuristic_extract") as mock_h:
                mock_h.return_value = ([], [])
                result = parser.parse("some unrecognized text", FAKE_PDF_BYTES)

            assert mock_llm.called

    def test_llm_json_parsing(self):
        """Test that valid JSON from LLM is correctly parsed into markers."""
        import json
        from src.parsers.adapters.generic import _item_to_marker

        item = {
            "name": "Hemoglobin A1c",
            "value": 5.4,
            "value_text": "5.4",
            "unit": "%",
            "reference_range": "<5.7",
            "flag": None,
        }
        marker = _item_to_marker(item)
        assert marker is not None
        assert marker.canonical_name == "hba1c"
        assert marker.value == pytest.approx(5.4)
        assert marker.reference_high == pytest.approx(5.7)

    def test_llm_null_value_handled(self):
        from src.parsers.adapters.generic import _item_to_marker

        item = {
            "name": "ANA Screen",
            "value": None,
            "value_text": "Negative",
            "unit": "",
            "reference_range": "",
            "flag": None,
        }
        marker = _item_to_marker(item)
        assert marker is not None
        assert marker.display_name == "ANA Screen"
        assert marker.value_text == "Negative"

    def test_llm_malformed_item_returns_none(self):
        from src.parsers.adapters.generic import _item_to_marker

        assert _item_to_marker({}) is None
        assert _item_to_marker({"name": ""}) is None
