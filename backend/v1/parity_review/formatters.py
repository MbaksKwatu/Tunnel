"""
Response formatting utilities for Parity Review.
Structured data and markdown tables for tool results. No interpretation or assessment.
"""
from __future__ import annotations

from typing import Any, Dict, List


def format_metric_response(metric_name: str, result: Dict[str, Any]) -> str:
    output: List[str] = []
    output.append(f"## {metric_name}\n")

    value = result.get("value") or result.get("value_pct")
    if value is not None:
        unit = result.get("unit", "")
        output.append(f"**Value:** {_format_value(value, unit)}\n")

    calculation = result.get("calculation")
    if calculation:
        output.append(f"**Calculation:** `{calculation}`\n")

    ctx = result.get("context")
    if ctx:
        output.append(f"\n{ctx}\n")

    return "\n".join(output)


def format_entity_profile(entity_result: Dict[str, Any]) -> str:
    if not entity_result.get("found"):
        return entity_result.get("message", "Entity not found")

    profile = entity_result["profile"]
    currency = entity_result.get("currency", "KES")

    output: List[str] = []
    output.append(f"## {entity_result['entity_name']}\n")
    output.append(f"**Classification:** {entity_result['entity_type']}\n")

    output.append("\n| Metric | Value |")
    output.append("|--------|-------|")
    output.append(f"| Total Transactions | {profile['total_transactions']} |")
    output.append(f"| Total Credits | {currency} {profile.get('total_credit_kes', 0):,.0f} |")
    output.append(f"| Total Debits | {currency} {profile.get('total_debit_kes', 0):,.0f} |")
    output.append(f"| % of Category | {profile['pct_of_category']:.1f}% |")
    output.append(f"| First Seen | {profile.get('first_seen', '—')} |")
    output.append(f"| Last Seen | {profile.get('last_seen', '—')} |\n")

    recent = entity_result.get("recent_transactions", [])
    if recent:
        output.append("\n### Transaction History\n")
        output.append("| Date | Amount | Direction |")
        output.append("|------|--------|-----------|")
        for txn in recent[:10]:
            output.append(
                f"| {txn['date']} | {currency} {abs(txn['amount_kes']):,.0f} | {txn['direction']} |"
            )

    return "\n".join(output)


def format_flag_explanation(flag_result: Dict[str, Any]) -> str:
    if not flag_result.get("flagged"):
        return flag_result.get("message", "Not flagged")

    output: List[str] = []
    output.append(f"## {flag_result['entity_name']} — Flagged Transactions\n")

    output.append(f"**Flagged transaction count:** {flag_result['total_flagged_transactions']}\n")

    anomalies = flag_result["anomalies_by_severity"]
    output.append("| Severity | Count |")
    output.append("|----------|-------|")
    for level in ("critical", "high", "medium", "low"):
        count = anomalies.get(level, 0)
        if count > 0:
            output.append(f"| {level.upper()} | {count} |")
    output.append("")

    explanation = flag_result.get("explanation", "")
    if explanation:
        output.append(explanation)

    return "\n".join(output)


def _format_value(value: float, unit: str = "") -> str:
    if unit == "%":
        return f"{value:.1f}%"
    if unit in ("KES", "currency"):
        return f"KES {value:,.0f}"
    if unit == "ratio":
        return f"{value:.2f}"
    return f"{value:,.2f}"
