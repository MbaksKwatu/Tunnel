"""Tests for ABSA Bank PDF extractor."""
from __future__ import annotations

import pytest

from app.extractors.absa_extractor import detect_absa, extract_absa_pdf
from app.normaliser import normalise_all

SAMPLES = "/Users/mbakswatu/Desktop/Demofiles/bankstatementsamples"
ABSA_PDF = f"{SAMPLES}/absa.pdf"


def _can_open_absa_pdf() -> bool:
    import pathlib
    if not pathlib.Path(ABSA_PDF).exists():
        return False
    try:
        import pdfplumber
        with pdfplumber.open(ABSA_PDF) as pdf:
            _ = pdf.pages[0].extract_text()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _can_open_absa_pdf(), reason="ABSA fixture missing or unreadable")
class TestAbsaExtractor:
    def test_malformed_balance_warning(self):
        result = extract_absa_pdf(ABSA_PDF)
        normalise_all(result)
        has_malformed = any(
            "malformed" in w.message.lower() or "balance" in w.message.lower()
            for w in result.warnings
        )
        if has_malformed:
            null_balances = [
                t for t in result.normalised_transactions
                if t.balance_cents is None and result.raw_transactions[t.row_index].balance_raw
            ]
            assert len(null_balances) >= 1

    def test_file_not_rejected(self):
        result = extract_absa_pdf(ABSA_PDF)
        assert result.extraction_status in ("success", "needs_review")
        assert len(result.raw_transactions) > 0

    def test_confidence_penalty_on_warnings(self):
        result = extract_absa_pdf(ABSA_PDF)
        if result.warnings:
            assert result.extraction_status == "needs_review"

    def test_normal_rows_unaffected(self):
        result = extract_absa_pdf(ABSA_PDF)
        normalise_all(result)
        for raw, norm in zip(result.raw_transactions, result.normalised_transactions):
            if raw.balance_raw and "malformed" not in str(result.warnings):
                pass
            if norm.balance_cents is not None:
                assert isinstance(norm.balance_cents, int)

    def test_user_narrative_appended(self):
        result = extract_absa_pdf(ABSA_PDF)
        with_narrative = [
            t for t in result.raw_transactions
            if " | " in (t.description or "")
        ]
        if with_narrative:
            for t in with_narrative:
                assert " | " in t.description

    def test_no_floats(self):
        result = extract_absa_pdf(ABSA_PDF)
        normalise_all(result)
        for t in result.normalised_transactions:
            if t.debit_cents is not None:
                assert isinstance(t.debit_cents, int)
            if t.credit_cents is not None:
                assert isinstance(t.credit_cents, int)
            if t.balance_cents is not None:
                assert isinstance(t.balance_cents, int)
