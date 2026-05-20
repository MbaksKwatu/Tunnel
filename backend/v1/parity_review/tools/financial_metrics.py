"""
Financial metrics calculations for Parity Review.
All input amounts are integer cents; displayed in KES (÷100).
Growth/burden values are in basis points.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


def calculate_financial_metrics(deal_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate DSCR, revenue growth, cash flow volatility, and burn rate.
    """
    csi     = deal_data["csi"]
    metrics = deal_data["metrics"]
    monthly = deal_data["monthly"]
    loan_repayment_cents = deal_data["loan_repayment_total_cents"]
    n_months = deal_data["n_months"] or 1

    avg_inflow_cents = int(
        csi.get("average_monthly_inflow_cents")
        or metrics.get("average_monthly_inflow_cents")
        or 0
    )
    rev_growth_bps = int(
        csi.get("revenue_growth_bps")
        or metrics.get("revenue_growth_bps")
        or 0
    )
    loan_burden_bps = int(
        csi.get("loan_repayment_burden_bps")
        or metrics.get("loan_repayment_burden_bps")
        or 0
    )

    # DSCR
    monthly_loan_cents = loan_repayment_cents // n_months if loan_repayment_cents > 0 else 0
    if monthly_loan_cents > 0 and avg_inflow_cents > 0:
        dscr = avg_inflow_cents / monthly_loan_cents
        dscr_assessment = (
            "Excellent (>2.0)"      if dscr >= 2.0  else
            "Good (1.5-2.0)"        if dscr >= 1.5  else
            "Acceptable (1.25-1.5)" if dscr >= 1.25 else
            "Weak (1.0-1.25)"       if dscr >= 1.0  else
            "Inadequate (<1.0)"
        )
    else:
        dscr = None
        dscr_assessment = "No loan repayments detected — cannot calculate DSCR"

    # Revenue growth (bps → %)
    rev_growth_pct = rev_growth_bps / 100
    if rev_growth_bps != 0:
        growth_assessment = (
            "Strong growth"               if rev_growth_pct >= 20  else
            "Healthy growth"              if rev_growth_pct >= 10  else
            "Stable"                      if rev_growth_pct >= 0   else
            "Declining — needs explanation"
        )
    else:
        growth_assessment = "Insufficient data to calculate growth"

    # Cash flow volatility
    if len(monthly) >= 3:
        nets = [m["net_cents"] for m in monthly]
        avg_net = sum(nets) / len(nets)
        std_dev = math.sqrt(sum((x - avg_net) ** 2 for x in nets) / len(nets))
        volatility_pct = (std_dev / abs(avg_net) * 100) if avg_net != 0 else 0
        volatility_assessment = (
            "Highly volatile (>50%)"       if volatility_pct > 50  else
            "Moderately volatile (25-50%)" if volatility_pct > 25  else
            "Stable (<25%)"
        )
    else:
        volatility_pct = None
        std_dev = None
        volatility_assessment = "Insufficient monthly data"

    # Burn rate
    negative_months = [m for m in monthly if m["net_cents"] < 0]
    if negative_months:
        avg_burn_cents = sum(abs(m["net_cents"]) for m in negative_months) // len(negative_months)
        burn_assessment = f"{len(negative_months)}/{len(monthly)} months had negative cash flow"
    else:
        avg_burn_cents = 0
        burn_assessment = "No negative cash flow months"

    return {
        "dscr": {
            "value": round(dscr, 2) if dscr is not None else None,
            "assessment": dscr_assessment,
            "avg_monthly_inflow_kes": avg_inflow_cents / 100,
            "monthly_loan_repayment_kes": monthly_loan_cents / 100,
        },
        "revenue_growth": {
            "value_pct": round(rev_growth_pct, 1),
            "assessment": growth_assessment,
        },
        "loan_burden": {
            "value_pct": round(loan_burden_bps / 100, 1),
            "assessment": (
                "Healthy (<30%)" if loan_burden_bps < 3000 else
                "Elevated (30-50%)" if loan_burden_bps < 5000 else
                "High (>50%)"
            ),
        },
        "cash_flow_volatility": {
            "value_pct": round(volatility_pct, 1) if volatility_pct is not None else None,
            "assessment": volatility_assessment,
        },
        "burn_rate": {
            "avg_burn_kes": avg_burn_cents / 100,
            "assessment": burn_assessment,
            "negative_months": len(negative_months),
            "total_months": len(monthly),
        },
        "summary": _financial_summary(dscr, rev_growth_pct, volatility_pct, len(negative_months), len(monthly)),
    }


def _financial_summary(
    dscr: Optional[float],
    rev_growth_pct: float,
    volatility_pct: Optional[float],
    negative_months: int,
    total_months: int,
) -> str:
    parts = []
    if dscr is not None:
        if dscr >= 1.5:
            parts.append(f"Strong debt service capacity (DSCR: {dscr:.2f})")
        elif dscr >= 1.25:
            parts.append(f"Acceptable debt service capacity (DSCR: {dscr:.2f})")
        else:
            parts.append(f"⚠️ Weak debt service capacity (DSCR: {dscr:.2f})")

    if rev_growth_pct >= 15:
        parts.append(f"Strong revenue growth ({rev_growth_pct:.1f}%)")
    elif rev_growth_pct >= 0:
        parts.append(f"Stable revenue ({rev_growth_pct:.1f}% growth)")
    else:
        parts.append(f"⚠️ Revenue declining ({rev_growth_pct:.1f}%)")

    if volatility_pct is not None and volatility_pct > 50:
        parts.append("⚠️ Highly volatile cash flows")

    if negative_months > 0 and total_months > 0:
        pct_neg = (negative_months / total_months) * 100
        if pct_neg > 33:
            parts.append(f"⚠️ {negative_months}/{total_months} months cash flow negative")

    return ". ".join(parts) + "." if parts else "Insufficient data for summary."
