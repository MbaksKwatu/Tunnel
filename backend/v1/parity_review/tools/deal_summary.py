"""
Deal-level summary: transaction counts, totals by direction and role,
monthly breakdown, and role distribution.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List


_ROLE_LABELS = {
    "revenue_operational": "Revenue (operational)",
    "revenue_non_operational": "Revenue (non-operational)",
    "supplier_payment": "Supplier payment",
    "loan_repayment": "Loan repayment",
    "loan_inflow": "Loan inflow",
    "payroll": "Payroll",
    "tax_payment": "Tax payment",
    "kra_payment": "KRA payment",
    "bank_charge": "Bank charge",
    "transfer_internal": "Internal transfer",
    "needs_review": "Needs review",
    "other": "Other / unclassified",
}


def get_deal_summary(deal_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return deal-level counts and totals: credits vs debits, by role,
    and monthly breakdown.
    """
    tagged   = deal_data["tagged"]
    monthly  = deal_data["monthly"]
    currency = deal_data["currency"]

    # --- Credits vs debits ---
    credit_txns = [t for t in tagged if t["signed_amount_cents"] > 0]
    debit_txns  = [t for t in tagged if t["signed_amount_cents"] < 0]

    total_credit_cents = sum(t["signed_amount_cents"] for t in credit_txns)
    total_debit_cents  = sum(abs(t["signed_amount_cents"]) for t in debit_txns)

    # --- By role ---
    role_agg: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "credit_cents": 0, "debit_cents": 0}
    )
    for t in tagged:
        role = t["role"]
        amt = t["signed_amount_cents"]
        role_agg[role]["count"] += 1
        if amt > 0:
            role_agg[role]["credit_cents"] += amt
        else:
            role_agg[role]["debit_cents"] += abs(amt)

    role_breakdown = []
    for role, agg in sorted(role_agg.items(), key=lambda x: x[1]["count"], reverse=True):
        role_breakdown.append({
            "role": role,
            "label": _ROLE_LABELS.get(role, role),
            "count": agg["count"],
            "credit_kes": round(agg["credit_cents"] / 100, 2),
            "debit_kes": round(agg["debit_cents"] / 100, 2),
        })

    # --- Monthly breakdown ---
    monthly_rows = []
    for m in monthly:
        monthly_rows.append({
            "month": m["month"],
            "inflow_kes": round(m["inflow_cents"] / 100, 2),
            "outflow_kes": round(m["outflow_cents"] / 100, 2),
            "net_kes": round(m["net_cents"] / 100, 2),
        })

    # --- Distinct entities ---
    distinct_entities = len({t["entity_id"] for t in tagged if t["entity_id"]})

    return {
        "currency": currency,
        "total_transactions": len(tagged),
        "transaction_direction": {
            "credits": {
                "count": len(credit_txns),
                "total_kes": round(total_credit_cents / 100, 2),
            },
            "debits": {
                "count": len(debit_txns),
                "total_kes": round(total_debit_cents / 100, 2),
            },
            "net_kes": round((total_credit_cents - total_debit_cents) / 100, 2),
        },
        "role_breakdown": role_breakdown,
        "monthly_breakdown": monthly_rows,
        "distinct_entities": distinct_entities,
        "period_months": deal_data["n_months"],
    }
