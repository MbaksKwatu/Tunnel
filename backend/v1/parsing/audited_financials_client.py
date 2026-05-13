"""
Client for the /v1/ingest/audited-financials endpoint on parity-ingestion.

Sends an audited-financials PDF to parity-ingestion and returns a dict
ready for insertion into pds_audited_financials.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

PARITY_INGESTION_URL = os.getenv("PARITY_INGESTION_URL", "").rstrip("/")


class AuditedFinancialsExtractionError(Exception):
    """Raised when parity-ingestion fails to extract audited financials."""


def extract_audited_financials_via_ingestion(
    file_bytes: bytes,
    file_name: str,
) -> Dict[str, Any]:
    """
    POST a PDF to parity-ingestion /v1/ingest/audited-financials.

    Returns the full extraction dict (all IS / BS / CF / notes fields).
    Raises AuditedFinancialsExtractionError on HTTP errors or timeout.
    """
    if not PARITY_INGESTION_URL:
        raise AuditedFinancialsExtractionError(
            "PARITY_INGESTION_URL is not configured"
        )

    url = f"{PARITY_INGESTION_URL}/v1/ingest/audited-financials"
    files = {"file": (file_name, file_bytes, "application/pdf")}

    try:
        with httpx.Client(timeout=httpx.Timeout(300.0)) as client:
            resp = client.post(url, files=files)
    except httpx.TimeoutException as exc:
        raise AuditedFinancialsExtractionError(
            f"Timeout calling parity-ingestion audited-financials: {exc}"
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

    data = resp.json()
    logger.info(
        "[AUDITED CLIENT] Extracted %s FY%s — confidence=%s",
        data.get("company_name"),
        data.get("financial_year"),
        data.get("extraction_confidence"),
    )
    return data
