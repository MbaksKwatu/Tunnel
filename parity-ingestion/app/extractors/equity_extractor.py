"""
Equity Bank Kenya PDF statement extractor.

Columns: Date | Value | Particulars | Money Out | Money In | Balance
Date format: DD-MM-YYYY
Value column: skip entirely.
Money Out → negative (debit_raw). Money In → positive (credit_raw).
Dr balance: Strip "Dr", parse as positive, set balance_is_overdrawn=True.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional, Tuple

import pdfplumber

from app.models import ExtractionResult, RawTransaction, WarningItem

_DATE_PAT = re.compile(r"^(\d{2}-\d{2}-\d{4})\s")
_AMOUNT_PAT = re.compile(r"[\d,]+\.\d{2}")


def detect_equity(file_path: str) -> bool:
    """Return True if the PDF appears to be an Equity Bank statement."""
    try:
        with pdfplumber.open(file_path) as pdf:
            text = ""
            for page in pdf.pages[:2]:
                t = page.extract_text()
                if t:
                    text += t + " "
            text_upper = text.upper()
            has_stmt = "STATEMENT OF ACCOUNT" in text_upper
            has_equity = "EQUITY" in text_upper
            has_cols = (
                "PARTICULARS" in text_upper
                and "MONEY OUT" in text_upper
                and "MONEY IN" in text_upper
            )
            return bool(has_stmt and has_equity and has_cols)
    except Exception:
        return False


def _parse_equity_date(raw: str) -> Optional[str]:
    """Parse DD-MM-YYYY to ISO YYYY-MM-DD."""
    if not raw or not raw.strip():
        return None
    try:
        dt = datetime.strptime(raw.strip(), "%d-%m-%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_equity_balance(raw: str) -> Tuple[int, bool]:
    """
    Parse balance. Strip "Dr" suffix for overdrawn. Return (cents, is_overdrawn).
    Always returns positive cents.
    """
    if not raw or not raw.strip():
        return 0, False

    s = raw.strip()
    is_overdrawn = s.upper().endswith("DR")
    clean = s.replace("Dr", "").replace("dr", "").strip()

    if not clean:
        return 0, is_overdrawn

    clean = clean.replace(",", "")
    if clean.startswith("-"):
        clean = clean[1:]

    try:
        if "." in clean:
            whole_str, frac_str = clean.split(".", 1)
            frac_str = frac_str.ljust(2, "0")[:2]
            whole = int(whole_str) if whole_str else 0
            frac = int(frac_str)
            return whole * 100 + frac, is_overdrawn
        return int(clean) * 100, is_overdrawn
    except ValueError:
        return 0, False


def _is_skip_row(desc: str) -> bool:
    t = (desc or "").upper()
    return (
        "PAGE TOTAL" in t
        or "GRAND TOTAL" in t
        or "UNCLEARED CHEQUES" in t
        or t.startswith("NOTE: ANY OMISSION")
        or t.startswith("DO YOU NEED FOREIGN EXCHANGE")
    )


def _parse_equity_line(line: str) -> Optional[dict]:
    """Parse a transaction line. Returns dict or None if not a valid txn line."""
    line = line.strip()
    if not line:
        return None

    m = _DATE_PAT.match(line)
    if not m:
        return None

    date_raw = m.group(1)
    rest = line[len(date_raw) :].strip()

    amounts = _AMOUNT_PAT.findall(rest)
    has_dr = " Dr" in rest or " dr" in rest

    if not amounts:
        if "0.00" in rest or rest.strip() in ("0", ""):
            return {
                "date_raw": date_raw,
                "particulars": rest,
                "money_out": "",
                "money_in": "",
                "balance_raw": "",
                "is_opening": "OPENING" in rest.upper() or "B/FWD" in rest.upper(),
            }
        return None

    def strip_amounts(s: str, amts: List[str]) -> str:
        for a in amts:
            s = s.replace(a, " ", 1)
        return re.sub(r"\s+", " ", s).strip()

    if len(amounts) == 3:
        money_out, money_in, balance_raw = amounts[0], amounts[1], amounts[2]
        if has_dr:
            balance_raw = amounts[2] + " Dr"
        particulars = strip_amounts(rest.replace("Dr", "").replace("dr", ""), amounts)
    elif len(amounts) == 2:
        money_out = amounts[0]
        money_in = ""
        balance_raw = amounts[1] + " Dr" if has_dr else amounts[1]
        particulars = strip_amounts(rest.replace("Dr", "").replace("dr", ""), amounts)
    elif len(amounts) == 1:
        money_out = ""
        money_in = "" if has_dr else amounts[0]
        balance_raw = amounts[0] + " Dr" if has_dr else amounts[0]
        particulars = strip_amounts(rest.replace("Dr", "").replace("dr", ""), amounts)
    else:
        money_out = amounts[-3] if len(amounts) >= 3 else ""
        money_in = amounts[-2] if len(amounts) >= 2 else ""
        balance_raw = amounts[-1] + (" Dr" if has_dr else "")
        particulars = strip_amounts(rest.replace("Dr", "").replace("dr", ""), amounts)

    return {
        "date_raw": date_raw,
        "particulars": particulars,
        "money_out": money_out,
        "money_in": money_in,
        "balance_raw": balance_raw,
        "is_opening": False,
    }


def extract_equity_pdf(file_path: str) -> ExtractionResult:
    transactions: List[RawTransaction] = []
    warnings: List[WarningItem] = []
    row_idx = 0

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            in_transactions = False
            for line in text.split("\n"):
                if "Date" in line and "Particulars" in line and "Money Out" in line:
                    in_transactions = True
                    continue
                if not in_transactions:
                    continue

                parsed = _parse_equity_line(line)
                if not parsed:
                    if line.strip() == "0.00":
                        parsed = {
                            "date_raw": "",
                            "particulars": "Opening Balance",
                            "money_out": "",
                            "money_in": "",
                            "balance_raw": "0.00",
                            "is_opening": True,
                        }
                    else:
                        continue

                if _is_skip_row(parsed["particulars"]):
                    continue

                iso_date = _parse_equity_date(parsed["date_raw"]) or ""
                balance_raw = parsed["balance_raw"]
                balance_cents, is_overdrawn = _parse_equity_balance(balance_raw)
                balance_str = (
                    balance_raw.replace("Dr", "").replace("dr", "").strip()
                    if balance_raw
                    else ""
                )

                debit_raw = (
                    parsed["money_out"].replace(",", "").lstrip("-")
                    if parsed["money_out"]
                    else ""
                )
                credit_raw = (
                    parsed["money_in"].replace(",", "")
                    if parsed["money_in"]
                    else ""
                )

                if parsed.get("is_opening"):
                    debit_raw = ""
                    credit_raw = ""

                transactions.append(
                    RawTransaction(
                        row_index=row_idx,
                        date_raw=iso_date,
                        description=parsed["particulars"],
                        debit_raw=debit_raw,
                        credit_raw=credit_raw,
                        balance_raw=balance_str,
                        source_file=file_path,
                        extraction_confidence=1.0,
                        balance_is_overdrawn=is_overdrawn if "Dr" in (parsed["balance_raw"] or "") else None,
                    )
                )
                row_idx += 1

    return ExtractionResult(
        source_file=file_path,
        extractor_type="equity_pdf",
        row_count=len(transactions),
        extraction_status="success",
        warnings=warnings,
        raw_transactions=transactions,
    )
