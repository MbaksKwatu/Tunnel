"""
Response formatting utilities for Parity Review.
Visual indicators, structured data, and better markdown for tool results.
"""
from __future__ import annotations

from typing import Any, Dict, List


def format_metric_response(metric_name: str, result: Dict[str, Any]) -> str:
    output: List[str] = []
    output.append(f"## {metric_name}\n")

    assessment = result.get("assessment", "")
    indicator = _risk_indicator(assessment)
    output.append(f"{indicator} **{assessment}**\n")

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
    output.append(f"**Type:** {entity_result['entity_type']}\n")

    output.append("\n| Metric | Value |")
    output.append("|--------|-------|")
    output.append(f"| Total Transactions | {profile['total_transactions']} |")
    output.append(f"| Total Credits | {currency} {profile.get('total_credit_kes', 0):,.0f} |")
    output.append(f"| Total Debits | {currency} {profile.get('total_debit_kes', 0):,.0f} |")
    output.append(f"| % of Category | {profile['pct_of_category']:.1f}% |")
    output.append(f"| First Seen | {profile.get('first_seen', '—')} |")
    output.append(f"| Last Seen | {profile.get('last_seen', '—')} |\n")

    risk = entity_result.get("risk_assessment", "")
    if risk:
        indicator = "🔴" if "HIGH" in risk else "✅"
        output.append(f"{indicator} **Risk Assessment:** {risk}\n")

    recent = entity_result.get("recent_transactions", [])
    if recent:
        output.append("\n### Recent Transactions\n")
        for txn in recent[:5]:
            flag = " 🚩" if txn.get("flagged") else ""
            output.append(
                f"- {txn['date']}: {currency} {abs(txn['amount_kes']):,.0f} "
                f"({txn['direction']}){flag}"
            )

    return "\n".join(output)


def format_flag_explanation(flag_result: Dict[str, Any]) -> str:
    if not flag_result.get("flagged"):
        return f"✅ {flag_result.get('message', 'Not flagged')}"

    output: List[str] = []
    output.append(f"## 🚩 {flag_result['entity_name']} — Flagged for Review\n")

    anomalies = flag_result["anomalies_by_severity"]
    output.append(f"**Total Flagged Transactions:** {flag_result['total_flagged_transactions']}\n")

    output.append("**By Severity:**")
    if anomalies.get("critical", 0) > 0:
        output.append(f"- 🔴 **CRITICAL:** {anomalies['critical']}")
    if anomalies.get("high", 0) > 0:
        output.append(f"- ⚠️ **HIGH:** {anomalies['high']}")
    if anomalies.get("medium", 0) > 0:
        output.append(f"- ⚠️ **MEDIUM:** {anomalies['medium']}")
    output.append("")

    output.append(flag_result.get("explanation", ""))

    action = flag_result.get("recommended_action", "")
    if action:
        output.append(f"\n### 💡 Recommended Action\n{action}")

    return "\n".join(output)


def _risk_indicator(assessment: str) -> str:
    low = assessment.lower()
    if any(w in low for w in ("excellent", "strong", "good", "healthy", "stable")):
        return "✅"
    if any(w in low for w in ("acceptable", "moderate")):
        return "⚠️"
    if any(w in low for w in ("weak", "poor", "inadequate", "high risk", "high (", "declining")):
        return "🔴"
    return "ℹ️"


def _format_value(value: float, unit: str = "") -> str:
    if unit == "%":
        return f"{value:.1f}%"
    if unit in ("KES", "currency"):
        return f"KES {value:,.0f}"
    if unit == "ratio":
        return f"{value:.2f}"
    return f"{value:,.2f}"
