"""Tests for Equity Bank PDF extractor."""
from __future__ import annotations

from pathlib import Path

import pdfplumber
import pytest

from app.extractors.equity_extractor import (
    _detect_split_transaction_header,
    _parse_business_txn_line,
    detect_equity,
    extract_equity_pdf,
)
from app.normaliser import normalise_all

SAMPLES = "/Users/mbakswatu/Desktop/Demofiles/bankstatementsamples"
EQUITY_PDF = f"{SAMPLES}/Unlock PDF Equity Unlocked.pdf"
# April 2025: split column header ("Transacti" / "on Date") + split date lines (DD-MM- / YYYY on next lines)
EQUITY_APR_2025 = (
    "/Users/mbakswatu/Desktop/parity/sayuni/2025/pdf/"
    "Sassy Cosmetics - Equity Bank - 1180279761781 - Apr 2025.pdf"
)
EQUITY_FEB_2025 = (
    "/Users/mbakswatu/Desktop/parity/sayuni/2025/pdf/"
    "Sassy Cosmetics - Equity Bank - 1180279761781 - Feb 2025.pdf"
)


def _amount_cents(norm_txn) -> int:
    debit = norm_txn.debit_cents or 0
    credit = norm_txn.credit_cents or 0
    return credit - debit


@pytest.mark.skipif(
    not __import__("pathlib").Path(EQUITY_PDF).exists(),
    reason="Equity fixture missing",
)
class TestEquityExtractor:
    def test_dr_balance_positive_overdrawn(self):
        result = extract_equity_pdf(EQUITY_PDF)
        normalise_all(result)
        overdrawn = [t for t in result.raw_transactions if t.balance_is_overdrawn]
        for t in overdrawn:
            norm = result.normalised_transactions[t.row_index]
            assert norm.balance_cents is not None
            assert norm.balance_cents > 0
            assert isinstance(norm.balance_cents, int)

    def test_hyphen_date_format(self):
        result = extract_equity_pdf(EQUITY_PDF)
        for t in result.raw_transactions:
            if t.date_raw and len(t.date_raw) == 10:
                assert t.date_raw[4] == "-" and t.date_raw[7] == "-"

    def test_opening_balance_zero(self):
        result = extract_equity_pdf(EQUITY_PDF)
        normalise_all(result)
        opening = [
            t for t in result.normalised_transactions
            if "OPENING" in (t.description or "").upper() or "B/FWD" in (t.description or "").upper()
        ]
        if opening:
            for t in opening:
                assert _amount_cents(t) == 0

    def test_page_total_excluded(self):
        result = extract_equity_pdf(EQUITY_PDF)
        for t in result.raw_transactions:
            assert "Page Total" not in (t.description or "")

    def test_truncated_description_no_raise(self):
        result = extract_equity_pdf(EQUITY_PDF)
        assert result.extraction_status in ("success", "needs_review")

    def test_no_floats(self):
        result = extract_equity_pdf(EQUITY_PDF)
        normalise_all(result)
        for t in result.normalised_transactions:
            if t.debit_cents is not None:
                assert isinstance(t.debit_cents, int)
            if t.credit_cents is not None:
                assert isinstance(t.credit_cents, int)
            if t.balance_cents is not None:
                assert isinstance(t.balance_cents, int)


@pytest.mark.skipif(
    not Path(EQUITY_APR_2025).exists(),
    reason="April 2025 Equity PDF fixture missing",
)
class TestEquityApril2025SplitHeader:
    def test_split_transaction_header_detected(self):
        with pdfplumber.open(EQUITY_APR_2025) as pdf:
            lines = pdf.pages[0].extract_text().split("\n")
        assert _detect_split_transaction_header(lines)

    def test_april_2025_extracts_split_date_layout(self):
        """
        PDF header shows Total Search Results: 3190; coordinate-based split-date
        extraction should match that count (line-based path dropped ~904 rows).
        """
        result = extract_equity_pdf(EQUITY_APR_2025)
        assert len(result.raw_transactions) == 3190


def test_business_parser_accepts_single_date_customer_reference_layout():
    line = "01-02-2025 POS SALE REF123 12,345.00 1,234,567.00"
    parsed, bal = _parse_business_txn_line(line, "", previous_balance=130000000)
    assert parsed is not None
    assert parsed["date_raw"] == "01-02-2025"
    assert parsed["money_out"] == "12345.00"
    assert parsed["money_in"] == ""
    assert parsed["balance_raw"] == "1,234,567.00"
    assert "REF123" in parsed["particulars"]
    assert bal == 123456700


@pytest.mark.skipif(
    not Path(EQUITY_FEB_2025).exists(),
    reason="February 2025 Equity PDF fixture missing",
)
def test_february_2025_customer_reference_layout_extracts():
    result = extract_equity_pdf(EQUITY_FEB_2025)
    assert len(result.raw_transactions) == 2673
