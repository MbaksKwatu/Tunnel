"""Tests for KCB Online extractor using Buildex 2025 statement."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.extractors.kcb_extractor import detect_kcb_online, extract_kcb_online_pdf
from app.extractors.router import route_extract
from app.normaliser import normalise_all

FIXTURES = Path(__file__).parent / "fixtures" / "buildex"
KCB_PDF = FIXTURES / "kcb_buildex_2025.pdf"

# Summary figures from PDF header (used for totals assertions)
_EXPECTED_TOTAL_IN_CENTS = 4_177_469_160   # KES 41,774,691.60
_EXPECTED_TOTAL_OUT_CENTS = 4_121_043_965  # KES 41,210,439.65


@pytest.mark.skipif(
    not KCB_PDF.exists(),
    reason="KCB Buildex fixture missing — copy to tests/fixtures/buildex/kcb_buildex_2025.pdf",
)
class TestKCBOnlineDetection:
    def test_detect_kcb_online(self):
        assert detect_kcb_online(str(KCB_PDF))

    def test_router_routes_to_kcb_online(self):
        result = route_extract(str(KCB_PDF))
        assert hasattr(result, "extractor_type")
        assert result.extractor_type == "kcb_online_pdf"


@pytest.mark.skipif(
    not KCB_PDF.exists(),
    reason="KCB Buildex fixture missing — copy to tests/fixtures/buildex/kcb_buildex_2025.pdf",
)
class TestKCBOnlineExtraction:
    @pytest.fixture(scope="class")
    def result(self):
        r = extract_kcb_online_pdf(str(KCB_PDF))
        normalise_all(r)
        return r

    def test_row_count_reasonable(self, result):
        # 126-page annual statement; expect 2000+ rows
        assert result.row_count >= 1_800

    def test_extractor_type(self, result):
        assert result.extractor_type == "kcb_online_pdf"

    def test_all_dates_iso_format(self, result):
        iso_pat = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        for t in result.raw_transactions:
            if t.date_raw:
                assert iso_pat.match(t.date_raw), f"Bad date: {t.date_raw!r}"

    def test_dates_within_statement_period(self, result):
        # Statement covers "Last 12 Months" from Jan 30 2025 — may include early-2026 rows
        for t in result.raw_transactions:
            if t.date_raw and len(t.date_raw) == 10:
                year = t.date_raw[:4]
                assert year in ("2025", "2026"), f"Out-of-range date: {t.date_raw}"

    def test_statement_covers_full_year(self, result):
        dates = {t.date_raw for t in result.raw_transactions if t.date_raw}
        assert any(d.startswith("2025-01") for d in dates), "No January 2025 transactions"
        assert any(d.startswith("2025-12") for d in dates), "No December 2025 transactions"

    def test_amounts_are_integers(self, result):
        for t in result.normalised_transactions:
            if t.debit_cents is not None:
                assert isinstance(t.debit_cents, int)
            if t.credit_cents is not None:
                assert isinstance(t.credit_cents, int)
            if t.balance_cents is not None:
                assert isinstance(t.balance_cents, int)

    def test_total_credits_match_pdf_summary(self, result):
        total = sum(n.credit_cents or 0 for n in result.normalised_transactions)
        assert total == _EXPECTED_TOTAL_IN_CENTS, (
            f"Credits mismatch: got {total}, expected {_EXPECTED_TOTAL_IN_CENTS}"
        )

    def test_total_debits_match_pdf_summary(self, result):
        total = sum(n.debit_cents or 0 for n in result.normalised_transactions)
        assert total == _EXPECTED_TOTAL_OUT_CENTS, (
            f"Debits mismatch: got {total}, expected {_EXPECTED_TOTAL_OUT_CENTS}"
        )

    def test_b_fwd_row_has_zero_amount(self, result):
        b_fwd = [t for t in result.raw_transactions if "B/FWD" in (t.description or "").upper()]
        assert len(b_fwd) >= 1, "No B/FWD row found"
        for t in b_fwd:
            n = result.normalised_transactions[t.row_index]
            assert (n.debit_cents or 0) == 0
            assert (n.credit_cents or 0) == 0

    def test_mpesa_transactions_present(self, result):
        mpesa = [t for t in result.raw_transactions if "MPESA" in (t.description or "").upper()]
        assert len(mpesa) >= 10, f"Too few MPESA rows: {len(mpesa)}"

    def test_no_needs_review_above_threshold(self, result):
        nr = [n for n in result.normalised_transactions if n.normalisation_status == "NEEDS_REVIEW"]
        pct = 100 * len(nr) / max(result.row_count, 1)
        assert pct < 5, f"needs_review rate {pct:.1f}% exceeds 5%"

    def test_opening_balance_10074_kes(self, result):
        # PDF header: Balance At Period Start: 10,074.34 KES → 1,007,434 cents
        b_fwd = [t for t in result.raw_transactions if "B/FWD" in (t.description or "").upper()]
        assert b_fwd, "B/FWD row missing"
        n = result.normalised_transactions[b_fwd[0].row_index]
        assert n.balance_cents == 1_007_434, f"Opening balance: {n.balance_cents}"
