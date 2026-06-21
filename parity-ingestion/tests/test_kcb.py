"""Tests for KCB Bank PDF extractor."""
from __future__ import annotations

import pytest

from app.extractors.kcb_extractor import detect_kcb, extract_kcb_pdf, parse_kcb_date
from app.harness import _check_balance_reconciliation
from app.normaliser import normalise_all

SAMPLES = "/Users/mbakswatu/Documents/Parity/Pilot & Demo/Bank Statement Samples"
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
        """The literal phrase check alone is insufficient — pdfplumber
        sometimes splits "END" across row-groups (e.g. "...PERIOD E" +
        "ND:"), so this phrase never appears verbatim even when the footer
        text leaks into a transaction's description. Check the fragment
        that's actually present on a single row instead (PAR-26)."""
        result = extract_kcb_pdf(KCB_PDF)
        for t in result.raw_transactions:
            assert "BALANCE AT PERIOD" not in (t.description or "").upper()

    def test_period_summary_totals_not_merged_into_last_transaction(self):
        """Regression test for PAR-26: the statement's aggregate money-out/
        money-in/balance totals row (printed right after "Balance at Period
        End") was being merged into the last real transaction's credit,
        inflating it by the whole statement's total credits (~1.37M KES in
        this fixture). Confirm the last row's amount is a real transaction
        amount, not the aggregate total, and that reconciliation holds."""
        result = extract_kcb_pdf(KCB_PDF)
        assert _check_balance_reconciliation(result) is True
        last = result.raw_transactions[-1]
        # The real last transaction in this statement is a 10,891.00 debit —
        # the bug instead produced an empty debit and a 1,366,739.75 credit.
        assert last.credit_raw == ""
        assert last.debit_raw != ""

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
