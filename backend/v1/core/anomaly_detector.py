"""
Anomaly detection for transactions — runs after classification.

Detects capital injections, entity amount spikes, and statistically
unusual transactions relative to the business's own baseline.

Operates entirely on already-classified transactions; does not change roles.
Results are stored in tx["anomalies"] as a list of flag dicts.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple


# ── Thresholds (all tunable) ──────────────────────────────────────────────────

# Fraction of avg monthly inflow that makes a single transaction "extremely large"
_CRITICAL_MONTHLY_PCT = 0.50

# Fraction of avg monthly inflow that makes a transaction worth flagging
_HIGH_MONTHLY_PCT = 0.15

# Multiple of avg daily inflow that triggers a daily-pattern flag
_DAILY_SPIKE_MULTIPLIER = 10

# Minimum absolute amount (cents) before any size-based flag fires
_MIN_FLAG_AMOUNT_CENTS = 50_000_00  # KES 500K

# Entities with ≤ this many transactions are considered "rare"
_RARE_ENTITY_MAX_TXNS = 2

# Multiple of an entity's own average that triggers a spike flag
_ENTITY_SPIKE_MULTIPLIER = 3

# Single transaction representing ≥ this % of total outflows = concentration flag
_SUPPLIER_CONCENTRATION_PCT = 5.0

# Minimum amount and divisor for round-number flag
_ROUND_NUMBER_MIN_CENTS = 100_000_000   # KES 1M (100M cents)
_ROUND_NUMBER_MODULO_CENTS = 10_000_000  # divisible by KES 100K (10M cents)


# ── Business context ──────────────────────────────────────────────────────────

def _parse_date(d: str) -> Optional[datetime]:
    if not d:
        return None
    try:
        return datetime.strptime(d, "%Y-%m-%d")
    except ValueError:
        return None


def calculate_business_context(transactions: List[Dict]) -> Dict:
    """
    Aggregate baseline metrics across all transactions.
    Called once per analysis run; result is passed to detect_anomalies().
    """
    credits = [t for t in transactions if int(t.get("signed_amount_cents", 0)) > 0 and not t.get("is_transfer")]
    debits  = [t for t in transactions if int(t.get("signed_amount_cents", 0)) < 0 and not t.get("is_transfer")]

    total_inflow  = sum(int(t["signed_amount_cents"]) for t in credits)
    total_outflow = sum(abs(int(t["signed_amount_cents"])) for t in debits)

    # Monthly buckets (YYYY-MM keys)
    monthly_inflow: Dict[str, int] = defaultdict(int)
    daily_inflow:   Dict[str, int] = defaultdict(int)
    for t in credits:
        d = t.get("txn_date", "")
        if d:
            monthly_inflow[d[:7]] += int(t["signed_amount_cents"])
            daily_inflow[d]        += int(t["signed_amount_cents"])

    monthly_values = list(monthly_inflow.values())
    daily_values   = list(daily_inflow.values())

    avg_monthly = statistics.mean(monthly_values) if monthly_values else 0
    avg_daily   = statistics.mean(daily_values)   if daily_values   else 0

    return {
        "avg_monthly_inflow_cents": avg_monthly,
        "avg_daily_inflow_cents": avg_daily,
        "total_inflow_cents": total_inflow,
        "total_outflow_cents": total_outflow,
    }


# ── Entity history ────────────────────────────────────────────────────────────

def build_entity_history(transactions: List[Dict], entity_display_map: Dict[str, str]) -> Dict[str, Dict]:
    """
    Group transactions by display_name and compute per-entity statistics.

    entity_display_map: txn_id -> display_name (built from pipeline entity data).
    Returns: display_name -> history dict.
    """
    groups: Dict[str, List[Dict]] = defaultdict(list)
    for t in transactions:
        if t.get("is_transfer"):
            continue
        name = entity_display_map.get(t.get("txn_id", ""), "")
        if name:
            groups[name].append(t)

    history = {}
    for name, txns in groups.items():
        amounts = [abs(int(t["signed_amount_cents"])) for t in txns]
        credits_count = sum(1 for t in txns if int(t["signed_amount_cents"]) > 0)
        debits_count  = sum(1 for t in txns if int(t["signed_amount_cents"]) < 0)
        history[name] = {
            "total_transactions": len(txns),
            "avg_amount_cents": statistics.mean(amounts) if amounts else 0,
            "total_amount_cents": sum(amounts),
            "credit_count": credits_count,
            "debit_count": debits_count,
        }
    return history


# ── Single-transaction anomaly check ─────────────────────────────────────────

def detect_anomalies(
    txn: Dict,
    business_context: Dict,
    entity_hist: Dict,
) -> List[Dict]:
    """
    Returns a list of anomaly flag dicts for one transaction.
    Each flag has: type, severity, reason.
    Empty list means no anomalies.

    entity_hist: the history dict for this transaction's entity
                 (from build_entity_history output).
    """
    anomalies: List[Dict] = []
    amt = abs(int(txn.get("signed_amount_cents", 0)))
    is_credit = int(txn.get("signed_amount_cents", 0)) > 0

    if amt == 0 or txn.get("is_transfer"):
        return anomalies

    avg_monthly = business_context["avg_monthly_inflow_cents"]
    avg_daily   = business_context["avg_daily_inflow_cents"]
    total_outflow = business_context["total_outflow_cents"]

    # ── Rule 1: Extremely large relative to monthly scale ─────────────────────
    if avg_monthly > 0 and amt >= avg_monthly * _CRITICAL_MONTHLY_PCT and amt >= _MIN_FLAG_AMOUNT_CENTS:
        pct = amt / avg_monthly * 100
        anomalies.append({
            "type": "EXTREMELY_LARGE_TRANSACTION",
            "severity": "CRITICAL",
            "reason": f"Amount is {pct:.1f}% of avg monthly inflow",
        })

    # ── Rule 2: Large relative to monthly scale (HIGH, not already CRITICAL) ──
    elif avg_monthly > 0 and amt >= avg_monthly * _HIGH_MONTHLY_PCT and amt >= _MIN_FLAG_AMOUNT_CENTS:
        pct = amt / avg_monthly * 100
        anomalies.append({
            "type": "LARGE_TRANSACTION",
            "severity": "HIGH",
            "reason": f"Amount is {pct:.1f}% of avg monthly inflow",
        })

    # ── Rule 3: Daily pattern spike ───────────────────────────────────────────
    if avg_daily > 0 and amt >= avg_daily * _DAILY_SPIKE_MULTIPLIER and amt >= _MIN_FLAG_AMOUNT_CENTS:
        mult = amt / avg_daily
        anomalies.append({
            "type": "DAILY_PATTERN_ANOMALY",
            "severity": "MEDIUM",
            "reason": f"Transaction is {mult:.1f}x typical daily inflow volume",
        })

    # ── Rule 4: New entity with large amount ──────────────────────────────────
    total_txns = entity_hist.get("total_transactions", 0)
    if total_txns <= _RARE_ENTITY_MAX_TXNS and amt >= _MIN_FLAG_AMOUNT_CENTS:
        anomalies.append({
            "type": "NEW_ENTITY_LARGE_AMOUNT",
            "severity": "HIGH",
            "reason": f"Large amount from entity with only {total_txns} transaction(s) total",
        })

    # ── Rule 5: Possible capital injection (inflows only) ────────────────────
    if is_credit:
        is_large = avg_monthly > 0 and amt >= avg_monthly * _HIGH_MONTHLY_PCT and amt >= _MIN_FLAG_AMOUNT_CENTS
        is_rare  = total_txns <= _RARE_ENTITY_MAX_TXNS
        no_repayments = entity_hist.get("debit_count", 0) == 0

        if is_large and is_rare and no_repayments:
            anomalies.append({
                "type": "POSSIBLE_CAPITAL_INJECTION",
                "severity": "CRITICAL",
                "reason": (
                    f"Large inflow from rare entity ({total_txns} txn(s)) "
                    "with no reciprocal outflows — may be capital injection or one-off loan"
                ),
            })

    # ── Rule 6: Supplier concentration (outflows only) ────────────────────────
    if not is_credit and total_outflow > 0:
        pct = amt / total_outflow * 100
        if pct >= _SUPPLIER_CONCENTRATION_PCT:
            anomalies.append({
                "type": "HIGH_SUPPLIER_CONCENTRATION",
                "severity": "MEDIUM",
                "reason": f"Single transaction = {pct:.1f}% of total business outflows",
            })

    # ── Rule 7: Entity amount spike ───────────────────────────────────────────
    avg_entity = entity_hist.get("avg_amount_cents", 0)
    if total_txns > _RARE_ENTITY_MAX_TXNS and avg_entity > 0 and amt >= avg_entity * _ENTITY_SPIKE_MULTIPLIER:
        mult = amt / avg_entity
        anomalies.append({
            "type": "ENTITY_AMOUNT_SPIKE",
            "severity": "MEDIUM",
            "reason": f"Transaction is {mult:.1f}x this entity's typical amount",
        })

    # ── Rule 8: Suspiciously round large number ───────────────────────────────
    if amt >= _ROUND_NUMBER_MIN_CENTS and amt % _ROUND_NUMBER_MODULO_CENTS == 0:
        anomalies.append({
            "type": "ROUND_NUMBER_LARGE_AMOUNT",
            "severity": "LOW",
            "reason": "Perfectly round large amount — may be capital injection or estimate",
        })

    return anomalies


# ── Batch annotator ───────────────────────────────────────────────────────────

def annotate_anomalies(
    transactions: List[Dict],
    entity_display_map: Dict[str, str],
) -> None:
    """
    Annotate each transaction in-place with tx["anomalies"].
    Modifies the list elements; returns nothing.

    entity_display_map: txn_id -> display_name
    """
    context = calculate_business_context(transactions)
    entity_history = build_entity_history(transactions, entity_display_map)

    for tx in transactions:
        name = entity_display_map.get(tx.get("txn_id", ""), "")
        hist = entity_history.get(name, {
            "total_transactions": 0,
            "avg_amount_cents": 0,
            "total_amount_cents": 0,
            "credit_count": 0,
            "debit_count": 0,
        })
        tx["anomalies"] = detect_anomalies(tx, context, hist)
