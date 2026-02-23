"""PDF text extraction utilities.

Primary:  pdfplumber  — fast, accurate for digitally-produced PDFs.
Fallback: pytesseract — OCR for scanned / image-based PDFs.

Both paths return a list of page strings and a joined full-text string.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger("vitalis.parsers.pdf_utils")


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass
class ExtractionResult:
    """Result from extracting text out of a PDF."""

    pages: list[str]    # Per-page text (1-indexed via pages[page-1])
    full_text: str      # All pages joined with form-feed separator
    page_count: int
    method: str         # "pdfplumber" | "ocr" | "combined"
    warnings: list[str]

    @classmethod
    def empty(cls, warning: str = "") -> "ExtractionResult":
        return cls(
            pages=[],
            full_text="",
            page_count=0,
            method="none",
            warnings=[warning] if warning else [],
        )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def extract_text(file_bytes: bytes) -> ExtractionResult:
    """Extract text from PDF bytes.

    Tries pdfplumber first.  If the extracted text is suspiciously short
    (< 100 chars per page on average) the PDF is likely scanned, and we
    fall back to OCR via pytesseract.

    Args:
        file_bytes: Raw PDF bytes.

    Returns:
        ExtractionResult with per-page and full text.
    """
    result = _extract_pdfplumber(file_bytes)

    if result.page_count == 0:
        return ExtractionResult.empty("PDF has zero pages or could not be opened")

    avg_chars = len(result.full_text) / result.page_count if result.page_count else 0

    if avg_chars < 100:
        logger.info(
            "pdfplumber extracted only %.0f chars/page — attempting OCR fallback",
            avg_chars,
        )
        ocr_result = _extract_ocr(file_bytes)
        if ocr_result.full_text:
            ocr_result.warnings.append(
                "OCR used — original PDF appears to be scanned"
            )
            return ocr_result
        else:
            result.warnings.append(
                "OCR attempted but produced no text — returning pdfplumber output"
            )

    return result


# ---------------------------------------------------------------------------
# pdfplumber extraction
# ---------------------------------------------------------------------------


def _extract_pdfplumber(file_bytes: bytes) -> ExtractionResult:
    """Extract text using pdfplumber."""
    try:
        import pdfplumber  # type: ignore[import]
    except ImportError:
        logger.warning("pdfplumber not installed — cannot extract PDF text")
        return ExtractionResult.empty("pdfplumber not installed")

    pages: list[str] = []
    warnings: list[str] = []

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                try:
                    # Extract with table awareness — pdfplumber handles column
                    # layout better when we also extract tables explicitly.
                    page_text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""

                    # Also try extracting tables and append their text
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            for row in table:
                                if row:
                                    row_text = "  ".join(
                                        str(cell).strip() if cell else ""
                                        for cell in row
                                    )
                                    if row_text.strip():
                                        page_text += "\n" + row_text

                    pages.append(page_text)
                except Exception as exc:
                    warnings.append(f"Page {i}: extraction failed — {exc}")
                    pages.append("")
    except Exception as exc:
        logger.error("pdfplumber failed to open PDF: %s", exc)
        return ExtractionResult.empty(f"pdfplumber open error: {exc}")

    full_text = "\f".join(pages)  # form-feed between pages
    return ExtractionResult(
        pages=pages,
        full_text=full_text,
        page_count=len(pages),
        method="pdfplumber",
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# OCR fallback
# ---------------------------------------------------------------------------


def _extract_ocr(file_bytes: bytes) -> ExtractionResult:
    """Extract text via pytesseract OCR (for scanned PDFs)."""
    try:
        import pytesseract  # type: ignore[import]
        from PIL import Image  # type: ignore[import]
    except ImportError:
        return ExtractionResult.empty(
            "pytesseract / Pillow not installed — OCR unavailable"
        )

    try:
        import fitz  # PyMuPDF  # type: ignore[import]
    except ImportError:
        return ExtractionResult.empty(
            "PyMuPDF (fitz) not installed — cannot rasterise PDF for OCR"
        )

    pages: list[str] = []
    warnings: list[str] = []

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for i, page in enumerate(doc, start=1):
            try:
                # Render at 300 DPI for good OCR accuracy
                mat = fitz.Matrix(300 / 72, 300 / 72)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                text = pytesseract.image_to_string(
                    img,
                    lang="eng",
                    config="--oem 3 --psm 6",
                )
                pages.append(text)
            except Exception as exc:
                warnings.append(f"OCR page {i} failed: {exc}")
                pages.append("")
        doc.close()
    except Exception as exc:
        logger.error("OCR extraction failed: %s", exc)
        return ExtractionResult.empty(f"OCR error: {exc}")

    full_text = "\f".join(pages)
    return ExtractionResult(
        pages=pages,
        full_text=full_text,
        page_count=len(pages),
        method="ocr",
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Text cleaning helpers used by adapter parsers
# ---------------------------------------------------------------------------


def clean_whitespace(text: str) -> str:
    """Collapse repeated spaces/tabs into single spaces; preserve newlines."""
    lines = []
    for line in text.splitlines():
        lines.append(re.sub(r"[ \t]+", " ", line).strip())
    return "\n".join(lines)


def split_pages(full_text: str) -> list[str]:
    """Split a full_text string (form-feed-separated) back into pages."""
    return full_text.split("\f")


def lines_around(text: str, pattern: str, context: int = 5) -> list[str]:
    """Return ``context`` lines before/after the first line matching *pattern*.

    Useful for debugging parser logic — shows the surrounding context of a
    matched region.
    """
    rx = re.compile(pattern, re.IGNORECASE)
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if rx.search(line):
            start = max(0, i - context)
            end = min(len(lines), i + context + 1)
            return lines[start:end]
    return []
