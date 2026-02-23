"""Tests for the generic epigenetic parser."""

import pytest
from src.parsers.adapters.epi_generic import EpigeneticGenericParser

SAMPLE_GENERIC_EPI = """
Biological Age Assessment Report
Provider: myDNAge

Test Date: 2026-01-15
Patient: Test User

Results:
Chronological Age: 42
Biological Age: 39 years
Horvath Clock: 38.5 years
Hannum Clock: 40.2 years

Telomere Length: 6.8 kb
Telomere Percentile: 58th percentile
"""


class TestGenericEpiCanParse:
    def setup_method(self):
        self.parser = EpigeneticGenericParser()

    def test_can_parse_bio_age_content(self):
        assert self.parser.can_parse(SAMPLE_GENERIC_EPI)

    def test_cannot_parse_dexa(self):
        assert not self.parser.can_parse("DexaFit Body Fat 18%")


class TestGenericEpiParse:
    def setup_method(self):
        self.parser = EpigeneticGenericParser()
        self.result = self.parser.parse_structured(SAMPLE_GENERIC_EPI)

    def test_success(self):
        assert self.result.success

    def test_biological_age(self):
        assert self.result.primary_biological_age is not None
        assert 35 < self.result.primary_biological_age < 45

    def test_chronological_age(self):
        assert self.result.chronological_age == pytest.approx(42, abs=1)

    def test_clocks(self):
        assert len(self.result.clocks) >= 1

    def test_empty_input(self):
        result = self.parser.parse_structured("")
        assert result.needs_review  # Empty input should flag for review
