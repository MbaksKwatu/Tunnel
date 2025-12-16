import pandas as pd
import numpy as np
from typing import List, Dict, Any
import logging
import re

logger = logging.getLogger(__name__)

class Evaluator:
    """Evaluates financial documents to calculate key performance metrics"""
    
    def evaluate(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate financial metrics from parsed rows
        
        Metrics:
        1. Revenue Growth %: (last - first) / first * 100
        2. Cash Flow Stability: stddev(revenue - expenses)
        3. Expense Efficiency: expenses.mean() / revenue.mean()
        """
        if not rows:
            return {"metrics": []}
            
        try:
            df = pd.DataFrame(rows)
            
            # Identify columns
            revenue_col = self._find_column(df, ['revenue', 'income', 'sales', 'receipt', 'turnover'])
            expense_col = self._find_column(df, ['expense', 'cost', 'payment', 'outgoing', 'spend', 'debit'])
            
            metrics = []
            
            # Pre-process columns to numeric
            rev_series = pd.Series([0]*len(df))
            exp_series = pd.Series([0]*len(df))

            if 'amount' in df.columns:
                amt_series = df['amount'].apply(self._to_numeric).fillna(0)
                rev_series = amt_series.clip(lower=0)
                exp_series = (-amt_series.clip(upper=0))
            else:
                if revenue_col:
                    rev_series = df[revenue_col].apply(self._to_numeric).fillna(0)
                
                if expense_col:
                    exp_series = df[expense_col].apply(self._to_numeric).fillna(0)
                
            # Filter out zero rows for meaningful calc? 
            # Requirement says (last - first). Assuming time series order.
            
            # 1. Revenue Growth %
            revenue_growth = 0.0
            if len(rev_series) > 0:
                # Filter non-zero values for "first" to avoid div by zero
                non_zero_rev = rev_series[rev_series != 0]
                if len(non_zero_rev) >= 2:
                    first = non_zero_rev.iloc[0]
                    last = non_zero_rev.iloc[-1]
                    if first != 0:
                        revenue_growth = ((last - first) / first) * 100
            
            metrics.append({
                "name": "Revenue Growth %",
                "value": float(round(revenue_growth, 2))
            })
            
            # 2. Cash Flow Stability
            # stddev(revenue - expenses)
            net_flow = rev_series - exp_series
            stability = 0.0
            if len(net_flow) > 1:
                stability = float(net_flow.std())
            
            metrics.append({
                "name": "Cash Flow Stability",
                "value": float(round(stability, 2))
            })
            
            # 3. Expense Efficiency
            # expenses.mean() / revenue.mean()
            efficiency = 0.0
            rev_mean = rev_series.mean()
            exp_mean = exp_series.mean()
            
            if rev_mean > 0:
                efficiency = (exp_mean / rev_mean) * 100  # Usually expressed as % or ratio
                # Requirement says value, but efficiency usually implies lower is better or ratio.
                # I'll return ratio * 100 for percentage
            
            metrics.append({
                "name": "Expense Efficiency",
                "value": float(round(efficiency, 2))
            })
            
            return {"metrics": metrics}
            
        except Exception as e:
            logger.error(f"Error evaluating metrics: {e}")
            return {"metrics": [], "error": str(e)}

    def _find_column(self, df: pd.DataFrame, keywords: List[str]) -> str:
        """Find column matching keywords"""
        for col in df.columns:
            col_lower = str(col).lower()
            for kw in keywords:
                if kw in col_lower:
                    return col
        return None

    def _to_numeric(self, value: Any) -> float:
        """Convert value to numeric"""
        if pd.isna(value):
            return 0.0
        try:
            # Clean string
            str_val = str(value).replace('$', '').replace(',', '').replace(' ', '')
            # Handle parentheses for negative
            if '(' in str_val and ')' in str_val:
                str_val = '-' + str_val.replace('(', '').replace(')', '')
            return float(str_val)
        except (ValueError, TypeError):
            return 0.0
