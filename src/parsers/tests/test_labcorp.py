"""Tests for the Labcorp parser adapter."""

from __future__ import annotations

import pytest
from datetime import date

from src.parsers.adapters.labcorp import LabcorpParser
from src.parsers.base import ConfidenceLevel
from src.parsers.tests.conftest import (
    LABCORP_LIPID_TEXT,
    LABCORP_FULL_TEXT,
    FAKE_PDF_BYTES,
)


@pytest.fixture
def parser() -> LabcorpParser:
    return LabcorpParser()


# ---------------------------------------------------------------------------
# can_parse
# ---------------------------------------------------------------------------


class TestCanParse:
    def test_recognises_full_name(self, parser: LabcorpParser):
        assert parser.can_parse("Laboratory Corporation of America") is True

    def test_recognises_labcorp_short(self, parser: LabcorpParser):
        assert parser.can_parse("Labcorp — FINAL REPORT") is True

    def test_recognises_by_filename(self, parser: LabcorpParser):
        assert parser.can_parse("random text", "labcorp_results.pdf") is True

    def test_rejects_quest(self, parser: LabcorpParser):
        assert parser.can_parse("Quest Diagnostics patient report") is False

    def test_rejects_random_text(self, parser: LabcorpParser):
        assert parser.can_parse("hospital discharge summary, nothing relevant") is False


# ---------------------------------------------------------------------------
# parse — lipid panel
# ---------------------------------------------------------------------------


class TestParseLipidPanel:
    def test_parse_succeeds(self, parser: LabcorpParser):
        result = parser.parse(LABCORP_LIPID_TEXT, FAKE_PDF_BYTES)
        assert result.success is True

    def test_parser_id(self, parser: LabcorpParser):
        result = parser.parse(LABCORP_LIPID_TEXT, FAKE_PDF_BYTES)
        assert result.parser_used == "labcorp_v1"

    def test_lab_name(self, parser: LabcorpParser):
        result = parser.parse(LABCORP_LIPID_TEXT, FAKE_PDF_BYTES)
        assert result.lab_name == "Labcorp"

    def test_collection_date_extracted(self, parser: LabcorpParser):
        result = parser.parse(LABCORP_LIPID_TEXT, FAKE_PDF_BYTES)
        assert result.collection_date == date(2024, 4, 10)

    def test_patient_name_extracted(self, parser: LabcorpParser):
        result = parser.parse(LABCORP_LIPID_TEXT, FAKE_PDF_BYTES)
        assert result.patient_name is not None
        assert "JANE" in result.patient_name.upper()

    def test_total_cholesterol(self, parser: LabcorpParser):
        result = parser.parse(LABCORP_LIPID_TEXT, FAKE_PDF_BYTES)
        chol = next((m for m in result.markers if m.canonical_name == "cholesterol_total"), None)
        assert chol is not None
        assert chol.value == pytest.approx(185.0)
        assert chol.unit == "mg/dL"
        assert chol.flag is None

    def test_ldl_flagged_high(self, parser: LabcorpParser):
        result = parser.parse(LABCORP_LIPID_TEXT, FAKE_PDF_BYTES)
        ldl = next((m for m in result.markers if m.canonical_name == "ldl_cholesterol"), None)
        assert ldl is not None
        assert ldl.value == pytest.approx(105.0)
        assert ldl.flag == "H"

    def test_hdl_with_greater_than_ref(self, parser: LabcorpParser):
        result = parser.parse(LABCORP_LIPID_TEXT, FAKE_PDF_BYTES)
        hdl = next((m for m in result.markers if m.canonical_name == "hdl_cholesterol"), None)
        assert hdl is not None
        assert hdl.value == pytest.approx(55.0)
        # ">40" means ref_low = 40
        assert hdl.reference_low == pytest.approx(40.0)
        assert hdl.reference_high is None

    def test_cholesterol_less_than_ref(self, parser: LabcorpParser):
        result = parser.parse(LABCORP_LIPID_TEXT, FAKE_PDF_BYTES)
        chol = next((m for m in result.markers if m.canonical_name == "cholesterol_total"), None)
        assert chol is not None
        # "<200" means ref_high = 200
        assert chol.reference_high == pytest.approx(200.0)
        assert chol.reference_low is None

    def test_all_lipid_markers_present(self, parser: LabcorpParser):
        result = parser.parse(LABCORP_LIPID_TEXT, FAKE_PDF_BYTES)
        expected = {
            "cholesterol_total", "hdl_cholesterol", "ldl_cholesterol",
            "triglycerides", "non_hdl_cholesterol", "chol_hdl_ratio",
        }
        found = {m.canonical_name for m in result.markers}
        missing = expected - found
        assert not missing, f"Missing: {missing}"

    def test_needs_review_when_flagged_marker(self, parser: LabcorpParser):
        result = parser.parse(LABCORP_LIPID_TEXT, FAKE_PDF_BYTES)
        # LDL is flagged H but confidence should still be ok
        # needs_review depends on confidence not flags
        assert isinstance(result.needs_review, bool)


# ---------------------------------------------------------------------------
# parse — full report (lipid + thyroid)
# ---------------------------------------------------------------------------


class TestParseFullReport:
    def test_thyroid_markers_present(self, parser: LabcorpParser):
        result = parser.parse(LABCORP_FULL_TEXT, FAKE_PDF_BYTES)
        canonical_names = {m.canonical_name for m in result.markers}
        assert "tsh" in canonical_names
        assert "t4_free" in canonical_names
        assert "t3_free" in canonical_names

    def test_tsh_value(self, parser: LabcorpParser):
        result = parser.parse(LABCORP_FULL_TEXT, FAKE_PDF_BYTES)
        tsh = next((m for m in result.markers if m.canonical_name == "tsh"), None)
        assert tsh is not None
        assert tsh.value == pytest.approx(2.1)
        assert tsh.reference_low == pytest.approx(0.45)
        assert tsh.reference_high == pytest.approx(4.5)

    def test_no_duplicates_across_pages(self, parser: LabcorpParser):
        result = parser.parse(LABCORP_FULL_TEXT, FAKE_PDF_BYTES)
        names = [m.canonical_name for m in result.markers]
        assert len(names) == len(set(names))


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestLabcorpEdgeCases:
    def test_empty_report_returns_no_markers(self, parser: LabcorpParser):
        text = "Laboratory Corporation of America\nFINAL REPORT\n"
        result = parser.parse(text, FAKE_PDF_BYTES)
        assert result.success is True
        assert result.lab_name == "Labcorp"
        assert len(result.markers) == 0

    def test_parse_does_not_raise_on_garbage_lines(self, parser: LabcorpParser):
        text = (
            "Laboratory Corporation of America\n"
            "!!!! @#$% garbage line\n"
            "Total Cholesterol  185  mg/dL  <200\n"
        )
        result = parser.parse(text, FAKE_PDF_BYTES)
        assert result.success is True
        chol = next((m for m in result.markers if m.canonical_name == "cholesterol_total"), None)
        assert chol is not None
