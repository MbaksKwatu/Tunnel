"""
Equity Bank Kenya PDF statement extractor.

Personal format:
  Columns: Date | Value | Particulars | Money Out | Money In | Balance
  Header: STATEMENT OF ACCOUNT + EQUITY + Particulars / Money Out / Money In

Business format:
  Header: Account Statement + Narrative / Debit / Credit / Running Balance
  Transaction Date + Value Date (value date ignored) + narrative + amounts
  Date format: DD-MM-YYYY
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, List, Optional, Tuple

import pdfplumber

from app.models import ExtractionResult, RawTransaction, WarningItem

_DATE_PAT = re.compile(r"^(\d{2}-\d{2}-\d{4})\s")
_DATE2_PAT = re.compile(r"^(\d{2}-\d{2}-\d{4})\s+(\d{2}-\d{2}-\d{4})\s+(.*)$")
_AMOUNT_PAT = re.compile(r"[\d,]+\.\d{2}")


def _is_equity_business_format(text: str) -> bool:
    """Equity business account PDF: Account Statement + Debit/Credit/Running Balance columns."""
    return (
        "Account Statement" in text
        and "Debit" in text
        and "Credit" in text
        and "Running Balance" in text
    )


def detect_equity(file_path: str) -> bool:
    """Return True if the PDF appears to be an Equity Bank statement (personal or business)."""
    try:
        with pdfplumber.open(file_path) as pdf:
            text = ""
            for page in pdf.pages[:2]:
                t = page.extract_text()
                if t:
                    text += t + " "
            if _is_equity_business_format(text):
                return True
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


def _strip_amounts_from_rest(rest: str, amts: List[str]) -> str:
    s = rest
    for a in amts:
        s = s.replace(a, " ", 1)
    s = s.replace("Dr", "").replace("dr", "")
    return re.sub(r"\s+", " ", s).strip()


def _parse_equity_line(line: str) -> Optional[dict]:
    """Parse a personal-format transaction line. Returns dict or None if not a valid txn line."""
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


def _amount_str_to_cents(s: str) -> int:
    t = s.replace(",", "").strip()
    if not t:
        return 0
    neg = t.startswith("-")
    if neg:
        t = t[1:]
    if "." in t:
        w, f = t.split(".", 1)
        f = (f + "00")[:2]
        v = int(w or 0) * 100 + int(f)
    else:
        v = int(t) * 100
    return -v if neg else v


def _cents_to_equity_raw(cents: Optional[int]) -> str:
    if cents is None or cents == 0:
        return ""
    neg = cents < 0
    c = abs(cents)
    body = f"{c // 100}.{c % 100:02d}"
    return f"-{body}" if neg else body


def _parse_equity_business_amounts(
    line: str, previous_balance: Optional[int] = None
) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """
    Parse debit/credit/balance from Equity business statement amount line.

    Only decimal money tokens (x,xxx.yy) are considered — avoids matching dates.

    Pattern:
    - 2 numbers: [Amount, Balance] — debit if balance fell, credit if balance rose
      (first row with no previous balance: treat as [Debit, Balance])
    - 1 number: balance-only fragment
    - 3 numbers: [Debit, Credit, Balance]
    - More than 3: use last three as debit, credit, balance

    Returns: (debit_cents, credit_cents, balance_cents) — None for absent debit/credit.
    """
    m = _DATE2_PAT.match(line.strip())
    if not m:
        return None, None, None

    rest = m.group(3).strip()
    matches = _AMOUNT_PAT.findall(rest)
    if not matches:
        return None, None, None

    amounts_cents = [_amount_str_to_cents(x) for x in matches]

    if len(amounts_cents) == 1:
        return None, None, amounts_cents[0]

    if len(amounts_cents) == 2:
        amount, balance = amounts_cents[0], amounts_cents[1]
        if previous_balance is not None:
            if balance < previous_balance:
                return amount, None, balance
            if balance > previous_balance:
                return None, amount, balance
            return None, None, balance
        # No prior balance: two tokens = [Debit, Balance] (business layout default)
        return amount, None, balance

    if len(amounts_cents) == 3:
        return amounts_cents[0], amounts_cents[1], amounts_cents[2]

    return amounts_cents[-3], amounts_cents[-2], amounts_cents[-1]


def _clean_equity_business_description(desc: str) -> str:
    """Remove header artifacts from business statement descriptions."""
    patterns_to_remove = [
        r"^n Date Date Reference\s+",
        r"^Date Date Reference\s+",
        r"^Transaction Date Value Date\s+",
        r"^Narrative\s+Debit\s+Credit\s+",
        r"^Reference\s+",
    ]

    cleaned = desc
    for pattern in patterns_to_remove:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _parse_business_txn_line(
    line: str,
    narrative_prefix: str,
    previous_balance: Optional[int] = None,
) -> Tuple[Optional[dict], Optional[int]]:
    """
    Parse a business-format line: TransactionDate ValueDate rest...
    Returns (parsed_row_dict_or_None, new_running_balance_cents_or_None).
    """
    m = _DATE2_PAT.match(line.strip())
    if not m:
        return None, None

    txn_date = m.group(1)
    rest = m.group(3).strip()
    amounts = _AMOUNT_PAT.findall(rest)
    has_dr = " Dr" in rest or " dr" in rest

    if not amounts:
        if "0.00" in rest or rest.strip() in ("0", ""):
            inline = _strip_amounts_from_rest(rest, [])
            particulars = _clean_equity_business_description(
                (narrative_prefix + " " + inline).strip()
            )
            return (
                {
                    "date_raw": txn_date,
                    "particulars": particulars,
                    "money_out": "",
                    "money_in": "",
                    "balance_raw": "",
                    "is_opening": "OPENING" in particulars.upper()
                    or "B/FWD" in particulars.upper(),
                },
                previous_balance,
            )
        return None, previous_balance

    debit_cents, credit_cents, balance_cents = _parse_equity_business_amounts(
        line, previous_balance
    )

    balance_raw = amounts[-1] + (" Dr" if has_dr else "")

    particulars_inline = _strip_amounts_from_rest(
        rest.replace("Dr", "").replace("dr", ""), amounts
    )
    particulars = _clean_equity_business_description(
        (narrative_prefix + " " + particulars_inline).strip()
    )

    if (
        debit_cents is None
        and credit_cents is None
        and balance_cents is not None
        and len(amounts) == 1
    ):
        # Balance-only line — advance running balance, no transaction row
        return None, balance_cents

    if debit_cents is None and credit_cents is None and len(amounts) >= 2:
        # No movement (e.g. flat balance) — still advance balance
        return None, balance_cents

    return (
        {
            "date_raw": txn_date,
            "particulars": particulars,
            "money_out": _cents_to_equity_raw(debit_cents) if debit_cents else "",
            "money_in": _cents_to_equity_raw(credit_cents) if credit_cents else "",
            "balance_raw": balance_raw,
            "is_opening": False,
        },
        balance_cents,
    )


def _append_raw_transaction(
    transactions: List[RawTransaction],
    parsed: dict,
    file_path: str,
    row_idx: int,
) -> int:
    if _is_skip_row(parsed["particulars"]):
        return row_idx

    iso_date = _parse_equity_date(parsed["date_raw"]) or ""
    balance_raw = parsed["balance_raw"]
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

    is_overdrawn = bool(balance_raw and ("Dr" in balance_raw or "dr" in balance_raw))

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
            balance_is_overdrawn=is_overdrawn if is_overdrawn else None,
        )
    )
    return row_idx + 1


def _extract_equity_personal(pdf: Any, file_path: str) -> List[RawTransaction]:
    transactions: List[RawTransaction] = []
    row_idx = 0

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

            row_idx = _append_raw_transaction(transactions, parsed, file_path, row_idx)

    return transactions


def _extract_equity_business(pdf: Any, file_path: str) -> List[RawTransaction]:
    """Business layout: narrative lines often precede the double-date amount line."""
    transactions: List[RawTransaction] = []
    row_idx = 0
    seen_table = False
    buffer: List[str] = []
    previous_balance: Optional[int] = None

    for page in pdf.pages:
        text = page.extract_text()
        if not text:
            continue

        for line in text.split("\n"):
            raw_line = line
            line = line.strip()
            if (
                "Narrative" in raw_line
                and "Debit" in raw_line
                and "Credit" in raw_line
                and "Running Balance" in raw_line
            ):
                seen_table = True
                buffer = []
                continue

            if not seen_table:
                continue

            if _DATE2_PAT.match(line):
                prefix = " ".join(buffer).strip()
                buffer = []
                parsed, bal_update = _parse_business_txn_line(
                    line, prefix, previous_balance
                )
                if bal_update is not None:
                    previous_balance = bal_update
                if not parsed:
                    continue
                row_idx = _append_raw_transaction(
                    transactions, parsed, file_path, row_idx
                )
            elif line:
                buffer.append(line)

    return transactions


def extract_equity_pdf(file_path: str) -> ExtractionResult:
    warnings: List[WarningItem] = []
    transactions: List[RawTransaction] = []

    with pdfplumber.open(file_path) as pdf:
        sample_parts: List[str] = []
        for i, page in enumerate(pdf.pages[:2]):
            t = page.extract_text()
            if t:
                sample_parts.append(t)
        sample = "\n".join(sample_parts)

        if _is_equity_business_format(sample):
            transactions = _extract_equity_business(pdf, file_path)
        else:
            transactions = _extract_equity_personal(pdf, file_path)

    return ExtractionResult(
        source_file=file_path,
        extractor_type="equity_pdf",
        row_count=len(transactions),
        extraction_status="success",
        warnings=warnings,
        raw_transactions=transactions,
    )
