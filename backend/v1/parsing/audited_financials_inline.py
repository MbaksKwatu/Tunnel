"""
Inline audited financials extraction for the Render backend.

Used as a fallback when the parity-ingestion service is unavailable or doesn't
yet expose the /v1/ingest/audited-financials endpoint.

Loads the extractor from the parity-ingestion directory (sibling of backend/).
Only needs pdfplumber, which is already in the backend's requirements.
"""
from __future__ import annotations

import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Resolve the parity-ingestion directory relative to this file:
#   backend/v1/parsing/audited_financials_inline.py
#   → ../../..  = Tunnel/
#   → ../../../parity-ingestion
_HERE = Path(__file__).resolve()
_PARITY_INGESTION_DIR = str(_HERE.parents[3] / "parity-ingestion")


def _load_extractor():
    """Lazily add parity-ingestion to sys.path and import the extractor."""
    if _PARITY_INGESTION_DIR not in sys.path:
        sys.path.insert(0, _PARITY_INGESTION_DIR)
    try:
        from app.extractors.audited_financials_extractor import extract_audited_financials
        return extract_audited_financials
    except ImportError as exc:
        raise ImportError(
            f"Could not import audited_financials_extractor from {_PARITY_INGESTION_DIR}: {exc}"
        ) from exc


def extract_audited_financials_inline(
    file_bytes: bytes,
    file_name: str,
) -> Dict[str, Any]:
    """
    Extract audited financials from a PDF using the parity-ingestion extractor.

    Returns the same dict shape that /v1/ingest/audited-financials returns.
    Raises ValueError or ImportError on failure.
    """
    ext = Path(file_name).suffix.lower()
    if ext != ".pdf":
        raise ValueError(f"Inline extraction only supports PDF; got '{ext}'")

    extract_fn = _load_extractor()

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    try:
        tmp.write(file_bytes)
        tmp.flush()
        tmp.close()
        result = extract_fn(tmp.name)
        logger.info(
            "[INLINE AUDIT] Extracted %s FY%s — confidence=%s",
            result.get("company_name"),
            result.get("financial_year"),
            result.get("extraction_confidence"),
        )
        return result
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
