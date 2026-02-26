from typing import Dict, Optional

# Revenue operational: sale, pos, mpesa, payment, client, receipt
_REVENUE_OP_KEYWORDS = frozenset({"sale", "pos", "mpesa", "payment", "client", "receipt"})
# Loan keywords: positive -> revenue_non_operational, negative -> supplier
_LOAN_KEYWORDS = frozenset({"loan", "facility", "credit", "disbursement"})
# Capital/equity injection: positive -> revenue_non_operational, negative -> supplier
_CAPITAL_KEYWORDS = frozenset({"capital", "director", "owner", "shareholder", "investment", "equity"})
# Refund/reversal: positive -> revenue_non_operational, negative -> supplier
_REFUND_KEYWORDS = frozenset({"reversal", "refund", "chargeback"})
# Payroll: salary, payroll, wages, staff
_PAYROLL_KEYWORDS = frozenset({"salary", "payroll", "wages", "staff"})
# Tax: tax, kra, vat, paye -> supplier
_TAX_KEYWORDS = frozenset({"tax", "kra", "vat", "paye"})


def _keyword_classify(descriptor: str, amount_cents: int) -> Optional[str]:
    """
    Deterministic keyword classification. Returns role or None if no match.
    Uses simple 'keyword in descriptor' - no regex, no fuzzy matching.
    Order: loan before revenue_operational so "loan repayment" matches loan (not "payment" in repayment).
    """
    d = (descriptor or "").lower()
    amt = amount_cents

    for kw in _LOAN_KEYWORDS:
        if kw in d:
            return "revenue_non_operational" if amt > 0 else "supplier"

    for kw in _CAPITAL_KEYWORDS:
        if kw in d:
            return "revenue_non_operational" if amt > 0 else "supplier"

    for kw in _REFUND_KEYWORDS:
        if kw in d:
            return "revenue_non_operational" if amt > 0 else "supplier"

    for kw in _REVENUE_OP_KEYWORDS:
        if kw in d:
            return "revenue_operational"

    for kw in _PAYROLL_KEYWORDS:
        if kw in d:
            return "payroll"

    for kw in _TAX_KEYWORDS:
        if kw in d:
            return "supplier"

    return None


def classify(txn: Dict) -> str:
    """
    Deterministic, rule-based classification.
    Order: 1) transfer, 2) keyword match on normalized_descriptor, 3) sign-based fallback.
    """
    if txn.get("is_transfer"):
        return "transfer"

    descriptor = txn.get("normalized_descriptor", "")
    amt = int(txn.get("signed_amount_cents", 0))
    role = _keyword_classify(descriptor, amt)
    if role is not None:
        return role

    # Fallback: positive -> revenue_operational, negative -> supplier, zero -> other
    if amt > 0:
        return "revenue_operational"
    if amt < 0:
        return "supplier"
    return "other"
