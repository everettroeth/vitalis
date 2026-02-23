"""Shared test fixtures and helpers for the parser engine test suite.

Synthetic PDF text is used throughout — no real PDFs are committed to the
repo for privacy and size reasons.  The synthetic text closely mirrors
the real-world output of pdfplumber on actual Quest / Labcorp PDFs.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Fixture data directory
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(path: str) -> dict[str, Any]:
    """Load a JSON fixture file relative to the fixtures directory."""
    return json.loads((FIXTURES_DIR / path).read_text())


# ---------------------------------------------------------------------------
# Synthetic Quest Diagnostics CMP text
# Mirrors the exact column layout produced by pdfplumber on real Quest PDFs.
# ---------------------------------------------------------------------------

QUEST_CMP_TEXT = """\
Quest Diagnostics                                                Page 1 of 2
Patient: JOHN DOE                              DOB: 01/15/1980
Specimen ID: XYZ123456                         Sex: Male
Ordering Physician: Dr. Jane Smith             NPI: 1234567890
Date of Collection: 03/15/2024                 Date Reported: 03/16/2024

COMPREHENSIVE METABOLIC PANEL
------------------------------------------------------------------------
Test Name                          Result  Flag  Reference Range  Units
------------------------------------------------------------------------
Glucose                            95            70-99            mg/dL
BUN                                15            7-25             mg/dL
Creatinine                         0.9           0.60-1.35        mg/dL
eGFR                               >60           >59              mL/min/1.73m2
BUN/Creatinine Ratio               17            9-20
Sodium                             140           136-145          mEq/L
Potassium                          4.2           3.5-5.1          mEq/L
Chloride                           102           98-107           mEq/L
CO2                                24            21-32            mEq/L
Calcium                            9.4           8.5-10.2         mg/dL
Total Protein                      7.2           6.3-8.2          g/dL
Albumin                            4.4           3.6-5.1          g/dL
Globulin                           2.8           1.5-4.5          g/dL
A/G Ratio                          1.6           1.2-2.2
Bilirubin, Total                   0.6           0.2-1.2          mg/dL
Alkaline Phosphatase               72            44-147           U/L
AST                                22            10-40            U/L
ALT                                18            7-56             U/L
"""

QUEST_CBC_TEXT = """\
Quest Diagnostics                                                Page 2 of 2
Patient: JOHN DOE
Specimen ID: XYZ123456

CBC WITH DIFFERENTIAL
------------------------------------------------------------------------
Test Name                          Result  Flag  Reference Range  Units
------------------------------------------------------------------------
WBC                                6.5           4.0-11.0         10^3/uL
RBC                                5.1           4.5-5.9          10^6/uL
Hemoglobin                         15.2          13.5-17.5        g/dL
Hematocrit                         45.1          41.0-53.0        %
MCV                                88            80-100           fL
MCH                                29.8          27.5-33.2        pg
MCHC                               33.7          31.5-35.7        g/dL
RDW                                12.8          11.5-14.5        %
Platelets                          250           150-400          10^3/uL
Neutrophils                        4.2           1.8-7.7          10^3/uL
Lymphocytes                        1.8           1.0-4.8          10^3/uL
Monocytes                          0.4           0.1-0.9          10^3/uL
Eosinophils                        0.1           0.0-0.4          10^3/uL
Basophils                          0.0           0.0-0.1          10^3/uL
Neutrophils %                      64.6          40.0-73.0        %
Lymphocytes %                      27.7          18.0-48.0        %
Monocytes %                        6.2           4.0-12.0         %
Eosinophils %                      1.5           0.0-5.0          %
Basophils %                        0.0           0.0-1.5          %
"""

QUEST_FULL_TEXT = QUEST_CMP_TEXT + "\f" + QUEST_CBC_TEXT

# ---------------------------------------------------------------------------
# Synthetic Labcorp Lipid Panel text
# ---------------------------------------------------------------------------

LABCORP_LIPID_TEXT = """\
Laboratory Corporation of America
FINAL REPORT

Patient: JANE SMITH                            Specimen ID: 987654321
Date of Collection: 04/10/2024                 Date Reported: 04/11/2024
Ordering Physician: Dr. Robert Jones           Sex: Female  Age: 45

LIPID PANEL
------------------------------------------------------------------------
Test Name                    Value    Flag    Units    Reference Interval
------------------------------------------------------------------------
Total Cholesterol            185              mg/dL    <200
HDL Cholesterol               55              mg/dL    >40
LDL Cholesterol              105      H       mg/dL    <100
Triglycerides                120              mg/dL    <150
Non-HDL Cholesterol          130              mg/dL    <130
Cholesterol/HDL Ratio          3.4            ratio    <5.0
"""

LABCORP_THYROID_TEXT = """\
Laboratory Corporation of America
FINAL REPORT

Patient: JANE SMITH
Specimen ID: 987654321

THYROID FUNCTION
------------------------------------------------------------------------
Test Name                    Value    Flag    Units    Reference Interval
------------------------------------------------------------------------
TSH                          2.1              mIU/L    0.450-4.500
Free T4                      1.2              ng/dL    0.82-1.77
Free T3                      3.1              pg/mL    2.0-4.4
"""

LABCORP_FULL_TEXT = LABCORP_LIPID_TEXT + "\f" + LABCORP_THYROID_TEXT

# ---------------------------------------------------------------------------
# Synthetic generic/unknown format text
# ---------------------------------------------------------------------------

GENERIC_LAB_TEXT = """\
ACME MEDICAL LABORATORY SERVICES
Patient Blood Work Report

Patient: TEST PATIENT
Collection Date: 05/20/2024

Results:
Glucose                  92            mg/dL           70-99
Hemoglobin A1c           5.4           %               <5.7
Vitamin D, 25-Hydroxy    42            ng/mL           30-100
Ferritin                 85            ng/mL           12-300
hs-CRP                   0.8           mg/L            <1.0
Homocysteine             9.2           µmol/L          <15.0
Testosterone             650           ng/dL           264-916
DHEA-S                   280           µg/dL           110-510
"""

# ---------------------------------------------------------------------------
# Minimal fake PDF bytes (valid enough for basic tests)
# In real tests with pdfplumber integration, use actual PDF bytes.
# ---------------------------------------------------------------------------

FAKE_PDF_BYTES = b"%PDF-1.4 fake pdf content"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def quest_cmp_text() -> str:
    return QUEST_CMP_TEXT


@pytest.fixture
def quest_cbc_text() -> str:
    return QUEST_CBC_TEXT


@pytest.fixture
def quest_full_text() -> str:
    return QUEST_FULL_TEXT


@pytest.fixture
def labcorp_lipid_text() -> str:
    return LABCORP_LIPID_TEXT


@pytest.fixture
def labcorp_full_text() -> str:
    return LABCORP_FULL_TEXT


@pytest.fixture
def generic_lab_text() -> str:
    return GENERIC_LAB_TEXT


@pytest.fixture
def fake_pdf_bytes() -> bytes:
    return FAKE_PDF_BYTES
