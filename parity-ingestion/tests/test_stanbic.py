"""Tests for Stanbic Bank Kenya PDF extractor.

Fixture: copy the real PDF to tests/fixtures/stanbic_zuridi.pdf
If the fixture is absent the full class is skipped.

Unit tests for pure helpers (date parsing) always run.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.extractors.stanbic_extractor import (
    _parse_date,
    _join_amount_parts,
    _detect_currency_from_ocr,
    detect_stanbic,
    extract_stanbic_pdf,
)

# ── Fixture path ──────────────────────────────────────────────────────────────
STANBIC_PDF = Path(__file__).parent / "fixtures" / "stanbic_zuridi.pdf"

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ── Unit tests (no fixture required) ─────────────────────────────────────────

class TestParseDateUnit:
    def test_standard(self):
        assert _parse_date("23 AUG 23") == "2023-08-23"

    def test_single_digit_day(self):
        assert _parse_date("1 JAN 24") == "2024-01-01"

    def test_case_insensitive(self):
        assert _parse_date("17 aug 23") == "2023-08-17"

    def test_all_months(self):
        months = [
            ("JAN", 1), ("FEB", 2), ("MAR", 3), ("APR", 4),
            ("MAY", 5), ("JUN", 6), ("JUL", 7), ("AUG", 8),
            ("SEP", 9), ("OCT", 10), ("NOV", 11), ("DEC", 12),
        ]
        for abbr, num in months:
            result = _parse_date(f"15 {abbr} 23")
            assert result == f"2023-{num:02d}-15", f"Failed for {abbr}"

    def test_returns_none_for_garbage(self):
        assert _parse_date("not a date") is None
        assert _parse_date("BALANCE BROUGHT FORWARD") is None
        assert _parse_date("") is None

    def test_two_digit_year_expansion(self):
        # years < 50 → 2000+
        assert _parse_date("01 JUL 23").startswith("2023")
        assert _parse_date("08 JAN 25").startswith("2025")


class TestJoinAmountPartsUnit:
    def test_single_full_amount(self):
        assert _join_amount_parts(["449,458.00CR"]) == "449,458.00CR"

    def test_two_part_split(self):
        assert _join_amount_parts(["449,", "458.00CR"]) == "449,458.00CR"

    def test_three_part_split(self):
        assert _join_amount_parts(["9,509,", "218.00CR"]) == "9,509,218.00CR"

    def test_truncated_decimal(self):
        # OCR sometimes clips cents: "250,000." → fix to "250,000.00"
        result = _join_amount_parts(["250,000."])
        assert result == "250,000.00"

    def test_empty(self):
        assert _join_amount_parts([]) == ""

    def test_plain_debit(self):
        assert _join_amount_parts(["40.00"]) == "40.00"

    def test_lowercase_cr(self):
        # OCR may produce "cR" instead of "CR"
        result = _join_amount_parts(["449,", "458.00cR"])
        assert result.upper() == "449,458.00CR"


# ── Integration tests (require fixture) ──────────────────────────────────────

@pytest.mark.skipif(
    not STANBIC_PDF.exists(),
    reason=f"Stanbic fixture missing — copy PDF to {STANBIC_PDF}",
)
class TestStanbicExtractor:

    @pytest.fixture(scope="class")
    def result(self):
        return extract_stanbic_pdf(str(STANBIC_PDF))

    def test_detection(self):
        assert detect_stanbic(str(STANBIC_PDF))

    def test_extractor_type(self, result):
        assert result.extractor_type == "stanbic_pdf"

    def test_currency_kes(self, result):
        assert result.currency == "KES"

    def test_transaction_count_in_range(self, result):
        # 80-page statement; expect at least 50 and at most 2000 transactions.
        assert 50 <= result.row_count <= 2000, (
            f"Unexpected row_count={result.row_count}"
        )

    def test_extraction_status(self, result):
        assert result.extraction_status in ("success", "needs_review")

    def test_all_dates_iso_format(self, result):
        for txn in result.raw_transactions:
            if txn.date_raw:
                assert _ISO_DATE.match(txn.date_raw), (
                    f"row {txn.row_index}: bad date {txn.date_raw!r}"
                )

    def test_no_float_contamination(self, result):
        for txn in result.raw_transactions:
            assert isinstance(txn.debit_raw,   str), f"debit not str at row {txn.row_index}"
            assert isinstance(txn.credit_raw,  str), f"credit not str at row {txn.row_index}"
            assert isinstance(txn.balance_raw, str), f"balance not str at row {txn.row_index}"

    def test_b_fwd_amounts_zeroed(self, result):
        bfwd = [
            t for t in result.raw_transactions
            if "BALANCE BROUGHT FORWARD" in (t.description or "").upper()
        ]
        for txn in bfwd:
            assert txn.debit_raw in ("", "0.00", "0"), (
                f"B/FWD debit not zeroed: {txn.debit_raw!r}"
            )
            assert txn.credit_raw in ("", "0.00", "0"), (
                f"B/FWD credit not zeroed: {txn.credit_raw!r}"
            )

    def test_cr_suffix_present_on_most_balances(self, result):
        # Zuridi is a credit-balance account; nearly all balances carry CR.
        non_empty = [t for t in result.raw_transactions if t.balance_raw]
        cr_count  = sum(1 for t in non_empty if t.balance_raw.upper().endswith("CR"))
        ratio = cr_count / len(non_empty) if non_empty else 0
        assert ratio > 0.5, (
            f"Expected >50 % of balances to end with CR, got {ratio:.0%}"
        )

    def test_no_negative_row_index(self, result):
        for txn in result.raw_transactions:
            assert txn.row_index >= 0

    def test_row_indexes_unique(self, result):
        idxs = [t.row_index for t in result.raw_transactions]
        assert len(idxs) == len(set(idxs)), "Duplicate row_index values found"

    def test_descriptions_non_empty(self, result):
        # At least 90 % of transactions should have a description.
        non_empty = sum(1 for t in result.raw_transactions if t.description.strip())
        ratio = non_empty / result.row_count if result.row_count else 0
        assert ratio > 0.90, (
            f"Too many blank descriptions: {ratio:.0%} non-empty"
        )

    def test_extraction_confidence_range(self, result):
        for txn in result.raw_transactions:
            assert 0.0 < txn.extraction_confidence <= 1.0


# ── Currency detection unit tests (no fixture required) ──────────────────────

class TestCurrencyDetection:

    def test_kes_from_currency_label(self):
        assert _detect_currency_from_ocr("... Customer No 1629757 Currency KES Statement ...") == "KES"

    def test_usd_from_currency_label(self):
        assert _detect_currency_from_ocr("... Customer No 1629757 Currency USD Statement ...") == "USD"

    def test_eur_from_currency_label(self):
        assert _detect_currency_from_ocr("... Currency EUR ...") == "EUR"

    def test_case_insensitive_label(self):
        assert _detect_currency_from_ocr("currency usd") == "USD"

    def test_usd_fallback_bare_token(self):
        # No "Currency" label, but "USD" appears in the text
        assert _detect_currency_from_ocr("Account 0100012065846 USD balance") == "USD"

    def test_default_to_kes_when_no_signal(self):
        assert _detect_currency_from_ocr("some random text with no currency marker") == "KES"

    def test_kes_wins_over_bare_usd_when_label_present(self):
        # Explicit "Currency KES" beats any incidental "USD" mention
        assert _detect_currency_from_ocr("Currency KES ... Swift USD payment") == "KES"


# ── USD account integration tests (require USD fixture) ──────────────────────

STANBIC_USD_PDF = Path(__file__).parent / "fixtures" / "stanbic_zuridi_usd.pdf"


@pytest.mark.skipif(
    not STANBIC_USD_PDF.exists(),
    reason=f"USD fixture missing — copy PDF to {STANBIC_USD_PDF}",
)
class TestStanbicUSD:

    @pytest.fixture(scope="class")
    def result(self):
        return extract_stanbic_pdf(str(STANBIC_USD_PDF))

    def test_detection(self):
        assert detect_stanbic(str(STANBIC_USD_PDF))

    def test_currency_usd(self, result):
        assert result.currency == "USD", (
            f"Expected currency=USD, got {result.currency!r}"
        )

    def test_extractor_type(self, result):
        assert result.extractor_type == "stanbic_pdf"

    def test_transaction_count_in_range(self, result):
        assert 50 <= result.row_count <= 3000, (
            f"Unexpected row_count={result.row_count}"
        )

    def test_extraction_status(self, result):
        assert result.extraction_status in ("success", "needs_review")

    def test_all_dates_iso_format(self, result):
        for txn in result.raw_transactions:
            if txn.date_raw:
                assert _ISO_DATE.match(txn.date_raw), (
                    f"row {txn.row_index}: bad date {txn.date_raw!r}"
                )

    def test_no_float_contamination(self, result):
        for txn in result.raw_transactions:
            assert isinstance(txn.debit_raw,   str)
            assert isinstance(txn.credit_raw,  str)
            assert isinstance(txn.balance_raw, str)

    def test_b_fwd_amounts_zeroed(self, result):
        bfwd = [
            t for t in result.raw_transactions
            if "BALANCE BROUGHT FORWARD" in (t.description or "").upper()
        ]
        for txn in bfwd:
            assert txn.debit_raw  in ("", "0.00", "0")
            assert txn.credit_raw in ("", "0.00", "0")

    def test_cr_suffix_on_most_balances(self, result):
        non_empty = [t for t in result.raw_transactions if t.balance_raw]
        cr_count  = sum(1 for t in non_empty if t.balance_raw.upper().endswith("CR"))
        ratio = cr_count / len(non_empty) if non_empty else 0
        assert ratio > 0.5, f"Expected >50 % CR balances, got {ratio:.0%}"

    def test_row_indexes_unique(self, result):
        idxs = [t.row_index for t in result.raw_transactions]
        assert len(idxs) == len(set(idxs)), "Duplicate row_index values found"
