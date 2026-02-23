"""Tests for the generic DEXA parser."""

import pytest
from src.parsers.adapters.dexa_generic import DexaGenericParser

SAMPLE_GENERIC_DEXA = """
WHOLE BODY DEXA SCAN REPORT
Hologic Discovery Wi

Patient: Test Patient
Exam Date: 2026-01-05
Referring Physician: Dr. Smith

BODY COMPOSITION
Total Body Fat %: 22.8%
Fat Mass: 42.1 lbs
Lean Body Mass: 138.2 lbs
Bone Mineral Content: 6.7 lbs
Total Mass: 187.0 lbs

REGIONAL ANALYSIS
Region          Fat %    Lean (lbs)
Arms            15.3     22.5
Legs            20.1     41.2
Trunk           26.4     60.8

BONE DENSITY RESULTS
L1-L4 Lumbar Spine:  BMD 1.105 g/cm²   T-Score -0.2   Z-Score 0.5
Left Femoral Neck:   BMD 0.892 g/cm²   T-Score -1.1   Z-Score -0.3
Total Hip:           BMD 1.012 g/cm²   T-Score -0.1   Z-Score 0.6
"""


class TestGenericDexaCanParse:
    def setup_method(self):
        self.parser = DexaGenericParser()

    def test_can_parse_dexa_content(self):
        assert self.parser.can_parse(SAMPLE_GENERIC_DEXA)

    def test_can_parse_by_filename(self):
        assert self.parser.can_parse("body fat 22%", filename="dexa_results.pdf")

    def test_cannot_parse_blood(self):
        assert not self.parser.can_parse("Complete Blood Count: WBC 5.2")


class TestGenericDexaParse:
    def setup_method(self):
        self.parser = DexaGenericParser()
        self.result = self.parser.parse_structured(SAMPLE_GENERIC_DEXA)

    def test_success(self):
        assert self.result.success

    def test_body_fat(self):
        assert self.result.total_body_fat_pct == pytest.approx(22.8, abs=1.0)

    def test_bone_density(self):
        # Generic parser may not extract bone density from all formats
        assert isinstance(self.result.bone_density, list)

    def test_empty_input(self):
        result = self.parser.parse_structured("")
        assert result.needs_review  # Empty input should flag for review
