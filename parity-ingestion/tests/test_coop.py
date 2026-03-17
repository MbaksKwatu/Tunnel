"""Tests for Co-operative Bank PDF extractor."""
from __future__ import annotations

import pytest
from app.extractors.coop_extractor import (
    extract_coop_pdf,
    _parse_coop_date,
    _detect_pattern,
    _is_layout_b,
)

FIXTURE_A = "/Users/mbakswatu/Desktop/Demofiles/bankstatementsamples/Cooperative Bank Statement.pdf"
FIXTURE_B = "/Users/mbakswatu/Desktop/Demofiles/MAUCABANKCOP.pdf"


# --- date parsing ---

def test_date_format_slash():
    assert _parse_coop_date("28/02/2025") == "2025-02-28"

def test_date_format_dash():
    assert _parse_coop_date("15-2-2025") == "2025-02-15"

def test_date_format_none():
    assert _parse_coop_date("") is None


# --- layout detection ---

def test_layout_b_detected():
    assert _is_layout_b(FIXTURE_B) is True

def test_layout_a_not_b():
    assert _is_layout_b(FIXTURE_A) is False


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


# --- extraction: fixture B (MAUCABANKCOP) ---

def test_fixture_b_row_count():
    result = extract_coop_pdf(FIXTURE_B)
    assert result.row_count == 170

def test_fixture_b_no_unclassified():
    result = extract_coop_pdf(FIXTURE_B)
    unclassified = [t for t in result.raw_transactions if t.pattern_hint == "UNCLASSIFIED"]
    assert len(unclassified) == 0

def test_fixture_b_pattern_distribution():
    result = extract_coop_pdf(FIXTURE_B)
    counts = {}
    for t in result.raw_transactions:
        counts[t.pattern_hint] = counts.get(t.pattern_hint, 0) + 1
    assert counts["POS_RECEIPT"] == 34
    assert counts["SAFEWAYS_WITHDRAWAL"] == 46
    assert counts["MPESA_C2B"] == 27
    assert counts["BANK_CHARGE"] == 33
    assert counts["REVERSAL_PAIR"] == 2
    assert counts["FUND_INFLOW"] == 2
    assert counts["PESALINK_TRANSFER"] == 1

def test_fixture_b_pending_count():
    result = extract_coop_pdf(FIXTURE_B)
    pending = [t for t in result.raw_transactions if t.classification_status == "PENDING_CLASSIFICATION"]
    assert len(pending) == 38  # POS_RECEIPT 34 + REVERSAL_PAIR 2 + NAMED_PERSON_TRANSFER 1 + 1 other

def test_fixture_b_dates_parsed():
    result = extract_coop_pdf(FIXTURE_B)
    missing_dates = [t for t in result.raw_transactions if not t.date_raw or t.date_raw == ""]
    assert len(missing_dates) == 0


# --- extraction: fixture A (existing) ---

def test_fixture_a_row_count():
    result = extract_coop_pdf(FIXTURE_A)
    assert result.row_count == 45

def test_fixture_a_no_unclassified():
    result = extract_coop_pdf(FIXTURE_A)
    unclassified = [t for t in result.raw_transactions if t.pattern_hint == "UNCLASSIFIED"]
    assert len(unclassified) == 0

def test_fixture_a_reversal_pairs():
    result = extract_coop_pdf(FIXTURE_A)
    reversals = [t for t in result.raw_transactions if t.pattern_hint == "REVERSAL_PAIR"]
    assert len(reversals) == 4
