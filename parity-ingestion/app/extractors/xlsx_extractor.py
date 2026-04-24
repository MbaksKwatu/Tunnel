"""
XLSX extraction — delegates to app.parsers.xlsx_parser (same logic as backend v1).
"""
from __future__ import annotations

import uuid
from pathlib import Path

from app.models import ExtractionResult
from app.parsers.xlsx_parser import extraction_result_from_xlsx_bytes


def extract_xlsx(file_path: str, *, deal_currency: str = "KES") -> ExtractionResult:
    content = Path(file_path).read_bytes()
    document_id = str(uuid.uuid4())
    result, _ = extraction_result_from_xlsx_bytes(
        content, document_id, deal_currency, file_path
    )
    return result
