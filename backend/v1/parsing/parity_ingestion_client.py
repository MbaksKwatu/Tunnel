"""
Client for parity-ingestion microservice.
When PARITY_INGESTION_URL is set, PDFs are sent to parity-ingestion for bank-specific
extraction (KCB, Equity, ABSA, Co-op, M-Pesa, SCB). Falls back to built-in parse_pdf otherwise.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

import httpx

from .common import canonical_hash, compute_txn_id, normalize_descriptor, sort_rows
from .errors import InvalidSchemaError


PARITY_INGESTION_URL = os.getenv("PARITY_INGESTION_URL", "").rstrip("/")


def _parity_result_to_rows(
    result: dict,
    document_id: str,
) -> List[Dict[str, Any]]:
    """Convert parity-ingestion ExtractionResult to backend row format."""
    rows: List[Dict[str, Any]] = []
    normalised = result.get("normalised_transactions") or []

    for n in normalised:
        debit = n.get("debit_cents") or 0
        credit = n.get("credit_cents") or 0
        signed_cents = credit - debit
        if signed_cents == 0:
            continue
        txn_date = n.get("date")
        if not txn_date:
            continue
        desc = n.get("description") or ""
        row_obj: Dict[str, Any] = {
            "txn_date": txn_date,
            "signed_amount_cents": signed_cents,
            "abs_amount_cents": abs(signed_cents),
            "raw_descriptor": desc,
            "parsed_descriptor": desc.strip(),
            "normalized_descriptor": normalize_descriptor(desc),
            "account_id": "default",
        }
        row_obj["txn_id"] = compute_txn_id(row_obj, document_id)
        rows.append(row_obj)

    return rows


def parse_pdf_via_parity_ingestion(
    file_bytes: bytes,
    file_name: str,
    document_id: str,
    deal_currency: str,
) -> Tuple[List[Dict[str, Any]], str, str]:
    """
    POST PDF to parity-ingestion, convert result to backend rows.
    Returns (rows, raw_transaction_hash, currency_detection).
    """
    url = f"{PARITY_INGESTION_URL}/v1/ingest/upload"
    files = {"file": (file_name or "upload.pdf", file_bytes, "application/pdf")}

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(url, files=files)
        if resp.status_code == 415:
            raise InvalidSchemaError(
                resp.json().get("detail", "Bank format not recognised by parity-ingestion.")
            )
        resp.raise_for_status()
        result = resp.json()

    if isinstance(result, dict) and result.get("status") == "UNSUPPORTED_FORMAT":
        raise InvalidSchemaError(
            result.get("message", "Bank format not recognised.")
        )

    rows = _parity_result_to_rows(result, document_id)
    if not rows:
        raise InvalidSchemaError("No valid transactions extracted from PDF")
    rows_sorted = sort_rows(rows)
    raw_hash = canonical_hash(rows_sorted)
    return rows_sorted, raw_hash, "unknown"
