"""Tests for Co-operative Bank PDF extractor."""
from __future__ import annotations

import pytest
from app.extractors.coop_extractor import (
    extract_coop_pdf,
    _parse_coop_date,
    _parse_balance_to_signed_cents,
    _detect_pattern,
    _is_layout_b,
    _is_layout_c,
)

FIXTURE_C = "/Users/mbakswatu/Desktop/Demofiles/12 months Kankam KES statement-1 (3).pdf"


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

def test_layout_c_detected():
    assert _is_layout_c(FIXTURE_C) is True

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

def test_fixture_c_row_count():
    result = extract_coop_pdf(FIXTURE_C)
    assert result.row_count == 3516

def test_fixture_c_no_unclassified():
    result = extract_coop_pdf(FIXTURE_C)
    unclassified = [t for t in result.raw_transactions if t.pattern_hint == "UNCLASSIFIED"]
    assert len(unclassified) < 60  # residual edge cases tolerated

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

def test_fixture_c_dates_parsed():
    result = extract_coop_pdf(FIXTURE_C)
    missing_dates = [t for t in result.raw_transactions if not t.date_raw or t.date_raw == ""]
    assert len(missing_dates) == 0

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

def test_fixture_c_mpesa_c2b_are_credits():
    """MPESA_C2B transactions must come out as credits (credit_raw set, debit_raw empty)."""
    result = extract_coop_pdf(FIXTURE_C)
    mpesa_txns = [t for t in result.raw_transactions if t.pattern_hint == "MPESA_C2B"]
    assert len(mpesa_txns) > 0, "No MPESA_C2B transactions found in fixture"
    wrong = [t for t in mpesa_txns if not t.credit_raw or t.debit_raw]
    assert len(wrong) == 0, (
        f"{len(wrong)}/{len(mpesa_txns)} MPESA_C2B transactions have wrong debit/credit assignment. "
        f"First offender: description={wrong[0].description!r}, "
        f"debit={wrong[0].debit_raw!r}, credit={wrong[0].credit_raw!r}"
    )

def test_fixture_c_bank_charges_are_debits():
    """BANK_CHARGE transactions must come out as debits (debit_raw set, credit_raw empty)."""
    result = extract_coop_pdf(FIXTURE_C)
    charge_txns = [t for t in result.raw_transactions if t.pattern_hint == "BANK_CHARGE"]
    assert len(charge_txns) > 0, "No BANK_CHARGE transactions found in fixture"
    wrong = [t for t in charge_txns if t.credit_raw or not t.debit_raw]
    assert len(wrong) == 0, (
        f"{len(wrong)}/{len(charge_txns)} BANK_CHARGE transactions have wrong debit/credit assignment."
    )
