"""
Parity analytics — deterministic pipeline computations for credit enrichment.

All amounts in integer cents. No floats.
Same input always produces same output.
"""
from __future__ import annotations

from typing import Any

# ── Revenue roles counted in cleaned annual totals ────────────────────────────
_ANNUAL_REVENUE_ROLES = frozenset({
    "revenue_operational",
    "mpesa_inflow",
    "pesalink_inflow",
    "revenue_non_operational",
})

# ── Expense roles counted in top-expenses surface ─────────────────────────────
_EXPENSE_ROLES = frozenset({
    "supplier",
    "supplier_payment",
    "payroll",
    "tax_payment",
    "bank_charge",
    "cash_withdrawal",
    "bill_payment",
    "merchant_payment",
})


def annual_revenue_summary(transactions: list[dict]) -> dict:
    """
    Compute cleaned annual revenue totals from classified transactions.

    Excludes: loan_inflow, capital_injection, reversal_credit, transfer, needs_review.
    Revenue roles included: revenue_operational, mpesa_inflow, pesalink_inflow,
    revenue_non_operational.

    Returns integer cents only. No floats.
    """
    by_year: dict[int, int] = {}

    for txn in transactions:
        role = txn.get("role") or txn.get("classification")
        if role not in _ANNUAL_REVENUE_ROLES:
            continue
        amount = txn.get("amount_cents", 0)
        if not isinstance(amount, int):
            raise ValueError(
                f"Non-integer amount_cents: {amount} on txn {txn.get('txn_id')}"
            )
        if amount <= 0:
            continue
        txn_date = txn.get("txn_date", "")
        if not txn_date:
            continue
        try:
            year = int(str(txn_date)[:4])
        except (ValueError, TypeError):
            continue
        by_year[year] = by_year.get(year, 0) + amount

    return {
        "annual_revenue_cents": by_year,
        "years_covered": sorted(by_year.keys()),
        "total_all_years_cents": sum(by_year.values()),
    }


def loan_drawdowns(transactions: list[dict]) -> dict:
    """
    Extract and surface all loan inflow transactions.

    Returns list sorted by date descending, with running total.
    All amounts in integer cents.
    """
    drawdowns: list[dict] = []
    total_cents = 0

    for txn in transactions:
        role = txn.get("role") or txn.get("classification")
        if role != "loan_inflow":
            continue
        amount = txn.get("amount_cents", 0)
        if not isinstance(amount, int):
            raise ValueError(
                f"Non-integer amount_cents on loan txn {txn.get('txn_id')}"
            )
        if amount <= 0:
            continue
        total_cents += amount
        drawdowns.append({
            "txn_date": txn.get("txn_date"),
            "entity_name": txn.get("entity_name") or txn.get("description", "Unknown"),
            "amount_cents": amount,
            "txn_id": txn.get("txn_id"),
        })

    drawdowns.sort(key=lambda x: str(x.get("txn_date", "")), reverse=True)

    return {
        "drawdowns": drawdowns,
        "total_drawdown_cents": total_cents,
        "drawdown_count": len(drawdowns),
    }


def kra_summary(transactions: list[dict]) -> dict:
    """
    Compute KRA tax payment summary.

    Returns: total paid, months with payments, compliance signal.
    All amounts integer cents.
    Compliance: COMPLIANT (payments in >= 10 months), PARTIAL (some), NOT_DETECTED (zero).
    """
    by_month: dict[str, int] = {}
    total_cents = 0
    payments: list[dict] = []

    for txn in transactions:
        role = txn.get("role") or txn.get("classification")
        if role != "tax_payment":
            continue
        amount = txn.get("amount_cents", 0)
        if not isinstance(amount, int):
            raise ValueError(
                f"Non-integer amount_cents on tax txn {txn.get('txn_id')}"
            )
        abs_amount = abs(amount)
        if abs_amount == 0:
            continue
        total_cents += abs_amount
        txn_date = str(txn.get("txn_date", ""))
        month_key = txn_date[:7] if len(txn_date) >= 7 else "unknown"
        by_month[month_key] = by_month.get(month_key, 0) + abs_amount
        payments.append({
            "txn_date": txn.get("txn_date"),
            "entity_name": txn.get("entity_name", "KRA"),
            "amount_cents": abs_amount,
        })

    months_with_payment = len(by_month)

    if months_with_payment == 0:
        compliance = "NOT_DETECTED"
    elif months_with_payment >= 10:
        compliance = "COMPLIANT"
    else:
        compliance = "PARTIAL"

    return {
        "total_tax_cents": total_cents,
        "months_with_payment": months_with_payment,
        "monthly_breakdown": by_month,
        "compliance": compliance,
        "payments": sorted(payments, key=lambda x: str(x.get("txn_date", ""))),
    }


def top_expenses_with_frequency(
    transactions: list[dict],
    top_n: int = 10,
) -> list[dict]:
    """
    Returns top N expense entities by total amount, with transaction frequency.

    Expense roles: supplier, supplier_payment, payroll, tax_payment, bank_charge,
                   cash_withdrawal, bill_payment, merchant_payment.
    All amounts integer cents.
    """
    entity_totals: dict[str, dict[str, Any]] = {}

    for txn in transactions:
        role = txn.get("role") or txn.get("classification")
        if role not in _EXPENSE_ROLES:
            continue
        amount = txn.get("amount_cents", 0)
        if not isinstance(amount, int):
            raise ValueError(
                f"Non-integer amount_cents on expense txn {txn.get('txn_id')}"
            )
        abs_amount = abs(amount)
        if abs_amount == 0:
            continue
        entity = txn.get("entity_name") or txn.get("description", "Unknown")
        if entity not in entity_totals:
            entity_totals[entity] = {"total_cents": 0, "txn_count": 0, "role": role}
        entity_totals[entity]["total_cents"] += abs_amount
        entity_totals[entity]["txn_count"] += 1

    sorted_entities = sorted(
        entity_totals.items(),
        key=lambda x: x[1]["total_cents"],
        reverse=True,
    )

    return [
        {
            "entity_name": name,
            "total_cents": data["total_cents"],
            "txn_count": data["txn_count"],
            "avg_transaction_cents": data["total_cents"] // data["txn_count"],
            "role": data["role"],
        }
        for name, data in sorted_entities[:top_n]
    ]
