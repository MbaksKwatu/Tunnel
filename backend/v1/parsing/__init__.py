from typing import Any, Dict, List, Tuple

from .csv_parser import parse_csv
from .errors import InvalidSchemaError, CurrencyMismatchError
from .pdf_parser import parse_pdf
from .xlsx_parser import parse_xlsx


def parse_file(file_bytes: bytes, file_type: str, document_id: str, deal_currency: str) -> Tuple[List[Dict[str, Any]], str, str]:
    """
    Returns (rows, raw_transaction_hash, currency_detection_flag)
    """
    normalized = (file_type or "").lower()
    if normalized == "xlsx":
        return parse_xlsx(file_bytes, document_id, deal_currency)
    if normalized == "csv":
        return parse_csv(file_bytes, document_id, deal_currency)
    if normalized == "pdf":
        return parse_pdf(file_bytes, document_id, deal_currency)
    raise InvalidSchemaError(f"Unsupported file type: {file_type}")
