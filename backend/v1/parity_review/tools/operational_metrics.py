"""
Operational metrics: supplier/customer concentration, working capital, payroll.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


_REVENUE_ROLES  = frozenset({"revenue_operational", "revenue_non_operational"})
_SUPPLIER_ROLES = frozenset({"supplier_payment"})


def calculate_operational_metrics(deal_data: Dict[str, Any]) -> Dict[str, Any]:
    top_suppliers = deal_data["top_suppliers"]
    top_revenue   = deal_data["top_revenue"]
    monthly       = deal_data["monthly"]
    tagged        = deal_data["tagged"]
    n_months      = deal_data["n_months"] or 1

    payroll_months    = deal_data["payroll_months"]
    payroll_stability = (deal_data["csi"].get("payroll_stability")
                         or deal_data["metrics"].get("payroll_stability")
                         or "Unknown")

    # Supplier concentration
    if top_suppliers:
        top_1_sup_pct = top_suppliers[0].get("pct_of_category", top_suppliers[0].get("pct_of_total", 0))
        top_5_sup_pct = sum(
            r.get("pct_of_category", r.get("pct_of_total", 0))
            for r in top_suppliers[:5]
        )
        supplier_risk = (
            "HIGH RISK"     if top_1_sup_pct > 20 else
            "MODERATE RISK" if top_1_sup_pct > 15 else
            "LOW RISK"
        )
    else:
        top_1_sup_pct = None
        top_5_sup_pct = None
        supplier_risk = "Insufficient data"

    # Customer concentration
    if top_revenue:
        top_1_cust_pct = top_revenue[0].get("pct_of_category", top_revenue[0].get("pct_of_total", 0))
        top_5_cust_pct = sum(
            r.get("pct_of_category", r.get("pct_of_total", 0))
            for r in top_revenue[:5]
        )
        customer_risk = (
            "HIGH RISK"     if top_1_cust_pct > 25 else
            "MODERATE RISK" if top_1_cust_pct > 15 else
            "LOW RISK"
        )
    else:
        top_1_cust_pct = None
        top_5_cust_pct = None
        customer_risk = "Insufficient data"

    # Working capital trend (first-quarter avg vs last-quarter avg of net monthly)
    if len(monthly) >= 3:
        first_q_avg = sum(m["net_cents"] for m in monthly[:3]) / 3
        last_q_avg  = sum(m["net_cents"] for m in monthly[-3:]) / 3
        if first_q_avg != 0:
            wc_trend_pct = (last_q_avg - first_q_avg) / abs(first_q_avg) * 100
        else:
            wc_trend_pct = 0.0
        wc_assessment = (
            "Improving"     if wc_trend_pct > 10  else
            "Stable"        if wc_trend_pct >= -10 else
            "Deteriorating"
        )
    else:
        wc_trend_pct  = None
        first_q_avg   = None
        last_q_avg    = None
        wc_assessment = "Insufficient data"

    # Payroll consistency
    payroll_consistency_pct = (payroll_months / n_months * 100) if n_months > 0 else 0
    payroll_label = (
        "Consistent workforce"    if payroll_consistency_pct >= 75 else
        "Sparse payroll data"     if payroll_consistency_pct >= 25 else
        "Minimal / no formal payroll"
    )

    return {
        "supplier_concentration": {
            "top_supplier_pct": round(top_1_sup_pct, 1) if top_1_sup_pct is not None else None,
            "top_5_pct": round(top_5_sup_pct, 1) if top_5_sup_pct is not None else None,
            "risk_level": supplier_risk,
            "top_supplier_name": top_suppliers[0]["entity_name"] if top_suppliers else None,
        },
        "customer_concentration": {
            "top_customer_pct": round(top_1_cust_pct, 1) if top_1_cust_pct is not None else None,
            "top_5_pct": round(top_5_cust_pct, 1) if top_5_cust_pct is not None else None,
            "risk_level": customer_risk,
            "top_customer_name": top_revenue[0]["entity_name"] if top_revenue else None,
        },
        "working_capital_trend": {
            "trend_pct": round(wc_trend_pct, 1) if wc_trend_pct is not None else None,
            "assessment": wc_assessment,
            "first_quarter_avg_kes": round(first_q_avg / 100, 0) if first_q_avg is not None else None,
            "last_quarter_avg_kes": round(last_q_avg / 100, 0) if last_q_avg is not None else None,
        },
        "payroll_stability": {
            "consistency_pct": round(payroll_consistency_pct, 0),
            "assessment": payroll_label,
            "months_with_payroll": payroll_months,
            "reported_stability": payroll_stability,
        },
        "summary": _operational_summary(supplier_risk, customer_risk, wc_assessment, payroll_label),
    }


def _operational_summary(
    supplier_risk: str,
    customer_risk: str,
    wc_trend: str,
    payroll_label: str,
) -> str:
    issues = []
    if supplier_risk == "HIGH RISK":
        issues.append("⚠️ High supplier concentration risk")
    elif supplier_risk == "MODERATE RISK":
        issues.append("⚠️ Moderate supplier concentration risk")
    if customer_risk == "HIGH RISK":
        issues.append("⚠️ High customer concentration risk")
    elif customer_risk == "MODERATE RISK":
        issues.append("⚠️ Moderate customer concentration risk")
    if wc_trend == "Deteriorating":
        issues.append("⚠️ Working capital deteriorating")
    if "Minimal" in payroll_label or "Sparse" in payroll_label:
        issues.append("ℹ️ Limited formal payroll detected")
    return " | ".join(issues) if issues else "✓ No major operational red flags"
