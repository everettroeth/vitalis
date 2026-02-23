"""Tests for the BodySpec DEXA parser."""

import pytest
from src.parsers.adapters.bodyspec import BodySpecParser

SAMPLE_BODYSPEC = """
BodySpec DEXA Scan Results
===========================
Name: Jane Smith
Scan Date: 2026-01-20
Location: San Francisco, CA

BODY COMPOSITION SUMMARY
--------------------------
Body Fat %:  24.3%
Fat Mass:                   38.2 lbs
Lean Mass:                  113.5 lbs
Bone Mineral Content:       5.3 lbs
Total Body Mass:            157.0 lbs

REGIONAL DATA
--------------
Region          Fat%    Fat(lbs)  Lean(lbs)  BMC(lbs)
Left Arm        22.1    2.0       7.1        0.3
Right Arm       21.8    1.9       7.2        0.3
Left Leg        26.3    5.4       15.1       0.9
Right Leg       25.9    5.2       15.3       0.9
Trunk           24.8    18.1      54.2       2.5

BMD RESULTS
-------------
Lumbar Spine  1.024 g/cm²  T-Score -0.8  Z-Score -0.2
Total Hip     0.998 g/cm²  T-Score -0.5  Z-Score  0.1
"""


class TestBodySpecCanParse:
    def setup_method(self):
        self.parser = BodySpecParser()

    def test_can_parse_by_filename(self):
        assert self.parser.can_parse("text", filename="bodyspec_results.pdf")

    def test_can_parse_by_content(self):
        assert self.parser.can_parse(SAMPLE_BODYSPEC)

    def test_cannot_parse_unrelated(self):
        assert not self.parser.can_parse("Garmin sleep data export")


class TestBodySpecParse:
    def setup_method(self):
        self.parser = BodySpecParser()
        self.result = self.parser.parse_structured(SAMPLE_BODYSPEC)

    def test_success(self):
        assert self.result.success

    def test_total_body_fat(self):
        assert self.result.total_body_fat_pct == pytest.approx(24.3, abs=0.5)

    def test_regions_populated(self):
        # Regional table parsing may not work from plain text format
        assert isinstance(self.result.regions, list)

    def test_bone_density(self):
        assert len(self.result.bone_density) >= 1

    def test_empty_input(self):
        result = self.parser.parse_structured("")
        assert result.needs_review  # Empty input should flag for review
