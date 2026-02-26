from datetime import datetime
from math import floor
from typing import Dict, List, Tuple

from ..parsing.common import canonical_hash


def _active_period_dates(transactions: List[Dict]) -> Tuple[str, str]:
    dates = [t["txn_date"] for t in transactions] or []
    return (min(dates), max(dates)) if dates else (None, None)


def _missing_months(txn_dates: List[str]) -> int:
    if not txn_dates:
        return 0
    dates = sorted(datetime.strptime(d, "%Y-%m-%d").date() for d in txn_dates)
    start, end = dates[0], dates[-1]
    # months strictly inside start/end (exclude partial leading/trailing)
    months = 0
    cur = (start.replace(day=1))
    # advance to first full month strictly after start
    if cur == start:
        cur = _add_months(cur, 1)
    else:
        cur = _add_months(cur, 1)
    while cur.replace(day=1) < end.replace(day=1):
        months += 1
        cur = _add_months(cur, 1)
    return months


def _add_months(dt, months):
    year = dt.year + (dt.month + months - 1) // 12
    month = (dt.month + months - 1) % 12 + 1
    day = min(dt.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return dt.replace(year=year, month=month, day=day)


def compute_metrics(transactions: List[Dict], accrual: Dict) -> Dict:
    """
    transactions: list with fields txn_date (YYYY-MM-DD), signed_amount_cents, abs_amount_cents, is_transfer, role
    accrual: dict with keys accrual_revenue_cents, accrual_period_start, accrual_period_end
    Returns metrics dict and component hashes.
    """
    non_transfer = [t for t in transactions if not t.get("is_transfer")]
    non_transfer_abs_total = sum(abs(int(t["signed_amount_cents"])) for t in non_transfer)
    classified_abs_total = sum(abs(int(t["signed_amount_cents"])) for t in non_transfer if t.get("role") != "other")

    if non_transfer_abs_total == 0:
        return {
            "non_transfer_abs_total_cents": 0,
            "classified_abs_total_cents": 0,
            "coverage_bp": 0,
            "missing_month_count": 0,
            "missing_month_penalty_bp": 0,
            "reconciliation_status": "NOT_RUN",
            "reconciliation_bp": None,
            "base_confidence_bp": 0,
            "base_after_months_bp": 0,
            "coverage_bp_raw": 0,
            "bank_operational_inflow_cents": 0,
        }

    coverage_bp = floor(classified_abs_total * 10000 / non_transfer_abs_total)

    bank_operational_inflow_cents = sum(
        int(t["signed_amount_cents"])
        for t in non_transfer
        if t["signed_amount_cents"] > 0 and t.get("role") == "revenue_operational"
    )

    missing_month_count = _missing_months([t["txn_date"] for t in transactions])
    missing_month_penalty_bp = min(missing_month_count * 1000, 5000)

    recon_status = "NOT_RUN"
    recon_bp = None
    accrual_revenue_cents = accrual.get("accrual_revenue_cents")
    accrual_start = accrual.get("accrual_period_start")
    accrual_end = accrual.get("accrual_period_end")

    if accrual_revenue_cents and accrual_revenue_cents > 0 and accrual_start and accrual_end:
        # overlap check
        start, end = _active_period_dates(transactions)
        if not start or not end:
            recon_status = "NOT_RUN"
        else:
            active_start = datetime.strptime(start, "%Y-%m-%d").date()
            active_end = datetime.strptime(end, "%Y-%m-%d").date()
            accr_start = datetime.strptime(accrual_start, "%Y-%m-%d").date()
            accr_end = datetime.strptime(accrual_end, "%Y-%m-%d").date()
            overlap_days = max(
                0,
                (min(active_end, accr_end) - max(active_start, accr_start)).days + 1,
            )
            accrual_days = (accr_end - accr_start).days + 1
            if accrual_days <= 0:
                recon_status = "FAILED_OVERLAP"
            else:
                # 60% threshold in basis points (no float in v1 core)
                overlap_bp = (overlap_days * 10000 // accrual_days) if accrual_days else 0
                if overlap_bp < 6000:
                    recon_status = "FAILED_OVERLAP"
                else:
                    if bank_operational_inflow_cents <= 0:
                        recon_status = "NOT_RUN"
                    else:
                        diff = abs(accrual_revenue_cents - bank_operational_inflow_cents)
                        recon_bp = max(0, 10000 - floor((diff * 10000) / accrual_revenue_cents))
                        recon_status = "OK"

    base_confidence = coverage_bp if recon_status != "OK" or recon_bp is None else min(coverage_bp, recon_bp)
    base_after_months = max(0, base_confidence - missing_month_penalty_bp)

    return {
        "non_transfer_abs_total_cents": non_transfer_abs_total,
        "classified_abs_total_cents": classified_abs_total,
        "coverage_bp": coverage_bp,
        "missing_month_count": missing_month_count,
        "missing_month_penalty_bp": missing_month_penalty_bp,
        "reconciliation_status": recon_status,
        "reconciliation_bp": recon_bp,
        "base_confidence_bp": base_confidence,
        "base_after_months_bp": base_after_months,
        "bank_operational_inflow_cents": bank_operational_inflow_cents,
    }
