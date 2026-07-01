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

# ── Inflow roles for monthly cashflow ────────────────────────────────────────
_CASHFLOW_INFLOW_ROLES = frozenset({
    "revenue_operational",
    "revenue_non_operational",
    "mpesa_inflow",
    "pesalink_inflow",
    "loan_inflow",
    "capital_injection",
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

# Below this absolute prior-month net (cents), a MoM % swing is too noisy to
# be meaningful (e.g. -100% from a near-zero base) — ported from
# parity-ingestion/app/analytics.py::_MOM_RELIABLE_THRESHOLD_CENTS.
_MOM_RELIABLE_THRESHOLD_CENTS = 1_000_000


def _mom_change_bps(prev_net: int, net: int) -> int:
    """Month-on-month change in basis points. Returns 0 if prev_net is zero."""
    if prev_net == 0:
        return 0
    return int((net - prev_net) * 10000 // prev_net)


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


def monthly_cashflow(transactions: list[dict]) -> list[dict]:
    """
    Month-by-month inflow/outflow/net from classified transactions.

    Inflows:  roles in _CASHFLOW_INFLOW_ROLES with amount_cents > 0.
    Outflows: abs(amount_cents) where amount_cents < 0.
    Zero-inflow months are included, not skipped.
    All amounts integer cents. No floats.
    Returns list sorted by month ascending.
    """
    monthly_in: dict[str, int] = {}
    monthly_out: dict[str, int] = {}
    months_seen: set[str] = set()

    for txn in transactions:
        amount = txn.get("amount_cents", 0)
        if not isinstance(amount, int):
            raise ValueError(
                f"Non-integer amount_cents: {amount} on txn {txn.get('txn_id')}"
            )
        txn_date = txn.get("txn_date", "")
        if not txn_date:
            continue
        month = str(txn_date)[:7]
        if len(month) < 7:
            continue
        months_seen.add(month)

        role = txn.get("role") or txn.get("classification") or ""
        if role in _CASHFLOW_INFLOW_ROLES and amount > 0:
            monthly_in[month] = monthly_in.get(month, 0) + amount
        elif amount < 0:
            monthly_out[month] = monthly_out.get(month, 0) + abs(amount)

    result = []
    prev_net: int | None = None
    for month in sorted(months_seen):
        inflow = monthly_in.get(month, 0)
        outflow = monthly_out.get(month, 0)
        net = inflow - outflow
        if prev_net is None:
            mom_change_bps = None
            mom_reliable = False
        else:
            mom_change_bps = _mom_change_bps(prev_net, net)
            mom_reliable = abs(prev_net) >= _MOM_RELIABLE_THRESHOLD_CENTS
        result.append({
            "month": month,
            "inflow_cents": inflow,
            "outflow_cents": outflow,
            "net_cents": net,
            "mom_change_bps": mom_change_bps,
            "mom_reliable": mom_reliable,
        })
        prev_net = net
    return result
