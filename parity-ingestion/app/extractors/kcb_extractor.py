"""
KCB Bank Kenya PDF statement extractor.

Uses extract_words + x-thresholds from Step 0 measurement.
Columns: TXN DATE | DESCRIPTION | VALUE DATE | MONEY OUT | MONEY IN | LEDGER BALANCE
Date format: DD MON YYYY (e.g. 20 JUL 2023)
"""
from __future__ import annotations

import re
from typing import List, Optional

import pdfplumber

from app.models import ExtractionResult, RawTransaction, WarningItem
from app.extractors.shared import _group_by_line

# X-thresholds from Step 0 (measured from real file)
_TXN_DATE_X_MAX = 95.0
_DESC_X_START = 197.6
_DESC_X_MAX = 340.0
_VALUE_DATE_X_START = 349.95
_VALUE_DATE_X_MAX = 500.0
_MONEY_OUT_X_START = 501.0
_MONEY_OUT_X_MAX = 650.0
_MONEY_IN_X_START = 653.0
_MONEY_IN_X_MAX = 800.0
_BALANCE_X_START = 805.0

_ROW_TOLERANCE = 3.0
_TXN_DATE_PAT = re.compile(r"^(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})$")
_AMOUNT_PAT = re.compile(r"^[\d,]+\.\d{2}$")

MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def parse_kcb_date(s: str) -> Optional[str]:
    """Parse '20 JUL 2023' to '2023-07-20'."""
    s = s.strip()
    if not s:
        return None
    parts = s.split()
    if len(parts) != 3:
        return None
    try:
        day = int(parts[0])
        mon = MONTH_MAP.get(parts[1].upper())
        year = int(parts[2])
        if mon is None:
            return None
        return f"{year}-{mon:02d}-{day:02d}"
    except (ValueError, IndexError):
        return None


def detect_kcb(file_path: str) -> bool:
    """Return True if the PDF appears to be a KCB account statement."""
    try:
        with pdfplumber.open(file_path) as pdf:
            if not pdf.pages:
                return False
            text = pdf.pages[0].extract_text() or ""
            text_upper = text.upper()
            has_kcb = "KCB" in text_upper or "KCB BANK" in text_upper
            has_stmt = "ACCOUNT STATEMENT" in text_upper
            has_cols = "TXN DATE" in text_upper and "LEDGER BALANCE" in text_upper
            return bool(has_kcb and has_stmt and has_cols)
    except Exception:
        return False


def _assign_kcb_column(w: dict) -> Optional[str]:
    text = w.get("text", "")
    x0 = w.get("x0", 0)

    if _AMOUNT_PAT.match(text):
        if x0 >= _BALANCE_X_START:
            return "balance"
        if x0 >= _MONEY_IN_X_START:
            return "money_in"
        if x0 >= _MONEY_OUT_X_START:
            return "money_out"

    if x0 < _TXN_DATE_X_MAX:
        return "txn_date"
    if _DESC_X_START <= x0 < _DESC_X_MAX:
        return "desc"
    if _VALUE_DATE_X_START <= x0 < _VALUE_DATE_X_MAX:
        return "value_date"
    return None


def extract_kcb_pdf(file_path: str) -> ExtractionResult:
    transactions: List[RawTransaction] = []
    warnings: List[WarningItem] = []
    row_idx = 0

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            if not words:
                continue

            rows = _group_by_line(words, _ROW_TOLERANCE)
            pending: Optional[dict] = None

            for row_words in rows:
                txn_date_parts: List[str] = []
                desc_parts: List[str] = []
                value_date_parts: List[str] = []
                money_out = ""
                money_in = ""
                balance_raw = ""

                for w in row_words:
                    col = _assign_kcb_column(w)
                    if col == "txn_date":
                        txn_date_parts.append(w["text"])
                    elif col == "desc":
                        desc_parts.append(w["text"])
                    elif col == "value_date":
                        value_date_parts.append(w["text"])
                    elif col == "money_out":
                        money_out = w["text"]
                    elif col == "money_in":
                        money_in = w["text"]
                    elif col == "balance":
                        balance_raw = w["text"]

                txn_date_str = " ".join(txn_date_parts).strip()
                desc_str = " ".join(desc_parts).strip()
                value_date_str = " ".join(value_date_parts).strip()

                if any(phrase in desc_str.upper() for phrase in [
                    "BALANCE AT PERIOD END",
                    "PERIOD END"
                ]):
                    continue

                if not txn_date_str and not desc_str and not money_out and not money_in:
                    continue

                iso_date = parse_kcb_date(txn_date_str)

                if txn_date_str and _TXN_DATE_PAT.match(txn_date_str):
                    if pending:
                        _flush_kcb_pending(pending, transactions, warnings)
                        pending = None

                    pending = {
                        "row_index": row_idx,
                        "date_raw": iso_date or txn_date_str,
                        "description": desc_str,
                        "debit_raw": money_out.replace(",", "").lstrip("-") if money_out else "",
                        "credit_raw": money_in.replace(",", "") if money_in else "",
                        "balance_raw": balance_raw,
                        "source_file": file_path,
                    }
                    row_idx += 1
                else:
                    if pending and desc_str:
                        pending["description"] = (
                            (pending["description"] or "") + " " + desc_str
                        ).strip()
                    if pending and money_out and not pending["debit_raw"]:
                        pending["debit_raw"] = money_out.replace(",", "").lstrip("-")
                    if pending and money_in and not pending["credit_raw"]:
                        pending["credit_raw"] = money_in.replace(",", "")
                    if pending and balance_raw and not pending["balance_raw"]:
                        pending["balance_raw"] = balance_raw

            if pending:
                _flush_kcb_pending(pending, transactions, warnings)
                pending = None

    return ExtractionResult(
        source_file=file_path,
        extractor_type="kcb_pdf",
        row_count=len(transactions),
        extraction_status="success",
        warnings=warnings,
        raw_transactions=transactions,
    )


def _flush_kcb_pending(
    pending: dict,
    transactions: List[RawTransaction],
    warnings: List[WarningItem],
) -> None:
    desc = pending["description"] or ""
    is_b_fwd = "B/FWD" in desc.upper() or "BALANCE B/FWD" in desc.upper()
    if is_b_fwd:
        pending["debit_raw"] = ""
        pending["credit_raw"] = ""

    transactions.append(
        RawTransaction(
            row_index=pending["row_index"],
            date_raw=pending["date_raw"],
            description=desc,
            debit_raw=pending["debit_raw"],
            credit_raw=pending["credit_raw"],
            balance_raw=pending["balance_raw"],
            source_file=pending["source_file"],
            extraction_confidence=1.0,
        )
    )
