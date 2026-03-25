from backend.v1.core.reconciliation import compute_reconciliation
from backend.v1.core.declared_financials import DeclaredFinancials


def test_reconciliation_e2e_basic():
    """
    Case: clean operational revenue only
    Expect: MATCH or INSUFFICIENT_DATA depending on declared
    """

    transactions = [
        {"role": "revenue_operational", "signed_amount_cents": 100000},
        {"role": "revenue_operational", "signed_amount_cents": 50000},
    ]

    declared = DeclaredFinancials(revenue=[150000])

    result = compute_reconciliation(declared, transactions)

    rev = result["revenue"]

    assert rev["detected_cents"] == 150000
    assert rev["status"] == "MATCH"
    assert "insight" in rev
    assert rev["explanation"]["included_revenue_cents"] == 150000


def test_reconciliation_with_transfers():
    """
    Case: mixed revenue + transfers
    Expect: transfers excluded and visible in explanation
    """

    transactions = [
        {"role": "revenue_operational", "signed_amount_cents": 100000},
        {"role": "transfer", "signed_amount_cents": 50000},
    ]

    declared = DeclaredFinancials(revenue=[100000])

    result = compute_reconciliation(declared, transactions)

    rev = result["revenue"]

    assert rev["detected_cents"] == 100000
    assert rev["status"] == "MATCH"
    assert rev["explanation"]["excluded_cents"] == 50000
    assert "transfer" in rev["insight"]


def test_reconciliation_mismatch():
    """
    Case: large mismatch
    Expect: MISMATCH
    """

    transactions = [
        {"role": "revenue_operational", "signed_amount_cents": 60000},
    ]

    declared = DeclaredFinancials(revenue=[100000])

    result = compute_reconciliation(declared, transactions)

    rev = result["revenue"]

    assert rev["detected_cents"] == 60000
    assert rev["status"] == "MISMATCH"


def test_insufficient_data():
    """
    Case: no declared revenue
    Expect: INSUFFICIENT_DATA
    """

    transactions = [
        {"role": "revenue_operational", "signed_amount_cents": 50000},
    ]

    declared = DeclaredFinancials(revenue=[0])

    result = compute_reconciliation(declared, transactions)

    rev = result["revenue"]

    assert rev["status"] == "INSUFFICIENT_DATA"
    assert rev["delta_cents"] is None
    assert rev["delta_bps"] is None
    assert "insight" in rev


def test_negative_and_noise_filtered():
    """
    Case: noise + negative flows
    Expect: ignored correctly
    """

    transactions = [
        {"role": "revenue_operational", "signed_amount_cents": 80000},
        {"role": "payroll", "signed_amount_cents": -30000},
        {"role": "bank_charge", "signed_amount_cents": -5000},
        {"role": "transfer", "signed_amount_cents": 20000},
    ]

    declared = DeclaredFinancials(revenue=[80000])

    result = compute_reconciliation(declared, transactions)

    rev = result["revenue"]

    assert rev["detected_cents"] == 80000
    assert rev["explanation"]["excluded_cents"] == 20000


def test_insight_generation():
    """
    Case: dominant exclusion type
    Expect: correct percentage + category
    """

    transactions = [
        {"role": "revenue_operational", "signed_amount_cents": 100000},
        {"role": "transfer", "signed_amount_cents": 100000},
    ]

    declared = DeclaredFinancials(revenue=[100000])

    result = compute_reconciliation(declared, transactions)

    rev = result["revenue"]

    # 50% excluded
    assert "50%" in rev["insight"]
    assert "transfer" in rev["insight"]

