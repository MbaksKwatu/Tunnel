"""
Tabular (CSV / Excel) extractor for audited / management financial statements.

Handles spreadsheet exports from accounting systems (QuickBooks, Sage, Xero)
where each financial statement section appears as a labelled block of rows.

Strategy:
  1. Read the file into a pandas DataFrame (one sheet, or the best sheet).
  2. Scan for keyword-bearing rows to locate IS / BS / CF sections.
  3. Extract line-item labels and their most recent numeric value.
  4. Map labels to canonical pds_audited_financials field names.
  5. Return the same dict shape as extract_audited_financials so callers
     are format-agnostic.

Confidence is capped at 60 for CSV (no cross-checks) and 65 for Excel
(multiple sheets possible).
"""
from __future__ import annotations

import hashlib
import logging
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# ── Amount helpers ─────────────────────────────────────────────────────────────

def _to_cents(val: Any) -> Optional[int]:
    """Convert a cell value (string, float, int) to integer cents."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip().replace(",", "").replace(" ", "")
    negative = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        cents = round(float(s) * 100)
        return -cents if negative else cents
    except ValueError:
        return None


# ── Section / label matchers ───────────────────────────────────────────────────

_IS_KEYWORDS = re.compile(
    r"income\s+statement|statement\s+of\s+(?:comprehensive\s+)?income|"
    r"profit\s+(?:and|&)\s+loss|p\s*[&/]\s*l|income\s+statement",
    re.I,
)
_BS_KEYWORDS = re.compile(
    r"balance\s+sheet|statement\s+of\s+financial\s+position|"
    r"statement\s+of\s+assets",
    re.I,
)
_CF_KEYWORDS = re.compile(
    r"cash\s+flow|cashflow|statement\s+of\s+cash",
    re.I,
)

# Maps normalised label substring → canonical field name (in cents)
_LABEL_MAP: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"turnover|total\s+revenue|gross\s+revenue|net\s+sales", re.I), "turnover_cents"),
    (re.compile(r"cost\s+of\s+(?:sales|goods\s+sold|revenue)|direct\s+costs", re.I), "cost_of_sales_cents"),
    (re.compile(r"gross\s+profit", re.I), "gross_profit_cents"),
    (re.compile(r"operating\s+(?:costs?|expenses?)", re.I), "operating_costs_cents"),
    (re.compile(r"(?:staff|employee|payroll|personnel)\s+(?:costs?|expenses?|salaries)", re.I), "staff_costs_cents"),
    (re.compile(r"administrative\s+(?:costs?|expenses?)", re.I), "administrative_costs_cents"),
    (re.compile(r"finance\s+(?:costs?|charges?)|interest\s+expense", re.I), "finance_costs_cents"),
    (re.compile(r"other\s+income", re.I), "other_income_cents"),
    (re.compile(r"profit\s+before\s+tax|income\s+before\s+tax|net\s+profit\s+before\s+tax", re.I), "profit_before_tax_cents"),
    (re.compile(r"(?:income\s+)?tax\s+(?:expense|charge)|taxation", re.I), "tax_expense_cents"),
    (re.compile(r"profit\s+(?:after\s+tax|for\s+the\s+year)|net\s+(?:profit|income)\s+after\s+tax", re.I), "profit_after_tax_cents"),
    # Balance sheet
    (re.compile(r"property[,\s]+plant\s+(?:and\s+equipment|&\s*eq)", re.I), "property_plant_equipment_cents"),
    (re.compile(r"intangible\s+assets?", re.I), "intangible_assets_cents"),
    (re.compile(r"inventor(?:y|ies)|stock(?:\s+in\s+trade)?", re.I), "inventory_cents"),
    (re.compile(r"trade\s+(?:and\s+other\s+)?receivables|accounts\s+receivable|debtors", re.I), "trade_receivables_cents"),
    (re.compile(r"cash\s+and\s+(?:cash\s+)?equivalents?|cash\s+at\s+bank|cash\s+and\s+bank", re.I), "cash_and_equivalents_cents"),
    (re.compile(r"total\s+assets", re.I), "total_assets_cents"),
    (re.compile(r"trade\s+(?:and\s+other\s+)?payables|accounts\s+payable|creditors", re.I), "trade_payables_cents"),
    (re.compile(r"total\s+liabilit", re.I), "total_liabilities_cents"),
    (re.compile(r"total\s+equity|shareholders['\s]+equity|net\s+assets", re.I), "equity_cents"),
    # Cash flow
    (re.compile(r"(?:net\s+cash\s+(?:from|generated\s+(?:from|by))|cash\s+(?:from|generated\s+from))\s+operating", re.I), "operating_cashflow_cents"),
    (re.compile(r"(?:net\s+cash\s+(?:used\s+in|from)|cash\s+(?:used\s+in|from))\s+investing", re.I), "investing_cashflow_cents"),
    (re.compile(r"(?:net\s+cash\s+(?:from|used\s+in)|cash\s+(?:from|used\s+in))\s+financing", re.I), "financing_cashflow_cents"),
    (re.compile(r"cash\s+at\s+(?:end|close\s+of\s+(?:year|period))|closing\s+cash", re.I), "cash_at_end_cents"),
    (re.compile(r"cash\s+at\s+(?:beginning|start|opening)|opening\s+cash", re.I), "cash_at_start_cents"),
]


def _match_label(label: str) -> Optional[str]:
    """Return the canonical field name for a spreadsheet label, or None."""
    for pattern, field in _LABEL_MAP:
        if pattern.search(label):
            return field
    return None


# ── Year / company helpers ─────────────────────────────────────────────────────

def _extract_year_from_df(df: pd.DataFrame) -> Optional[int]:
    """Look for a 4-digit year (2000-2099) in the column headers or first rows."""
    # Check column headers
    for col in df.columns:
        m = re.search(r"\b(20\d{2})\b", str(col))
        if m:
            return int(m.group(1))
    # Check first 5 rows
    for _, row in df.head(5).iterrows():
        for cell in row:
            m = re.search(r"\b(20\d{2})\b", str(cell))
            if m:
                return int(m.group(1))
    return None


def _extract_company_from_df(df: pd.DataFrame) -> str:
    """Return the best-guess company name from the first few rows."""
    for _, row in df.head(5).iterrows():
        for cell in row:
            s = str(cell).strip()
            if len(s) < 4 or re.match(r"^[\d,\.\(\)\-\s]+$", s):
                continue
            words = s.split()
            if sum(1 for w in words if w and w[0].isupper()) >= 2:
                return s[:120]
    return ""


# ── Core extraction ───────────────────────────────────────────────────────────

def _extract_fields_from_df(df: pd.DataFrame) -> Dict[str, Optional[int]]:
    """
    Walk every row in the dataframe and map labels to financial fields.
    Uses the last non-null numeric column as the value (most recent period).
    """
    fields: Dict[str, Optional[int]] = {}

    for _, row in df.iterrows():
        label_cell = str(row.iloc[0]).strip() if len(row) > 0 else ""
        if not label_cell or label_cell.lower() in ("nan", "none", ""):
            continue

        field = _match_label(label_cell)
        if not field:
            continue

        # Take the last non-null numeric value in the row (most recent year)
        value = None
        for cell in reversed(row.iloc[1:].tolist()):
            v = _to_cents(cell)
            if v is not None:
                value = v
                break

        if value is not None:
            fields[field] = value

    return fields


def _best_sheet(xls: pd.ExcelFile) -> pd.DataFrame:
    """
    Return the best sheet to use for financial extraction.
    Priority: a sheet whose name contains IS/BS/P&L keywords, else sheet 0.
    If the file has a single sheet, return that.
    """
    if len(xls.sheet_names) == 1:
        return pd.read_excel(xls, sheet_name=xls.sheet_names[0], header=None)

    for name in xls.sheet_names:
        n = name.lower()
        if any(kw in n for kw in ("summary", "financials", "financial", "accounts")):
            return pd.read_excel(xls, sheet_name=name, header=None)

    # Merge all sheets into one vertical stack for multi-sheet workbooks
    frames = []
    for name in xls.sheet_names:
        try:
            frames.append(pd.read_excel(xls, sheet_name=name, header=None))
        except Exception:
            pass
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _sha256(data: Dict[str, Any]) -> str:
    key = (
        f"{data.get('company_name')}|{data.get('financial_year')}|"
        f"{data.get('turnover_cents')}|{data.get('profit_after_tax_cents')}|"
        f"{data.get('cash_and_equivalents_cents')}"
    )
    return hashlib.sha256(key.encode()).hexdigest()


def _confidence(data: Dict[str, Any], base: int) -> Decimal:
    """Award up to base% from the presence of key financial fields."""
    key_fields = [
        "turnover_cents", "profit_after_tax_cents", "total_assets_cents",
        "cash_and_equivalents_cents", "financial_year",
    ]
    hits = sum(1 for f in key_fields if data.get(f) is not None)
    return Decimal(str(round(base * hits / len(key_fields), 2)))


# ── Public API ────────────────────────────────────────────────────────────────

def extract_audited_financials_from_csv(csv_path: str) -> Dict[str, Any]:
    """
    Extract financial statement fields from a CSV file.

    Returns the same dict shape as ``extract_audited_financials`` with
    ``extraction_method='csv_tabular'`` and confidence capped at 60.
    """
    try:
        df = pd.read_csv(csv_path, header=None, dtype=str)
    except Exception as exc:
        raise ValueError(f"Cannot read CSV: {exc}") from exc

    company = _extract_company_from_df(df)
    year = _extract_year_from_df(df)
    fields = _extract_fields_from_df(df)

    result: Dict[str, Any] = {
        "company_name": company or None,
        "financial_year": year,
        "financial_year_start": f"{year - 1}-01-01" if year else None,
        "financial_year_end": f"{year}-12-31" if year else None,
        "currency": "KES",
        **fields,
        "extraction_method": "csv_tabular",
    }

    result["extraction_confidence"] = _confidence(result, 60)
    result["sha256_hash"] = _sha256(result)

    logger.info(
        "[TABULAR] CSV extracted %s FY%s — confidence=%.1f%%",
        result.get("company_name"),
        result.get("financial_year"),
        float(result["extraction_confidence"]),
    )
    return result


def extract_audited_financials_from_excel(excel_path: str) -> Dict[str, Any]:
    """
    Extract financial statement fields from an Excel (.xlsx / .xls) file.

    Handles single-sheet and multi-sheet workbooks by merging all sheets.
    Returns the same dict shape as ``extract_audited_financials`` with
    ``extraction_method='excel_tabular'`` and confidence capped at 65.
    """
    try:
        xls = pd.ExcelFile(excel_path)
        df = _best_sheet(xls)
    except Exception as exc:
        raise ValueError(f"Cannot read Excel file: {exc}") from exc

    company = _extract_company_from_df(df)
    year = _extract_year_from_df(df)
    fields = _extract_fields_from_df(df)

    result: Dict[str, Any] = {
        "company_name": company or None,
        "financial_year": year,
        "financial_year_start": f"{year - 1}-01-01" if year else None,
        "financial_year_end": f"{year}-12-31" if year else None,
        "currency": "KES",
        **fields,
        "extraction_method": "excel_tabular",
    }

    result["extraction_confidence"] = _confidence(result, 65)
    result["sha256_hash"] = _sha256(result)

    logger.info(
        "[TABULAR] Excel extracted %s FY%s — confidence=%.1f%%",
        result.get("company_name"),
        result.get("financial_year"),
        float(result["extraction_confidence"]),
    )
    return result


__all__ = [
    "extract_audited_financials_from_csv",
    "extract_audited_financials_from_excel",
]
