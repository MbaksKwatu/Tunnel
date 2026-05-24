"""
Detailed transaction history and analysis for a specific entity.
"""
from __future__ import annotations

from typing import Any, Dict, List


def get_entity_details(entity_name: str, deal_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get all transactions and risk profile for a named entity.
    Matches on exact entity_name or case-insensitive substring of description.
    """
    tagged       = deal_data["tagged"]
    entity_names = deal_data["entity_names"]
    currency     = deal_data["currency"]

    name_lower = entity_name.lower()

    # Find all entity_ids whose display_name fuzzy-matches the query
    matched_eids = {
        eid for eid, name in entity_names.items()
        if name_lower in name.lower() or name.lower() in name_lower
    }

    entity_txns = [
        t for t in tagged
        if t["entity_id"] in matched_eids
        or name_lower in (t.get("description") or "").lower()
        or name_lower in (t.get("entity_name") or "").lower()
    ]

    if not entity_txns:
        return {
            "found": False,
            "message": f"No transactions found for '{entity_name}'",
            "suggestion": "Try a partial name. Check top_suppliers or top_revenue for available entities.",
        }

    credits = [t for t in entity_txns if t["signed_amount_cents"] > 0]
    debits  = [t for t in entity_txns if t["signed_amount_cents"] < 0]

    total_credit_cents = sum(t["signed_amount_cents"] for t in credits)
    total_debit_cents  = sum(abs(t["signed_amount_cents"]) for t in debits)

    # Entity type heuristic
    if total_credit_cents > total_debit_cents * 2:
        entity_type = "Revenue Source (Customer)"
        total_for_category_cents = sum(
            t["signed_amount_cents"] for t in tagged
            if t["role"] in ("revenue_operational", "revenue_non_operational")
            and t["signed_amount_cents"] > 0
        ) or 1
        pct_of_category = total_credit_cents / total_for_category_cents * 100
    elif total_debit_cents > total_credit_cents * 2:
        entity_type = "Supplier/Vendor"
        total_for_category_cents = sum(
            abs(t["signed_amount_cents"]) for t in tagged
            if t["role"] == "supplier_payment" and t["signed_amount_cents"] < 0
        ) or 1
        pct_of_category = total_debit_cents / total_for_category_cents * 100
    else:
        entity_type = "Mixed (Both Revenue and Expense)"
        total_for_category_cents = sum(abs(t["signed_amount_cents"]) for t in tagged) or 1
        pct_of_category = (total_credit_cents + total_debit_cents) / total_for_category_cents * 100

    dates = [t["txn_date"] for t in entity_txns if t["txn_date"]]
    first_seen = min(dates) if dates else None
    last_seen  = max(dates) if dates else None

    flagged_txns = [
        t for t in entity_txns
        if t.get("anomalies") or t["role"] in ("needs_review", "other")
    ]

    # Most recent 10 transactions
    recent = sorted(entity_txns, key=lambda x: x["txn_date"], reverse=True)[:10]
    formatted = []
    for t in recent:
        amt = t["signed_amount_cents"]
        formatted.append({
            "date": t["txn_date"],
            "amount_kes": amt / 100,
            "direction": "CREDIT" if amt > 0 else "DEBIT",
            "description": (t.get("description") or "")[:100],
            "role": t["role"],
            "flagged": bool(t.get("anomalies") or t["role"] in ("needs_review",)),
        })

    return {
        "found": True,
        "entity_name": entity_name,
        "entity_type": entity_type,
        "currency": currency,
        "profile": {
            "total_transactions": len(entity_txns),
            "credit_transactions": len(credits),
            "debit_transactions": len(debits),
            "total_credit_kes": round(total_credit_cents / 100, 2),
            "total_debit_kes": round(total_debit_cents / 100, 2),
            "avg_credit_kes": round(total_credit_cents / 100 / len(credits), 2) if credits else 0,
            "avg_debit_kes": round(total_debit_cents / 100 / len(debits), 2) if debits else 0,
            "pct_of_category": round(pct_of_category, 2),
            "first_seen": first_seen,
            "last_seen": last_seen,
            "flagged_transactions": len(flagged_txns),
        },
        "recent_transactions": formatted,
    }
