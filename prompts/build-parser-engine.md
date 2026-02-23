You are a senior Python engineer building the Lab PDF Parser Engine for Vitalis, a health intelligence platform targeting #1 in the world.

## Context
Read these files first:
- PLAN.md — project overview
- BUILD-ORDER.md — build strategy (parser is Phase 2, highest priority)
- COMPETITIVE-ANALYSIS.md — why parsers are our moat
- SCHEMA.md — data architecture (biomarker_dictionary, blood_panels, blood_markers tables)
- schema.sql — look at the biomarker_dictionary seed data for canonical marker names and aliases
- src/ — existing FastAPI app structure
- requirements.txt — current dependencies

## What to Build
A production-grade lab PDF parser engine with pluggable adapters. This is the CORE differentiator of the entire product.

### Architecture
```
src/parsers/
├── __init__.py              # Public API: parse_document(file_bytes, filename) -> ParseResult
├── base.py                  # BaseParser ABC, ParseResult, MarkerResult, ConfidenceLevel
├── registry.py              # Parser registry — auto-discovery, format detection, routing
├── normalizer.py            # Canonical marker name normalization (uses biomarker_dictionary aliases)
├── confidence.py            # Confidence scoring logic
├── pdf_utils.py             # PDF text extraction utilities (pdfplumber + OCR fallback)
├── adapters/
│   ├── __init__.py
│   ├── quest.py             # Quest Diagnostics parser
│   ├── labcorp.py           # Labcorp parser  
│   ├── insidetracker.py     # InsideTracker report parser
│   ├── function_health.py   # Function Health report parser
│   └── generic.py           # AI-powered fallback for unknown formats
└── tests/
    ├── __init__.py
    ├── conftest.py           # Shared fixtures, test helpers
    ├── test_quest.py         # Quest parser tests
    ├── test_labcorp.py       # Labcorp parser tests
    ├── test_normalizer.py    # Normalization tests
    ├── test_confidence.py    # Confidence scoring tests
    ├── test_registry.py      # Format detection tests
    ├── test_generic.py       # Generic/AI parser tests
    └── fixtures/
        ├── quest/            # Quest PDF fixtures + expected JSON
        ├── labcorp/          # Labcorp fixtures
        └── generic/          # Edge case fixtures
```

### Core Data Models (in base.py)

```python
class ConfidenceLevel(Enum):
    HIGH = "high"        # 0.9+ — exact format match, all fields parsed
    MEDIUM = "medium"    # 0.7-0.9 — format recognized, some ambiguity
    LOW = "low"          # 0.5-0.7 — AI fallback, needs human review
    UNCERTAIN = "uncertain"  # <0.5 — best guess, definitely needs review

class MarkerResult:
    canonical_name: str      # Matches biomarker_dictionary.canonical_name
    display_name: str        # Original name as printed on the lab report
    value: float             # Numeric value
    value_text: str          # Original text (e.g., ">100", "< 0.5", "Non-Reactive")
    unit: str                # As printed on report
    canonical_unit: str      # Normalized unit
    reference_low: float | None
    reference_high: float | None
    reference_text: str      # Original reference range text
    flag: str | None         # "H", "L", "A", None
    confidence: float        # 0.0-1.0
    confidence_reasons: list[str]  # Why this confidence level
    page: int                # Which page of PDF
    
class ParseResult:
    success: bool
    parser_used: str         # e.g., "quest_v1", "labcorp_v1", "generic_ai"
    format_detected: str     # e.g., "Quest Diagnostics - Comprehensive Metabolic Panel"
    confidence: ConfidenceLevel   # Overall parse confidence
    patient_name: str | None      # If detected (for verification, not storage)
    collection_date: date | None  # When blood was drawn
    report_date: date | None      # When report was generated
    lab_name: str | None
    ordering_provider: str | None
    markers: list[MarkerResult]
    warnings: list[str]      # Issues encountered
    needs_review: bool       # True if any marker has low confidence
    raw_text: str            # Full extracted text (for debugging)
    pages: int               # Total pages in PDF
    parse_time_ms: int       # How long parsing took
```

### Key Design Decisions

1. **Format Detection**: Each adapter registers patterns it recognizes (e.g., Quest reports always have "Quest Diagnostics" in header, specific formatting). Registry tries each adapter's `can_parse()` method.

2. **Normalization**: Every extracted marker name gets fuzzy-matched against the biomarker_dictionary aliases. Use rapidfuzz for fuzzy matching with a 85% threshold.

3. **Confidence Scoring**: 
   - Did the format match exactly? (+0.3)
   - Was the marker name found in dictionary? (+0.2)
   - Was the value parseable as a number? (+0.2)
   - Was the unit recognized? (+0.15)
   - Was the reference range parseable? (+0.15)

4. **PDF Extraction**: Use pdfplumber as primary (fast, accurate for digital PDFs). Fall back to pytesseract OCR for scanned PDFs.

5. **Generic/AI Parser**: For unknown formats, extract text and use Claude/GPT to identify markers. This is the fallback — always flags for human review.

6. **Unit Conversion**: Handle common unit conversions (mmol/L ↔ mg/dL for glucose, etc.) with conversion factors stored in normalizer.

### Quest Diagnostics Format
Quest reports typically have:
- Header with "Quest Diagnostics" logo/text
- Patient info section (name, DOB, specimen ID)
- Ordering physician
- Test sections with: Test Name | Result | Flag | Reference Range | Units
- Results are in tabular format, sometimes across multiple pages
- Special handling for: calculated values, comments, footnotes

### Labcorp Format
Labcorp reports have:
- "Laboratory Corporation of America" or "Labcorp" in header
- Similar tabular format but different column ordering
- Often include "FINAL REPORT" watermark
- Reference ranges sometimes in separate column, sometimes inline

### What to Actually Write

Write ALL the files listed in the architecture above. Write real, production-quality code. Include:
- Full type hints
- Docstrings
- Error handling
- Logging
- The actual parsing logic (regex patterns, text extraction, normalization)

For Quest and Labcorp parsers: implement real parsing logic based on the known format patterns. These should work on actual lab PDFs.

For tests: write comprehensive tests including:
- Happy path tests with mock PDF text
- Edge cases (missing values, unusual formats, multi-page)
- Normalization tests (fuzzy matching, unit conversion)
- Confidence scoring tests
- Registry/routing tests

Also create synthetic test fixtures as JSON (since we can't include real PDFs in the repo):
- `fixtures/quest/sample_cmp.expected.json` — expected output for a Quest CMP panel
- `fixtures/labcorp/sample_lipid.expected.json` — expected output for a Labcorp lipid panel

Update requirements.txt with new dependencies:
- pdfplumber
- rapidfuzz
- pytesseract (optional, for OCR)

Finally, add a FastAPI router at `src/routers/parsers.py` with:
- POST /api/documents/upload — upload PDF, parse, return results
- GET /api/documents/{id}/parse-result — get parse result
- POST /api/documents/{id}/confirm — user confirms/corrects parsed values

This is the most important code in the entire application. Take your time. Get it right.
