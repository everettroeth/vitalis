"""Data models for epigenetic / biological age test parse results.

These types are distinct from the standard ``ParseResult`` / ``MarkerResult``
used for blood labs.  Epigenetic reports expose multiple methylation clocks,
organ-system ages, and pace-of-aging metrics that require their own structure.

The ``EpigeneticParseResult`` is the primary return type from epigenetic
adapters' ``parse_structured()`` method.  Each adapter also implements
``parse()`` (returning a flat ``ParseResult``) so the standard registry can
route and store epigenetic documents alongside lab panels.

Unit conventions
----------------
All ages are in **years** (float).  Pace values (DunedinPACE) are
dimensionless rates (years of biological aging per calendar year).
Telomere length is in kilobases (kb).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from src.parsers.base import ConfidenceLevel


# ---------------------------------------------------------------------------
# Methylation clock result
# ---------------------------------------------------------------------------


@dataclass
class EpigeneticClockResult:
    """Result from a single epigenetic aging clock algorithm.

    Attributes:
        clock_name:   Canonical clock identifier.  One of:
                      ``"horvath"``, ``"hannum"``, ``"phenoage"``,
                      ``"grimage"``, ``"dunedinpace"``,
                      ``"elysium_index"``, ``"mydnage"``, ``"glycanage"``.
        value:        Predicted age in years, OR aging rate for DunedinPACE.
        unit:         ``"years"`` for age clocks, ``"rate"`` for DunedinPACE.
        description:  Optional human-readable interpretation from the report.
        confidence:   0.0–1.0 per-clock extraction confidence.
    """

    clock_name: str
    value: float
    unit: str = "years"
    description: str | None = None
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return {
            "clock_name": self.clock_name,
            "value": self.value,
            "unit": self.unit,
            "description": self.description,
            "confidence": round(self.confidence, 4),
        }


# ---------------------------------------------------------------------------
# Organ age result
# ---------------------------------------------------------------------------


@dataclass
class OrganAgeResult:
    """Biological age estimate for a single organ system.

    Attributes:
        organ_system:      Canonical organ system slug.  One of:
                           ``"immune"``, ``"heart"``, ``"liver"``,
                           ``"kidney"``, ``"brain"``, ``"lung"``,
                           ``"metabolic"``, ``"musculoskeletal"``,
                           ``"hormone"``, ``"blood"``, ``"inflammation"``.
        biological_age:    Estimated biological age of the organ system
                           in years.
        chronological_age: Patient's actual age in years at time of test.
        delta_years:       biological_age − chronological_age.  Negative
                           means the organ is aging younger than calendar
                           age; positive means older.
        confidence:        0.0–1.0 per-organ extraction confidence.
    """

    organ_system: str
    biological_age: float
    chronological_age: float
    delta_years: float
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return {
            "organ_system": self.organ_system,
            "biological_age": self.biological_age,
            "chronological_age": self.chronological_age,
            "delta_years": round(self.delta_years, 2),
            "confidence": round(self.confidence, 4),
        }


# ---------------------------------------------------------------------------
# Top-level epigenetic parse result
# ---------------------------------------------------------------------------


@dataclass
class EpigeneticParseResult:
    """Top-level result returned by any epigenetic test parser adapter.

    Attributes:
        success:          Whether parsing completed without a fatal error.
        parser_used:      Adapter identifier, e.g. ``"trudiagnostic_v1"``.
        format_detected:  Human-readable description of the detected format.
        confidence:       Overall extraction confidence.
        test_date:        Date of sample collection.
        patient_name:     Patient full name (PII — not stored server-side).
        provider:         Testing company name, e.g. ``"TruDiagnostic"``.

        chronological_age:    Patient's calendar age at time of test.
        primary_biological_age: The headline biological age displayed by
                              the provider.
        primary_clock_used:   Clock algorithm used for the headline age.

        clocks:           All individual clock results found in the report.
        organ_ages:       Organ-system biological ages (TruDiagnostic).

        pace_of_aging:    DunedinPACE score or equivalent rate.
        pace_interpretation: Provider's textual interpretation of the pace
                           score, e.g. ``"aging 18% slower than average"``.

        telomere_length:    Telomere length in kilobases (kb).
        telomere_percentile: Age-adjusted percentile (0–100).

        warnings:      Non-fatal issues encountered during parsing.
        needs_review:  True when confidence is LOW or UNCERTAIN.
        raw_text:      Full extracted PDF text (omitted from to_dict).
        parse_time_ms: Wall-clock parsing time.
        error:         Fatal error message if success is False.
    """

    success: bool
    parser_used: str
    format_detected: str
    confidence: ConfidenceLevel

    test_date: date | None = None
    patient_name: str | None = None
    provider: str | None = None

    chronological_age: float | None = None
    primary_biological_age: float | None = None
    primary_clock_used: str | None = None

    # Detailed clock breakdown
    clocks: list[EpigeneticClockResult] = field(default_factory=list)

    # Organ-specific ages (TruDiagnostic only)
    organ_ages: list[OrganAgeResult] = field(default_factory=list)

    # Pace of aging
    pace_of_aging: float | None = None
    pace_interpretation: str | None = None

    # Telomere
    telomere_length: float | None = None
    telomere_percentile: int | None = None

    warnings: list[str] = field(default_factory=list)
    needs_review: bool = False
    raw_text: str = ""
    parse_time_ms: int = 0
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "parser_used": self.parser_used,
            "format_detected": self.format_detected,
            "confidence": self.confidence.value,
            "test_date": self.test_date.isoformat() if self.test_date else None,
            "patient_name": self.patient_name,
            "provider": self.provider,
            "chronological_age": self.chronological_age,
            "primary_biological_age": self.primary_biological_age,
            "primary_clock_used": self.primary_clock_used,
            "clocks": [c.to_dict() for c in self.clocks],
            "organ_ages": [o.to_dict() for o in self.organ_ages],
            "pace_of_aging": self.pace_of_aging,
            "pace_interpretation": self.pace_interpretation,
            "telomere_length": self.telomere_length,
            "telomere_percentile": self.telomere_percentile,
            "warnings": self.warnings,
            "needs_review": self.needs_review,
            "parse_time_ms": self.parse_time_ms,
            "error": self.error,
            # raw_text intentionally omitted from default serialisation
        }
