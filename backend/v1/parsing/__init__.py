from typing import Any, Dict, List, Tuple

from .csv_parser import parse_csv
from .errors import InvalidSchemaError, CurrencyMismatchError
from .parity_ingestion_client import PARITY_INGESTION_URL, parse_pdf_via_parity_ingestion
from .pdf_parser import parse_pdf
from .xlsx_parser import parse_xlsx


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
    """
    normalized = (file_type or "").lower()
    if normalized == "xlsx":
        rows, raw_hash, currency_detection = parse_xlsx(file_bytes, document_id, deal_currency)
        return rows, raw_hash, currency_detection, {}
    if normalized == "csv":
        rows, raw_hash, currency_detection = parse_csv(file_bytes, document_id, deal_currency)
        return rows, raw_hash, currency_detection, {}
    if normalized == "pdf":
        if PARITY_INGESTION_URL:
            return parse_pdf_via_parity_ingestion(
                file_bytes, file_name or "upload.pdf", document_id, deal_currency
            )
        rows, raw_hash, currency_detection = parse_pdf(file_bytes, document_id, deal_currency)
        return rows, raw_hash, currency_detection, {}
    raise InvalidSchemaError(f"Unsupported file type: {file_type}")
