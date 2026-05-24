"""
Operational metrics: supplier/customer concentration, working capital, payroll.
Pure computation — returns figures and percentages, no risk labels or assessments.
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

    if top_suppliers:
        top_1_sup_pct = top_suppliers[0].get("pct_of_category", top_suppliers[0].get("pct_of_total", 0))
        top_5_sup_pct = sum(
            r.get("pct_of_category", r.get("pct_of_total", 0))
            for r in top_suppliers[:5]
        )
    else:
        top_1_sup_pct = None
        top_5_sup_pct = None

    if top_revenue:
        top_1_cust_pct = top_revenue[0].get("pct_of_category", top_revenue[0].get("pct_of_total", 0))
        top_5_cust_pct = sum(
            r.get("pct_of_category", r.get("pct_of_total", 0))
            for r in top_revenue[:5]
        )
    else:
        top_1_cust_pct = None
        top_5_cust_pct = None

    if len(monthly) >= 3:
        first_q_avg = sum(m["net_cents"] for m in monthly[:3]) / 3
        last_q_avg  = sum(m["net_cents"] for m in monthly[-3:]) / 3
        if first_q_avg != 0:
            wc_trend_pct = (last_q_avg - first_q_avg) / abs(first_q_avg) * 100
        else:
            wc_trend_pct = 0.0
    else:
        wc_trend_pct  = None
        first_q_avg   = None
        last_q_avg    = None

    payroll_consistency_pct = (payroll_months / n_months * 100) if n_months > 0 else 0

    return {
        "supplier_concentration": {
            "top_supplier_pct": round(top_1_sup_pct, 1) if top_1_sup_pct is not None else None,
            "top_5_pct": round(top_5_sup_pct, 1) if top_5_sup_pct is not None else None,
            "top_supplier_name": top_suppliers[0]["entity_name"] if top_suppliers else None,
        },
        "customer_concentration": {
            "top_customer_pct": round(top_1_cust_pct, 1) if top_1_cust_pct is not None else None,
            "top_5_pct": round(top_5_cust_pct, 1) if top_5_cust_pct is not None else None,
            "top_customer_name": top_revenue[0]["entity_name"] if top_revenue else None,
        },
        "working_capital_trend": {
            "trend_pct": round(wc_trend_pct, 1) if wc_trend_pct is not None else None,
            "first_quarter_avg_kes": round(first_q_avg / 100, 0) if first_q_avg is not None else None,
            "last_quarter_avg_kes": round(last_q_avg / 100, 0) if last_q_avg is not None else None,
        },
        "payroll_stability": {
            "consistency_pct": round(payroll_consistency_pct, 0),
            "months_with_payroll": payroll_months,
            "total_months": n_months,
            "reported_stability": payroll_stability,
        },
    }
