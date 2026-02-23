"""Tests for the parser registry — format detection and routing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.parsers.base import BaseParser, ConfidenceLevel, ParseResult
from src.parsers.registry import ParserRegistry, get_registry
from src.parsers.tests.conftest import (
    QUEST_CMP_TEXT,
    LABCORP_LIPID_TEXT,
    FAKE_PDF_BYTES,
)


# ---------------------------------------------------------------------------
# ParserRegistry — registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_register_adds_parser(self):
        registry = ParserRegistry()
        mock = MagicMock(spec=BaseParser)
        mock.PARSER_ID = "test_parser"
        mock.PRIORITY = 10
        registry.register(mock)
        assert "test_parser" in registry.registered

    def test_priority_ordering(self):
        registry = ParserRegistry()

        p1 = MagicMock(spec=BaseParser)
        p1.PARSER_ID = "high_pri"
        p1.PRIORITY = 5

        p2 = MagicMock(spec=BaseParser)
        p2.PARSER_ID = "low_pri"
        p2.PRIORITY = 50

        registry.register(p2)  # register low first
        registry.register(p1)  # then high

        # Should be sorted by priority
        assert registry.registered[0] == "high_pri"
        assert registry.registered[1] == "low_pri"


# ---------------------------------------------------------------------------
# detect_format
# ---------------------------------------------------------------------------


class TestDetectFormat:
    def _make_registry(self, *parsers: BaseParser) -> ParserRegistry:
        r = ParserRegistry()
        for p in parsers:
            r.register(p)
        return r

    def test_first_matching_parser_wins(self):
        p1 = MagicMock(spec=BaseParser)
        p1.PARSER_ID = "p1"
        p1.PRIORITY = 10
        p1.can_parse.return_value = True

        p2 = MagicMock(spec=BaseParser)
        p2.PARSER_ID = "p2"
        p2.PRIORITY = 20
        p2.can_parse.return_value = True

        registry = self._make_registry(p1, p2)
        result = registry.detect_format("some text")
        assert result.PARSER_ID == "p1"

    def test_no_match_returns_none(self):
        p1 = MagicMock(spec=BaseParser)
        p1.PARSER_ID = "p1"
        p1.PRIORITY = 10
        p1.can_parse.return_value = False

        registry = self._make_registry(p1)
        assert registry.detect_format("some text") is None

    def test_exception_in_can_parse_skips_parser(self):
        p1 = MagicMock(spec=BaseParser)
        p1.PARSER_ID = "bad_parser"
        p1.PRIORITY = 5
        p1.can_parse.side_effect = RuntimeError("oops")

        p2 = MagicMock(spec=BaseParser)
        p2.PARSER_ID = "good_parser"
        p2.PRIORITY = 10
        p2.can_parse.return_value = True

        registry = self._make_registry(p1, p2)
        result = registry.detect_format("text")
        assert result.PARSER_ID == "good_parser"


# ---------------------------------------------------------------------------
# Quest and Labcorp format detection (real adapters)
# ---------------------------------------------------------------------------


class TestRealFormatDetection:
    def setup_method(self):
        from src.parsers.adapters.quest import QuestParser
        from src.parsers.adapters.labcorp import LabcorpParser
        from src.parsers.adapters.generic import GenericAIParser

        self.registry = ParserRegistry()
        self.registry.register(QuestParser())
        self.registry.register(LabcorpParser())
        self.registry.register(GenericAIParser())

    def test_quest_text_detected(self):
        parser = self.registry.detect_format(QUEST_CMP_TEXT, "report.pdf")
        assert parser is not None
        assert parser.PARSER_ID == "quest_v1"

    def test_labcorp_text_detected(self):
        parser = self.registry.detect_format(LABCORP_LIPID_TEXT, "report.pdf")
        assert parser is not None
        assert parser.PARSER_ID == "labcorp_v1"

    def test_unknown_falls_to_generic(self):
        parser = self.registry.detect_format("some random text with no lab header", "file.pdf")
        assert parser is not None
        assert parser.PARSER_ID == "generic_ai"

    def test_filename_hint_quest(self):
        from src.parsers.adapters.quest import QuestParser
        p = QuestParser()
        assert p.can_parse("minimal text", "quest_results_2024.pdf") is True

    def test_filename_hint_labcorp(self):
        from src.parsers.adapters.labcorp import LabcorpParser
        p = LabcorpParser()
        assert p.can_parse("minimal text", "labcorp_report.pdf") is True


# ---------------------------------------------------------------------------
# Registry.route — with mocked PDF extraction
# ---------------------------------------------------------------------------


class TestRoute:
    def test_route_returns_failure_on_empty_text(self):
        registry = ParserRegistry()
        # No parsers registered

        with patch("src.parsers.registry.extract_text") as mock_extract:
            mock_result = MagicMock()
            mock_result.full_text = ""
            mock_result.page_count = 1
            mock_result.warnings = []
            mock_extract.return_value = mock_result

            result = registry.route(FAKE_PDF_BYTES, "empty.pdf")

        assert result.success is False
        assert result.confidence == ConfidenceLevel.UNCERTAIN

    def test_route_returns_failure_when_no_parsers(self):
        registry = ParserRegistry()
        # No parsers — detect_format returns None

        with patch("src.parsers.registry.extract_text") as mock_extract:
            mock_result = MagicMock()
            mock_result.full_text = "some extracted text from PDF"
            mock_result.page_count = 1
            mock_result.warnings = []
            mock_extract.return_value = mock_result

            result = registry.route(FAKE_PDF_BYTES, "test.pdf")

        assert result.success is False

    def test_route_catches_parser_exceptions(self):
        registry = ParserRegistry()

        bad_parser = MagicMock(spec=BaseParser)
        bad_parser.PARSER_ID = "exploding_parser"
        bad_parser.PRIORITY = 1
        bad_parser.can_parse.return_value = True
        bad_parser.parse.side_effect = RuntimeError("Unexpected failure")
        registry.register(bad_parser)

        with patch("src.parsers.registry.extract_text") as mock_extract:
            mock_result = MagicMock()
            mock_result.full_text = "some text"
            mock_result.page_count = 1
            mock_result.warnings = []
            mock_extract.return_value = mock_result

            result = registry.route(FAKE_PDF_BYTES, "test.pdf")

        assert result.success is False
        assert "exploding_parser" in (result.error or "")


# ---------------------------------------------------------------------------
# get_registry — singleton
# ---------------------------------------------------------------------------


def test_get_registry_returns_singleton():
    r1 = get_registry()
    r2 = get_registry()
    assert r1 is r2


def test_get_registry_has_all_adapters():
    registry = get_registry()
    ids = registry.registered
    assert "quest_v1" in ids
    assert "labcorp_v1" in ids
    assert "generic_ai" in ids
    # Generic AI should be last
    assert ids[-1] == "generic_ai"
