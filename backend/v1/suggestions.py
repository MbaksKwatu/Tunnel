"""
Parity Review Suggestions Engine.

Scans pipeline output and enrichment state.
Returns list of suggestion cards for analyst review.
Each card: type, title, summary, data, add_to_snapshot_key.

Determinism: same pipeline output + enrichment state always returns same suggestions.
No floats. All amounts in integer cents.
"""
from __future__ import annotations

try:
    from .analytics import (
        annual_revenue_summary,
        loan_drawdowns,
        kra_summary,
        top_expenses_with_frequency,
    )
except ImportError:
    from analytics import (  # type: ignore[no-redef]
        annual_revenue_summary,
        loan_drawdowns,
        kra_summary,
        top_expenses_with_frequency,
    )

SUGGESTION_TYPES = {
    "annual_revenue": "Annual revenue totals",
    "loan_drawdowns": "Loan drawdowns in period",
    "kra_summary": "KRA payment history",
    "expense_frequency": "Expense patterns with frequency",
    "owner_distributions": "Owner/director distributions",
    "cash_threshold": "Cash below threshold",
    "overdraft": "Overdraft periods",
    "large_transactions": "Large unmatched transactions",
}


def generate_suggestions(
    transactions: list[dict],
    enrichment: dict | None,
    avg_monthly_inflow_cents: int,
) -> list[dict]:
    """
    Generate suggestion cards for Parity Review.

    Args:
        transactions: classified transaction list (each txn has role and amount_cents)
        enrichment: current enrichment state (None if not started)
        avg_monthly_inflow_cents: from credit_scoring_inputs (integer cents)

    Returns:
        list of suggestion cards ordered by priority ascending (1 = highest)
    """
    already_added: set[str] = set()
    if enrichment and enrichment.get("added_sections"):
        already_added = set(enrichment["added_sections"])

    suggestions: list[dict] = []

    # 1. Annual revenue
    if "annual_revenue" not in already_added:
        rev = annual_revenue_summary(transactions)
        if rev["years_covered"]:
            suggestions.append({
                "type": "annual_revenue",
                "title": "Annual revenue totals",
                "priority": 1,
                "summary": f"{len(rev['years_covered'])} year(s) of cleaned revenue data available.",
                "data": rev,
                "add_to_snapshot_key": "annual_revenue",
            })

    # 2. Loan drawdowns
    if "loan_drawdowns" not in already_added:
        draws = loan_drawdowns(transactions)
        if draws["drawdown_count"] > 0:
            suggestions.append({
                "type": "loan_drawdowns",
                "title": "Loan drawdowns detected",
                "priority": 2,
                "summary": (
                    f"{draws['drawdown_count']} loan inflow(s) totalling "
                    f"KES {draws['total_drawdown_cents'] // 100:,}."
                ),
                "data": draws,
                "add_to_snapshot_key": "loan_drawdowns",
            })

    # 3. KRA summary — always surface (NOT_DETECTED is also a credit signal)
    if "kra_summary" not in already_added:
        kra = kra_summary(transactions)
        if kra["compliance"] != "NOT_DETECTED":
            suggestions.append({
                "type": "kra_summary",
                "title": f"KRA compliance — {kra['compliance']}",
                "priority": 3,
                "summary": (
                    f"KES {kra['total_tax_cents'] // 100:,} paid across "
                    f"{kra['months_with_payment']} month(s)."
                ),
                "data": kra,
                "add_to_snapshot_key": "kra_summary",
            })
        else:
            suggestions.append({
                "type": "kra_summary",
                "title": "KRA compliance — NOT DETECTED",
                "priority": 3,
                "summary": "No KRA payments found in statements. Verify with founder.",
                "data": kra,
                "add_to_snapshot_key": "kra_summary",
            })

    # 4. Expense frequency
    if "expense_frequency" not in already_added:
        expenses = top_expenses_with_frequency(transactions, top_n=10)
        if expenses:
            suggestions.append({
                "type": "expense_frequency",
                "title": "Top expenses with transaction frequency",
                "priority": 4,
                "summary": (
                    f"Top supplier: {expenses[0]['entity_name']} — "
                    f"KES {expenses[0]['total_cents'] // 100:,} "
                    f"across {expenses[0]['txn_count']} transaction(s)."
                ),
                "data": {"expenses": expenses},
                "add_to_snapshot_key": "expense_frequency",
            })

    # 5. Owner distributions (priority 2 — high credit signal)
    if "owner_distributions" not in already_added:
        owner_txns = [
            t for t in transactions
            if (t.get("role") or t.get("classification")) == "owner_distribution"
        ]
        if owner_txns:
            if not all(isinstance(t.get("amount_cents", 0), int) for t in owner_txns):
                raise ValueError(
                    "Non-integer amount_cents in owner distribution transactions"
                )
            total = sum(abs(t.get("amount_cents", 0)) for t in owner_txns)
            suggestions.append({
                "type": "owner_distributions",
                "title": "Owner/director distributions detected",
                "priority": 2,
                "summary": (
                    f"{len(owner_txns)} distribution(s) totalling "
                    f"KES {total // 100:,}."
                ),
                "data": {
                    "distributions": [
                        {
                            "txn_date": t.get("txn_date"),
                            "entity_name": t.get("entity_name", "Unknown"),
                            "amount_cents": abs(t.get("amount_cents", 0)),
                        }
                        for t in owner_txns
                    ],
                    "total_cents": total,
                },
                "add_to_snapshot_key": "owner_distributions",
            })

    suggestions.sort(key=lambda x: x["priority"])
    return suggestions
