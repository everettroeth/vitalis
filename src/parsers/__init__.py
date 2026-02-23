"""Vitalis Lab PDF Parser Engine — public API.

Usage::

    from src.parsers import parse_document

    with open("report.pdf", "rb") as f:
        result = parse_document(f.read(), "report.pdf")

    print(result.confidence)        # ConfidenceLevel.HIGH
    print(len(result.markers))      # e.g. 20
    for marker in result.markers:
        print(marker.canonical_name, marker.value, marker.unit)
"""

from __future__ import annotations

from src.parsers.base import (
    BaseParser,
    ConfidenceLevel,
    MarkerResult,
    ParseResult,
)
from src.parsers.registry import get_registry

__all__ = [
    "parse_document",
    "BaseParser",
    "ConfidenceLevel",
    "MarkerResult",
    "ParseResult",
]


def parse_document(file_bytes: bytes, filename: str = "") -> ParseResult:
    """Parse a lab report PDF and return structured results.

    This is the single entry point for all PDF parsing.  It automatically
    detects the lab format and dispatches to the correct adapter.

    Args:
        file_bytes: Raw bytes of the PDF file.
        filename:   Original filename — used as a format detection hint.

    Returns:
        :class:`ParseResult` with all extracted markers and metadata.

    Example::

        result = parse_document(pdf_bytes, "quest_cmp_2024.pdf")
        if result.success and result.confidence >= ConfidenceLevel.MEDIUM:
            for marker in result.markers:
                save_to_db(marker)
    """
    registry = get_registry()
    return registry.route(file_bytes, filename)
