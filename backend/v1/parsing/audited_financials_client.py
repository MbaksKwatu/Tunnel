"""
Client for the /v1/ingest/audited-financials endpoints on parity-ingestion.

Sends an audited-financials file (PDF, CSV, or Excel) to parity-ingestion
and returns a dict ready for insertion into pds_audited_financials.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

PARITY_INGESTION_URL = os.getenv("PARITY_INGESTION_URL", "").rstrip("/")

_TABULAR_EXTENSIONS = {".csv", ".xlsx", ".xls"}
_MIME_MAP = {
    ".pdf":  "application/pdf",
    ".csv":  "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls":  "application/vnd.ms-excel",
}


class AuditedFinancialsExtractionError(Exception):
    """Raised when parity-ingestion fails to extract audited financials."""


def _post_to_ingestion(url: str, file_bytes: bytes, file_name: str, mime: str) -> Dict[str, Any]:
    """POST a file to a parity-ingestion endpoint; return parsed JSON."""
    files = {"file": (file_name, file_bytes, mime)}
    try:
        with httpx.Client(timeout=httpx.Timeout(300.0)) as client:
            resp = client.post(url, files=files)
    except httpx.TimeoutException as exc:
        raise AuditedFinancialsExtractionError(
            f"Timeout calling parity-ingestion: {exc}"
        ) from exc
    except httpx.HTTPError as exc:
        raise AuditedFinancialsExtractionError(
            f"HTTP error calling parity-ingestion: {exc}"
        ) from exc

    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise AuditedFinancialsExtractionError(
            f"parity-ingestion returned {resp.status_code}: {detail}"
        )

    return resp.json()


def extract_audited_financials_via_ingestion(
    file_bytes: bytes,
    file_name: str,
) -> Dict[str, Any]:
    """
    POST an audited financials file to parity-ingestion.

    - PDF:        → /v1/ingest/audited-financials  (coordinate or OCR path)
    - CSV/Excel:  → /v1/ingest/audited-financials/tabular

    Falls back to inline pdfplumber extraction when parity-ingestion is
    unavailable or returns an error for PDF files.

    Returns the full extraction dict (all IS / BS / CF fields).
    Raises AuditedFinancialsExtractionError on failure.
    """
    ext = Path(file_name).suffix.lower()

    if PARITY_INGESTION_URL:
        mime = _MIME_MAP.get(ext, "application/octet-stream")
        if ext in _TABULAR_EXTENSIONS:
            url = f"{PARITY_INGESTION_URL}/v1/ingest/audited-financials/tabular"
        else:
            url = f"{PARITY_INGESTION_URL}/v1/ingest/audited-financials"

        try:
            data = _post_to_ingestion(url, file_bytes, file_name, mime)
            logger.info(
                "[AUDITED CLIENT] Extracted %s FY%s — confidence=%s method=%s",
                data.get("company_name"),
                data.get("financial_year"),
                data.get("extraction_confidence"),
                data.get("extraction_method"),
            )
            return data
        except AuditedFinancialsExtractionError as exc:
            if ext in _TABULAR_EXTENSIONS:
                # No inline fallback for CSV/Excel — re-raise
                raise
            logger.warning(
                "[AUDITED CLIENT] parity-ingestion failed (%s) — trying inline extraction", exc
            )

    # Inline fallback: run pdfplumber extractor directly on this worker.
    # Only works for PDF files; no OCR (scanned PDFs fall through to manual entry).
    if ext != ".pdf":
        raise AuditedFinancialsExtractionError(
            "PARITY_INGESTION_URL is not configured and inline extraction only supports PDF"
        )

    try:
        from .audited_financials_inline import extract_audited_financials_inline
        data = extract_audited_financials_inline(file_bytes, file_name)
        logger.info(
            "[AUDITED INLINE] Extracted %s FY%s — confidence=%s",
            data.get("company_name"),
            data.get("financial_year"),
            data.get("extraction_confidence"),
        )
        return data
    except Exception as exc:
        raise AuditedFinancialsExtractionError(
            f"Inline extraction failed: {exc}"
        ) from exc
