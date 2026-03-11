"""
Co-operative Bank Kenya PDF statement extractor.

Columns: Transaction Date | Value Date | Transaction Details | Reference Number | Debit | Credit | Balance
Date format: DD/MM/YYYY → ISO
"""
from __future__ import annotations

from datetime import datetime
from typing import List

import pdfplumber

from app.models import ExtractionResult, RawTransaction, WarningItem


def detect_coop(file_path: str) -> bool:
    """Return True if the PDF appears to be a Co-operative Bank statement."""
    try:
        with pdfplumber.open(file_path) as pdf:
            text = ""
            for page in pdf.pages[:3]:
                t = page.extract_text()
                if t:
                    text += t + " "
            text_upper = text.upper()
            has_bank = (
                "CO-OPERATIVE BANK" in text_upper
                or "COOPERATIVE BANK" in text_upper
                or "CO-OPERATIVE" in text_upper
            )
            has_stmt = "STATEMENT OF ACCOUNT" in text_upper
            has_marker = "KCOOKENA" in text_upper or "WE ARE YOU" in text_upper
            return bool(has_stmt and (has_bank or has_marker))
    except Exception:
        return False


def _parse_coop_date(raw: str) -> str | None:
    """Parse DD/MM/YYYY to ISO YYYY-MM-DD. Returns None on failure."""
    if not raw or not raw.strip():
        return None
    try:
        dt = datetime.strptime(raw.strip(), "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def _is_header_row(row: list) -> bool:
    """True if row is the column header."""
    if not row or len(row) < 5:
        return False
    first = (row[0] or "").upper()
    return "TRANSACTIO" in first or "VALUE DATE" in (row[1] or "").upper()


def _is_footer_row(description: str) -> bool:
    """Strip rows containing regulated-by text."""
    return "regulated by" in (description or "").lower()


def extract_coop_pdf(file_path: str) -> ExtractionResult:
    transactions: List[RawTransaction] = []
    warnings: List[WarningItem] = []
    row_idx = 0

    with pdfplumber.open(file_path) as pdf:
        pending: dict | None = None

        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables or []:
                for row in table:
                    if len(row) < 7:
                        continue

                    tx_date_raw = (row[0] or "").strip()
                    value_date_raw = (row[1] or "").strip()
                    details = (row[2] or "").strip().replace("\n", " ")
                    ref = (row[3] or "").strip().replace("\n", " ")
                    debit_raw = (row[4] or "").strip()
                    credit_raw = (row[5] or "").strip()
                    balance_raw = (row[6] or "").strip()

                    if _is_header_row(row):
                        continue

                    if _is_footer_row(details):
                        continue

                    if not value_date_raw and not details and not debit_raw and not credit_raw:
                        continue

                    iso_date = _parse_coop_date(tx_date_raw) or _parse_coop_date(value_date_raw)

                    if tx_date_raw:
                        if pending:
                            _flush_coop_pending(pending, transactions, warnings)
                            pending = None
                        pending = {
                            "row_index": row_idx,
                            "date_raw": iso_date or tx_date_raw,
                            "description": details,
                            "debit_raw": debit_raw,
                            "credit_raw": credit_raw,
                            "balance_raw": balance_raw,
                            "source_file": file_path,
                            "ref": ref,
                        }
                        row_idx += 1
                    else:
                        pending_ref = (pending or {}).get("ref", "")
                        if pending and ref and pending_ref and ref == pending_ref:
                            if details:
                                pending["description"] = (
                                    (pending["description"] or "") + " " + details
                                ).strip()
                            if debit_raw and not pending["debit_raw"]:
                                pending["debit_raw"] = debit_raw
                            if credit_raw and not pending["credit_raw"]:
                                pending["credit_raw"] = credit_raw
                            if balance_raw and not pending["balance_raw"]:
                                pending["balance_raw"] = balance_raw
                        else:
                            if pending:
                                _flush_coop_pending(pending, transactions, warnings)
                                pending = None
                            pending = {
                                "row_index": row_idx,
                                "date_raw": iso_date or value_date_raw,
                                "description": details,
                                "debit_raw": debit_raw,
                                "credit_raw": credit_raw,
                                "balance_raw": balance_raw,
                                "source_file": file_path,
                                "ref": ref,
                            }
                            row_idx += 1

        if pending:
            _flush_coop_pending(pending, transactions, warnings)

    has_warnings = len(warnings) > 0
    return ExtractionResult(
        source_file=file_path,
        extractor_type="coop_pdf",
        row_count=len(transactions),
        extraction_status="needs_review" if has_warnings else "success",
        warnings=warnings,
        raw_transactions=transactions,
    )


def _flush_coop_pending(
    pending: dict,
    transactions: List[RawTransaction],
    warnings: List[WarningItem],
) -> None:
    desc = pending["description"] or ""
    is_b_fwd = "B/FWD" in desc.upper() or "OPENING BALANCE" in desc.upper()

    if is_b_fwd:
        pending["debit_raw"] = ""
        pending["credit_raw"] = ""

    date_raw = pending["date_raw"]
    if not date_raw:
        date_raw = ""

    has_amounts = bool(pending["debit_raw"] or pending["credit_raw"] or pending["balance_raw"])
    confidence = 1.0 if (date_raw or desc) and (has_amounts or is_b_fwd) else 0.8

    transactions.append(
        RawTransaction(
            row_index=pending["row_index"],
            date_raw=date_raw,
            description=desc,
            debit_raw=pending["debit_raw"],
            credit_raw=pending["credit_raw"],
            balance_raw=pending["balance_raw"],
            source_file=pending["source_file"],
            extraction_confidence=confidence,
        )
    )
