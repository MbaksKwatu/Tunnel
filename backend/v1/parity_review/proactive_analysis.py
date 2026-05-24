"""
Generate proactive data summary when Parity Review chat first opens.
Pure computation — returns figures, counts, and breakdowns with no interpretation.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .tools.financial_metrics import calculate_financial_metrics
from .tools.operational_metrics import calculate_operational_metrics


_REVIEW_ROLES = frozenset({"needs_review", "other"})
_SUPPLIER_ROLES = frozenset({"supplier", "supplier_payment"})
_REVENUE_ROLES = frozenset({"revenue_operational", "revenue_other"})


def generate_proactive_analysis(deal_data: Dict[str, Any]) -> str:
    financial = calculate_financial_metrics(deal_data)
    operational = calculate_operational_metrics(deal_data)

    sections: List[str] = []

    company_name = (
        deal_data.get("canonical", {}).get("company_name")
        or deal_data.get("canonical", {}).get("deal_name")
        or "this deal"
    )
    currency = deal_data.get("currency", "KES")
    sections.append(f"**{company_name}** — Snapshot Data Summary\n")

    sections.append(_format_deal_overview(deal_data, currency))
    sections.append(_format_financial_metrics(financial, currency))
    sections.append(_format_top_entities(deal_data, currency))
    sections.append(_format_unclassified_summary(deal_data, currency))
    sections.append("---\n\nAsk a question to query the data.")

    return "\n".join(sections)


def _format_deal_overview(deal_data: Dict[str, Any], currency: str) -> str:
    tagged = deal_data.get("tagged", [])
    total_txns = len(tagged)
    n_months = deal_data.get("n_months", 0)

    credits = [t for t in tagged if t.get("signed_amount_cents", 0) > 0]
    debits = [t for t in tagged if t.get("signed_amount_cents", 0) < 0]
    total_inflow = sum(t["signed_amount_cents"] for t in credits) / 100
    total_outflow = sum(abs(t["signed_amount_cents"]) for t in debits) / 100

    review_count = sum(1 for t in tagged if t.get("role") in _REVIEW_ROLES)

    lines = [
        "## DEAL OVERVIEW\n",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Transactions | {total_txns:,} |",
        f"| Period | {n_months} months |",
        f"| Total inflow | {currency} {total_inflow:,.2f} |",
        f"| Total outflow | {currency} {total_outflow:,.2f} |",
        f"| Net cash flow | {currency} {total_inflow - total_outflow:,.2f} |",
        f"| Unclassified | {review_count} transactions |",
        "",
    ]
    return "\n".join(lines)


def _format_financial_metrics(financial: Dict[str, Any], currency: str) -> str:
    lines = ["## COMPUTED METRICS\n"]

    rows = []
    dscr = financial.get("dscr", {})
    if dscr.get("value") is not None:
        rows.append(f"| DSCR | {dscr['value']:.2f} |")

    growth = financial.get("revenue_growth", {})
    if growth.get("value_pct") is not None:
        rows.append(f"| Revenue growth (H1 vs H2) | {growth['value_pct']:.1f}% |")

    volatility = financial.get("cash_flow_volatility", {})
    cv = volatility.get("value_pct")
    if cv is not None:
        rows.append(f"| Cash flow CV | {cv:.1f}% |")

    burden = financial.get("loan_burden", {})
    if burden.get("value_pct") is not None:
        rows.append(f"| Loan repayment / total outflow | {burden['value_pct']:.1f}% |")

    burn = financial.get("burn_rate", {})
    neg = burn.get("negative_months", 0)
    total = burn.get("total_months", 0)
    if total > 0:
        rows.append(f"| Months with negative cash flow | {neg} / {total} |")

    if rows:
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.extend(rows)
    else:
        lines.append("No financial metrics computed.")

    lines.append("")
    return "\n".join(lines)


def _format_top_entities(deal_data: Dict[str, Any], currency: str) -> str:
    tagged = deal_data.get("tagged", [])

    supplier_totals: Dict[str, int] = {}
    revenue_totals: Dict[str, int] = {}

    for t in tagged:
        name = t.get("entity_name") or t.get("description") or "Unknown"
        role = t.get("role", "")
        amt = abs(t.get("signed_amount_cents", 0))
        if role in _SUPPLIER_ROLES:
            supplier_totals[name] = supplier_totals.get(name, 0) + amt
        elif role in _REVENUE_ROLES:
            revenue_totals[name] = revenue_totals.get(name, 0) + amt

    lines = ["## TOP ENTITIES\n"]

    top_suppliers = sorted(supplier_totals.items(), key=lambda x: x[1], reverse=True)[:10]
    if top_suppliers:
        lines.append("**Suppliers (by total amount)**\n")
        lines.append("| # | Entity | Amount |")
        lines.append("|---|--------|--------|")
        for i, (name, cents) in enumerate(top_suppliers, 1):
            lines.append(f"| {i} | {name[:50]} | {currency} {cents / 100:,.2f} |")
        lines.append("")

    top_revenue = sorted(revenue_totals.items(), key=lambda x: x[1], reverse=True)[:10]
    if top_revenue:
        lines.append("**Revenue sources (by total amount)**\n")
        lines.append("| # | Entity | Amount |")
        lines.append("|---|--------|--------|")
        for i, (name, cents) in enumerate(top_revenue, 1):
            lines.append(f"| {i} | {name[:50]} | {currency} {cents / 100:,.2f} |")
        lines.append("")

    return "\n".join(lines)


def _format_unclassified_summary(deal_data: Dict[str, Any], currency: str) -> str:
    tagged = deal_data.get("tagged", [])
    review_txns = [t for t in tagged if t.get("role") in _REVIEW_ROLES]

    if not review_txns:
        return "## UNCLASSIFIED TRANSACTIONS\n\nNone.\n"

    total_amt = sum(abs(t.get("signed_amount_cents", 0)) for t in review_txns) / 100

    entity_counts: Dict[str, int] = {}
    for t in review_txns:
        name = t.get("entity_name") or t.get("description") or "Unknown"
        entity_counts[name] = entity_counts.get(name, 0) + 1

    top_unclassified = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    lines = [
        "## UNCLASSIFIED TRANSACTIONS\n",
        f"**Count:** {len(review_txns)} transactions",
        f"**Total amount:** {currency} {total_amt:,.2f}\n",
    ]

    if top_unclassified:
        lines.append("| Entity | Transactions |")
        lines.append("|--------|-------------|")
        for name, count in top_unclassified:
            lines.append(f"| {name[:50]} | {count} |")
        lines.append("")

    return "\n".join(lines)
