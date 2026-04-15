from typing import Dict, Optional, Tuple

# ── ONTOLOGY v2.0 ─────────────────────────────────────────────────────────────
# Every keyword group maps to a specific role.
# Order of evaluation is fixed and deterministic.
# Every path returns a (role, classification_reason) tuple.
# ─────────────────────────────────────────────────────────────────────────────

# Strip categories — excluded from all financial calculations
_OPENING_BALANCE_KEYWORDS = frozenset({
    "b/fwd", "balance b/fwd", "balance b/f", "opening balance",
    "balance brought forward", "brought forward"
})
_CLOSING_BALANCE_KEYWORDS = frozenset({
    "balance at period end", "closing balance", "balance carried forward",
    "balance c/fwd", "balance c/f"
})

# Loan inflows — positive: loan_inflow, negative: loan_repayment
_LOAN_KEYWORDS = frozenset({
    "loan", "facility", "disbursement", "loan repayment",
    "fuliza", "tala", "branch loan", "zenka", "timia", "okolea",
    "kcb loop", "equity loan", "ncba loop"
})

# Known microfinance and bank paybill patterns for loan repayment detection
_LOAN_REPAYMENT_PATTERNS = frozenset({
    "choice microfinance", "faulu", "kwft", "smep", "sumac",
    "rafiki microfinance", "century microfinance", "uwezo",
    "oda collection"
})

# Capital injection (positive only)
# Note: "capital" as a standalone word matches company names (e.g. "Fourth Generation Capital Ltd")
# Only match multi-word phrases that unambiguously indicate an equity injection
_CAPITAL_KEYWORDS = frozenset({
    "equity injection", "shareholder contribution", "director contribution",
    "owner contribution", "capital injection", "share capital"
})

# Company name suffixes that contain capital/investment keywords but are NOT injections
_COMPANY_SUFFIXES = frozenset({
    "capital limited", "capital ltd", "capital llp", "capital plc",
    "investment limited", "investment ltd", "investment trust",
    "investments limited", "investments ltd",
    "trust registered", "africa trust",
})

# Reversal and refund credits — auto-excluded from revenue
_REVERSAL_KEYWORDS = frozenset({
    "reversal", "refund", "chargeback", "reversed", "reverse",
    "refer to drawer", "insufficient funds", "dishonoured", "dishonored",
    "unpaid cheque", "unpaid check", "returned cheque", "returned check",
    "bounced", "chq rejected", "cheque rejected", "failed payment",
    "payment failed", "rev ", "rev/", "rev-"
})

# Non-operational revenue — grants, rental, government transfers
_NON_OP_REVENUE_KEYWORDS = frozenset({
    "grant", "rental income", "rent income", "subsidy",
    "government transfer", "ngcdf", "constituency", "bursary"
})

# Revenue operational — confirmed trading income
_REVENUE_OP_KEYWORDS = frozenset({
    "sale", "pos", "mpesa", "payment received", "client payment",
    "receipt", "c2b", "till", "paybill receipt"
})

# Payroll — outflows only
_PAYROLL_KEYWORDS = frozenset({
    "salary", "payroll", "wages", "staff payment", "net pay",
    "salaries", "wage payment"
})

# Tax payments — outflows only
_TAX_KEYWORDS = frozenset({
    "tax", "kra", "vat", "paye", "withholding tax", "income tax",
    "corporate tax", "turnover tax"
})

# Bank charges and fees — outflows only
_BANK_CHARGE_KEYWORDS = frozenset({
    "charge", "fee", "commission", "excise", "excise duty",
    "transaction fee", "transfer fee", "withdrawal charge",
    "maintenance fee", "ledger fee", "monthly fee", "annual fee",
    "pesalink fee", "funds transfer debit fee", "debit fee",
    "alert crg", "crg excise", "kplcprepaidcomm", "int.coll",
    "interest run", "interest charge", "interest collected",
    "agency charge", "atm charge", "unpaid cheque commission"
})

# Cash withdrawals — outflows only
_CASH_WITHDRAWAL_KEYWORDS = frozenset({
    "atm cash", "cash withdrawal", "agent wdl", "cheque withdrawal",
    "agent withdrawal", "atm withdrawal", "cash draw"
})

# Airtime and data — outflows only
_AIRTIME_KEYWORDS = frozenset({
    "airtime", "recharge", "data bundle", "bundle purchase",
    "safaricom data", "airtime purchase"
})

# Bill payments — outflows only
_BILL_PAYMENT_KEYWORDS = frozenset({
    "//bill//", "pay bill", "paybill", "bill payment",
    "utility payment", "kplc", "nairobi water", "kenya power",
    "pay utility", "mpesab2c"
})

# Merchant and POS purchases — outflows only
_MERCHANT_KEYWORDS = frozenset({
    "merchant payment", "pos txn", "pos purchase",
    "supermarket", "naivas", "quickmart", "carrefour",
    "java", "chicken inn", "cinemax"
})

# Mobile money transfers — outflows only
_MOBILE_TRANSFER_KEYWORDS = frozenset({
    "mobile money tr", "mobile payment", "send money",
    "customer transfer", "transfer of funds"
})

# PesaLink inflows — credits only
_PESALINK_INFLOW_KEYWORDS = frozenset({
    "pesalink", "pesa link"
})

# Named counterparty threshold — positive amounts above this get needs_review
_LARGE_POSITIVE_THRESHOLD_CENTS = 10_000_000  # KES 100,000

DEBIT_ONLY_ROLES = {
    "bank_charge", "loan_repayment", "tax_payment", "supplier_payment",
    "merchant_payment", "reversal_debit", "pesalink_outflow", "payroll"
}

CREDIT_ONLY_ROLES = {
    "revenue_operational", "loan_inflow", "capital_injection",
    "reversal_credit", "pesalink_inflow", "mpesa_inflow"
}


def _keyword_classify(descriptor: str, amount_cents: int) -> Optional[Tuple[str, str]]:
    """
    Deterministic keyword classification.
    Returns (role, classification_reason) tuple or None if no match.

    Evaluation order is fixed — first match wins:
    1. Strip categories (opening/closing balance)
    2. Loan inflow / loan repayment
    3. Capital injection
    4. Reversal credit
    5. Non-operational revenue
    6. Payroll
    7. Tax payment
    8. Bank charges
    9. Cash withdrawal
    10. Airtime
    11. Bill payment
    12. Merchant payment
    13. Mobile money transfer
    14. PesaLink inflow
    15. Revenue operational
    """
    d = (descriptor or "").lower()
    amt = amount_cents

    # PAYED BY / PAID BY prefix → revenue_operational (must run before all other checks)
    if d.startswith("payed by") or d.startswith("paid by"):
        return ("revenue_operational", "keyword_match:payed_by_prefix")

    # MPS credit prefix → revenue_operational
    if d.startswith("mps") and amt > 0:
        return ("revenue_operational", "keyword_match:mps_credit_inflow")

    # 1. Strip categories
    for kw in _OPENING_BALANCE_KEYWORDS:
        if kw in d:
            return ("opening_balance", f"keyword_match:{kw}:opening_balance")
    for kw in _CLOSING_BALANCE_KEYWORDS:
        if kw in d:
            return ("closing_balance", f"keyword_match:{kw}:closing_balance")

    # 2. Loan keywords
    for kw in _LOAN_KEYWORDS:
        if kw in d:
            if amt > 0:
                return ("loan_inflow", f"keyword_match:{kw}:loan_keywords")
            else:
                return ("loan_repayment", f"keyword_match:{kw}:loan_keywords")
    for kw in _LOAN_REPAYMENT_PATTERNS:
        if kw in d:
            return ("loan_repayment", f"keyword_match:{kw}:loan_repayment_patterns")

    # 3. Capital injection (positive only)
    for kw in _CAPITAL_KEYWORDS:
        if kw in d:
            if amt > 0:
                return ("capital_injection", f"keyword_match:{kw}:capital_keywords")
            else:
                return ("supplier", f"keyword_match:{kw}:capital_keywords_negative")

    # 4. Reversal credit
    for kw in _REVERSAL_KEYWORDS:
        if kw in d:
            if amt > 0:
                return ("reversal_credit", f"keyword_match:{kw}:reversal_keywords")
            else:
                return ("reversal_debit", f"keyword_match:{kw}:reversal_keywords")

    # 5. Non-operational revenue
    for kw in _NON_OP_REVENUE_KEYWORDS:
        if kw in d:
            return ("revenue_non_operational", f"keyword_match:{kw}:non_op_revenue_keywords")

    # 6. Payroll (negative only — salary received is revenue_operational)
    for kw in _PAYROLL_KEYWORDS:
        if kw in d:
            if amt < 0:
                return ("payroll", f"keyword_match:{kw}:payroll_keywords")
            else:
                return ("revenue_operational", f"keyword_match:{kw}:payroll_keywords_inbound")

    # 7. Tax payment
    for kw in _TAX_KEYWORDS:
        if kw in d:
            return ("tax_payment", f"keyword_match:{kw}:tax_keywords")

    # 8. Bank charges
    for kw in _BANK_CHARGE_KEYWORDS:
        if kw in d:
            return ("bank_charge", f"keyword_match:{kw}:bank_charge_keywords")

    # 9. Cash withdrawal
    for kw in _CASH_WITHDRAWAL_KEYWORDS:
        if kw in d:
            return ("cash_withdrawal", f"keyword_match:{kw}:cash_withdrawal_keywords")

    # 10. Airtime
    for kw in _AIRTIME_KEYWORDS:
        if kw in d:
            return ("airtime_purchase", f"keyword_match:{kw}:airtime_keywords")

    # 11. Bill payment
    for kw in _BILL_PAYMENT_KEYWORDS:
        if kw in d:
            if amt < 0:
                return ("bill_payment", f"keyword_match:{kw}:bill_payment_keywords")
            else:
                return ("revenue_operational", f"keyword_match:{kw}:bill_payment_inbound")

    # Supermarket cheque → supplier_payment (before generic cheque-to-merchant path)
    if "chq:" in d and "supermarket" in d:
        return ("supplier_payment", "keyword_match:supermarket_cheque")

    # 12. Merchant payment
    for kw in _MERCHANT_KEYWORDS:
        if kw in d:
            return ("merchant_payment", f"keyword_match:{kw}:merchant_keywords")

    # 13. Mobile money transfer
    for kw in _MOBILE_TRANSFER_KEYWORDS:
        if kw in d:
            if amt < 0:
                return ("mobile_money_transfer", f"keyword_match:{kw}:mobile_transfer_keywords")
            else:
                return ("mpesa_inflow", f"keyword_match:{kw}:mobile_transfer_keywords_inbound")

    # 14. PesaLink
    for kw in _PESALINK_INFLOW_KEYWORDS:
        if kw in d:
            if amt > 0:
                return ("pesalink_inflow", f"keyword_match:{kw}:pesalink_keywords")
            elif amt <= -_LARGE_POSITIVE_THRESHOLD_CENTS:
                return ("needs_review", f"keyword_match:{kw}:pesalink_large_outbound")
            else:
                return ("bill_payment", f"keyword_match:{kw}:pesalink_keywords_outbound")

    # 15. Revenue operational
    for kw in _REVENUE_OP_KEYWORDS:
        if kw in d:
            return ("revenue_operational", f"keyword_match:{kw}:revenue_op_keywords")

    return None


def classify(txn: Dict) -> str:
    """
    Deterministic, rule-based classification. Returns role string only.
    Use classify_with_reason() to get the full (role, reason) tuple.
    """
    role, _ = classify_with_reason(txn)
    return role


def classify_with_reason(txn: Dict) -> Tuple[str, str]:
    """
    Deterministic, rule-based classification with audit trail.
    Returns (role, classification_reason) tuple.

    Order:
    1. Transfer flag
    2. Keyword match on normalized_descriptor
    3. Large positive fallback -> needs_review
    4. Sign-based fallback
    """
    if txn.get("is_transfer"):
        return ("transfer", "is_transfer:flag")

    descriptor = txn.get("normalized_descriptor", "")
    amt = int(txn.get("signed_amount_cents", 0))

    result = _keyword_classify(descriptor, amt)
    if result is not None:
        role, reason = result
    elif amt > 0:
        if amt >= _LARGE_POSITIVE_THRESHOLD_CENTS:
            role, reason = "needs_review", f"fallback:large_positive_no_keyword_match:amount_{amt}"
        else:
            role, reason = "revenue_operational", "fallback:positive_amount"
    elif amt < 0:
        role, reason = "supplier", "fallback:negative_amount"
    else:
        role, reason = "other", "fallback:zero_amount"

    # Direction consistency guard
    if role in DEBIT_ONLY_ROLES and amt > 0:
        return ("needs_review", f"direction_conflict:{role}_on_credit")
    if role in CREDIT_ONLY_ROLES and amt < 0:
        return ("needs_review", f"direction_conflict:{role}_on_debit")

    return (role, reason)
