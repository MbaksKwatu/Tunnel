"""
Parity Review — default flag seeding.

After first snapshot generation, auto-create three default custom flags.
Idempotent: if flags already exist for the deal, no new flags are created.
All threshold amounts in integer cents. Multipliers in basis points.
"""
from __future__ import annotations

import copy

DEFAULT_FLAGS: list[dict] = [
    {
        "flag_type": "threshold",
        "flag_name": "Low cash alert",
        "flag_severity": "warning",
        "flag_description": "Months where total cash falls below KES 500,000",
        "criteria": {
            "metric": "closing_balance",
            "comparison": "less_than",
            "threshold_cents": 50_000_000,  # KES 500,000 in cents
            "dynamic": False,
        },
    },
    {
        "flag_type": "threshold",
        "flag_name": "Overdraft days",
        "flag_severity": "warning",
        "flag_description": "Days where running balance falls below zero",
        "criteria": {
            "metric": "overdraft_days",
            "comparison": "greater_than",
            "threshold_cents": 0,
            "dynamic": False,
        },
    },
    {
        "flag_type": "threshold",
        "flag_name": "Large transaction review",
        "flag_severity": "info",
        "flag_description": "Transactions above 15% of average monthly inflow",
        "criteria": {
            "metric": "single_transaction_amount",
            "comparison": "greater_than",
            "threshold_cents": None,
            "dynamic": True,
            "dynamic_basis": "avg_monthly_inflow",
            "dynamic_multiplier_bps": 1500,  # 15% = 1500 bps
        },
    },
]


def seed_default_flags(
    deal_id: str,
    avg_monthly_inflow_cents: int,
    flags_repo=None,
) -> list[dict]:
    """
    Create default flags for a deal if none exist yet.

    Called once after first snapshot generation.
    Idempotent — if flags already exist, returns existing list unchanged.

    dynamic_multiplier_bps: 1500 = 15% of avg monthly inflow.
    """
    if flags_repo is not None:
        existing = flags_repo.list_flags(deal_id)
        if existing:
            return existing

    resolved: list[dict] = []
    for flag_template in DEFAULT_FLAGS:
        flag = copy.deepcopy(flag_template)
        flag["deal_id"] = deal_id
        criteria = flag["criteria"]
        if criteria.get("dynamic"):
            threshold = (
                avg_monthly_inflow_cents * criteria["dynamic_multiplier_bps"]
            ) // 10000
            criteria["threshold_cents"] = threshold
        resolved.append(flag)

    if flags_repo is not None:
        for flag in resolved:
            flags_repo.insert_flag(flag)

    return resolved
