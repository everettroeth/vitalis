"""Tests for the Elysium Health epigenetic parser."""

import pytest
from src.parsers.adapters.elysium import ElysiumParser

SAMPLE_ELYSIUM = """
Elysium Health — Index Biological Age Test
============================================
Patient: Jane D.
Test Date: 2026-02-01

YOUR RESULTS
--------------
Biological Age:       32 years
Chronological Age:    38 years
Rate of Aging:        0.89

You are biologically 6 years younger than your chronological age.
Your rate of aging indicates you are aging 11% slower than average.

Cumulative Rate of Aging:  0.91
"""


class TestElysiumCanParse:
    def setup_method(self):
        self.parser = ElysiumParser()

    def test_can_parse_by_filename(self):
        assert self.parser.can_parse("text", filename="elysium_index.pdf")

    def test_can_parse_by_content(self):
        assert self.parser.can_parse(SAMPLE_ELYSIUM)

    def test_cannot_parse_unrelated(self):
        assert not self.parser.can_parse("DexaFit Body Composition")


class TestElysiumParse:
    def setup_method(self):
        self.parser = ElysiumParser()
        self.result = self.parser.parse_structured(SAMPLE_ELYSIUM)

    def test_success(self):
        assert self.result.success

    def test_biological_age(self):
        assert self.result.primary_biological_age == pytest.approx(32, abs=1)

    def test_chronological_age(self):
        assert self.result.chronological_age == pytest.approx(38, abs=1)

    def test_pace_of_aging(self):
        assert self.result.pace_of_aging is not None
        assert self.result.pace_of_aging < 1.0

    def test_empty_input(self):
        result = self.parser.parse_structured("")
        assert result.needs_review  # Empty input should flag for review
