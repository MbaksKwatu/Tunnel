"""
M-Pesa PDF full statement extractor.

Separate from mpesa_extractor.py (CSV). Do not modify or import from mpesa_extractor.py.

Columns: Receipt No | Completion Time | Details | Transaction Status | Paid in | Withdrawn | Balance
Date: YYYY-MM-DD HH:MM:SS — take first 10 chars for ISO date.
Status filter: Transaction Status == "Completed" (case-insensitive). Discard others.
Paid in → positive amount (credit_raw). Withdrawn → negative (debit_raw).
"""
from __future__ import annotations

from typing import List

import pdfplumber

from app.models import ExtractionResult, RawTransaction, WarningItem


def detect_mpesa_pdf(file_path: str) -> bool:
    """Return True if the PDF appears to be an M-Pesa full statement."""
    try:
        with pdfplumber.open(file_path) as pdf:
            text = ""
            for page in pdf.pages[:2]:
                t = page.extract_text()
                if t:
                    text += t + " "
            return (
                "MPESA FULL STATEMENT" in text
                and "Safaricom" in text
                and "Receipt No" in text
            )
    except Exception:
        return False


def _parse_mpesa_date(completion_time: str) -> str:
    """Extract YYYY-MM-DD from 'YYYY-MM-DD HH:MM:SS' format."""
    if not completion_time or len(completion_time) < 10:
        return ""
    return completion_time.strip()[:10]


def extract_mpesa_pdf(file_path: str) -> ExtractionResult:
    transactions: List[RawTransaction] = []
    warnings: List[WarningItem] = []
    row_idx = 0

    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables or []:
                    header_idx: int | None = None
                    for i, row in enumerate(table):
                        if not row or len(row) < 6:
                            continue
                        first = (row[0] or "").strip()
                        if "Receipt No" in first or "Receipt No" in str(row):
                            header_idx = i
                            break

                    if header_idx is None:
                        continue

                    for row in table[header_idx + 1 :]:
                        if len(row) < 6:
                            continue

                        receipt = (row[0] or "").strip()
                        completion_time = (row[1] or "").strip()
                        details = (row[2] or "").strip().replace("\n", " ")
                        status = (row[3] or "").strip()
                        paid_in = (row[4] or "").strip()
                        withdrawn = (row[5] or "").strip()
                        balance = (row[6] if len(row) > 6 else "") or ""
                        balance = balance.strip()

                        if not completion_time and not details:
                            continue

                        if status.upper() != "COMPLETED":
                            continue

                        date_raw = _parse_mpesa_date(completion_time)
                        if not date_raw:
                            continue

                        if paid_in:
                            debit_raw = ""
                            credit_raw = paid_in.replace(",", "")
                        elif withdrawn:
                            debit_raw = withdrawn.replace(",", "").lstrip("-")
                            credit_raw = ""
                        else:
                            debit_raw = ""
                            credit_raw = ""

                        transactions.append(
                            RawTransaction(
                                row_index=row_idx,
                                date_raw=date_raw,
                                description=details,
                                debit_raw=debit_raw,
                                credit_raw=credit_raw,
                                balance_raw=balance,
                                source_file=file_path,
                                extraction_confidence=1.0,
                            )
                        )
                        row_idx += 1

    except Exception as e:
        return ExtractionResult(
            source_file=file_path,
            extractor_type="mpesa_pdf",
            row_count=0,
            extraction_status="failed",
            warnings=[
                WarningItem(row_index=0, message=str(e), raw_text=""),
            ],
            raw_transactions=[],
        )

    return ExtractionResult(
        source_file=file_path,
        extractor_type="mpesa_pdf",
        row_count=len(transactions),
        extraction_status="success",
        warnings=warnings,
        raw_transactions=transactions,
    )
