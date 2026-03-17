"""
Parity post-extraction analytics layer.
Operates on classified RawTransaction lists.
All arithmetic in integer cents. No floats.
"""
from __future__ import annotations

from collections import defaultdict
from typing import List, Dict, Any

from app.models import RawTransaction


def _parse_amount(raw: str) -> int:
    """Parse amount string to integer cents. Returns 0 on failure."""
    if not raw or not raw.strip():
        return 0
    cleaned = raw.strip().replace(",", "").replace(" CR", "").replace(" DR", "")
    try:
        return int(round(float(cleaned) * 100))
    except ValueError:
        return 0


def _parse_balance(raw: str) -> tuple[int, bool]:
    """
    Parse balance string to (cents, is_overdraft).
    Returns (0, False) on failure.
    """
    if not raw or not raw.strip():
        return (0, False)
    is_dr = "DR" in raw.upper()
    cleaned = raw.strip().replace(",", "").replace(" CR", "").replace(" DR", "")
    try:
        cents = int(round(float(cleaned) * 100))
        return (cents, is_dr)
    except ValueError:
        return (0, False)


def _month_key(date_raw: str) -> str:
    """Extract YYYY-MM from ISO date string. Returns empty string on failure."""
    if not date_raw or len(date_raw) < 7:
        return ""
    return date_raw[:7]


REVENUE_HINTS = {
    "MPESA_C2B",
    "POS_RECEIPT",
    "FUND_INFLOW",
    "INWARD_EFT_CREDIT",
}

EXPENSE_HINTS = {
    "SAFEWAYS_WITHDRAWAL",
    "NAMED_PERSON_TRANSFER",
    "CASH_WITHDRAWAL",
    "PESALINK_TRANSFER",
    "MPESA_TRANSFER",
    "AIRTIME_PURCHASE",
    "CARD_PURCHASE",
}

BANK_FEE_HINTS = {
    "BANK_CHARGE",
    "INTEREST",
    "KPLC_PREPAID",
}

NON_REVENUE_HINTS = EXPENSE_HINTS | BANK_FEE_HINTS | {"REVERSAL_PAIR"}


def revenue_quality(transactions: List[RawTransaction]) -> Dict[str, Any]:
    """
    Quality of revenue analysis.
    Strips non-revenue items and aggregates by month and counterparty.
    """
    revenue_txns = [
        t for t in transactions
        if t.pattern_hint in REVENUE_HINTS
        and t.pattern_hint != "REVERSAL_PAIR"
    ]

    monthly: Dict[str, int] = defaultdict(int)
    by_counterparty: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"total_cents": 0, "count": 0, "months": set()}
    )

    for t in revenue_txns:
        amount = _parse_amount(t.credit_raw)
        month = _month_key(t.date_raw)
        if month:
            monthly[month] += amount

        counterparty = _extract_counterparty(t.description, t.pattern_hint)
        by_counterparty[counterparty]["total_cents"] += amount
        by_counterparty[counterparty]["count"] += 1
        if month:
            by_counterparty[counterparty]["months"].add(month)

    monthly_list = sorted(
        [{"month": k, "total_cents": v} for k, v in monthly.items()],
        key=lambda x: x["month"],
    )

    total_revenue_cents = sum(monthly.values())
    month_count = len(monthly_list)
    avg_monthly_cents = total_revenue_cents // month_count if month_count else 0

    counterparty_list = sorted(
        [
            {
                "counterparty": k,
                "total_cents": v["total_cents"],
                "transaction_count": v["count"],
                "avg_transaction_cents": v["total_cents"] // v["count"] if v["count"] else 0,
                "active_months": len(v["months"]),
            }
            for k, v in by_counterparty.items()
        ],
        key=lambda x: x["total_cents"],
        reverse=True,
    )

    return {
        "total_revenue_cents": total_revenue_cents,
        "average_monthly_revenue_cents": avg_monthly_cents,
        "month_count": month_count,
        "monthly_breakdown": monthly_list,
        "counterparty_breakdown": counterparty_list,
        "transaction_count": len(revenue_txns),
        "pending_classification_count": sum(
            1 for t in transactions
            if t.classification_status == "PENDING_CLASSIFICATION"
            and t.pattern_hint in REVENUE_HINTS
        ),
    }


def expense_patterns(transactions: List[RawTransaction]) -> Dict[str, Any]:
    """
    Expense pattern analysis.
    Ranks by category and counterparty. Flags owner distributions and large single transactions.
    """
    expense_txns = [
        t for t in transactions
        if t.pattern_hint in EXPENSE_HINTS
    ]

    by_category: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"total_cents": 0, "count": 0}
    )
    by_counterparty: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"total_cents": 0, "count": 0, "category": ""}
    )
    large_transactions = []
    owner_distributions = []

    all_amounts = [_parse_amount(t.debit_raw) for t in expense_txns]
    avg_expense = sum(all_amounts) // len(all_amounts) if all_amounts else 0
    large_threshold = max(avg_expense * 3, 500000 * 100)

    for t in expense_txns:
        amount = _parse_amount(t.debit_raw)
        category = t.pattern_hint
        by_category[category]["total_cents"] += amount
        by_category[category]["count"] += 1

        counterparty = _extract_counterparty(t.description, t.pattern_hint)
        by_counterparty[counterparty]["total_cents"] += amount
        by_counterparty[counterparty]["count"] += 1
        by_counterparty[counterparty]["category"] = category

        if amount >= large_threshold:
            large_transactions.append({
                "date": t.date_raw,
                "description": t.description[:80],
                "amount_cents": amount,
                "category": category,
            })

        if t.pattern_hint in {"NAMED_PERSON_TRANSFER", "CASH_WITHDRAWAL"}:
            owner_distributions.append({
                "date": t.date_raw,
                "description": t.description[:80],
                "amount_cents": amount,
            })

    total_expense_cents = sum(v["total_cents"] for v in by_category.values())

    category_list = sorted(
        [
            {
                "category": k,
                "total_cents": v["total_cents"],
                "count": v["count"],
                "pct_bps": int(v["total_cents"] * 10000 // total_expense_cents)
                if total_expense_cents else 0,
            }
            for k, v in by_category.items()
        ],
        key=lambda x: x["total_cents"],
        reverse=True,
    )

    counterparty_list = sorted(
        [
            {
                "counterparty": k,
                "total_cents": v["total_cents"],
                "count": v["count"],
                "category": v["category"],
            }
            for k, v in by_counterparty.items()
        ],
        key=lambda x: x["total_cents"],
        reverse=True,
    )

    return {
        "total_expense_cents": total_expense_cents,
        "category_breakdown": category_list,
        "counterparty_breakdown": counterparty_list[:10],
        "large_transactions": sorted(
            large_transactions, key=lambda x: x["amount_cents"], reverse=True
        ),
        "owner_distributions": owner_distributions,
        "transaction_count": len(expense_txns),
    }


def cash_position(transactions: List[RawTransaction], threshold_cents: int = 50000000) -> Dict[str, Any]:
    """
    Cash position analysis.
    Tracks running balance, flags overdraft events and balance below threshold.
    threshold_cents defaults to KES 500,000 (50000000 cents).
    """
    sorted_txns = sorted(
        [t for t in transactions if t.balance_raw and t.date_raw],
        key=lambda x: (x.date_raw, x.row_index),
    )

    overdraft_events = []
    below_threshold_events = []
    balance_history = []

    for t in sorted_txns:
        balance_cents, is_dr = _parse_balance(t.balance_raw)
        signed_balance = -balance_cents if is_dr else balance_cents

        balance_history.append({
            "date": t.date_raw,
            "balance_cents": signed_balance,
            "is_overdraft": is_dr,
        })

        if is_dr:
            overdraft_events.append({
                "date": t.date_raw,
                "balance_cents": signed_balance,
                "description": t.description[:60],
            })

        if signed_balance < threshold_cents and not is_dr:
            below_threshold_events.append({
                "date": t.date_raw,
                "balance_cents": signed_balance,
                "description": t.description[:60],
            })

    min_balance = min((b["balance_cents"] for b in balance_history), default=0)
    max_balance = max((b["balance_cents"] for b in balance_history), default=0)

    return {
        "overdraft_count": len(overdraft_events),
        "overdraft_events": overdraft_events[:10],
        "below_threshold_count": len(below_threshold_events),
        "below_threshold_events": below_threshold_events[:10],
        "threshold_cents": threshold_cents,
        "min_balance_cents": min_balance,
        "max_balance_cents": max_balance,
        "balance_history_count": len(balance_history),
    }


def _extract_counterparty(description: str, pattern_hint: str) -> str:
    """
    Extract a clean counterparty name from a transaction description.
    Falls back to pattern_hint if no name can be parsed.
    """
    desc = (description or "").strip()

    if pattern_hint == "MPESA_C2B":
        parts = desc.split("~")
        if len(parts) >= 5:
            name = parts[-1].replace("Mourine Catherine", "Mourine Catherine")
            return name.strip() or "MPESA_UNKNOWN"
        return "MPESA_UNKNOWN"

    if pattern_hint == "SAFEWAYS_WITHDRAWAL":
        return "Safeways Express"

    if pattern_hint == "FUND_INFLOW":
        if "FOURTH GENERATION" in desc.upper():
            return "Fourth Generation Capital Ltd"
        if "SOMO AFRICA" in desc.upper():
            return "The Somo Africa Trust"
        return "FUND_UNKNOWN"

    if pattern_hint == "POS_RECEIPT":
        parts = desc.split("~")
        if len(parts) >= 3:
            return parts[2].strip() or "POS_UNKNOWN"
        return "POS_UNKNOWN"

    if pattern_hint in {"NAMED_PERSON_TRANSFER", "CASH_WITHDRAWAL"}:
        words = desc.strip().split()
        if len(words) <= 4:
            return desc.strip()
        return desc[:40].strip()

    if pattern_hint == "PESALINK_TRANSFER":
        return "PesaLink Transfer"

    return pattern_hint


_MOM_RELIABLE_THRESHOLD_CENTS = 1000000


def _mom_change_bps(prev: int, curr: int) -> int:
    """Month-on-month change in basis points. Returns 0 if prev is zero."""
    if prev == 0:
        return 0
    return int((curr - prev) * 10000 // prev)


def monthly_cashflow(transactions: List[RawTransaction]) -> List[Dict[str, Any]]:
    """
    Month-on-month cash flow with MoM % change.
    Includes mom_reliable flag — False when previous month net is below
    threshold and ratio is not meaningful.
    Returns list sorted by month ascending.
    """
    monthly_in: Dict[str, int] = defaultdict(int)
    monthly_out: Dict[str, int] = defaultdict(int)

    for t in transactions:
        if t.pattern_hint == "REVERSAL_PAIR":
            continue
        month = _month_key(t.date_raw)
        if not month:
            continue
        credit = _parse_amount(t.credit_raw)
        debit = _parse_amount(t.debit_raw)
        if credit > 0:
            monthly_in[month] += credit
        if debit > 0:
            monthly_out[month] += debit

    all_months = sorted(set(list(monthly_in.keys()) + list(monthly_out.keys())))
    result = []
    prev_net = 0
    for i, month in enumerate(all_months):
        inflow = monthly_in.get(month, 0)
        outflow = monthly_out.get(month, 0)
        net = inflow - outflow
        if i == 0:
            mom_bps = 0
            mom_reliable = False
        else:
            mom_bps = _mom_change_bps(prev_net, net)
            mom_reliable = abs(prev_net) >= _MOM_RELIABLE_THRESHOLD_CENTS
        result.append({
            "month": month,
            "inflow_cents": inflow,
            "outflow_cents": outflow,
            "net_cents": net,
            "mom_change_bps": mom_bps,
            "mom_reliable": mom_reliable,
        })
        prev_net = net

    return result


def entity_discovery_flags(transactions: List[RawTransaction]) -> List[Dict[str, Any]]:
    """
    Surface findings not typically declared in loan applications.
    Mirrors Sayuni Capital Section 05 format.
    """
    flags = []

    fund_inflows = [t for t in transactions if t.pattern_hint == "FUND_INFLOW"]
    for t in fund_inflows:
        amount = _parse_amount(t.credit_raw)
        counterparty = _extract_counterparty(t.description, t.pattern_hint)
        flags.append({
            "finding": f"{counterparty} — undeclared fund inflow",
            "category": "UNDISCLOSED_LOAN_OR_INVESTMENT",
            "value_cents": amount,
            "date": t.date_raw,
            "action": "CONFIRM WITH APPLICANT",
        })

    named_person = [t for t in transactions if t.pattern_hint == "NAMED_PERSON_TRANSFER"]
    for t in named_person:
        amount = _parse_amount(t.debit_raw)
        flags.append({
            "finding": f"{t.description[:60]} — large named person transfer",
            "category": "POSSIBLE_OWNER_DISTRIBUTION",
            "value_cents": amount,
            "date": t.date_raw,
            "action": "VERIFY RELATIONSHIP TO BUSINESS",
        })

    pesalink = [t for t in transactions if t.pattern_hint == "PESALINK_TRANSFER"]
    for t in pesalink:
        amount = _parse_amount(t.debit_raw)
        flags.append({
            "finding": "PesaLink transfer — possible intercompany obligation",
            "category": "POSSIBLE_INTERCOMPANY_TRANSFER",
            "value_cents": amount,
            "date": t.date_raw,
            "action": "CONFIRM BENEFICIARY AND PURPOSE",
        })

    reversals = [t for t in transactions if t.pattern_hint == "REVERSAL_PAIR"]
    if reversals:
        flags.append({
            "finding": f"{len(reversals)} reversed transactions detected",
            "category": "REVERSAL_PATTERN",
            "value_cents": sum(_parse_amount(t.debit_raw) for t in reversals),
            "date": reversals[0].date_raw,
            "action": "REVIEW FOR FAILED PAYMENTS OR DISPUTES",
        })

    pending = [t for t in transactions if t.classification_status == "PENDING_CLASSIFICATION"
               and t.pattern_hint not in {"POS_RECEIPT", "REVERSAL_PAIR"}]
    if pending:
        flags.append({
            "finding": f"{len(pending)} transactions require analyst classification",
            "category": "PENDING_CLASSIFICATION",
            "value_cents": 0,
            "date": "",
            "action": "CLASSIFY BEFORE FINALISING REPORT",
        })

    return flags


def revenue_quality(transactions: List[RawTransaction]) -> Dict[str, Any]:
    """
    Quality of revenue analysis.
    Strips non-revenue items and aggregates by month and counterparty.
    """
    revenue_txns = [
        t for t in transactions
        if t.pattern_hint in REVENUE_HINTS
        and t.pattern_hint != "REVERSAL_PAIR"
    ]

    monthly: Dict[str, int] = defaultdict(int)
    by_counterparty: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"total_cents": 0, "count": 0, "months": set(), "monthly_counts": defaultdict(int)}
    )

    for t in revenue_txns:
        amount = _parse_amount(t.credit_raw)
        month = _month_key(t.date_raw)
        if month:
            monthly[month] += amount

        counterparty = _extract_counterparty(t.description, t.pattern_hint)
        by_counterparty[counterparty]["total_cents"] += amount
        by_counterparty[counterparty]["count"] += 1
        if month:
            by_counterparty[counterparty]["months"].add(month)
            by_counterparty[counterparty]["monthly_counts"][month] += 1

    monthly_list = sorted(
        [{"month": k, "total_cents": v} for k, v in monthly.items()],
        key=lambda x: x["month"],
    )

    total_revenue_cents = sum(monthly.values())
    month_count = len(monthly_list)
    avg_monthly_cents = total_revenue_cents // month_count if month_count else 0

    counterparty_list = sorted(
        [
            {
                "counterparty": k,
                "total_cents": v["total_cents"],
                "pct_bps": int(v["total_cents"] * 10000 // total_revenue_cents) if total_revenue_cents else 0,
                "transaction_count": v["count"],
                "avg_transaction_cents": v["total_cents"] // v["count"] if v["count"] else 0,
                "active_months": len(v["months"]),
                "monthly_frequency": dict(sorted(v["monthly_counts"].items())),
            }
            for k, v in by_counterparty.items()
        ],
        key=lambda x: x["total_cents"],
        reverse=True,
    )

    return {
        "total_revenue_cents": total_revenue_cents,
        "average_monthly_revenue_cents": avg_monthly_cents,
        "month_count": month_count,
        "monthly_breakdown": monthly_list,
        "counterparty_breakdown": counterparty_list,
        "transaction_count": len(revenue_txns),
        "pending_classification_count": sum(
            1 for t in transactions
            if t.classification_status == "PENDING_CLASSIFICATION"
            and t.pattern_hint in REVENUE_HINTS
        ),
    }


def expense_patterns(transactions: List[RawTransaction]) -> Dict[str, Any]:
    """
    Expense pattern analysis.
    Ranks by category and counterparty. Flags owner distributions and large single transactions.
    """
    expense_txns = [
        t for t in transactions
        if t.pattern_hint in EXPENSE_HINTS
    ]

    total_expense_cents = sum(_parse_amount(t.debit_raw) for t in expense_txns)

    by_category: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"total_cents": 0, "count": 0}
    )
    by_counterparty: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"total_cents": 0, "count": 0, "category": ""}
    )
    large_transactions = []
    owner_distributions = []

    large_threshold = 5000000

    for t in expense_txns:
        amount = _parse_amount(t.debit_raw)
        category = t.pattern_hint
        by_category[category]["total_cents"] += amount
        by_category[category]["count"] += 1

        counterparty = _extract_counterparty(t.description, t.pattern_hint)
        by_counterparty[counterparty]["total_cents"] += amount
        by_counterparty[counterparty]["count"] += 1
        by_counterparty[counterparty]["category"] = category

        if amount >= large_threshold:
            large_transactions.append({
                "date": t.date_raw,
                "description": t.description[:80],
                "amount_cents": amount,
                "category": category,
            })

        if t.pattern_hint in {"NAMED_PERSON_TRANSFER", "CASH_WITHDRAWAL"}:
            owner_distributions.append({
                "date": t.date_raw,
                "description": t.description[:80],
                "amount_cents": amount,
            })

    category_list = sorted(
        [
            {
                "category": k,
                "total_cents": v["total_cents"],
                "count": v["count"],
                "pct_bps": int(v["total_cents"] * 10000 // total_expense_cents)
                if total_expense_cents else 0,
            }
            for k, v in by_category.items()
        ],
        key=lambda x: x["total_cents"],
        reverse=True,
    )

    counterparty_list = sorted(
        [
            {
                "counterparty": k,
                "total_cents": v["total_cents"],
                "count": v["count"],
                "pct_bps": int(v["total_cents"] * 10000 // total_expense_cents)
                if total_expense_cents else 0,
                "category": v["category"],
            }
            for k, v in by_counterparty.items()
        ],
        key=lambda x: x["total_cents"],
        reverse=True,
    )

    return {
        "total_expense_cents": total_expense_cents,
        "category_breakdown": category_list,
        "counterparty_breakdown": counterparty_list[:10],
        "large_transactions": sorted(
            large_transactions, key=lambda x: x["amount_cents"], reverse=True
        ),
        "owner_distributions": owner_distributions,
        "transaction_count": len(expense_txns),
    }


def cash_position(transactions: List[RawTransaction], threshold_cents: int = 50000000) -> Dict[str, Any]:
    """
    Cash position analysis.
    Tracks running balance, flags overdraft events and balance below threshold.
    threshold_cents defaults to KES 500,000 (50000000 cents).
    """
    sorted_txns = sorted(
        [t for t in transactions if t.balance_raw and t.date_raw],
        key=lambda x: (x.date_raw, x.row_index),
    )

    overdraft_events = []
    below_threshold_events = []
    balance_history = []

    for t in sorted_txns:
        balance_cents, is_dr = _parse_balance(t.balance_raw)
        signed_balance = -balance_cents if is_dr else balance_cents

        balance_history.append({
            "date": t.date_raw,
            "balance_cents": signed_balance,
            "is_overdraft": is_dr,
        })

        if is_dr:
            overdraft_events.append({
                "date": t.date_raw,
                "balance_cents": signed_balance,
                "description": t.description[:60],
            })

        if signed_balance < threshold_cents and not is_dr:
            below_threshold_events.append({
                "date": t.date_raw,
                "balance_cents": signed_balance,
                "description": t.description[:60],
            })

    min_balance = min((b["balance_cents"] for b in balance_history), default=0)
    max_balance = max((b["balance_cents"] for b in balance_history), default=0)

    return {
        "overdraft_count": len(overdraft_events),
        "overdraft_events": overdraft_events[:10],
        "below_threshold_count": len(below_threshold_events),
        "below_threshold_events": below_threshold_events[:10],
        "threshold_cents": threshold_cents,
        "min_balance_cents": min_balance,
        "max_balance_cents": max_balance,
        "balance_history_count": len(balance_history),
    }


def run_analytics(transactions: List[RawTransaction], threshold_cents: int = 50000000) -> Dict[str, Any]:
    """
    Run all analytics modules and return combined result.
    """
    return {
        "summary": {
            "total_transactions": len(transactions),
            "auto_classified": sum(1 for t in transactions if t.classification_status == "AUTO_CLASSIFIED"),
            "pending_classification": sum(1 for t in transactions if t.classification_status == "PENDING_CLASSIFICATION"),
            "analyst_classified": sum(1 for t in transactions if t.classification_status == "ANALYST_CLASSIFIED"),
        },
        "monthly_cashflow": monthly_cashflow(transactions),
        "revenue_quality": revenue_quality(transactions),
        "expense_patterns": expense_patterns(transactions),
        "cash_position": cash_position(transactions, threshold_cents),
        "entity_discovery_flags": entity_discovery_flags(transactions),
    }
