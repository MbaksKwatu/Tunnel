from __future__ import annotations

import io
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

from v1.parsing.xlsx_parser import (
    _is_equity_excel,
    _normalise_equity_excel_columns,
    parse_xlsx,
    scan_equity_excel_header,
)
import datetime

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


def _december_2025_layout_workbook_bytes() -> bytes:
    """Synthetic December 2025 Equity layout: preamble, header row 7, 3030 data rows, 2 footer rows."""
    wb = Workbook()
    ws = wb.active
    for _ in range(5):
        ws.append(["preamble", "", "", "", ""])
    ws.append(["", "", "", "", "Total Count: 3030"])
    header = [
        "Transaction Date",
        "Value Date",
        None,
        "Narrative",
        "Extra",
        None,
        "Debit",
        "Credit",
        "Running Balance",
        "Transaction Reference",
        "Customer Reference",
        "Cheque Number",
        "Remarks 1",
        "Remarks 2",
    ]
    ws.append(header)
    for i in range(3030):
        debit = "100.00" if i % 2 == 0 else None
        credit = None if i % 2 == 0 else "50.00"
        ws.append(
            [
                datetime.datetime(2025, 12, 15, 0, 0),
                "",
                "",
                f"Txn {i}",
                "",
                "",
                debit,
                credit,
                f"{1000 + i}.00",
                f"TR{i}",
                f"CR{i}",
                "",
                "",
                "",
            ]
        )
    # Bank footer summary rows after last transaction — no date column; must not be parsed as txns.
    ws.append(
        [
            None,
            "",
            "",
            "Total Credits",
            "",
            "",
            None,
            "999999.00",
            "",
            "",
            "",
            "",
            "",
            "",
        ]
    )
    ws.append(
        [
            None,
            "",
            "",
            "Total Debits",
            "",
            "",
            "888888.00",
            None,
            "",
            "",
            "",
            "",
            "",
            "",
        ]
    )
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_december_2025_equity_layout_preamble_header_and_parse():
    raw = _december_2025_layout_workbook_bytes()
    wb = load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
    ws = wb.active

    assert ws.cell(row=6, column=5).value == "Total Count: 3030"

    idx, header_row = scan_equity_excel_header(ws)
    assert idx == 6
    assert header_row.count(None) == 2
    assert _is_equity_excel(header_row) is True

    mapping = _normalise_equity_excel_columns(header_row)
    assert mapping["date"] == 0
    assert mapping["description"] == 3
    assert mapping["debit"] == 6
    assert mapping["credit"] == 7
    assert mapping["balance"] == 8
    assert mapping["reference"] == 9

    wb.close()

    rows, _, _ = parse_xlsx(raw, "doc-dec-2025", "KES")
    assert len(rows) == 3030
