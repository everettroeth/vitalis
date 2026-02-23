"""Tests for the Quest Diagnostics parser adapter."""

from __future__ import annotations

import pytest
from datetime import date

from src.parsers.adapters.quest import QuestParser
from src.parsers.base import ConfidenceLevel
from src.parsers.tests.conftest import (
    QUEST_CMP_TEXT,
    QUEST_CBC_TEXT,
    QUEST_FULL_TEXT,
    FAKE_PDF_BYTES,
)


@pytest.fixture
def parser() -> QuestParser:
    return QuestParser()


# ---------------------------------------------------------------------------
# can_parse
# ---------------------------------------------------------------------------


class TestCanParse:
    def test_recognises_quest_header(self, parser: QuestParser):
        assert parser.can_parse(QUEST_CMP_TEXT) is True

    def test_recognises_lowercase(self, parser: QuestParser):
        assert parser.can_parse("quest diagnostics patient report") is True

    def test_rejects_labcorp(self, parser: QuestParser):
        assert parser.can_parse("Laboratory Corporation of America FINAL REPORT") is False

    def test_recognises_by_filename(self, parser: QuestParser):
        assert parser.can_parse("some unrelated text", "quest_results.pdf") is True

    def test_rejects_random_text(self, parser: QuestParser):
        assert parser.can_parse("random unrelated text") is False

    def test_recognises_questdiagnostics_url(self, parser: QuestParser):
        assert parser.can_parse("See results at questdiagnostics.com") is True


# ---------------------------------------------------------------------------
# parse — CMP panel
# ---------------------------------------------------------------------------


class TestParseCMP:
    def test_parse_succeeds(self, parser: QuestParser):
        result = parser.parse(QUEST_CMP_TEXT, FAKE_PDF_BYTES)
        assert result.success is True

    def test_parser_id(self, parser: QuestParser):
        result = parser.parse(QUEST_CMP_TEXT, FAKE_PDF_BYTES)
        assert result.parser_used == "quest_v1"

    def test_lab_name(self, parser: QuestParser):
        result = parser.parse(QUEST_CMP_TEXT, FAKE_PDF_BYTES)
        assert result.lab_name == "Quest Diagnostics"

    def test_collection_date_extracted(self, parser: QuestParser):
        result = parser.parse(QUEST_CMP_TEXT, FAKE_PDF_BYTES)
        assert result.collection_date == date(2024, 3, 15)

    def test_report_date_extracted(self, parser: QuestParser):
        result = parser.parse(QUEST_CMP_TEXT, FAKE_PDF_BYTES)
        assert result.report_date == date(2024, 3, 16)

    def test_patient_name_extracted(self, parser: QuestParser):
        result = parser.parse(QUEST_CMP_TEXT, FAKE_PDF_BYTES)
        assert result.patient_name is not None
        assert "JOHN" in result.patient_name.upper()

    def test_ordering_provider_extracted(self, parser: QuestParser):
        result = parser.parse(QUEST_CMP_TEXT, FAKE_PDF_BYTES)
        assert result.ordering_provider is not None
        assert "Smith" in result.ordering_provider

    def test_glucose_extracted(self, parser: QuestParser):
        result = parser.parse(QUEST_CMP_TEXT, FAKE_PDF_BYTES)
        glucose = next((m for m in result.markers if m.canonical_name == "glucose"), None)
        assert glucose is not None
        assert glucose.value == pytest.approx(95.0)
        assert glucose.unit == "mg/dL"
        assert glucose.reference_low == pytest.approx(70.0)
        assert glucose.reference_high == pytest.approx(99.0)
        assert glucose.flag is None

    def test_all_cmp_markers_present(self, parser: QuestParser):
        result = parser.parse(QUEST_CMP_TEXT, FAKE_PDF_BYTES)
        expected = {
            "glucose", "bun", "creatinine", "egfr", "bun_creatinine_ratio",
            "sodium", "potassium", "chloride", "carbon_dioxide", "calcium",
            "protein_total", "albumin", "globulin", "albumin_globulin_ratio",
            "bilirubin_total", "alkaline_phosphatase", "ast", "alt",
        }
        found = {m.canonical_name for m in result.markers}
        missing = expected - found
        assert not missing, f"Missing markers: {missing}"

    def test_sodium_value(self, parser: QuestParser):
        result = parser.parse(QUEST_CMP_TEXT, FAKE_PDF_BYTES)
        sodium = next((m for m in result.markers if m.canonical_name == "sodium"), None)
        assert sodium is not None
        assert sodium.value == pytest.approx(140.0)

    def test_ast_reference_range(self, parser: QuestParser):
        result = parser.parse(QUEST_CMP_TEXT, FAKE_PDF_BYTES)
        ast = next((m for m in result.markers if m.canonical_name == "ast"), None)
        assert ast is not None
        assert ast.reference_low == pytest.approx(10.0)
        assert ast.reference_high == pytest.approx(40.0)

    def test_high_confidence_for_known_format(self, parser: QuestParser):
        result = parser.parse(QUEST_CMP_TEXT, FAKE_PDF_BYTES)
        high_conf = [m for m in result.markers if m.confidence >= 0.85]
        # Most markers should be high confidence
        assert len(high_conf) >= len(result.markers) * 0.7


# ---------------------------------------------------------------------------
# parse — CBC panel
# ---------------------------------------------------------------------------


class TestParseCBC:
    def test_wbc_extracted(self, parser: QuestParser):
        result = parser.parse(QUEST_CBC_TEXT, FAKE_PDF_BYTES)
        wbc = next((m for m in result.markers if m.canonical_name == "wbc"), None)
        assert wbc is not None
        assert wbc.value == pytest.approx(6.5)
        assert wbc.unit == "10^3/uL"

    def test_hemoglobin_extracted(self, parser: QuestParser):
        result = parser.parse(QUEST_CBC_TEXT, FAKE_PDF_BYTES)
        hgb = next((m for m in result.markers if m.canonical_name == "hemoglobin"), None)
        assert hgb is not None
        assert hgb.value == pytest.approx(15.2)

    def test_differential_pct_extracted(self, parser: QuestParser):
        result = parser.parse(QUEST_CBC_TEXT, FAKE_PDF_BYTES)
        neut_pct = next(
            (m for m in result.markers if m.canonical_name == "neutrophils_pct"), None
        )
        assert neut_pct is not None
        assert neut_pct.value == pytest.approx(64.6)


# ---------------------------------------------------------------------------
# parse — full two-page report
# ---------------------------------------------------------------------------


class TestParseFullReport:
    def test_full_report_marker_count(self, parser: QuestParser):
        result = parser.parse(QUEST_FULL_TEXT, FAKE_PDF_BYTES)
        assert len(result.markers) >= 30  # CMP (18) + CBC (19)

    def test_no_duplicate_markers(self, parser: QuestParser):
        result = parser.parse(QUEST_FULL_TEXT, FAKE_PDF_BYTES)
        canonical_names = [m.canonical_name for m in result.markers]
        # Deduplication should ensure no exact duplicates
        assert len(canonical_names) == len(set(canonical_names))

    def test_overall_confidence_high(self, parser: QuestParser):
        result = parser.parse(QUEST_FULL_TEXT, FAKE_PDF_BYTES)
        assert result.confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestQuestEdgeCases:
    def test_egfr_greater_than_value(self, parser: QuestParser):
        """eGFR is often expressed as '>60' — value should be 60."""
        result = parser.parse(QUEST_CMP_TEXT, FAKE_PDF_BYTES)
        egfr = next((m for m in result.markers if m.canonical_name == "egfr"), None)
        assert egfr is not None
        assert egfr.value == pytest.approx(60.0)
        assert ">" in egfr.value_text

    def test_empty_text_returns_no_markers(self, parser: QuestParser):
        result = parser.parse("Quest Diagnostics\n", FAKE_PDF_BYTES)
        assert result.success is True
        assert len(result.markers) == 0

    def test_malformed_line_skipped_gracefully(self, parser: QuestParser):
        text = "Quest Diagnostics\n\nGarbage line with no values\n\nGlucose  95  70-99  mg/dL"
        result = parser.parse(text, FAKE_PDF_BYTES)
        glucose = next((m for m in result.markers if m.canonical_name == "glucose"), None)
        assert glucose is not None
        assert glucose.value == pytest.approx(95.0)
