"""
Generate proactive analysis when Parity Review chat first opens.
Surfaces key insights without waiting for user questions.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .tools.financial_metrics import calculate_financial_metrics
from .tools.operational_metrics import calculate_operational_metrics


_REVIEW_ROLES = frozenset({"needs_review", "other"})


def generate_proactive_analysis(deal_data: Dict[str, Any]) -> str:
    financial = calculate_financial_metrics(deal_data)
    operational = calculate_operational_metrics(deal_data)

    critical_issues = _identify_critical_issues(deal_data, financial, operational)
    risks = _identify_key_risks(deal_data, operational)
    strengths = _identify_strengths(deal_data, financial, operational)
    recommendations = _generate_recommendations(critical_issues, risks)

    sections: List[str] = []

    company_name = (
        deal_data.get("canonical", {}).get("company_name")
        or deal_data.get("canonical", {}).get("deal_name")
        or "this company"
    )
    sections.append(f"I've analyzed **{company_name}**'s snapshot. Here are the key findings:\n")

    if critical_issues:
        sections.append(f"## 🔴 CRITICAL ISSUES ({len(critical_issues)})\n")
        for issue in critical_issues:
            sections.append(f"• {issue}\n")
        sections.append("")

    if risks:
        sections.append("## ⚠️ KEY RISKS\n")
        for risk in risks:
            sections.append(f"• {risk}\n")
        sections.append("")

    if strengths:
        sections.append("## ✅ STRENGTHS\n")
        for s in strengths:
            sections.append(f"• {s}\n")
        sections.append("")

    sections.append("## 📊 FINANCIAL SUMMARY\n")
    sections.append(_format_financial_summary(financial))
    sections.append("")

    if recommendations:
        sections.append("## 💡 RECOMMENDATIONS\n")
        for rec in recommendations:
            sections.append(f"• {rec}\n")
        sections.append("")

    sections.append("---\n\nWhat would you like to explore further?")
    return "\n".join(sections)


def _identify_critical_issues(
    deal_data: Dict[str, Any],
    financial: Dict[str, Any],
    operational: Dict[str, Any],
) -> List[str]:
    issues: List[str] = []
    currency = deal_data.get("currency", "KES")

    rev_growth_pct = financial.get("revenue_growth", {}).get("value_pct")
    if rev_growth_pct is not None and rev_growth_pct < -20:
        issues.append(f"Revenue declined {abs(rev_growth_pct):.1f}% year-over-year — needs explanation")

    dscr = financial.get("dscr", {}).get("value")
    if dscr is not None and dscr < 1.25:
        issues.append(f"DSCR of {dscr:.2f} is below recommended 1.25 threshold — debt service capacity concern")

    tagged = deal_data.get("tagged", [])
    review_count = sum(1 for t in tagged if t.get("role") in _REVIEW_ROLES)
    total_txns = len(tagged) or 1
    flagged_pct = (review_count / total_txns) * 100

    if flagged_pct > 20:
        issues.append(
            f"{review_count} transactions ({flagged_pct:.1f}%) need classification — high data quality issue"
        )

    for t in tagged:
        for a in t.get("anomalies") or []:
            if a.get("severity") == "CRITICAL":
                entity_name = t.get("entity_name") or "Unknown"
                amt_kes = abs(t.get("signed_amount_cents", 0)) / 100
                reason = (a.get("type") or "unknown").replace("_", " ").lower()
                issues.append(f"{entity_name}: {currency} {amt_kes:,.0f} flagged as {reason}")
                if len(issues) >= 5:
                    return issues

    burn = financial.get("burn_rate", {})
    negative_months = burn.get("negative_months", 0)
    total_months = burn.get("total_months", 0) or deal_data.get("n_months", 12)
    if total_months > 0 and negative_months > total_months / 3:
        issues.append(
            f"{negative_months}/{total_months} months had negative cash flow — liquidity concern"
        )

    return issues


def _identify_key_risks(
    deal_data: Dict[str, Any],
    operational: Dict[str, Any],
) -> List[str]:
    risks: List[str] = []

    cust = operational.get("customer_concentration", {})
    top_cust_pct = cust.get("top_customer_pct")
    top_cust_name = cust.get("top_customer_name")
    if top_cust_pct and top_cust_pct > 25:
        risks.append(
            f"**{top_cust_name}** represents {top_cust_pct:.1f}% of revenue (HIGH customer concentration)"
        )
    elif top_cust_pct and top_cust_pct > 15:
        risks.append(
            f"**{top_cust_name}** represents {top_cust_pct:.1f}% of revenue (moderate concentration)"
        )

    sup = operational.get("supplier_concentration", {})
    top_sup_pct = sup.get("top_supplier_pct")
    top_sup_name = sup.get("top_supplier_name")
    if top_sup_pct and top_sup_pct > 20:
        risks.append(
            f"**{top_sup_name}** represents {top_sup_pct:.1f}% of costs (supplier concentration)"
        )

    wc = operational.get("working_capital_trend", {})
    if wc.get("assessment") == "Deteriorating":
        risks.append("Working capital deteriorating over the period — operational strain")

    payroll = operational.get("payroll_stability", {})
    payroll_assessment = payroll.get("assessment", "")
    if "Minimal" in payroll_assessment or "Sparse" in payroll_assessment:
        risks.append(f"Limited formal payroll detected — {payroll_assessment.lower()}")

    return risks


def _identify_strengths(
    deal_data: Dict[str, Any],
    financial: Dict[str, Any],
    operational: Dict[str, Any],
) -> List[str]:
    strengths: List[str] = []

    dscr = financial.get("dscr", {}).get("value")
    if dscr and dscr >= 1.5:
        strengths.append(f"DSCR: {dscr:.2f} (strong debt service capacity — above 1.5 threshold)")
    elif dscr and dscr >= 1.25:
        strengths.append(f"DSCR: {dscr:.2f} (acceptable debt service capacity)")

    loan_burden_pct = financial.get("loan_burden", {}).get("value_pct", 0)
    if loan_burden_pct < 5:
        strengths.append(f"Loan burden: {loan_burden_pct:.1f}% of outflows (low debt load)")

    rev_growth_pct = financial.get("revenue_growth", {}).get("value_pct")
    if rev_growth_pct is not None and rev_growth_pct > 15:
        strengths.append(f"Revenue growth: {rev_growth_pct:.1f}% (strong growth trajectory)")
    elif rev_growth_pct is not None and rev_growth_pct > 0:
        strengths.append(f"Revenue growth: {rev_growth_pct:.1f}% (positive growth)")

    volatility = financial.get("cash_flow_volatility", {})
    if volatility.get("assessment") == "Stable (<25%)":
        strengths.append("Stable cash flows — predictable revenue pattern")

    cust = operational.get("customer_concentration", {})
    top_cust_pct = cust.get("top_customer_pct")
    if top_cust_pct and top_cust_pct < 15:
        strengths.append(
            f"Diversified customer base — top customer only {top_cust_pct:.1f}% of revenue"
        )

    csi = deal_data.get("csi", {})
    metrics = deal_data.get("metrics", {})
    kra = csi.get("kra_compliance") or metrics.get("kra_compliance")
    if kra and kra.upper() == "COMPLIANT":
        tax_months = deal_data.get("tax_months", 0)
        strengths.append(f"Tax compliant — KRA payments in {tax_months} months")

    return strengths


def _generate_recommendations(
    critical_issues: List[str],
    risks: List[str],
) -> List[str]:
    recommendations: List[str] = []

    if critical_issues:
        recommendations.append(
            "**Address critical issues before proceeding** — obtain explanations and supporting documentation"
        )

    if any("classification" in i.lower() or "flagged" in i.lower() for i in critical_issues):
        recommendations.append(
            "Review and classify flagged transactions to improve data quality"
        )

    if any("revenue" in i.lower() and "decline" in i.lower() for i in critical_issues):
        recommendations.append(
            "Request explanation for revenue decline — verify if temporary or structural issue"
        )

    if any("concentration" in r.lower() for r in risks):
        recommendations.append(
            "Assess concentration risk mitigation — customer contracts, supplier alternatives"
        )

    if any("capital injection" in i.lower() for i in critical_issues):
        recommendations.append(
            "Classify capital injection transactions — distinguish equity from loans"
        )

    if not critical_issues and not risks:
        recommendations.append(
            "Financial profile appears healthy — proceed with standard due diligence"
        )

    return recommendations


def _format_financial_summary(financial: Dict[str, Any]) -> str:
    lines: List[str] = []

    dscr = financial.get("dscr", {})
    if dscr.get("value") is not None:
        lines.append(f"**DSCR:** {dscr['value']:.2f} — {dscr['assessment']}")

    growth = financial.get("revenue_growth", {})
    if growth.get("value_pct") is not None:
        lines.append(f"**Revenue Growth:** {growth['value_pct']:.1f}% — {growth['assessment']}")

    volatility = financial.get("cash_flow_volatility", {})
    if volatility.get("assessment"):
        lines.append(f"**Cash Flow Volatility:** {volatility['assessment']}")

    burden = financial.get("loan_burden", {})
    if burden.get("value_pct") is not None:
        lines.append(f"**Loan Burden:** {burden['value_pct']:.1f}% — {burden['assessment']}")

    burn = financial.get("burn_rate", {})
    if burn.get("negative_months", 0) > 0:
        lines.append(f"**Burn Rate:** {burn['assessment']}")

    return "\n".join(lines) if lines else "Financial metrics calculated — ask for details"
