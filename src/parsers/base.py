"""Base classes and data models for the Vitalis lab PDF parser engine.

Every parser adapter must subclass BaseParser and return ParseResult /
MarkerResult instances.  These types are the single source of truth
consumed by the FastAPI layer, the database writer, and the frontend.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import ClassVar

logger = logging.getLogger("vitalis.parsers")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ConfidenceLevel(str, Enum):
    """Human-readable confidence band for a parse result or individual marker.

    Thresholds:
        HIGH      >= 0.90  — exact format match, all fields cleanly parsed
        MEDIUM    >= 0.70  — format recognised, minor ambiguity
        LOW       >= 0.50  — AI fallback or unusual layout; needs review
        UNCERTAIN  < 0.50  — best-effort only; always flags for human review
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"

    @classmethod
    def from_score(cls, score: float) -> "ConfidenceLevel":
        if score >= 0.90:
            return cls.HIGH
        if score >= 0.70:
            return cls.MEDIUM
        if score >= 0.50:
            return cls.LOW
        return cls.UNCERTAIN


# ---------------------------------------------------------------------------
# Marker result
# ---------------------------------------------------------------------------


@dataclass
class MarkerResult:
    """Parsed representation of a single biomarker extracted from a lab report.

    Attributes:
        canonical_name:     Matches ``biomarker_dictionary.canonical_name``
                            (snake_case, e.g. ``"glucose"``).
        display_name:       Name exactly as printed on the source report.
        value:              Parsed numeric value (after unit conversion if any).
        value_text:         Raw text from the report (e.g. ``">100"``, ``"<0.5"``).
        unit:               Unit as printed on the report.
        canonical_unit:     Normalised unit (e.g. ``"mg/dL"`` → ``"mg/dL"``).
        reference_low:      Lower bound of normal range, or None.
        reference_high:     Upper bound of normal range, or None.
        reference_text:     Original reference range string.
        flag:               ``"H"`` (high), ``"L"`` (low), ``"A"`` (abnormal),
                            ``"C"`` (critical), or ``None``.
        confidence:         0.0–1.0 per-marker confidence score.
        confidence_reasons: Human-readable reasons driving the score.
        page:               1-based page number in the source PDF.
    """

    canonical_name: str
    display_name: str
    value: float
    value_text: str
    unit: str
    canonical_unit: str = ""
    reference_low: float | None = None
    reference_high: float | None = None
    reference_text: str = ""
    flag: str | None = None
    confidence: float = 0.0
    confidence_reasons: list[str] = field(default_factory=list)
    page: int = 1

    def __post_init__(self) -> None:
        # Coerce flag to uppercase if present
        if self.flag:
            self.flag = self.flag.strip().upper() or None

    @property
    def confidence_level(self) -> ConfidenceLevel:
        return ConfidenceLevel.from_score(self.confidence)

    @property
    def is_abnormal(self) -> bool:
        return self.flag is not None

    def to_dict(self) -> dict:
        return {
            "canonical_name": self.canonical_name,
            "display_name": self.display_name,
            "value": self.value,
            "value_text": self.value_text,
            "unit": self.unit,
            "canonical_unit": self.canonical_unit,
            "reference_low": self.reference_low,
            "reference_high": self.reference_high,
            "reference_text": self.reference_text,
            "flag": self.flag,
            "confidence": round(self.confidence, 4),
            "confidence_level": self.confidence_level.value,
            "confidence_reasons": self.confidence_reasons,
            "page": self.page,
        }


# ---------------------------------------------------------------------------
# Parse result
# ---------------------------------------------------------------------------


@dataclass
class ParseResult:
    """Top-level result returned by any parser adapter.

    Attributes:
        success:            Whether parsing completed without a fatal error.
        parser_used:        Identifier of the adapter that produced this result,
                            e.g. ``"quest_v1"``, ``"generic_ai"``.
        format_detected:    Human-readable format name, e.g.
                            ``"Quest Diagnostics — Comprehensive Metabolic Panel"``.
        confidence:         Overall confidence level (derived from marker scores).
        patient_name:       Patient full name if detectable (not stored, only for
                            client-side verification).
        collection_date:    Date blood was collected.
        report_date:        Date the report was issued.
        lab_name:           Laboratory name as printed.
        ordering_provider:  Ordering physician name.
        markers:            All successfully extracted markers.
        warnings:           Non-fatal issues encountered during parsing.
        needs_review:       ``True`` if ANY marker has LOW or UNCERTAIN confidence.
        raw_text:           Full extracted PDF text (for debugging / AI fallback).
        pages:              Total page count of the source PDF.
        parse_time_ms:      Wall-clock parsing time in milliseconds.
        error:              Fatal error message if ``success`` is ``False``.
    """

    success: bool
    parser_used: str
    format_detected: str
    confidence: ConfidenceLevel
    markers: list[MarkerResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    needs_review: bool = False
    raw_text: str = ""
    pages: int = 0
    parse_time_ms: int = 0
    patient_name: str | None = None
    collection_date: date | None = None
    report_date: date | None = None
    lab_name: str | None = None
    ordering_provider: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "parser_used": self.parser_used,
            "format_detected": self.format_detected,
            "confidence": self.confidence.value,
            "patient_name": self.patient_name,
            "collection_date": self.collection_date.isoformat()
            if self.collection_date
            else None,
            "report_date": self.report_date.isoformat()
            if self.report_date
            else None,
            "lab_name": self.lab_name,
            "ordering_provider": self.ordering_provider,
            "markers": [m.to_dict() for m in self.markers],
            "warnings": self.warnings,
            "needs_review": self.needs_review,
            "pages": self.pages,
            "parse_time_ms": self.parse_time_ms,
            "error": self.error,
            # raw_text intentionally omitted from default serialisation (large)
        }


# ---------------------------------------------------------------------------
# Base parser
# ---------------------------------------------------------------------------


class BaseParser(ABC):
    """Abstract base class for all lab report parser adapters.

    Subclasses must implement ``can_parse`` and ``parse``.  The registry calls
    ``can_parse`` to route a document to the correct adapter before calling
    ``parse``.

    Class-level attributes:
        PARSER_ID:    Unique slug, e.g. ``"quest_v1"``.
        PRIORITY:     Lower = tried first.  Generic AI parser should be last.
        LAB_NAME:     Human-readable lab / format name.
    """

    PARSER_ID: ClassVar[str] = "base"
    PRIORITY: ClassVar[int] = 50
    LAB_NAME: ClassVar[str] = "Unknown"

    @abstractmethod
    def can_parse(self, text: str, filename: str = "") -> bool:
        """Return True if this adapter recognises the document.

        Args:
            text:     Full extracted text of the PDF.
            filename: Original filename (may provide hints).
        """

    @abstractmethod
    def parse(self, text: str, file_bytes: bytes, filename: str = "") -> ParseResult:
        """Parse the document and return a structured ParseResult.

        Args:
            text:       Full extracted text from pdf_utils.
            file_bytes: Raw PDF bytes (available for OCR or page-level work).
            filename:   Original filename.
        """

    # ------------------------------------------------------------------
    # Shared helpers — available to all adapters
    # ------------------------------------------------------------------

    @staticmethod
    def _clean(s: str) -> str:
        """Strip excess whitespace from a string."""
        return " ".join(s.split())

    @staticmethod
    def _safe_float(text: str) -> float | None:
        """Parse a potentially decorated numeric string.

        Handles:
            ``>60``  → ``60.0``
            ``<0.5`` → ``0.5``
            ``5.2H`` → ``5.2``
            ``Non-Reactive`` → ``None``
        """
        text = text.strip()
        # Strip common decorations
        for prefix in (">", "<", ">=", "<=", "≥", "≤", "~"):
            text = text.lstrip(prefix)
        # Strip trailing letter flags (H, L, A, C)
        text = text.rstrip("HLAChlac").strip()
        try:
            return float(text.replace(",", ""))
        except ValueError:
            return None
