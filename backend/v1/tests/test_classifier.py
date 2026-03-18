"""
Tests for Parity ontology v2.0 classifier.
Every test verifies both role and classification_reason format.
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.classifier import classify, classify_with_reason


def txn(descriptor, amount):
    return {"normalized_descriptor": descriptor, "signed_amount_cents": amount}


# ── STRIP CATEGORIES ──────────────────────────────────────────────────────────

def test_opening_balance_stripped():
    role, reason = classify_with_reason(txn("balance b/fwd", 0))
    assert role == "opening_balance"
    assert "opening_balance" in reason

def test_closing_balance_stripped():
    role, reason = classify_with_reason(txn("balance at period end", 100000))
    assert role == "closing_balance"
    assert "closing_balance" in reason

# ── LOAN INFLOW ───────────────────────────────────────────────────────────────

def test_loan_inflow_keyword_disbursement():
    role, reason = classify_with_reason(txn("fourth generation capital loan disbursement", 29849325))
    assert role == "loan_inflow"
    assert "keyword_match" in reason

def test_loan_inflow_keyword_facility():
    role, reason = classify_with_reason(txn("credit facility drawdown", 50000000))
    assert role == "loan_inflow"
    assert "keyword_match" in reason

def test_loan_repayment_negative():
    role, reason = classify_with_reason(txn("loan repayment kcb", -1250000))
    assert role == "loan_repayment"
    assert "keyword_match" in reason

def test_loan_repayment_microfinance_pattern():
    role, reason = classify_with_reason(txn("pay bill online to 444174 choice microfinance bank", -320000))
    assert role == "loan_repayment"
    assert "keyword_match" in reason

def test_fuliza_repayment():
    role, reason = classify_with_reason(txn("fuliza repayment safaricom", -234000))
    assert role == "loan_repayment"
    assert "keyword_match" in reason

# ── CAPITAL INJECTION ─────────────────────────────────────────────────────────

def test_capital_injection_equity():
    role, reason = classify_with_reason(txn("equity injection from shareholder", 50000000))
    assert role == "capital_injection"
    assert "keyword_match" in reason

def test_capital_injection_director():
    role, reason = classify_with_reason(txn("director contribution to business", 10000000))
    assert role == "capital_injection"
    assert "keyword_match" in reason

# ── REVERSAL ──────────────────────────────────────────────────────────────────

def test_reversal_credit():
    role, reason = classify_with_reason(txn("reversed aba6ce209025 safeways express", 4000000))
    assert role == "reversal_credit"
    assert "keyword_match" in reason

def test_reversal_debit():
    role, reason = classify_with_reason(txn("reversal of failed payment", -1900000))
    assert role == "reversal_debit"
    assert "keyword_match" in reason

# ── PAYROLL ───────────────────────────────────────────────────────────────────

def test_payroll_outflow():
    role, reason = classify_with_reason(txn("salary payment staff net pay", -10000000))
    assert role == "payroll"
    assert "keyword_match" in reason

def test_salary_inbound_is_revenue():
    role, reason = classify_with_reason(txn("salary credit from employer", 8400000))
    assert role == "revenue_operational"
    assert "keyword_match" in reason

# ── TAX PAYMENT ───────────────────────────────────────────────────────────────

def test_tax_payment_kra():
    role, reason = classify_with_reason(txn("kra paye payment march 2025", -500000))
    assert role == "tax_payment"
    assert "keyword_match" in reason

def test_tax_payment_vat():
    role, reason = classify_with_reason(txn("vat remittance quarterly", -320000))
    assert role == "tax_payment"
    assert "keyword_match" in reason

# ── BANK CHARGES ──────────────────────────────────────────────────────────────

def test_bank_charge_excise():
    role, reason = classify_with_reason(txn("excise duty for the fee", -500))
    assert role == "bank_charge"
    assert "keyword_match" in reason

def test_bank_charge_maintenance():
    role, reason = classify_with_reason(txn("msme bronze maintenance fee monthly", -10000))
    assert role == "bank_charge"
    assert "keyword_match" in reason

def test_bank_charge_interest():
    role, reason = classify_with_reason(txn("int.coll 01-01-2025 to 31-01-2025", -1000))
    assert role == "bank_charge"
    assert "keyword_match" in reason

def test_bank_charge_alert():
    role, reason = classify_with_reason(txn("debit alert crg cb0567683", -3500))
    assert role == "bank_charge"
    assert "keyword_match" in reason

# ── CASH WITHDRAWAL ───────────────────────────────────────────────────────────

def test_cash_withdrawal_atm():
    role, reason = classify_with_reason(txn("atm cash kcb 4243142016004052", -2000000))
    assert role == "cash_withdrawal"
    assert "keyword_match" in reason

def test_cash_withdrawal_agent():
    role, reason = classify_with_reason(txn("agent wdl sz09bfcceqn0", -1500000))
    assert role == "cash_withdrawal"
    assert "keyword_match" in reason

# ── AIRTIME ───────────────────────────────────────────────────────────────────

def test_airtime_purchase():
    role, reason = classify_with_reason(txn("airtime purchase safaricom", -5000))
    assert role == "airtime_purchase"
    assert "keyword_match" in reason

def test_data_bundle():
    role, reason = classify_with_reason(txn("customer bundle purchase safaricom data", -20000))
    assert role == "airtime_purchase"
    assert "keyword_match" in reason

# ── BILL PAYMENT ──────────────────────────────────────────────────────────────

def test_bill_payment_mpesa():
    role, reason = classify_with_reason(txn("mpesab2c-11 0710642294 bill mb bp", -5000000))
    assert role == "bill_payment"
    assert "keyword_match" in reason

def test_bill_payment_kplc():
    role, reason = classify_with_reason(txn("kplc prepaid 14243228146 properties kiambaa", -20000))
    assert role == "bill_payment"
    assert "keyword_match" in reason

def test_bill_payment_paybill():
    role, reason = classify_with_reason(txn("pay bill online to 7847061 uber bv", -150000))
    assert role == "bill_payment"
    assert "keyword_match" in reason

# ── MERCHANT PAYMENT ─────────────────────────────────────────────────────────

def test_merchant_payment_pos():
    role, reason = classify_with_reason(txn("pos txn 4243142016004052 naivas supermarket", -109360))
    assert role == "merchant_payment"
    assert "keyword_match" in reason

def test_merchant_payment_named():
    role, reason = classify_with_reason(txn("merchant payment to 7099197 naivas", -50000))
    assert role == "merchant_payment"
    assert "keyword_match" in reason

# ── MOBILE MONEY ──────────────────────────────────────────────────────────────

def test_mobile_money_transfer_outbound():
    role, reason = classify_with_reason(txn("mobile money tr mm230559o0589 custom", -17439700))
    assert role == "mobile_money_transfer"
    assert "keyword_match" in reason

def test_mobile_money_inbound():
    role, reason = classify_with_reason(txn("mobile payment received customer", 4300500))
    assert role == "mpesa_inflow"
    assert "keyword_match" in reason

# ── PESALINK ──────────────────────────────────────────────────────────────────

def test_pesalink_inflow():
    role, reason = classify_with_reason(txn("pesalink inbound transfer from bank", 9995000))
    assert role == "pesalink_inflow"
    assert "keyword_match" in reason

def test_pesalink_outbound():
    role, reason = classify_with_reason(txn("pesalink 16958003230901 payment", -40000000))
    assert role == "bill_payment"
    assert "keyword_match" in reason

# ── REVENUE OPERATIONAL ───────────────────────────────────────────────────────

def test_revenue_mpesa_c2b():
    role, reason = classify_with_reason(txn("mpesa c2b customer payment receipt", 100000))
    assert role == "revenue_operational"
    assert "keyword_match" in reason

def test_revenue_pos_receipt():
    role, reason = classify_with_reason(txn("pos receipt sale confirmed", 500000))
    assert role == "revenue_operational"
    assert "keyword_match" in reason

# ── FALLBACK ──────────────────────────────────────────────────────────────────

def test_large_positive_fallback_needs_review():
    role, reason = classify_with_reason(txn("the somo africa trust payment", 53760000))
    assert role == "needs_review"
    assert "fallback" in reason
    assert "large_positive" in reason

def test_small_positive_fallback_revenue():
    role, reason = classify_with_reason(txn("unknown small credit", 50000))
    assert role == "revenue_operational"
    assert "fallback" in reason

def test_negative_fallback_supplier():
    role, reason = classify_with_reason(txn("unknown debit", -100000))
    assert role == "supplier"
    assert "fallback" in reason

def test_zero_fallback_other():
    role, reason = classify_with_reason(txn("zero amount row", 0))
    assert role == "other"
    assert "fallback" in reason

# ── TRANSFER FLAG ─────────────────────────────────────────────────────────────

def test_transfer_flag_overrides_all():
    role, reason = classify_with_reason({"is_transfer": True, "normalized_descriptor": "loan disbursement", "signed_amount_cents": 50000000})
    assert role == "transfer"
    assert "is_transfer" in reason

# ── CLASSIFICATION REASON ALWAYS POPULATED ────────────────────────────────────

def test_classification_reason_never_empty():
    test_txns = [
        txn("balance b/fwd", 0),
        txn("loan disbursement", 5000000),
        txn("salary payment", -1000000),
        txn("unknown", 999),
        txn("unknown large", 50000000),
        txn("unknown debit", -999),
    ]
    for t in test_txns:
        _, reason = classify_with_reason(t)
        assert reason and len(reason) > 0, f"Empty reason for: {t}"

# ── BACKWARD COMPATIBILITY ────────────────────────────────────────────────────

def test_classify_returns_string():
    role = classify(txn("mpesa payment", 100000))
    assert isinstance(role, str)
    assert len(role) > 0
