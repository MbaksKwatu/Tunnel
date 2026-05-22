"""Tests for KCB Bank PDF extractor."""
from __future__ import annotations

import pytest

from app.extractors.kcb_extractor import detect_kcb, extract_kcb_pdf, parse_kcb_date
from app.normaliser import normalise_all

SAMPLES = "/Users/mbakswatu/Desktop/Demofiles/bankstatementsamples"
KCB_PDF = f"{SAMPLES}/KCB Bank Statement (1).pdf"


def _amount_cents(norm_txn) -> int:
    debit = norm_txn.debit_cents or 0
    credit = norm_txn.credit_cents or 0
    return credit - debit


@pytest.mark.skipif(
    not __import__("pathlib").Path(KCB_PDF).exists(),
    reason="KCB fixture missing",
)
class TestKcbExtractor:
    def test_transaction_count(self):
        result = extract_kcb_pdf(KCB_PDF)
        assert result.row_count >= 45
        assert result.row_count <= 70

    def test_text_month_date(self):
        assert parse_kcb_date("20 JUL 2023") == "2023-07-20"
        assert parse_kcb_date("24 JUL 2023") == "2023-07-24"

    def test_multi_line_description(self):
        result = extract_kcb_pdf(KCB_PDF)
        mobile_rows = [
            t for t in result.raw_transactions
            if "Mobile Money" in (t.description or "") and "MM2305" in (t.description or "")
        ]
        assert len(mobile_rows) >= 1
        for t in mobile_rows:
            assert " " in (t.description or "")

    def test_balance_b_fwd_included(self):
        result = extract_kcb_pdf(KCB_PDF)
        normalise_all(result)
        b_fwd = [t for t in result.raw_transactions if "B/FWD" in (t.description or "").upper()]
        assert len(b_fwd) >= 1
        for t in b_fwd:
            norm = result.normalised_transactions[t.row_index]
            assert _amount_cents(norm) == 0

    def test_balance_at_period_end_excluded(self):
        result = extract_kcb_pdf(KCB_PDF)
        for t in result.raw_transactions:
            assert "BALANCE AT PERIOD END" not in (t.description or "").upper()

    def test_blank_page_no_failure(self):
        result = extract_kcb_pdf(KCB_PDF)
        assert result.extraction_status in ("success", "needs_review")

    def test_page_count_no_exception(self):
        extract_kcb_pdf(KCB_PDF)

    def test_no_floats(self):
        result = extract_kcb_pdf(KCB_PDF)
        normalise_all(result)
        for t in result.normalised_transactions:
            if t.debit_cents is not None:
                assert isinstance(t.debit_cents, int)
            if t.credit_cents is not None:
                assert isinstance(t.credit_cents, int)
            if t.balance_cents is not None:
                assert isinstance(t.balance_cents, int)
