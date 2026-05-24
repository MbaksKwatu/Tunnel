"""
Explain why transactions or entities are flagged for review.
"""
from __future__ import annotations

from typing import Any, Dict, List


_REVIEW_ROLES = frozenset({"needs_review", "other"})


def explain_flagged_item(entity_name: str, deal_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Explain why an entity is flagged. Works from roles and anomaly annotations.
    """
    tagged       = deal_data["tagged"]
    entity_names = deal_data["entity_names"]
    currency     = deal_data["currency"]

    name_lower = entity_name.lower()

    # Match on entity name or description
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
            "flagged": False,
            "message": f"'{entity_name}' not found in transactions",
            "note": "Check the exact entity name in top_suppliers or top_revenue.",
        }

    # Flagged = role is needs_review/other OR has anomalies annotation
    flagged_txns = [
        t for t in entity_txns
        if t["role"] in _REVIEW_ROLES or t.get("anomalies")
    ]

    if not flagged_txns:
        return {
            "flagged": False,
            "message": f"'{entity_name}' has no flagged transactions",
            "note": f"All {len(entity_txns)} transactions are classified — role: {entity_txns[0]['role'] if entity_txns else 'unknown'}",
        }

    # Collect anomaly annotations
    all_anomalies: List[Dict] = []
    for t in flagged_txns:
        for a in (t.get("anomalies") or []):
            all_anomalies.append({
                "transaction_date": t["txn_date"],
                "amount_kes": t["signed_amount_cents"] / 100,
                "type": a.get("type"),
                "severity": a.get("severity"),
                "reason": a.get("reason"),
            })
        # If no anomaly annotation but role is review, create implicit entry
        if not t.get("anomalies") and t["role"] in _REVIEW_ROLES:
            all_anomalies.append({
                "transaction_date": t["txn_date"],
                "amount_kes": t["signed_amount_cents"] / 100,
                "type": "UNCLASSIFIED",
                "severity": "HIGH",
                "reason": f"Transaction role is '{t['role']}'",
            })

    critical = [a for a in all_anomalies if a.get("severity") == "CRITICAL"]
    high     = [a for a in all_anomalies if a.get("severity") == "HIGH"]
    medium   = [a for a in all_anomalies if a.get("severity") == "MEDIUM"]
    low      = [a for a in all_anomalies if a.get("severity") == "LOW"]

    # Entity context
    credits = [t for t in entity_txns if t["signed_amount_cents"] > 0]
    debits  = [t for t in entity_txns if t["signed_amount_cents"] < 0]
    history = {
        "total_transactions": len(entity_txns),
        "credit_count": len(credits),
        "debit_count": len(debits),
        "total_credit_kes": sum(t["signed_amount_cents"] for t in credits) / 100,
        "total_debit_kes": sum(abs(t["signed_amount_cents"]) for t in debits) / 100,
    }

    explanation = _generate_explanation(entity_name, critical, high, medium, low, history, flagged_txns, currency)

    return {
        "flagged": True,
        "entity_name": entity_name,
        "total_flagged_transactions": len(flagged_txns),
        "anomalies_by_severity": {
            "critical": len(critical),
            "high": len(high),
            "medium": len(medium),
            "low": len(low),
        },
        "detailed_anomalies": all_anomalies,
        "entity_context": history,
        "explanation": explanation,
    }


def _generate_explanation(
    entity_name: str,
    critical: List[Dict],
    high: List[Dict],
    medium: List[Dict],
    low: List[Dict],
    history: Dict,
    flagged_txns: List[Dict],
    currency: str,
) -> str:
    parts = [
        f"**{entity_name}** has {len(flagged_txns)} flagged transaction(s)."
    ]

    if critical:
        parts.append(f"\n**CRITICAL ({len(critical)}):**")
        for c in critical[:3]:
            amt = abs(c.get("amount_kes", 0))
            parts.append(f"- {c.get('reason')} ({currency} {amt:,.0f} on {c.get('transaction_date')})")

    if high:
        parts.append(f"\n**HIGH PRIORITY ({len(high)}):**")
        for h in high[:3]:
            amt = abs(h.get("amount_kes", 0))
            parts.append(f"- {h.get('reason')} ({currency} {amt:,.0f})")

    parts.append(f"\n**ENTITY CONTEXT:**")
    parts.append(f"- Total transactions: {history['total_transactions']}")
    parts.append(f"- Credits: {history['credit_count']} txns, {currency} {history['total_credit_kes']:,.0f}")
    parts.append(f"- Debits: {history['debit_count']} txns, {currency} {history['total_debit_kes']:,.0f}")

    return "\n".join(parts)


