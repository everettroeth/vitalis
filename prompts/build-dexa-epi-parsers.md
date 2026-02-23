You are a senior Python engineer extending the Vitalis Lab Parser Engine with DEXA scan and epigenetic test parsers.

## Context
Read these files first:
- src/parsers/base.py — existing ParseResult, MarkerResult, ConfidenceLevel models
- src/parsers/registry.py — how parsers register and route
- src/parsers/normalizer.py — how biomarker names are normalized
- src/parsers/adapters/quest.py — example of a well-structured parser adapter
- src/parsers/tests/conftest.py — how test fixtures work
- SCHEMA.md — dexa_scans, dexa_regions, dexa_bone_density, epigenetic_tests, epigenetic_organ_ages tables
- schema.sql — table schemas for DEXA and epigenetic data

## What to Build

### 1. DEXA Scan Parsers

Create parsers for body composition DEXA scan reports. DEXA reports contain:
- Total body fat %, lean mass, bone mineral density
- Regional breakdown (arms, legs, trunk, android, gynoid)
- Visceral adipose tissue (VAT)
- T-scores and Z-scores for bone density
- Comparison to previous scans

**Adapters to build:**

**DexaFit** (`src/parsers/adapters/dexafit.py`)
- DexaFit is the largest DEXA scan provider in the US
- Reports include: total body composition, regional breakdown, visceral fat, bone density
- PDF format with tables and sometimes charts
- Key fields: Total Body Fat %, Lean Mass (lbs/kg), Fat Mass, BMC, BMD, VAT mass, Android/Gynoid ratio, regional fat %

**BodySpec** (`src/parsers/adapters/bodyspec.py`)
- Similar to DexaFit but different PDF layout
- Often simpler reports focused on body composition
- Key fields: Total Fat %, Lean Mass, Fat Mass, BMD, regional breakdown

**Generic DEXA** (`src/parsers/adapters/dexa_generic.py`)
- AI-powered fallback for Hologic, GE Lunar, and unknown DEXA formats
- Hospital/clinic DEXA reports vary widely
- Extract key metrics using regex + AI fallback

### 2. DEXA Data Models

Create new result types in a new file `src/parsers/dexa_models.py`:

```python
@dataclass
class DexaRegionResult:
    region: str              # "total", "left_arm", "right_arm", "left_leg", "right_leg", "trunk", "android", "gynoid", "head"
    fat_pct: float | None
    fat_mass_g: float | None
    lean_mass_g: float | None
    bmc_g: float | None      # Bone mineral content
    total_mass_g: float | None
    confidence: float

@dataclass
class DexaBoneDensityResult:
    site: str                # "lumbar_spine", "femoral_neck", "total_hip", "forearm"
    bmd_g_cm2: float | None  # Bone mineral density
    t_score: float | None    # Compared to young adult
    z_score: float | None    # Compared to age-matched
    confidence: float

@dataclass  
class DexaParseResult:
    success: bool
    parser_used: str
    format_detected: str
    confidence: ConfidenceLevel
    scan_date: date | None
    patient_name: str | None
    facility: str | None
    
    # Total body composition
    total_body_fat_pct: float | None
    total_fat_mass_g: float | None
    total_lean_mass_g: float | None
    total_bmc_g: float | None
    total_mass_g: float | None
    
    # Special metrics
    vat_mass_g: float | None          # Visceral adipose tissue
    vat_volume_cm3: float | None
    android_gynoid_ratio: float | None
    fat_mass_index: float | None      # FMI = fat mass / height²
    lean_mass_index: float | None     # LMI = lean mass / height²
    appendicular_lean_mass_g: float | None  # ALM = arms + legs lean
    
    # Regional breakdown
    regions: list[DexaRegionResult]
    
    # Bone density
    bone_density: list[DexaBoneDensityResult]
    
    warnings: list[str]
    needs_review: bool
    raw_text: str
    parse_time_ms: int
```

### 3. Epigenetic Test Parsers

Create parsers for biological age / epigenetic test results:

**TruDiagnostic** (`src/parsers/adapters/trudiagnostic.py`)
- Largest consumer epigenetic testing company
- Reports include: biological age (multiple clocks), pace of aging (DunedinPACE), organ-specific ages, telomere length
- Key clocks: Horvath, Hannum, PhenoAge, GrimAge, DunedinPACE
- Organ ages: immune, heart, liver, kidney, brain, etc.
- PDF report with summary page + detailed breakdown

**Elysium Index** (`src/parsers/adapters/elysium.py`)
- Simpler report: biological age, pace of aging, cumulative pace
- Uses their own "Index" biological age algorithm
- Key fields: Biological Age, Chronological Age, Rate of Aging

**Generic Epigenetic** (`src/parsers/adapters/epi_generic.py`)
- Fallback for other providers (myDNAge, GlycanAge, etc.)
- Extract biological age, chronological age, and any clock values found

### 4. Epigenetic Data Models

Create `src/parsers/epi_models.py`:

```python
@dataclass
class EpigeneticClockResult:
    clock_name: str          # "horvath", "hannum", "phenoage", "grimage", "dunedinpace", "elysium_index"
    value: float             # Age in years, or rate (DunedinPACE)
    unit: str                # "years" or "rate" (DunedinPACE is a rate, not age)
    description: str | None
    confidence: float

@dataclass
class OrganAgeResult:
    organ_system: str        # "immune", "heart", "liver", "kidney", "brain", "lung", "metabolic", "musculoskeletal", "hormone", "blood", "inflammation"
    biological_age: float
    chronological_age: float
    delta_years: float       # positive = older, negative = younger
    confidence: float

@dataclass
class EpigeneticParseResult:
    success: bool
    parser_used: str
    format_detected: str
    confidence: ConfidenceLevel
    test_date: date | None
    patient_name: str | None
    provider: str | None
    
    chronological_age: float | None
    primary_biological_age: float | None  # The "headline" bio age
    primary_clock_used: str | None
    
    # All clock results
    clocks: list[EpigeneticClockResult]
    
    # Organ-specific ages (TruDiagnostic)
    organ_ages: list[OrganAgeResult]
    
    # Pace of aging
    pace_of_aging: float | None           # DunedinPACE or equivalent
    pace_interpretation: str | None       # "aging 26% slower than average"
    
    # Telomere
    telomere_length: float | None
    telomere_percentile: int | None
    
    warnings: list[str]
    needs_review: bool
    raw_text: str
    parse_time_ms: int
```

### 5. Register ALL new parsers in registry.py

Update the adapter __init__.py and registry to auto-register all new parsers.

### 6. Tests

Write comprehensive tests for each parser:
- `test_dexafit.py` — with realistic mock DEXA report text
- `test_bodyspec.py` — with realistic mock text
- `test_trudiagnostic.py` — with realistic mock epigenetic report text
- `test_elysium.py` — with realistic mock text
- `test_dexa_generic.py` — edge cases
- `test_epi_generic.py` — edge cases

Create realistic test fixtures in conftest.py with sample report text that matches real report formats.

### 7. Update normalizer.py

Add DEXA and epigenetic canonical names to the biomarker aliases dictionary:
- body_fat_pct, lean_mass, bone_mineral_density, vat_mass, etc.
- biological_age, horvath_age, grimage, dunedinpace, telomere_length, etc.

### File structure:
```
src/parsers/
├── dexa_models.py          # DexaParseResult, DexaRegionResult, DexaBoneDensityResult
├── epi_models.py           # EpigeneticParseResult, EpigeneticClockResult, OrganAgeResult
├── adapters/
│   ├── dexafit.py
│   ├── bodyspec.py
│   ├── dexa_generic.py
│   ├── trudiagnostic.py
│   ├── elysium.py
│   └── epi_generic.py
└── tests/
    ├── test_dexafit.py
    ├── test_bodyspec.py
    ├── test_trudiagnostic.py
    ├── test_elysium.py
    ├── test_dexa_generic.py
    └── test_epi_generic.py
```

Write production-quality code. Type hints, docstrings, error handling, logging. Follow the exact same patterns as quest.py and labcorp.py.
