from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import load_workbook

from v1.parsing.xlsx_parser import (
    _is_equity_excel,
    _normalise_equity_excel_columns,
    parse_xlsx,
)

JAN_XLSX = Path(
    "/Users/mbakswatu/Desktop/parity/sayuni/2025/Excel/"
    "Sassy Cosmetics - Equity Bank - 1180279761781 - Jan 2025.xlsx"
)
FEB_XLSX = Path(
    "/Users/mbakswatu/Desktop/parity/sayuni/2025/Excel/"
    "Sassy Cosmetics - Equity Bank - 1180279761781 - Feb 2025.xlsx"
)


def _load_header(path: Path):
    wb = load_workbook(path, data_only=True)
    ws = wb.worksheets[0]
    return [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]


@pytest.mark.skipif(not JAN_XLSX.exists(), reason="January Equity Excel fixture missing")
def test_equity_jan_detection_and_parse():
    header = _load_header(JAN_XLSX)
    assert _is_equity_excel(header) is True
    mapping = _normalise_equity_excel_columns(header)
    for col in ("date", "description", "debit", "credit", "balance"):
        assert col in mapping

    rows, _, _ = parse_xlsx(JAN_XLSX.read_bytes(), "doc-jan", "KES")
    # Fixture currently yields 2677 transaction rows after skipping footer rows.
    assert len(rows) == 2677

    signed = [r["signed_amount_cents"] for r in rows]
    assert any(v > 0 for v in signed)
    assert any(v < 0 for v in signed)
    assert all("txn_date" in r and "normalized_descriptor" in r for r in rows[:3])


@pytest.mark.skipif(not FEB_XLSX.exists(), reason="February Equity Excel fixture missing")
def test_equity_feb_detection_and_parse():
    header = _load_header(FEB_XLSX)
    assert _is_equity_excel(header) is True
    mapping = _normalise_equity_excel_columns(header)
    for col in ("date", "description", "debit", "credit", "balance"):
        assert col in mapping

    rows, _, _ = parse_xlsx(FEB_XLSX.read_bytes(), "doc-feb", "KES")
    assert len(rows) > 0
