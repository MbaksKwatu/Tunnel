"""
Query and filter individual transactions from the deal snapshot.
Returns matching transactions with amounts, dates, descriptions, and reference codes.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


MAX_RESULTS = 50  # cap to prevent token explosion


def query_transactions(
    filters: Dict[str, Any],
    deal_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Filter transactions by role, amount range, entity, date range, or anomaly presence.
    Returns up to MAX_RESULTS transactions sorted by absolute amount descending.
    """
    tagged = deal_data["tagged"]
    currency = deal_data["currency"]

    role = filters.get("role")
    min_cents = filters.get("min_amount_cents")
    max_cents = filters.get("max_amount_cents")
    entity = filters.get("entity_name", "").lower() if filters.get("entity_name") else None
    date_from = filters.get("date_from")
    date_to = filters.get("date_to")
    has_anomalies = filters.get("has_anomalies")

    matches = []
    for t in tagged:
        amt_abs = abs(t["signed_amount_cents"])

        if role and t["role"] != role:
            continue
        if min_cents is not None and amt_abs < min_cents:
            continue
        if max_cents is not None and amt_abs > max_cents:
            continue
        if entity:
            name_match = entity in (t.get("entity_name") or "").lower()
            desc_match = entity in (t.get("description") or "").lower()
            if not name_match and not desc_match:
                continue
        if date_from and t["txn_date"] < date_from:
            continue
        if date_to and t["txn_date"] > date_to:
            continue
        if has_anomalies is True and not t.get("anomalies"):
            continue
        if has_anomalies is False and t.get("anomalies"):
            continue

        matches.append(t)

    # Sort by absolute amount descending (most material first)
    matches.sort(key=lambda t: abs(t["signed_amount_cents"]), reverse=True)

    total_matches = len(matches)
    total_amount_cents = sum(abs(t["signed_amount_cents"]) for t in matches)
    credit_count = sum(1 for t in matches if t["signed_amount_cents"] > 0)
    debit_count = sum(1 for t in matches if t["signed_amount_cents"] < 0)

    # Format top N results
    results = []
    for t in matches[:MAX_RESULTS]:
        amt = t["signed_amount_cents"]
        results.append({
            "txn_id": t["txn_id"],
            "date": t["txn_date"],
            "amount_kes": round(amt / 100, 2),
            "abs_amount_kes": round(abs(amt) / 100, 2),
            "direction": "CREDIT" if amt > 0 else "DEBIT",
            "role": t["role"],
            "entity_name": t.get("entity_name") or "",
            "description": (t.get("description") or "")[:120],
            "anomalies": t.get("anomalies") or [],
        })

    return {
        "currency": currency,
        "filters_applied": {k: v for k, v in filters.items() if v is not None},
        "total_matches": total_matches,
        "credits": credit_count,
        "debits": debit_count,
        "total_amount_kes": round(total_amount_cents / 100, 2),
        "showing": min(total_matches, MAX_RESULTS),
        "truncated": total_matches > MAX_RESULTS,
        "transactions": results,
    }
