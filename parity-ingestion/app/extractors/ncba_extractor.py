"""
NCBA Bank Kenya PDF statement extractor.

Supports common layouts:
- Date | Description/Narrative | Debit | Credit | Balance
- Date | Value Date | Description | Money Out | Money In | Balance
Date formats: DD/MM/YYYY, DD-MM-YYYY, DD Mon YYYY
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

import pdfplumber

from app.models import ExtractionResult, RawTransaction, WarningItem

# Date patterns (order matters — try most specific first)
_DATE_PAT_DDMMYYYY = re.compile(r"^(\d{1,2}[/-]\d{1,2}[/-]\d{4})\s")
_DATE_PAT_DDMonYYYY = re.compile(r"^(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\s")
_AMOUNT_PAT = re.compile(r"[\d,]+\.\d{2}")

MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def detect_ncba(file_path: str) -> bool:
    """Return True if the PDF appears to be an NCBA Bank Kenya statement."""
    try:
        with pdfplumber.open(file_path) as pdf:
            text = ""
            for page in pdf.pages[:3]:
                t = page.extract_text()
                if t:
                    text += t + " "
            text_upper = text.upper()
            has_ncba = (
                "NCBA" in text_upper
                or "NCBA BANK" in text_upper
                or "NCBA GROUP" in text_upper
                or ("NIC" in text_upper and "CBA" in text_upper)
            )
            return bool(has_ncba)
    except Exception:
        return False


def _parse_ncba_date(raw: str) -> Optional[str]:
    """Parse common NCBA date formats to ISO YYYY-MM-DD."""
    if not raw or not raw.strip():
        return None
    s = raw.strip()

    # DD/MM/YYYY or DD-MM-YYYY
    for sep in ["/", "-"]:
        try:
            dt = datetime.strptime(s, f"%d{sep}%m{sep}%Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # DD Mon YYYY (e.g. 20 JUL 2023)
    parts = s.split()
    if len(parts) == 3:
        try:
            day = int(parts[0])
            mon = MONTH_MAP.get(parts[1].upper())
            year = int(parts[2])
            if mon is not None:
                return f"{year}-{mon:02d}-{day:02d}"
        except (ValueError, IndexError):
            pass

    return None


def _is_skip_row(desc: str) -> bool:
    t = (desc or "").upper()
    return (
        "PAGE TOTAL" in t
        or "GRAND TOTAL" in t
        or "BALANCE AT PERIOD END" in t
        or "BALANCE B/FWD" in t
        or "OPENING BALANCE" in t
        or t.startswith("NOTE:")
        or "PAGE" in t and "OF" in t
    )


def _parse_ncba_line(line: str) -> Optional[dict]:
    """Parse a transaction line. Returns dict or None if not a valid txn line."""
    line = line.strip()
    if not line:
        return None

    # Try DD/MM/YYYY or DD-MM/YYYY first
    m = _DATE_PAT_DDMMYYYY.match(line)
    if not m:
        m = _DATE_PAT_DDMonYYYY.match(line)
    if not m:
        return None

    date_raw = m.group(1)
    rest = line[len(date_raw) :].strip()

    amounts = _AMOUNT_PAT.findall(rest)
    has_dr = " Dr" in rest or " dr" in rest or " DR" in rest

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


def extract_ncba_pdf(file_path: str) -> ExtractionResult:
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
                # Detect transaction section by common header patterns
                line_upper = line.upper()
                if (
                    ("DATE" in line_upper or "TXN DATE" in line_upper or "TRANSACTION DATE" in line_upper)
                    and ("DEBIT" in line_upper or "MONEY OUT" in line_upper or "DR" in line_upper)
                    and ("CREDIT" in line_upper or "MONEY IN" in line_upper or "CR" in line_upper)
                ):
                    in_transactions = True
                    continue
                if (
                    "DATE" in line_upper
                    and ("DESCRIPTION" in line_upper or "NARRATIVE" in line_upper or "PARTICULARS" in line_upper)
                    and ("BALANCE" in line_upper or "AMOUNT" in line_upper)
                ):
                    in_transactions = True
                    continue

                if not in_transactions:
                    continue

                parsed = _parse_ncba_line(line)
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

                iso_date = _parse_ncba_date(parsed["date_raw"]) or ""
                balance_raw = parsed.get("balance_raw", "")
                balance_str = (
                    balance_raw.replace("Dr", "").replace("dr", "").strip()
                    if balance_raw
                    else ""
                )

                debit_raw = (
                    parsed["money_out"].replace(",", "").lstrip("-")
                    if parsed.get("money_out")
                    else ""
                )
                credit_raw = (
                    parsed["money_in"].replace(",", "")
                    if parsed.get("money_in")
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
                    )
                )
                row_idx += 1

    return ExtractionResult(
        source_file=file_path,
        extractor_type="ncba_pdf",
        row_count=len(transactions),
        extraction_status="success",
        warnings=warnings,
        raw_transactions=transactions,
    )
