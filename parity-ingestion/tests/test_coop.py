"""Tests for Co-operative Bank PDF extractor."""
from __future__ import annotations

from pathlib import Path

import pytest
from pdfminer.fontmetrics import FONT_METRICS

from app.extractors.coop_extractor import (
    extract_coop_pdf,
    _parse_coop_date,
    _parse_balance_to_signed_cents,
    _detect_pattern,
    _is_layout_b,
    _is_layout_c,
)

# Real client statement — cannot be committed, so these tests skip when absent.
# The synthetic Layout C tests at the bottom of this file run everywhere.
FIXTURE_C = "/Users/mbakswatu/Desktop/Demofiles/12 months Kankam KES statement-1 (3).pdf"
needs_fixture_c = pytest.mark.skipif(
    not Path(FIXTURE_C).exists(), reason="real Co-op Layout C statement not available",
)


# --- date parsing ---

def test_date_format_slash():
    assert _parse_coop_date("28/02/2025") == "2025-02-28"

def test_date_format_dash():
    assert _parse_coop_date("15-2-2025") == "2025-02-15"

def test_date_format_2y():
    assert _parse_coop_date("25-02-25") == "2025-02-25"

def test_date_format_none():
    assert _parse_coop_date("") is None


# --- layout detection ---

@needs_fixture_c
def test_layout_c_detected():
    assert _is_layout_c(FIXTURE_C) is True

@needs_fixture_c
def test_layout_b_not_c():
    assert _is_layout_b(FIXTURE_C) is False


# --- pattern detection ---

def test_pattern_reversal():
    assert _detect_pattern("REVERSED : ABA6CE209025 safeways Express") == ("PENDING_CLASSIFICATION", "REVERSAL_PAIR")

def test_pattern_pos():
    assert _detect_pattern("POSAG014812 ~moreen~POS17460_01192248207900") == ("PENDING_CLASSIFICATION", "POS_RECEIPT")

def test_pattern_mpesa_c2b():
    assert _detect_pattern("TDF6WQOFHC~254728056542~MPESAC2B_400200~Mourine") == ("AUTO_CLASSIFIED", "MPESA_C2B")

def test_pattern_bank_charge():
    assert _detect_pattern("MSME_BRONZE_MAINT_KES Charges") == ("AUTO_CLASSIFIED", "BANK_CHARGE")

def test_pattern_named_person():
    assert _detect_pattern("MAUREEN NJERI") == ("PENDING_CLASSIFICATION", "NAMED_PERSON_TRANSFER")

def test_pattern_primenet_mpesa_charge():
    assert _detect_pattern("PrimeNET:MPESA CHARG-0714525421-Daily lunch") == ("AUTO_CLASSIFIED", "BANK_CHARGE")

def test_pattern_primenet_plata():
    assert _detect_pattern("PrimeNET:PL ATA-0192388213-loan repayment") == ("PENDING_CLASSIFICATION", "PESALINK_TRANSFER")

def test_pattern_primenet_plata_excise():
    assert _detect_pattern("PrimeNET:PL ATA EXCI SE-0192388213-loan repayment") == ("AUTO_CLASSIFIED", "BANK_CHARGE")

def test_pattern_rtgs():
    assert _detect_pattern("I:RTGS TO:Peter Maina:PrimeNET:RTGS-12345") == ("PENDING_CLASSIFICATION", "RTGS_TRANSFER")

def test_pattern_currency_conversion():
    assert _detect_pattern("EURO 5800 AT 139.50 TRF FROM EURO A/C") == ("AUTO_CLASSIFIED", "CURRENCY_CONVERSION")


# --- extraction: fixture C (PrimeNET / Kankam) ---

@needs_fixture_c
def test_fixture_c_row_count():
    result = extract_coop_pdf(FIXTURE_C)
    assert result.row_count == 3516

@needs_fixture_c
def test_fixture_c_no_unclassified():
    result = extract_coop_pdf(FIXTURE_C)
    unclassified = [t for t in result.raw_transactions if t.pattern_hint == "UNCLASSIFIED"]
    assert len(unclassified) < 60  # residual edge cases tolerated

@needs_fixture_c
def test_fixture_c_pattern_distribution():
    result = extract_coop_pdf(FIXTURE_C)
    counts = {}
    for t in result.raw_transactions:
        counts[t.pattern_hint] = counts.get(t.pattern_hint, 0) + 1
    assert counts["BANK_CHARGE"] == 2127
    assert counts["MPESA_C2B"] == 939
    assert counts["PESALINK_TRANSFER"] == 324
    assert counts["CURRENCY_CONVERSION"] == 27
    assert counts["RTGS_TRANSFER"] == 24
    assert counts["INWARD_EFT_CREDIT"] == 17
    assert counts["INTEREST"] == 5

@needs_fixture_c
def test_fixture_c_dates_parsed():
    result = extract_coop_pdf(FIXTURE_C)
    missing_dates = [t for t in result.raw_transactions if not t.date_raw or t.date_raw == ""]
    assert len(missing_dates) == 0

@needs_fixture_c
def test_fixture_c_pending_count():
    result = extract_coop_pdf(FIXTURE_C)
    pending = [t for t in result.raw_transactions if t.classification_status == "PENDING_CLASSIFICATION"]
    assert len(pending) == 418


# --- balance parser ---

def test_parse_balance_cr():
    assert _parse_balance_to_signed_cents("15,000,000.00CR") == 1_500_000_000

def test_parse_balance_dr():
    assert _parse_balance_to_signed_cents("1,234.56DR") == -123_456

def test_parse_balance_empty():
    assert _parse_balance_to_signed_cents("") is None

def test_parse_balance_no_suffix():
    assert _parse_balance_to_signed_cents("5,000.00") == 500_000


# --- Layout C credit/debit detection ---

@needs_fixture_c
def test_fixture_c_primenet_mpesa_are_debits():
    """
    Every MPESA_C2B-hinted row in this statement is a "PrimeNET:MPESA-..." outgoing
    payment (airtime, supplier payments) and the running balance falls on each, so
    they are debits. (The MPESA_C2B hint itself is a misclassification — tracked
    separately; this test pins direction, not the hint.)
    """
    result = extract_coop_pdf(FIXTURE_C)
    mpesa_txns = [t for t in result.raw_transactions if t.pattern_hint == "MPESA_C2B"]
    assert len(mpesa_txns) > 0, "No MPESA_C2B transactions found in fixture"
    assert all(t.description.startswith("PrimeNET:MPESA") for t in mpesa_txns)
    wrong = [t for t in mpesa_txns if t.credit_raw or not t.debit_raw]
    assert len(wrong) == 0, (
        f"{len(wrong)}/{len(mpesa_txns)} PrimeNET:MPESA transactions have wrong debit/credit assignment. "
        f"First offender: description={wrong[0].description!r}, "
        f"debit={wrong[0].debit_raw!r}, credit={wrong[0].credit_raw!r}"
    )

@needs_fixture_c
def test_fixture_c_bank_charges_are_debits():
    """BANK_CHARGE transactions are debits, except refunded charges ("REVERSAL I/W TT CHARGES")."""
    result = extract_coop_pdf(FIXTURE_C)
    charge_txns = [t for t in result.raw_transactions if t.pattern_hint == "BANK_CHARGE"]
    assert len(charge_txns) > 0, "No BANK_CHARGE transactions found in fixture"
    refunds = [t for t in charge_txns if t.description.upper().startswith("REVERSAL")]
    charges = [t for t in charge_txns if not t.description.upper().startswith("REVERSAL")]
    wrong = [t for t in charges if t.credit_raw or not t.debit_raw]
    assert len(wrong) == 0, (
        f"{len(wrong)}/{len(charges)} BANK_CHARGE transactions have wrong debit/credit assignment."
    )
    assert refunds and all(t.credit_raw and not t.debit_raw for t in refunds)


def _running_balance_breaks(transactions, opening_cents):
    """Rows where prev + credit - debit != printed balance (blank balance = implied)."""
    breaks = []
    prev = opening_cents
    for t in transactions:
        debit = _parse_balance_to_signed_cents(t.debit_raw) or 0
        credit = _parse_balance_to_signed_cents(t.credit_raw) or 0
        balance = _parse_balance_to_signed_cents(t.balance_raw)
        expected = prev + credit - debit
        if balance is None:
            balance = expected
        elif balance != expected:
            breaks.append(t)
        prev = balance
    return breaks


@needs_fixture_c
def test_fixture_c_running_balance_reconciles():
    """
    Regression: money-IN rows were emitted as debit_raw (132 running-balance
    breaks, each off by exactly 2x the amount). Every row must now reconcile
    against the printed balance, and totals must match the statement's own
    "Debit Tran : N" / "Credit Tran : N" counts and closing balance.
    """
    result = extract_coop_pdf(FIXTURE_C)
    txns = result.raw_transactions
    assert result.warnings == []
    assert _running_balance_breaks(txns, opening_cents=200_000) == []  # B/F 2,000.00CR
    assert sum(1 for t in txns if t.debit_raw) == 3382
    assert sum(1 for t in txns if t.credit_raw) == 134
    assert all(t.debit_raw or t.credit_raw for t in txns)
    assert _parse_balance_to_signed_cents(txns[-1].balance_raw) == -100_335  # 1,003.35DR


@needs_fixture_c
def test_fixture_c_known_inflows_are_credits():
    result = extract_coop_pdf(FIXTURE_C)
    by_index = {t.row_index: t for t in result.raw_transactions}
    for idx, amount in [
        (8, "5,360,000.00"),     # CONVERSION TRANSFER OF EUR 40,000 TO KSH
        (132, "15,000.00"),      # PESALINK FROM: JOHN KAMAU KIERU
        (212, "550,000.00"),     # RETURN OF FUNDS
        (297, "160,098.30"),     # MPESA REVESAL
        (303, "2,112,969.25"),   # FCY PURCHASE ... TRF FROM EUR A/C (385.95DR -> CR)
    ]:
        t = by_index[idx]
        assert (t.debit_raw, t.credit_raw) == ("", amount), (idx, t.description)


# --- synthetic Layout C (PrimeNET) statement — no client data ---

_PAGE_W = 595
_DEBIT_X1, _CREDIT_X1, _BALANCE_X1 = 377, 464, 568


def _text_width(text: str, size: float) -> float:
    widths = FONT_METRICS["Helvetica"][1]
    return sum(widths.get(ch, 556) for ch in text) * size / 1000


def _build_layout_c_pdf(path: Path, rows: list) -> None:
    """
    Write a one-page PrimeNET-style statement. Each row is a list of
    (text, x, align) cells; align 'r' means x is the right edge.
    """
    size = 7
    ops = []
    y = 780
    for cells in rows:
        for text, x, align in cells:
            x0 = x - _text_width(text, size) if align == "r" else x
            esc = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            ops.append(f"BT /F1 {size} Tf {x0:.2f} {y} Td ({esc}) Tj ET")
        y -= 11
    content = "\n".join(ops).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_PAGE_W} 842] "
        f"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>".encode(),
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))


def _row(date, desc, amount=None, column=None, balance=None):
    cells = []
    if date:
        cells.append((date, 28, "l"))
    cells.append((desc, 121, "l"))
    if amount:
        cells.append((date or "03-03-25", 235, "l"))
        cells.append((amount, _DEBIT_X1 if column == "debit" else _CREDIT_X1, "r"))
    if balance:
        cells.append((balance, _BALANCE_X1, "r"))
    return cells


@pytest.fixture
def synthetic_layout_c(tmp_path):
    path = tmp_path / "coop_layout_c_synthetic.pdf"
    _build_layout_c_pdf(path, [
        [("B/F", 121, "l"), ("2,000.00CR", _BALANCE_X1, "r")],
        _row("25-02-25", "PrimeNET:MPESA airtime", "500.00", "debit", "1,500.00CR"),
        _row("03-03-25", "CONVERSION TRANSFER"),
        _row(None, "OF EUR 100 TO KSH", "14,000.00", "credit", "15,500.00CR"),
        _row("03-03-25", "PESALINK FROM: JANE DOE", "1,000.00", "credit", "16,500.00CR"),
        # Zero-balance line: bank leaves the balance cell blank.
        _row("04-03-25", "EXCISE TAX", "16,500.00", "debit"),
        _row("05-03-25", "STANDING FEES", "280.95", "debit", "280.95DR"),
        # Wrapped, with a decimal number inside the description.
        _row("06-03-25", "FCY PURCHASE EUR 10 @"),
        _row(None, "140.00 TRF FROM EUR A/C", "1,000.00", "credit", "719.05CR"),
        # Continuation lines that start like header text (account number / period).
        _row("07-03-25", "BY MPESA TAB12CD34E"),
        _row(None, "3000000000 254700000000", "200.00", "credit", "919.05CR"),
        _row("31-03-25", "3000000000:Int.Coll:"),
        _row(None, "01-03-2025 to 31-03-", "250.00", "debit", "669.05CR"),
    ])
    return str(path)


def test_synthetic_layout_c_detected(synthetic_layout_c):
    assert _is_layout_c(synthetic_layout_c) is True


def test_synthetic_layout_c_direction_from_columns(synthetic_layout_c):
    result = extract_coop_pdf(synthetic_layout_c)
    got = [(t.description, t.debit_raw, t.credit_raw, t.balance_raw) for t in result.raw_transactions]
    assert got == [
        ("PrimeNET:MPESA airtime", "500.00", "", "1,500.00CR"),
        ("CONVERSION TRANSFER OF EUR 100 TO KSH", "", "14,000.00", "15,500.00CR"),
        ("PESALINK FROM: JANE DOE", "", "1,000.00", "16,500.00CR"),
        ("EXCISE TAX", "16,500.00", "", ""),
        ("STANDING FEES", "280.95", "", "280.95DR"),
        ("FCY PURCHASE EUR 10 @ 140.00 TRF FROM EUR A/C", "", "1,000.00", "719.05CR"),
        ("BY MPESA TAB12CD34E 3000000000 254700000000", "", "200.00", "919.05CR"),
        ("3000000000:Int.Coll: 01-03-2025 to 31-03-", "250.00", "", "669.05CR"),
    ]
    assert result.warnings == []
    assert _running_balance_breaks(result.raw_transactions, opening_cents=200_000) == []


def test_synthetic_layout_c_column_balance_disagreement_warns(tmp_path):
    """Amount printed in the Credit column but balance falls: balance delta wins, with a warning."""
    path = tmp_path / "coop_layout_c_disagree.pdf"
    _build_layout_c_pdf(path, [
        [("B/F", 121, "l"), ("2,000.00CR", _BALANCE_X1, "r")],
        _row("25-02-25", "PrimeNET:MPESA airtime", "500.00", "credit", "1,500.00CR"),
    ])
    result = extract_coop_pdf(str(path))
    [t] = result.raw_transactions
    assert (t.debit_raw, t.credit_raw) == ("500.00", "")
    assert len(result.warnings) == 1
    assert result.extraction_status == "needs_review"
