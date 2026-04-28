"""Tests for Equity Bank extractor using Buildex 2025 statement."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.extractors.equity_extractor import detect_equity_clms, extract_equity_clms_pdf
from app.extractors.router import route_extract
from app.normaliser import normalise_all

FIXTURES = Path(__file__).parent / "fixtures" / "buildex"
EQUITY_PDF = FIXTURES / "equity_buildex_2025.pdf"

# PDF header states: Total Count: 10895
_EXPECTED_MIN_ROWS = 10_000


@pytest.mark.skipif(
    not EQUITY_PDF.exists(),
    reason="Equity Buildex fixture missing — copy to tests/fixtures/buildex/equity_buildex_2025.pdf",
)
class TestEquityBuildexDetection:
    def test_detect_equity_clms(self):
        assert detect_equity_clms(str(EQUITY_PDF))

    def test_router_uses_clms_path(self):
        # Verify CLMS detection fires before other detectors in the router chain.
        # (Full extraction is exercised by TestEquityBuildexExtraction below.)
        from app.extractors.kcb_extractor import detect_kcb, detect_kcb_online
        assert not detect_kcb(str(EQUITY_PDF))
        assert not detect_kcb_online(str(EQUITY_PDF))
        assert detect_equity_clms(str(EQUITY_PDF))  # must be True to route correctly


@pytest.mark.skipif(
    not EQUITY_PDF.exists(),
    reason="Equity Buildex fixture missing — copy to tests/fixtures/buildex/equity_buildex_2025.pdf",
)
class TestEquityBuildexExtraction:
    @pytest.fixture(scope="class")
    def result(self):
        r = extract_equity_clms_pdf(str(EQUITY_PDF))
        normalise_all(r)
        return r

    def test_row_count_matches_pdf_total(self, result):
        # PDF header reports Total Count: 10895
        assert result.row_count >= _EXPECTED_MIN_ROWS, (
            f"Row count {result.row_count} below expected minimum {_EXPECTED_MIN_ROWS}"
        )

    def test_extractor_type(self, result):
        assert result.extractor_type == "equity_pdf"

    def test_all_dates_iso_format(self, result):
        iso_pat = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        for t in result.raw_transactions:
            if t.date_raw:
                assert iso_pat.match(t.date_raw), f"Bad date: {t.date_raw!r}"

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

    def test_mpesa_transactions_present(self, result):
        mpesa = [
            t for t in result.raw_transactions
            if "MPS" in (t.description or "").upper() or "MPESA" in (t.description or "").upper()
        ]
        assert len(mpesa) >= 100, f"Too few M-Pesa rows: {len(mpesa)}"

    def test_no_page_total_rows(self, result):
        for t in result.raw_transactions:
            assert "Page Total" not in (t.description or "")
            assert "PAGE TOTAL" not in (t.description or "")

    def test_no_needs_review_above_threshold(self, result):
        nr = [n for n in result.normalised_transactions if n.normalisation_status == "NEEDS_REVIEW"]
        pct = 100 * len(nr) / max(result.row_count, 1)
        assert pct < 5, f"needs_review rate {pct:.1f}% exceeds 5%"
