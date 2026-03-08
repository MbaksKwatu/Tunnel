"""
SCB Kenya bank statement PDF extractor.

Column assignment uses x-centre = (x0 + x1) / 2 throughout.
An additional x0 >= 500 guard filters exchange-rate mentions
embedded in Particulars text before centre-based assignment.

Confirmed column centres from page-1 inspection:
  Debit   : centre <= 635
  Credit  : 635 < centre <= 740
  Balance : centre > 740
"""
from __future__ import annotations

import re
from typing import List, Tuple

import pdfplumber

from app.models import ExtractionResult, RawTransaction, WarningItem
from app.extractors.shared import _group_by_line

# ── column centre thresholds (calibrated from real file) ─────────────────────
_DEBIT_MAX_CENTRE: float = 635.0
_CREDIT_MAX_CENTRE: float = 740.0
# Balance: centre > 740

# Amount words must also have x0 >= this to exclude in-description numbers
_AMOUNT_MIN_X0: float = 500.0

# Date column: words at x0 < this value
_DATE_MAX_X0: float = 120.0

# Description column: words with x0 between this and _AMOUNT_MIN_X0
_DESC_MIN_X0: float = 110.0

# Row grouping tolerance (points)
_ROW_TOP_TOLERANCE: float = 4.0

# Date pattern for SCB Kenya: DD/Mon/YYYY
_DATE_PAT = re.compile(r"^\d{2}/[A-Za-z]{3}/\d{4}$")

# Amount pattern: comma-formatted number
_AMOUNT_PAT = re.compile(r"^[\d,]+\.\d{2}$")

# Markers for opening/closing balance rows
_BALANCE_MARKERS = ("OPENING BALANCE", "CLOSING BALANCE", "BROUGHT FORWARD")


def _centre(word: dict) -> float:
    return (word["x0"] + word["x1"]) / 2.0


def _assign_amount_column(word: dict) -> str | None:
    """Return 'debit', 'credit', 'balance', or None if not an amount column word."""
    if not _AMOUNT_PAT.match(word["text"]):
        return None
    if word["x0"] < _AMOUNT_MIN_X0:
        return None
    c = _centre(word)
    if c <= _DEBIT_MAX_CENTRE:
        return "debit"
    if c <= _CREDIT_MAX_CENTRE:
        return "credit"
    return "balance"


def _group_words_into_rows(words: list[dict]) -> list[list[dict]]:
    """Bucket words into visual rows using top-position proximity."""
    return _group_by_line(words, _ROW_TOP_TOLERANCE)


def _is_balance_marker_row(desc_parts: list[str]) -> bool:
    text = " ".join(desc_parts).upper()
    return any(m in text for m in _BALANCE_MARKERS)


def extract_scb_pdf(file_path: str) -> ExtractionResult:
    transactions: list[RawTransaction] = []
    warnings: list[WarningItem] = []
    row_idx = 0

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            if not words:
                continue

            visual_rows = _group_words_into_rows(words)

            # Pending transaction being assembled (for multi-line merging)
            pending: dict | None = None

            for row_words in visual_rows:
                # Separate words into their logical columns
                date_parts: list[str] = []
                desc_parts: list[str] = []
                debit_parts: list[str] = []
                credit_parts: list[str] = []
                balance_parts: list[str] = []

                for w in row_words:
                    col = _assign_amount_column(w)
                    if col == "debit":
                        debit_parts.append(w["text"])
                    elif col == "credit":
                        credit_parts.append(w["text"])
                    elif col == "balance":
                        balance_parts.append(w["text"])
                    elif w["x0"] < _DATE_MAX_X0:
                        date_parts.append(w["text"])
                    elif _DESC_MIN_X0 <= w["x0"] < _AMOUNT_MIN_X0:
                        desc_parts.append(w["text"])

                date_str = " ".join(date_parts).strip()
                desc_str = " ".join(desc_parts).strip()
                debit_str = " ".join(debit_parts).strip()
                credit_str = " ".join(credit_parts).strip()
                balance_str = " ".join(balance_parts).strip()

                # Skip header rows (contain column label words)
                if date_str in ("Trx.", "Date", "Trx. Date") or desc_str in (
                    "Particulars",
                    "Statement Of Account",
                ):
                    continue

                has_date = bool(_DATE_PAT.match(date_str))
                has_content = bool(desc_str or debit_str or credit_str or balance_str)

                if not has_content:
                    continue

                # Opening/closing balance markers — warn and skip
                if _is_balance_marker_row(desc_parts + date_parts):
                    if pending is not None:
                        # flush pending before warning row
                        _flush_pending(pending, transactions, warnings)
                        pending = None
                    raw_text = " ".join(
                        w["text"] for w in row_words
                    )
                    warnings.append(
                        WarningItem(
                            row_index=row_idx,
                            message="Balance marker row skipped",
                            raw_text=raw_text,
                        )
                    )
                    row_idx += 1
                    continue

                if has_date:
                    # Flush any pending transaction before starting a new one
                    if pending is not None:
                        _flush_pending(pending, transactions, warnings)
                    pending = {
                        "row_index": row_idx,
                        "date_raw": date_str,
                        "description": desc_str,
                        "debit_raw": debit_str,
                        "credit_raw": credit_str,
                        "balance_raw": balance_str,
                        "source_file": file_path,
                    }
                    row_idx += 1
                else:
                    # Continuation row — append description and fill in any missing amounts
                    if pending is not None:
                        if desc_str:
                            pending["description"] = (
                                pending["description"] + " " + desc_str
                            ).strip()
                        if debit_str and not pending["debit_raw"]:
                            pending["debit_raw"] = debit_str
                        if credit_str and not pending["credit_raw"]:
                            pending["credit_raw"] = credit_str
                        if balance_str and not pending["balance_raw"]:
                            pending["balance_raw"] = balance_str
                    # continuation rows without a pending parent are silently dropped

            # Flush last pending transaction for this page
            if pending is not None:
                _flush_pending(pending, transactions, warnings)
                pending = None

    has_warnings = len(warnings) > 0
    return ExtractionResult(
        source_file=file_path,
        extractor_type="scb_pdf",
        row_count=len(transactions),
        extraction_status="needs_review" if has_warnings else "success",
        warnings=warnings,
        raw_transactions=transactions,
    )


def _flush_pending(
    pending: dict,
    transactions: list[RawTransaction],
    warnings: list[WarningItem],
) -> None:
    desc = pending["description"]
    date = pending["date_raw"]

    has_date = bool(_DATE_PAT.match(date))
    has_amounts = bool(
        pending["debit_raw"] or pending["credit_raw"] or pending["balance_raw"]
    )

    if not has_date and not desc:
        return

    if has_date and has_amounts:
        confidence = 1.0
    elif has_date:
        confidence = 0.8
        warnings.append(
            WarningItem(
                row_index=pending["row_index"],
                message="Transaction row missing all amount fields",
                raw_text=f"{date} | {desc}",
            )
        )
    else:
        confidence = 0.9

    transactions.append(
        RawTransaction(
            row_index=pending["row_index"],
            date_raw=date,
            description=desc,
            debit_raw=pending["debit_raw"],
            credit_raw=pending["credit_raw"],
            balance_raw=pending["balance_raw"],
            source_file=pending["source_file"],
            extraction_confidence=confidence,
        )
    )
