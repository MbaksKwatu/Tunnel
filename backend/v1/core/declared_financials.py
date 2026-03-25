from __future__ import annotations

from typing import Dict, List, Optional


class DeclaredFinancials:
    """
    Canonical representation of SME-declared financial data.

    Designed for:
    - audited statements (structured)
    - accountant summaries (semi-structured)
    - manual SME inputs (messy)

    All values are integer cents.
    """

    def __init__(
        self,
        revenue: Optional[List[int]] = None,
        expenses: Optional[List[int]] = None,
        profit: Optional[List[int]] = None,
        period: str = "annual",  # "monthly" or "annual"
    ):
        self.revenue = revenue or []
        self.expenses = expenses or []
        self.profit = profit or []
        self.period = period

    def total_revenue(self) -> int:
        return sum(self.revenue)

    def total_expenses(self) -> int:
        return sum(self.expenses)

    def total_profit(self) -> int:
        return sum(self.profit)

    def has_revenue(self) -> bool:
        return len(self.revenue) > 0

    def has_expenses(self) -> bool:
        return len(self.expenses) > 0

    def has_profit(self) -> bool:
        return len(self.profit) > 0

    def to_dict(self) -> Dict:
        return {
            "revenue": self.revenue,
            "expenses": self.expenses,
            "profit": self.profit,
            "period": self.period,
        }

