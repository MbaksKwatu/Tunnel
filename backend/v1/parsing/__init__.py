from typing import Any, Dict, List, Tuple

from .csv_parser import parse_csv
from .errors import InvalidSchemaError, CurrencyMismatchError
from .parity_ingestion_client import PARITY_INGESTION_URL, parse_via_parity_ingestion


def parse_file(
    file_bytes: bytes,
    file_type: str,
    document_id: str,
    deal_currency: str,
    file_name: str = "",
) -> Tuple[List[Dict[str, Any]], str, str, Dict[str, Any]]:
    """
    Returns (rows, raw_transaction_hash, currency_detection_flag, analytics).
    analytics is {} for non-parity parsers.
    PDF and XLSX are parsed via parity-ingestion when PARITY_INGESTION_URL is set.
    """
    normalized = (file_type or "").lower()
    if normalized == "csv":
        rows, raw_hash, currency_detection = parse_csv(file_bytes, document_id, deal_currency)
        return rows, raw_hash, currency_detection, {}
    if normalized in ("xlsx", "pdf"):
        if not PARITY_INGESTION_URL:
            raise RuntimeError("PARITY_INGESTION_URL not set — cannot parse PDF/XLSX without parity-ingestion")
        default_name = "upload.pdf" if normalized == "pdf" else "upload.xlsx"
        return parse_via_parity_ingestion(
            file_bytes, file_name or default_name, document_id, deal_currency
        )
    raise InvalidSchemaError(f"Unsupported file type: {file_type}")
