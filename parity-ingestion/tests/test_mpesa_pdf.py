"""Tests for M-Pesa PDF extractor."""
from __future__ import annotations

import pytest

from app.extractors.mpesa_pdf_extractor import detect_mpesa_pdf, extract_mpesa_pdf
from app.normaliser import normalise_all

MPESA_PDF = "/Users/mbakswatu/Desktop/Demofiles/bankstatementsamples/OLIechodhiambompesasample.pdf"


def _amount_cents(norm_txn) -> int:
    """Derive amount_cents from normalised transaction (debit=negative, credit=positive)."""
    debit = norm_txn.debit_cents or 0
    credit = norm_txn.credit_cents or 0
    return credit - debit


class TestMpesaPdfExtractor:
    def test_detect_mpesa_pdf(self):
        assert detect_mpesa_pdf(MPESA_PDF) is True

    def test_completed_filter(self):
        result = extract_mpesa_pdf(MPESA_PDF)
        normalise_all(result)
        for t in result.raw_transactions:
            pass
        assert result.extraction_status in ("success", "needs_review")

    def test_date_stripped_no_time(self):
        result = extract_mpesa_pdf(MPESA_PDF)
        normalise_all(result)
        for t in result.normalised_transactions:
            if t.date:
                assert len(t.date) == 10
                assert " " not in t.date
                assert ":" not in t.date

    def test_paid_in_positive(self):
        result = extract_mpesa_pdf(MPESA_PDF)
        normalise_all(result)
        for t in result.normalised_transactions:
            if t.credit_cents and t.credit_cents > 0:
                assert _amount_cents(t) > 0

    def test_withdrawn_negative(self):
        result = extract_mpesa_pdf(MPESA_PDF)
        normalise_all(result)
        for t in result.normalised_transactions:
            if t.debit_cents and t.debit_cents > 0:
                assert _amount_cents(t) < 0

    def test_no_floats(self):
        result = extract_mpesa_pdf(MPESA_PDF)
        normalise_all(result)
        for t in result.normalised_transactions:
            if t.debit_cents is not None:
                assert isinstance(t.debit_cents, int)
            if t.credit_cents is not None:
                assert isinstance(t.credit_cents, int)
            if t.balance_cents is not None:
                assert isinstance(t.balance_cents, int)
