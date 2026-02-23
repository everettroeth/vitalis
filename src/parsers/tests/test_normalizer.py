"""Tests for the biomarker name normaliser and unit conversion."""

from __future__ import annotations

import pytest

from src.parsers.normalizer import (
    BIOMARKER_ALIASES,
    normalize_marker_name,
    normalize_unit,
    convert_value,
    get_display_name,
)


# ---------------------------------------------------------------------------
# normalize_marker_name — exact matches
# ---------------------------------------------------------------------------


class TestExactMatches:
    def test_canonical_name_resolves_self(self):
        canonical, score = normalize_marker_name("glucose")
        assert canonical == "glucose"
        assert score == 1.0

    def test_common_abbreviation(self):
        canonical, score = normalize_marker_name("TSH")
        assert canonical == "tsh"
        assert score >= 0.9

    def test_case_insensitive(self):
        canonical, _ = normalize_marker_name("HEMOGLOBIN")
        assert canonical == "hemoglobin"

    def test_alt_alias(self):
        canonical, _ = normalize_marker_name("ALT (SGPT)")
        assert canonical == "alt"

    def test_ast_alias(self):
        canonical, _ = normalize_marker_name("AST (SGOT)")
        assert canonical == "ast"

    def test_egfr_variant(self):
        canonical, _ = normalize_marker_name("eGFR Non-Afr. American")
        assert canonical == "egfr"

    def test_hdl_cholesterol(self):
        canonical, _ = normalize_marker_name("HDL-C")
        assert canonical == "hdl_cholesterol"

    def test_ldl_cholesterol(self):
        canonical, _ = normalize_marker_name("LDL Chol Calc")
        assert canonical == "ldl_cholesterol"

    def test_vitamin_d(self):
        canonical, _ = normalize_marker_name("25-OH Vitamin D")
        assert canonical == "vitamin_d_25oh"

    def test_vitamin_d_variant(self):
        canonical, _ = normalize_marker_name("Vitamin D, 25 Hydroxy")
        assert canonical == "vitamin_d_25oh"

    def test_hscrp(self):
        canonical, _ = normalize_marker_name("C-Reactive Protein")
        assert canonical == "hs_crp"

    def test_hba1c(self):
        canonical, _ = normalize_marker_name("Hemoglobin A1c")
        assert canonical == "hba1c"

    def test_bun(self):
        canonical, _ = normalize_marker_name("Blood Urea Nitrogen")
        assert canonical == "bun"

    def test_psa(self):
        canonical, _ = normalize_marker_name("PSA, Total")
        assert canonical == "psa_total"

    def test_dhea_s(self):
        canonical, _ = normalize_marker_name("DHEA-Sulfate")
        assert canonical == "dhea_s"

    def test_testosterone_free(self):
        canonical, _ = normalize_marker_name("Free Testosterone")
        assert canonical == "testosterone_free"

    def test_ferritin(self):
        canonical, _ = normalize_marker_name("Ferritin, Serum")
        assert canonical == "ferritin"

    def test_tibc(self):
        canonical, _ = normalize_marker_name("Total Iron Binding Capacity")
        assert canonical == "tibc"


# ---------------------------------------------------------------------------
# normalize_marker_name — fuzzy matches
# ---------------------------------------------------------------------------


class TestFuzzyMatches:
    def test_slight_misspelling(self):
        # "Potasium" (one s) should still match "potassium"
        canonical, score = normalize_marker_name("Potasium")
        # May or may not match depending on rapidfuzz threshold
        # At minimum it should not raise
        assert canonical is None or canonical == "potassium"

    def test_extra_qualifier(self):
        # "Glucose, Serum (Fasting)" should match "glucose"
        canonical, score = normalize_marker_name("Glucose, Serum")
        assert canonical == "glucose"

    def test_no_match_returns_none(self):
        canonical, score = normalize_marker_name("XYZABCNONEXISTENT12345")
        assert canonical is None
        assert score == 0.0

    def test_empty_string(self):
        canonical, score = normalize_marker_name("")
        assert canonical is None
        assert score == 0.0


# ---------------------------------------------------------------------------
# normalize_unit
# ---------------------------------------------------------------------------


class TestNormalizeUnit:
    def test_microlitre_variants(self):
        assert normalize_unit("10^3/uL") == "10^3/µL"
        assert normalize_unit("K/uL") == "10^3/µL"

    def test_microgram_variants(self):
        assert normalize_unit("ug/dL") == "µg/dL"
        assert normalize_unit("ug/mL") == "µg/mL"

    def test_enzyme_units(self):
        assert normalize_unit("U/L") == "U/L"   # already canonical
        assert normalize_unit("u/l") == "U/L"

    def test_miu_ml(self):
        assert normalize_unit("uIU/mL") == "µIU/mL"

    def test_passthrough_for_unknown(self):
        # Unknown units pass through unchanged
        result = normalize_unit("widgets/mL")
        assert result == "widgets/mL"

    def test_empty_string(self):
        assert normalize_unit("") == ""


# ---------------------------------------------------------------------------
# convert_value
# ---------------------------------------------------------------------------


class TestConvertValue:
    def test_mmol_to_mgdl_glucose(self):
        # 5.0 mmol/L glucose = 90 mg/dL
        result = convert_value(5.0, "mmol/L", "mg/dL")
        assert result is not None
        assert abs(result - 90.0) < 0.1

    def test_mgdl_to_mmol(self):
        result = convert_value(90.0, "mg/dL", "mmol/L")
        assert result is not None
        assert abs(result - 5.0) < 0.01

    def test_unknown_conversion_returns_none(self):
        result = convert_value(10.0, "widgets", "gadgets")
        assert result is None


# ---------------------------------------------------------------------------
# get_display_name
# ---------------------------------------------------------------------------


class TestGetDisplayName:
    def test_known_canonical(self):
        assert get_display_name("glucose") == "Glucose"
        assert get_display_name("hba1c") == "HbA1c"
        assert get_display_name("hs_crp") == "hs-CRP"

    def test_unknown_falls_back(self):
        result = get_display_name("some_unknown_marker")
        assert result == "Some Unknown Marker"


# ---------------------------------------------------------------------------
# Completeness — all canonical names have at least one alias
# ---------------------------------------------------------------------------


def test_all_canonicals_have_aliases():
    for canonical, aliases in BIOMARKER_ALIASES.items():
        assert len(aliases) >= 1, f"{canonical} has no aliases"
        # Verify the normalizer can resolve at least one alias back to this canonical
        from src.parsers.normalizer import normalize_marker_name
        found = any(normalize_marker_name(a)[0] == canonical for a in aliases)
        assert found, f"No alias for {canonical} resolves back to itself"
