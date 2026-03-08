"""
PDF type detector — distinguishes digital (text-layer) PDFs from scanned
(image-only) PDFs using pdfplumber word extraction.

Threshold: fewer than 10 words across the first 2 pages = scanned.
The 10-word buffer accommodates PDFs that carry a small text stamp (e.g. a
watermark or page number) on an otherwise image-only page.
"""
from __future__ import annotations

import pdfplumber

_SCANNED_WORD_THRESHOLD = 10
_PAGES_TO_CHECK = 2


def is_scanned_pdf(path: str) -> bool:
    """
    Return True if the PDF has no meaningful extractable text.

    Opens up to the first _PAGES_TO_CHECK pages with pdfplumber and counts
    total words.  If the total is below _SCANNED_WORD_THRESHOLD, the file is
    treated as a scanned / image-only PDF that requires OCR.
    """
    total_words = 0
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[:_PAGES_TO_CHECK]:
            words = page.extract_words()
            total_words += len(words)
            if total_words >= _SCANNED_WORD_THRESHOLD:
                return False
    return total_words < _SCANNED_WORD_THRESHOLD
