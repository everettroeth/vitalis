"""Tests for the TruDiagnostic epigenetic parser."""

import pytest
from src.parsers.adapters.trudiagnostic import TruDiagnosticParser

SAMPLE_TRUDIAGNOSTIC = """
TruDiagnostic TruAge Report
=============================
Patient: Everett R.
Test Date: 2026-01-10
Chronological Age: 35

BIOLOGICAL AGE SUMMARY
------------------------
TruAge (Biological Age):  31.4 years
Chronological Age:        35.0 years
You are aging 3.6 years younger than your chronological age.

EPIGENETIC CLOCKS
------------------
Clock               Value (years)
Horvath             32.1
Hannum              30.8
PhenoAge            29.5
GrimAge             33.2
DunedinPACE         0.82 (rate)

PACE OF AGING
--------------
DunedinPACE Score:  0.82
Interpretation:     You are aging 18% slower than average.

ORGAN-SPECIFIC AGES
---------------------
Organ System        Bio Age   Chrono Age   Delta
Immune              33.1      35.0         -1.9
Heart               30.5      35.0         -4.5
Liver               32.8      35.0         -2.2
Kidney              34.1      35.0         -0.9
Brain               29.8      35.0         -5.2
Lung                31.2      35.0         -3.8
Metabolic           33.5      35.0         -1.5
Inflammation        30.0      35.0         -5.0

TELOMERE LENGTH
----------------
Estimated Telomere Length:  7.2 kb
Percentile (age-matched):  72nd
"""


class TestTruDiagnosticCanParse:
    def setup_method(self):
        self.parser = TruDiagnosticParser()

    def test_can_parse_by_filename(self):
        assert self.parser.can_parse("text", filename="trudiagnostic_report.pdf")

    def test_can_parse_by_content(self):
        assert self.parser.can_parse(SAMPLE_TRUDIAGNOSTIC)

    def test_cannot_parse_unrelated(self):
        assert not self.parser.can_parse("Quest Diagnostics Blood Panel")


class TestTruDiagnosticParse:
    def setup_method(self):
        self.parser = TruDiagnosticParser()
        self.result = self.parser.parse_structured(SAMPLE_TRUDIAGNOSTIC)

    def test_success(self):
        assert self.result.success

    def test_chronological_age(self):
        assert self.result.chronological_age == pytest.approx(35.0, abs=1.0)

    def test_primary_biological_age(self):
        assert self.result.primary_biological_age is not None
        assert 25 < self.result.primary_biological_age < 40

    def test_clocks_populated(self):
        assert len(self.result.clocks) >= 4

    def test_horvath_clock(self):
        horvath = next((c for c in self.result.clocks if "horvath" in c.clock_name.lower()), None)
        assert horvath is not None
        assert horvath.value == pytest.approx(32.1, abs=1.0)

    def test_dunedinpace(self):
        dp = next((c for c in self.result.clocks if "dunedi" in c.clock_name.lower()), None)
        assert dp is not None
        assert dp.value == pytest.approx(0.82, abs=0.1)

    def test_organ_ages_populated(self):
        assert len(self.result.organ_ages) >= 5

    def test_organ_age_delta(self):
        heart = next((o for o in self.result.organ_ages if "heart" in o.organ_system.lower()), None)
        if heart:
            assert heart.delta_years < 0  # Younger than chrono age

    def test_pace_of_aging(self):
        assert self.result.pace_of_aging is not None
        assert self.result.pace_of_aging < 1.0  # Aging slower

    def test_telomere(self):
        assert self.result.telomere_length is not None

    def test_empty_input(self):
        result = self.parser.parse_structured("")
        assert result.needs_review  # Empty input should flag for review
