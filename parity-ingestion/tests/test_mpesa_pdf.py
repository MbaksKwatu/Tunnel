"""Tests for M-Pesa PDF extractor."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.extractors.mpesa_pdf_extractor import detect_mpesa_pdf, extract_mpesa_pdf
from app.normaliser import normalise_all

_FIXTURES = Path(__file__).parent / "fixtures"
_MPESA_PDF = _FIXTURES / "mpesa" / "mauca_mpesa.pdf"

pytestmark = pytest.mark.skipif(
    not _MPESA_PDF.exists(),
    reason=f"M-Pesa fixture missing: {_MPESA_PDF.name} — place a real M-Pesa PDF at tests/fixtures/mpesa/",
)


def _amount_cents(norm_txn) -> int:
    debit = norm_txn.debit_cents or 0
    credit = norm_txn.credit_cents or 0
    return credit - debit


@pytest.fixture(scope="module")
def mpesa_result():
    """Extract and normalise once; share across all tests in this module."""
    result = extract_mpesa_pdf(str(_MPESA_PDF))
    normalise_all(result)
    return result


class TestMpesaPdfExtractor:
    def test_detect_mpesa_pdf(self):
        assert detect_mpesa_pdf(str(_MPESA_PDF)) is True

    def test_extraction_success(self, mpesa_result):
        assert mpesa_result.extraction_status in ("success", "needs_review")
        assert mpesa_result.row_count > 0

    def test_date_stripped_no_time(self, mpesa_result):
        for t in mpesa_result.normalised_transactions:
            if t.date:
                assert len(t.date) == 10
                assert " " not in t.date
                assert ":" not in t.date

    def test_paid_in_positive(self, mpesa_result):
        for t in mpesa_result.normalised_transactions:
            if t.credit_cents and t.credit_cents > 0:
                assert _amount_cents(t) > 0

    def test_withdrawn_negative(self, mpesa_result):
        for t in mpesa_result.normalised_transactions:
            if t.debit_cents and t.debit_cents > 0:
                assert _amount_cents(t) < 0

    def test_no_floats(self, mpesa_result):
        for t in mpesa_result.normalised_transactions:
            if t.debit_cents is not None:
                assert isinstance(t.debit_cents, int)
            if t.credit_cents is not None:
                assert isinstance(t.credit_cents, int)
            if t.balance_cents is not None:
                assert isinstance(t.balance_cents, int)

    def test_all_dates_present(self, mpesa_result):
        missing = [t for t in mpesa_result.normalised_transactions if not t.date]
        assert len(missing) == 0

    def test_idempotent_extraction(self):
        """Same file extracted twice produces identical row sequence — determinism guard."""
        r1 = extract_mpesa_pdf(str(_MPESA_PDF))
        r2 = extract_mpesa_pdf(str(_MPESA_PDF))
        assert r1.row_count == r2.row_count
        keys1 = [(t.date_raw, t.description[:30]) for t in r1.raw_transactions]
        keys2 = [(t.date_raw, t.description[:30]) for t in r2.raw_transactions]
        assert keys1 == keys2
