"""
XLSX parsing runs on parity-ingestion (GCP). This module re-exports the shared
parser implementation for tests and tooling only — production upload uses
`parse_via_parity_ingestion` and never imports this file.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

_TUNNEL_ROOT = Path(__file__).resolve().parents[3]
_PARITY_INGESTION = _TUNNEL_ROOT / "parity-ingestion"
if _PARITY_INGESTION.is_dir() and str(_PARITY_INGESTION) not in sys.path:
    sys.path.insert(0, str(_PARITY_INGESTION))

from app.parsers.xlsx_parser import (  # noqa: E402
    _is_equity_excel,
    _normalise_equity_excel_columns,
    parse_xlsx as _parse_xlsx_full,
)


def parse_xlsx(
    file_bytes: bytes, document_id: str, deal_currency: str
) -> Tuple[List[Dict[str, Any]], str, str]:
    """Same contract as legacy backend — fourth return value (is_equity) is dropped."""
    rows, raw_hash, currency_detection, _is_eq = _parse_xlsx_full(
        file_bytes, document_id, deal_currency
    )
    return rows, raw_hash, currency_detection


__all__ = ["parse_xlsx", "_is_equity_excel", "_normalise_equity_excel_columns"]
