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


# ---------------------------------------------------------------------------
# Synthetic DexaFit DEXA report
# Mirrors pdfplumber text extraction from a real DexaFit report PDF.
# ---------------------------------------------------------------------------

DEXAFIT_TEXT = """DexaFit
DEXA Body Composition Analysis

Name: John Doe                          Date: January 15, 2024
Age: 35      Sex: Male      Height: 5' 10"      Weight: 175.0 lbs      BMI: 25.1

TOTAL BODY COMPOSITION
Total Body Fat %                          22.5%
Fat Mass                                  39.4 lbs
Lean Mass                                131.9 lbs
Bone Mineral Content (BMC)                 6.1 lbs
Total Mass                               177.4 lbs

VISCERAL ADIPOSE TISSUE
VAT Mass                                   0.35 lbs
VAT Volume                               198.0 cm3

ANDROID / GYNOID
Android Fat %                             25.2%
Gynoid Fat %                              20.1%
Android/Gynoid Ratio                       1.25

REGIONAL BODY COMPOSITION
Region          Fat %    Fat (lbs)  Lean (lbs)  BMC (lbs)  Total (lbs)
Left Arm        26.1%      2.1        5.7          0.4        8.2
Right Arm       27.3%      2.2        5.9          0.4        8.5
Left Leg        25.8%      8.2       22.9          1.1       32.2
Right Leg       24.9%      8.0       23.3          1.1       32.4
Trunk           21.5%     17.4       62.1          2.9       82.4
Android         25.2%      3.1        9.1          0.5       12.7
Gynoid          20.1%      6.8       25.8          1.0       33.6

BONE MINERAL DENSITY
Site                    BMD (g/cm2)  T-Score  Z-Score  Classification
Lumbar Spine (L1-L4)       1.142       0.8      0.5      Normal
Femoral Neck               0.998      -0.2      0.2      Normal
Total Hip                  1.054       0.3      0.5      Normal
"""

# ---------------------------------------------------------------------------
# Synthetic BodySpec DEXA report
# ---------------------------------------------------------------------------

BODYSPEC_TEXT = """BodySpec DEXA Scan Report

Client: Jane Smith                        Scan Date: 03/10/2024
Age: 28   Sex: Female   Height: 5'5"   Weight: 135 lbs

BODY COMPOSITION                    Result     Previous    Change
Body Fat %          28.4%       30.2%      -1.8%
Fat Mass            38.3 lbs    40.7 lbs   -2.4 lbs
Lean Mass           93.8 lbs    92.1 lbs   +1.7 lbs
Bone Mass            4.4 lbs     4.4 lbs    0.0 lbs
Total              136.5 lbs   137.2 lbs   -0.7 lbs

VISCERAL FAT
Visceral Fat Mass:  0.28 lbs
Visceral Fat Vol:   153.0 cm3

ANDROID/GYNOID
Android:  32.1%
Gynoid:   37.5%
Ratio:    0.86

REGIONAL COMPOSITION
               Fat %   Fat (lbs)  Lean (lbs)  Total (lbs)
Left Arm       29.2%    1.5        3.5         5.1
Right Arm      28.8%    1.5        3.6         5.2
Left Leg       32.1%   10.1       20.8        31.3
Right Leg      31.5%    9.9       21.1        31.4
Trunk          25.3%   15.3       44.8        60.6

BONE DENSITY
Region              g/cm2    T-Score   Z-Score
Total Spine          1.078    -0.3       0.8
Femoral Neck         0.882    -0.9       0.5
Total Hip            0.941    -0.6       0.7
"""

# ---------------------------------------------------------------------------
# Synthetic Generic DEXA report (Hologic style)
# ---------------------------------------------------------------------------

DEXA_GENERIC_TEXT = """Hologic Horizon DXA System
Body Composition Analysis Report

Patient: Michael Torres
Date of Exam: 06/22/2024
Facility: Wellness Medical Center

TOTAL BODY RESULTS
Body Fat %:          19.8%
Fat Mass:            36.2 lbs
Lean Mass:          144.8 lbs
Total Mass:         185.2 lbs

VISCERAL ADIPOSE TISSUE
Visceral Adipose Tissue Mass:   0.42 lbs
Visceral Adipose Tissue Volume: 231.0 cm3

ANDROID GYNOID
Android:  22.4%
Gynoid:   17.8%
A/G Ratio:  1.26

REGIONAL
               Fat %   Fat lbs  Lean lbs  Total lbs
Left Arm       22.1%    1.9      6.5       8.5
Right Arm      23.0%    2.0      6.7       8.8
Left Leg       21.3%    7.8     28.2      37.5
Right Leg      20.8%    7.6     28.5      37.5
Trunk          18.5%   16.9     72.9      93.5

BONE MINERAL DENSITY
Lumbar Spine  1.198  1.3  0.8
Femoral Neck  1.045  0.1  0.4
Total Hip     1.089  0.4  0.6
"""

# ---------------------------------------------------------------------------
# Synthetic TruDiagnostic epigenetic report
# ---------------------------------------------------------------------------

TRUDIAGNOSTIC_TEXT = """TruDiagnostic TruAge Complete Epigenetic Test
Comprehensive Biological Aging Analysis

Patient Name: Jane Smith
Collection Date: February 20, 2024
Kit ID: TRU-2024-98765

Chronological Age: 42 years

BIOLOGICAL AGE OVERVIEW
Your TruAge: 38.2 years
Age Difference: -3.8 years

You are biologically 3.8 years younger than your chronological age.

METHYLATION CLOCK RESULTS
Clock              Biological Age    Difference
Horvath            36.5 years        -5.5 years
Hannum             37.8 years        -4.2 years
PhenoAge           38.1 years        -3.9 years
GrimAge            39.2 years        -2.8 years

PACE OF AGING (DunedinPACE)
DunedinPACE score: 0.82
You are aging 18% slower than average.
Percentile: 78th

ORGAN SYSTEM AGES
Organ System         Biological Age   Difference   Status
Immune System             35.2         -6.8 yrs     Younger
Cardiovascular            37.5         -4.5 yrs     Younger
Liver                     40.1         -1.9 yrs     Younger
Kidney                    38.8         -3.2 yrs     Younger
Brain/Cognitive           36.9         -5.1 yrs     Younger
Lung/Pulmonary            41.2         -0.8 yrs     Same
Metabolic                 39.5         -2.5 yrs     Younger
Musculoskeletal           37.3         -4.7 yrs     Younger
Hormonal/Endocrine        42.8          0.8 yrs     Older
Blood/Hematopoietic       35.1         -6.9 yrs     Younger
Inflammatory              38.4         -3.6 yrs     Younger

TELOMERE LENGTH
Length: 7.8 kb
Percentile: 72nd percentile for your age and sex
"""

# ---------------------------------------------------------------------------
# Synthetic Elysium Health Index report
# ---------------------------------------------------------------------------

ELYSIUM_TEXT = """Elysium Health — Index Biological Age Test

Name: Robert Johnson
Date of Collection: April 5, 2024

YOUR RESULTS

Biological Age    31.2 years
Chronological Age
    38 years

You are 6.8 years YOUNGER than your chronological age.

Rate of Aging    0.84 years/year
Aging 16% slower than your peers

WHAT YOUR RESULTS MEAN
Your Index biological age of 31.2 is lower than your chronological age of 38,
indicating that at the molecular level, your body is functioning more like
someone who is younger.

Your rate of aging of 0.84 means you are aging slightly slower than average.
"""

# ---------------------------------------------------------------------------
# Synthetic Generic Epigenetic report (GlycanAge style)
# ---------------------------------------------------------------------------

EPI_GENERIC_TEXT = """GlycanAge Biological Age Test
Advanced Glycan Biomarker Analysis

Patient: Sarah Connor
Collection Date: 07/14/2024

RESULTS SUMMARY
Biological Age:     35.0 years
Chronological Age: 41 years

Your biological age is 6 years younger than your chronological age.

DNA METHYLATION ANALYSIS
Horvath Clock:      34.2 years
Hannum Clock:       35.8 years
GrimAge:            36.1 years
DunedinPACE score: 0.79
You are aging 21% slower than average.

TELOMERE LENGTH
Telomere length: 8.2 kb
72nd percentile for your age
"""


# ---------------------------------------------------------------------------
# Synthetic non-DEXA text (should not match DEXA parsers)
# ---------------------------------------------------------------------------

NOT_DEXA_TEXT = """Quest Diagnostics
Patient: John Doe
Glucose    95    70-99    mg/dL
Cholesterol    185    <200    mg/dL
"""

NOT_EPI_TEXT = """LabCorp Laboratory Services
Patient Blood Work
Hemoglobin A1c    5.4%
Vitamin D    42 ng/mL
"""


# ---------------------------------------------------------------------------
# New fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dexafit_text() -> str:
    return DEXAFIT_TEXT


@pytest.fixture
def bodyspec_text() -> str:
    return BODYSPEC_TEXT


@pytest.fixture
def dexa_generic_text() -> str:
    return DEXA_GENERIC_TEXT


@pytest.fixture
def trudiagnostic_text() -> str:
    return TRUDIAGNOSTIC_TEXT


@pytest.fixture
def elysium_text() -> str:
    return ELYSIUM_TEXT


@pytest.fixture
def epi_generic_text() -> str:
    return EPI_GENERIC_TEXT


@pytest.fixture
def not_dexa_text() -> str:
    return NOT_DEXA_TEXT


@pytest.fixture
def not_epi_text() -> str:
    return NOT_EPI_TEXT
