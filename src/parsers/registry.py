"""Parser registry — auto-discovery, format detection, and routing.

The registry holds all registered adapters sorted by priority.  When
``parse_document`` is called, it tries each adapter's ``can_parse()`` in
priority order and dispatches to the first match.  If no adapter matches,
it falls back to the ``generic_ai`` adapter.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from src.parsers.base import BaseParser, ConfidenceLevel, ParseResult
from src.parsers.pdf_utils import extract_text

if TYPE_CHECKING:
    pass

logger = logging.getLogger("vitalis.parsers.registry")


class ParserRegistry:
    """Registry of all parser adapters.

    Usage::

        registry = ParserRegistry()
        registry.register(QuestParser())
        registry.register(LabcorpParser())
        registry.register(GenericAIParser())   # must be last / highest priority #

        result = registry.route(file_bytes, "report.pdf")
    """

    def __init__(self) -> None:
        self._parsers: list[BaseParser] = []

    def register(self, parser: BaseParser) -> None:
        """Add an adapter and keep the list sorted by priority (ascending)."""
        self._parsers.append(parser)
        self._parsers.sort(key=lambda p: p.PRIORITY)
        logger.debug(
            "Registered parser %s (priority=%d)",
            parser.PARSER_ID,
            parser.PRIORITY,
        )

    def detect_format(self, text: str, filename: str = "") -> BaseParser | None:
        """Return the first adapter that claims it can parse the document."""
        for parser in self._parsers:
            try:
                if parser.can_parse(text, filename):
                    logger.info(
                        "Format detected: %s → %s",
                        filename or "<unnamed>",
                        parser.PARSER_ID,
                    )
                    return parser
            except Exception as exc:
                logger.warning(
                    "Parser %s raised during can_parse: %s",
                    parser.PARSER_ID,
                    exc,
                )
        return None

    def route(self, file_bytes: bytes, filename: str = "") -> ParseResult:
        """Extract text, detect format, and dispatch to the correct parser.

        Args:
            file_bytes: Raw PDF bytes.
            filename:   Original filename (used as a format hint).

        Returns:
            ParseResult from the winning adapter.
        """
        t0 = time.monotonic()

        # Step 1: Extract text
        extraction = extract_text(file_bytes)

        if not extraction.full_text.strip():
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            return ParseResult(
                success=False,
                parser_used="none",
                format_detected="Unknown",
                confidence=ConfidenceLevel.UNCERTAIN,
                warnings=extraction.warnings or ["No text could be extracted from PDF"],
                raw_text="",
                pages=extraction.page_count,
                parse_time_ms=elapsed_ms,
                error="No text extracted — PDF may be corrupted or empty",
            )

        text = extraction.full_text

        # Step 2: Detect format
        matched_parser = self.detect_format(text, filename)

        if matched_parser is None:
            # This should never happen if GenericAIParser is registered
            # (it always returns True from can_parse), but handle gracefully.
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            return ParseResult(
                success=False,
                parser_used="none",
                format_detected="Unknown",
                confidence=ConfidenceLevel.UNCERTAIN,
                warnings=["No parser available for this document format"],
                raw_text=text,
                pages=extraction.page_count,
                parse_time_ms=elapsed_ms,
                error="No matching parser found",
            )

        # Step 3: Parse
        try:
            result = matched_parser.parse(text, file_bytes, filename)
        except Exception as exc:
            logger.exception(
                "Parser %s raised an unhandled exception: %s",
                matched_parser.PARSER_ID,
                exc,
            )
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            return ParseResult(
                success=False,
                parser_used=matched_parser.PARSER_ID,
                format_detected="Unknown",
                confidence=ConfidenceLevel.UNCERTAIN,
                warnings=[],
                raw_text=text,
                pages=extraction.page_count,
                parse_time_ms=elapsed_ms,
                error=f"Parser {matched_parser.PARSER_ID} raised: {exc}",
            )

        # Merge extraction warnings into result
        result.warnings = extraction.warnings + result.warnings
        result.pages = extraction.page_count
        result.raw_text = text

        # Update parse_time to include extraction time
        total_ms = int((time.monotonic() - t0) * 1000)
        result.parse_time_ms = total_ms

        logger.info(
            "Parsed %s → %d markers, confidence=%s, time=%dms",
            filename or "<unnamed>",
            len(result.markers),
            result.confidence.value,
            total_ms,
        )

        return result

    @property
    def registered(self) -> list[str]:
        """Return list of registered parser IDs in priority order."""
        return [p.PARSER_ID for p in self._parsers]


# ---------------------------------------------------------------------------
# Singleton registry — populated in parsers/__init__.py
# ---------------------------------------------------------------------------

_registry: ParserRegistry | None = None


def get_registry() -> ParserRegistry:
    """Return the global registry instance, creating it if needed."""
    global _registry
    if _registry is None:
        _registry = _build_default_registry()
    return _registry


def _build_default_registry() -> ParserRegistry:
    """Instantiate and register all built-in adapters."""
    from src.parsers.adapters.quest import QuestParser
    from src.parsers.adapters.labcorp import LabcorpParser
    from src.parsers.adapters.insidetracker import InsideTrackerParser
    from src.parsers.adapters.function_health import FunctionHealthParser
    from src.parsers.adapters.generic import GenericAIParser

    registry = ParserRegistry()
    registry.register(QuestParser())
    registry.register(LabcorpParser())
    registry.register(InsideTrackerParser())
    registry.register(FunctionHealthParser())
    registry.register(GenericAIParser())  # always last — catch-all
    return registry
