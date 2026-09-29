"""Tests for the SBM Bank (Kenya) PDF extractor.

Two layers:

  1. Synthetic-statement tests — a small PDF is generated at test time with
     reportlab (skipped if reportlab is absent). It mirrors the real layout
     (wrapped details, 4-line M-Pesa fee bundles, a positive-"Debit"
     reversal bundle, the 3 ref-number shapes, page-break continuation,
     footer on page 2 only) using fabricated names/numbers, so the real
     client statement never has to be committed.

  2. Real-file tests — the actual 90-page Amuriki / GBFund upload. Not
     committed (client PII: names, phone numbers, account number). Point
     SBM_REAL_PDF at it to run; skipped otherwise.
"""
from __future__ import annotations

import os
import pathlib
from decimal import Decimal

import pytest

from app.extractors.router import route_extract
from app.extractors.sbm_extractor import (
    _parse_sbm_date,
    detect_sbm,
    extract_sbm_pdf,
    reconcile_balances,
)
from app.models import RawTransaction
from app.normaliser import normalise_all

REAL_PDF = os.environ.get(
    "SBM_REAL_PDF", "/Users/mbakswatu/Desktop/SBM Bank Statements for Arthur Harry.pdf"
)
_HAS_REAL = pathlib.Path(REAL_PDF).exists()

# ── Unit tests (no fixture required) ─────────────────────────────────────────


class TestParseDate:
    def test_standard(self):
        assert _parse_sbm_date("04-MAR-26") == "2026-03-04"

    def test_december(self):
        assert _parse_sbm_date("31-DEC-25") == "2025-12-31"

    def test_invalid(self):
        assert _parse_sbm_date("2026-06-14T22:00:00.000+01:00") is None
        assert _parse_sbm_date("") is None


def _tx(i, debit="", credit="", balance="0.00"):
    return RawTransaction(
        row_index=i, date_raw="2026-03-04", description="x",
        debit_raw=debit, credit_raw=credit, balance_raw=balance, source_file="x",
    )


class TestReconcile:
    def test_derives_blank_opening(self):
        bad, opening = reconcile_balances([_tx(0, credit="300.00", balance="300.00")], None)
        assert bad == [] and opening == Decimal("0.00")

    def test_flags_break(self):
        rows = [_tx(0, credit="300.00", balance="300.00"), _tx(1, debit="10.00", balance="291.00")]
        bad, _ = reconcile_balances(rows, Decimal(0))
        assert bad == [1]


# ── Synthetic statement ──────────────────────────────────────────────────────

_HEADER = [
    "Printing Date: 15-06-2026",
    "Statement Period: 04-MAR-26 to 2026-06-14T22:00:00.000+01:00",
    "Account Name: TEST TRADING LIMITED Opening Balance:",
    "Account Number: 0000000000001 Total Debits: 600.00",
    "Account Type: BUSINESS PLUS CURRENT ACCOUNT Total Credits: 400,885.80",
    "Currency: KES Uncleared Balance:",
    "Telephone Number: 254700000000 Available Balance: 400,285.80",
]
_COLS = [
    "Transaction Transaction Details Ref Number Instrument Value Date Debit Credit Balance",
    "Date Code",
]
_FOOTER = [
    "Page 2 of 2",
    "SBM Bank (Kenya) Limited is regulated by the Central Bank of Kenya. For any queries on your statement please reach out to our Contact",
    "Centre via e-mail to atyourservice@sbmbank.co.ke or call +254 730 175 000 , +254 709 800 000",
]
_PAGE1_ROWS = [
    "04-MAR-26 Mpesa Deposit 000MPDT260633439 04-MAR-26 0.00 300.00 300.00",
    "UC00AAAAAA UC00AAAAAA -",
    "254700000001 - Jane",
    "Doe",
    "06-MAR-26 Incoming PesaLink Transfer 000PESD260640231 05-MAR-26 0.00 400,000.00 400,300.00",
    "20260305WIFU",
    "/000 TEST + TRADING",
    "06-MAR-26 IB MPESA Withdrawal 003ICMB260650018 06-MAR-26 -1,000.00 0.00 399,300.00",
    "C030613054359055027",
    "254700000000 Uber",
    "06-MAR-26 Safaricom MPESA Charges 003ICMB260650018 06-MAR-26 -5.00 0.00 399,295.00",
    "C030613054359055027",
    "254700000000 Uber",
    "06-MAR-26 Mfukoni MPESA Charges 003ICMB260650018 06-MAR-26 -8.00 0.00 399,287.00",
    "C030613054359055027",
    "254700000000 Uber",
    "06-MAR-26 EXCISE TAX 003ICMB260650018 06-MAR-26 -1.20 0.00 399,285.80",
    "C030613054359055027",
    "254700000000 Uber",
    # Reversal bundle: POSITIVE figures in the Debit column, same ref as the original.
    "07-MAR-26 IB MPESA Withdrawal 003ICMB260650018 07-MAR-26 1,000.00 0.00 400,285.80",
    "C030613054359055027",
    "254700000000 Uber",
    "07-MAR-26 Safaricom MPESA Charges 003ICMB260650018 07-MAR-26 5.00 0.00 400,290.80",
    "07-MAR-26 Mfukoni MPESA Charges 003ICMB260650018 07-MAR-26 8.00 0.00 400,298.80",
    "07-MAR-26 EXCISE TAX 003ICMB260650018 07-MAR-26 1.20 0.00 400,300.00",
]
# Page 2 opens mid-flow: repeated column headers, rows with the odd ref shapes.
_PAGE2_ROWS = [
    "08-MAR-26 Inward Cheque Payment 0003607260760460 000001 08-MAR-26 -300.00 0.00 400,000.00",
    "08-MAR-26 SEARCH FEE 003CSFPKES 00001 08-MAR-26 -300.00 0.00 399,700.00",
    "09-MAR-26 Incoming RTGs 003RTIN261320011 FTC260512L 09-MAR-26 0.00 585.80 400,285.80",
    "FROM SOME PAYER",
]


def _build_pdf(path: pathlib.Path, pages=None) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=A4)
    for lines in pages or (_HEADER + _COLS + _PAGE1_ROWS, _COLS + _PAGE2_ROWS + _FOOTER):
        y = 800
        for ln in lines:
            c.setFont("Helvetica", 7)
            c.drawString(20, y, ln)
            y -= 11
        c.showPage()
    c.save()


@pytest.fixture(scope="module")
def synthetic_pdf(tmp_path_factory):
    pytest.importorskip("reportlab")
    p = tmp_path_factory.mktemp("sbm") / "synthetic_sbm.pdf"
    _build_pdf(p)
    return str(p)


class TestSyntheticStatement:
    def test_detect(self, synthetic_pdf):
        assert detect_sbm(synthetic_pdf) is True

    def test_routes_to_sbm(self, synthetic_pdf):
        assert route_extract(synthetic_pdf).extractor_type == "sbm_pdf"

    def test_row_count_and_status(self, synthetic_pdf):
        r = extract_sbm_pdf(synthetic_pdf)
        assert r.row_count == 13
        assert r.extraction_status == "success", r.warnings
        assert r.currency == "KES"

    def test_running_balance_reconciles(self, synthetic_pdf):
        r = extract_sbm_pdf(synthetic_pdf)
        bad, opening = reconcile_balances(r.raw_transactions, None)
        assert bad == []
        assert opening == Decimal("0.00")
        assert r.raw_transactions[-1].balance_raw == "400285.80"

    def test_wrapped_details_joined(self, synthetic_pdf):
        t = extract_sbm_pdf(synthetic_pdf).raw_transactions[0]
        assert t.description.startswith("Mpesa Deposit UC00AAAAAA UC00AAAAAA - 254700000001 - Jane Doe")
        assert t.date_raw == "2026-03-04"
        assert t.credit_raw == "300.00" and t.debit_raw == ""

    def test_fee_bundle_shares_ref(self, synthetic_pdf):
        tx = extract_sbm_pdf(synthetic_pdf).raw_transactions[2:6]
        assert [t.description.split(" C0306")[0] for t in tx] == [
            "IB MPESA Withdrawal", "Safaricom MPESA Charges", "Mfukoni MPESA Charges", "EXCISE TAX",
        ]
        assert all(t.description.endswith("[ref 003ICMB260650018]") for t in tx)
        assert [t.debit_raw for t in tx] == ["1000.00", "5.00", "8.00", "1.20"]
        assert [t.pattern_hint for t in tx] == ["MPESA_TRANSFER", "BANK_CHARGE", "BANK_CHARGE", "BANK_CHARGE"]

    def test_positive_debit_is_reversal_credit(self, synthetic_pdf):
        tx = extract_sbm_pdf(synthetic_pdf).raw_transactions[6:10]
        assert all(t.debit_raw == "" for t in tx)
        assert [t.credit_raw for t in tx] == ["1000.00", "5.00", "8.00", "1.20"]
        assert all(t.pattern_hint == "REVERSAL_PAIR" for t in tx)

    def test_ref_shapes_and_page_break(self, synthetic_pdf):
        r = extract_sbm_pdf(synthetic_pdf).raw_transactions
        assert [t.description.rsplit("[ref ", 1)[1] for t in r[-3:]] == [
            "0003607260760460 000001]", "003CSFPKES 00001]", "003RTIN261320011 FTC260512L]",
        ]
        assert r[-1].description.startswith("Incoming RTGs FROM SOME PAYER")
        assert r[-1].pattern_hint == "RTGS_TRANSFER"

    def test_normaliser_clean(self, synthetic_pdf):
        n = normalise_all(extract_sbm_pdf(synthetic_pdf))
        assert n.normalisation_warnings == []
        assert n.normalised_transactions[0].date == "2026-03-04"


class TestUnpairedPositiveDebit:
    """A positive Debit figure with no earlier debit of the same ref and amount
    is still money in (the balance proves it) but is NOT labelled a reversal."""

    _ROWS = [
        "04-MAR-26 Mpesa Deposit 000MPDT260633439 04-MAR-26 0.00 300.00 300.00",
        "05-MAR-26 IB MPESA Withdrawal 003ICMB260650018 05-MAR-26 -100.00 0.00 200.00",
        # Same ref, different amount -> no match.
        "06-MAR-26 IB MPESA Withdrawal 003ICMB260650018 06-MAR-26 50.00 0.00 250.00",
        # Ref never seen before -> no match.
        "07-MAR-26 Interest Credit 003INTC260660001 07-MAR-26 25.00 0.00 275.00",
    ]
    @pytest.fixture(scope="class")
    def result(self, tmp_path_factory):
        pytest.importorskip("reportlab")
        hdr = [
            ln.replace("Total Debits: 600.00", "Total Debits: 25.00")
              .replace("Total Credits: 400,885.80", "Total Credits: 300.00")
              .replace("Available Balance: 400,285.80", "Available Balance: 275.00")
            for ln in _HEADER
        ]
        p = tmp_path_factory.mktemp("sbm_unpaired") / "unpaired.pdf"
        _build_pdf(p, pages=[hdr + _COLS + self._ROWS + _FOOTER])
        return extract_sbm_pdf(str(p))

    def test_direction_still_credit_and_balance_reconciles(self, result):
        tx = result.raw_transactions
        assert [t.credit_raw for t in tx[2:]] == ["50.00", "25.00"]
        assert all(t.debit_raw == "" for t in tx[2:])
        assert reconcile_balances(tx, None)[0] == []

    def test_not_labelled_reversal(self, result):
        tx = result.raw_transactions
        assert [t.pattern_hint for t in tx[2:]] == ["UNCLASSIFIED", "UNCLASSIFIED"]
        assert all(t.pattern_hint != "REVERSAL_PAIR" for t in tx)

    def test_warned_and_needs_review(self, result):
        assert result.extraction_status == "needs_review"
        msgs = [w for w in result.warnings if "not labelled as a reversal" in w.message]
        assert [w.row_index for w in msgs] == [2, 3]
        # No other warnings: header totals still reconcile.
        assert len(result.warnings) == 2, result.warnings


class TestNotSbm:
    def test_non_sbm_text_rejected(self, tmp_path):
        pytest.importorskip("reportlab")
        from reportlab.pdfgen import canvas

        p = tmp_path / "other.pdf"
        c = canvas.Canvas(str(p))
        c.drawString(40, 800, "Some Other Bank Statement Date Description Debit Credit Balance")
        c.drawString(40, 780, "Paid via SBM Bank (Kenya) Limited PesaLink")
        c.save()
        assert detect_sbm(str(p)) is False


# ── Real-file tests (Amuriki / GBFund upload, not committed) ─────────────────


@pytest.mark.skipif(not _HAS_REAL, reason="real SBM statement not available (set SBM_REAL_PDF)")
class TestRealStatement:
    @pytest.fixture(scope="class")
    def result(self):
        return extract_sbm_pdf(REAL_PDF)

    def test_detect_and_route(self):
        assert detect_sbm(REAL_PDF) is True

    def test_row_count(self, result):
        assert result.row_count == 1758

    def test_no_warnings(self, result):
        assert result.warnings == [] and result.extraction_status == "success"

    def test_every_running_balance_reconciles(self, result):
        bad, opening = reconcile_balances(result.raw_transactions, None)
        assert bad == []
        assert opening == Decimal("0.00")

    def test_matches_header_totals(self, result):
        tx = result.raw_transactions
        rev = sum((Decimal(t.credit_raw) for t in tx if t.pattern_hint == "REVERSAL_PAIR"), Decimal(0))
        out = sum((Decimal(t.debit_raw) for t in tx if t.debit_raw), Decimal(0))
        cr = sum((Decimal(t.credit_raw) for t in tx if t.credit_raw), Decimal(0)) - rev
        assert out - rev == Decimal("12429504.70")      # header Total Debits (net of reversals)
        assert cr == Decimal("14097700.00")             # header Total Credits
        assert tx[-1].balance_raw == "1668195.30"       # header Available Balance

    def test_reversal_bundle(self, result):
        rev = [t for t in result.raw_transactions if t.pattern_hint == "REVERSAL_PAIR"]
        assert [t.credit_raw for t in rev] == ["1000.00", "5.00", "8.00", "1.20"]
        assert {t.date_raw for t in rev} == {"2026-03-23"}
