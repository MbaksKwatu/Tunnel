"""
Analyst enrichment engine.

Computes enriched hashes and evaluates custom threshold flags against
a base snapshot's canonical analytics. All base snapshot data is read-only.
"""

import hashlib
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def compute_enriched_hash(
    base_snapshot_hash: str,
    overrides: List[Dict[str, Any]],
    flags: List[Dict[str, Any]],
    narrative: str,
) -> str:
    """
    Deterministic hash of (base + analyst additions).
    Same inputs always yield the same enriched_hash.
    """
    payload = {
        "base_snapshot_hash": base_snapshot_hash,
        "classification_overrides": sorted(overrides, key=lambda o: o.get("txn_id", "")),
        "custom_flags": sorted(flags, key=lambda f: f.get("flag_name", "")),
        "narrative": narrative or "",
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def evaluate_threshold_flag(flag_def: Dict[str, Any], base_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate a threshold flag against the base snapshot's canonical_json data.

    Returns a dict with keys: triggered, trigger_count, trigger_details.
    """
    criteria = flag_def.get("criteria", {})
    metric = criteria.get("metric", "")
    threshold_cents = criteria.get("threshold_cents", 0)
    comparison = criteria.get("comparison", "less_than")

    import json as _json
    canonical_raw = base_snapshot.get("canonical_json") or "{}"
    try:
        data = _json.loads(canonical_raw) if isinstance(canonical_raw, str) else canonical_raw
    except Exception:
        logger.warning("[ENRICHMENT] Could not parse canonical_json for flag evaluation")
        return {"triggered": False, "trigger_count": 0, "trigger_details": []}

    metrics = data.get("metrics", {})
    transactions = data.get("transactions", [])

    if metric == "closing_balance":
        monthly = _extract_monthly_balances(transactions)
        breaches = _apply_comparison(monthly, "balance_cents", comparison, threshold_cents)
        return {
            "triggered": len(breaches) > 0,
            "trigger_count": len(breaches),
            "trigger_details": breaches,
        }

    if metric == "overdraft_days":
        days_negative = [
            {"date": t["txn_date"], "balance_cents": t.get("running_balance_cents", 0)}
            for t in transactions
            if t.get("running_balance_cents", 0) < 0
        ]
        return {
            "triggered": len(days_negative) > 0,
            "trigger_count": len(days_negative),
            "trigger_details": days_negative[:50],
        }

    if metric == "single_transaction_amount":
        breaches = []
        for t in transactions:
            amt = abs(t.get("signed_amount_cents", 0))
            if _compare(amt, comparison, threshold_cents):
                breaches.append({"txn_id": t.get("txn_id"), "amount_cents": amt, "date": t.get("txn_date")})
        return {
            "triggered": len(breaches) > 0,
            "trigger_count": len(breaches),
            "trigger_details": breaches[:50],
        }

    # Unknown metric — return not triggered with a warning
    logger.warning("[ENRICHMENT] Unknown flag metric: %s", metric)
    return {"triggered": False, "trigger_count": 0, "trigger_details": []}


def build_enrichment_record(
    *,
    base_snapshot_id: str,
    base_snapshot_hash: str,
    analyst_id: str,
    analyst_name: Optional[str],
    overrides: List[Dict[str, Any]],
    flags: List[Dict[str, Any]],
    narrative: str,
    enrichment_reason: str,
    is_final: bool,
) -> Dict[str, Any]:
    enriched_hash = compute_enriched_hash(base_snapshot_hash, overrides, flags, narrative)
    return {
        "id": str(uuid.uuid4()),
        "base_snapshot_id": base_snapshot_id,
        "enriched_hash": enriched_hash,
        "analyst_id": analyst_id,
        "analyst_name": analyst_name,
        "narrative": narrative,
        "enrichment_reason": enrichment_reason,
        "is_final": is_final,
    }


def build_override_records(
    enrichment_id: str,
    overrides: List[Dict[str, Any]],
    analyst_id: str,
) -> List[Dict[str, Any]]:
    records = []
    for o in overrides:
        records.append({
            "id": str(uuid.uuid4()),
            "enrichment_id": enrichment_id,
            "txn_id": o["txn_id"],
            "original_role": o["original_role"],
            "original_reason": o.get("original_reason"),
            "override_role": o["override_role"],
            "override_reason": o["override_reason"],
            "overridden_by": analyst_id,
        })
    return records


def build_flag_records(
    enrichment_id: str,
    flags: List[Dict[str, Any]],
    analyst_id: str,
) -> List[Dict[str, Any]]:
    records = []
    for f in flags:
        records.append({
            "id": str(uuid.uuid4()),
            "enrichment_id": enrichment_id,
            "flag_type": f["flag_type"],
            "flag_name": f["flag_name"],
            "flag_severity": f["flag_severity"],
            "flag_description": f["flag_description"],
            "criteria": f["criteria"],
            "triggered": f.get("triggered", False),
            "trigger_count": f.get("trigger_count", 0),
            "trigger_details": f.get("trigger_details", []),
            "created_by": analyst_id,
        })
    return records


# ── internal helpers ──────────────────────────────────────────────────────────

def _extract_monthly_balances(transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Derive approximate month-end closing balances from sorted transactions."""
    by_month: Dict[str, int] = {}
    for t in sorted(transactions, key=lambda x: x.get("txn_date", "")):
        month = (t.get("txn_date") or "")[:7]  # "YYYY-MM"
        if month:
            by_month[month] = by_month.get(month, 0) + t.get("signed_amount_cents", 0)
    return [{"month": m, "balance_cents": v} for m, v in sorted(by_month.items())]


def _apply_comparison(
    rows: List[Dict[str, Any]],
    value_key: str,
    comparison: str,
    threshold: int,
) -> List[Dict[str, Any]]:
    return [r for r in rows if _compare(r.get(value_key, 0), comparison, threshold)]


def _compare(value: int, comparison: str, threshold: int) -> bool:
    if comparison == "less_than":
        return value < threshold
    if comparison == "greater_than":
        return value > threshold
    if comparison == "less_than_or_equal":
        return value <= threshold
    if comparison == "greater_than_or_equal":
        return value >= threshold
    return False
