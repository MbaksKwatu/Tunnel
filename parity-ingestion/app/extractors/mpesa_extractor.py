"""
M-Pesa CSV statement extractor.

Expected CSV structure (confirmed from real file inspection):
  Rows 1-N   : metadata / summary block (variable length)
  Row K      : "Receipt No.,Completion Time,..." — this is the column header
  Rows K+1.. : transaction data

Column mapping (0-indexed after slicing to transaction block):
  0  receipt_no
  1  date_part       e.g. "2024-04-23T00:00:00"
  2  time_part       e.g. "16:08:03.005000"
  3  details
  4  status          e.g. "Completed"
  5  paid_in         credit amount (positive) or empty
  6  withdrawn       debit amount (negative, e.g. "-55") or empty
  7  (unused)
  8  balance

Phase 1: no date parsing, no float conversion. All amounts stored as raw strings.
Withdrawn values are stored as-is (including the negative sign).
"""
from __future__ import annotations

import pandas as pd

from app.models import ExtractionResult, RawTransaction, WarningItem

_HEADER_SENTINEL = "Receipt No."
_EXPECTED_STATUS = "Completed"


def extract_mpesa_csv(file_path: str) -> ExtractionResult:
    # Read without assuming any header — preserve the full file
    raw = pd.read_csv(file_path, header=None, dtype=str, keep_default_na=False)

    # Locate the row that contains the column headers
    header_row_idx: int | None = None
    for i, row in raw.iterrows():
        if str(row.iloc[0]).strip() == _HEADER_SENTINEL:
            header_row_idx = int(i)
            break

    if header_row_idx is None:
        return ExtractionResult(
            source_file=file_path,
            extractor_type="mpesa_csv",
            row_count=0,
            extraction_status="failed",
            warnings=[
                WarningItem(
                    row_index=0,
                    message=f"Could not find '{_HEADER_SENTINEL}' header row in CSV",
                    raw_text="",
                )
            ],
            raw_transactions=[],
        )

    # Slice to transaction rows only
    data = raw.iloc[header_row_idx + 1 :].reset_index(drop=True)

    # Pad to at least 9 columns if file is narrower
    while data.shape[1] < 9:
        data[data.shape[1]] = ""

    data.columns = list(range(data.shape[1]))

    transactions: list[RawTransaction] = []
    warnings: list[WarningItem] = []

    for row_idx, row in data.iterrows():
        receipt_no  = str(row[0]).strip()
        date_part   = str(row[1]).strip()
        time_part   = str(row[2]).strip()
        details     = str(row[3]).strip()
        status      = str(row[4]).strip()
        paid_in     = str(row[5]).strip()
        withdrawn   = str(row[6]).strip()
        balance     = str(row[8]).strip() if data.shape[1] > 8 else ""

        # Skip completely empty rows
        if not receipt_no and not details:
            continue

        # Warn on non-Completed rows but still include them
        if status and status != _EXPECTED_STATUS:
            warnings.append(
                WarningItem(
                    row_index=int(row_idx),
                    message=f"Unexpected transaction status: {status!r}",
                    raw_text=f"{receipt_no} | {details}",
                )
            )

        # Combine date + time as a single raw string — no parsing
        date_raw = f"{date_part} {time_part}".strip()

        # credit_raw = paid_in field (positive value or "")
        credit_raw = paid_in if paid_in not in ("", "nan") else ""

        # debit_raw = withdrawn field, stored as-is (may include negative sign)
        debit_raw = withdrawn if withdrawn not in ("", "nan") else ""

        balance_raw = balance if balance not in ("", "nan") else ""

        # Confidence: 1.0 if all key fields present
        key_fields = [date_raw, details, (credit_raw or debit_raw)]
        confidence = 1.0 if all(key_fields) else 0.9

        transactions.append(
            RawTransaction(
                row_index=int(row_idx),
                date_raw=date_raw,
                description=details,
                debit_raw=debit_raw,
                credit_raw=credit_raw,
                balance_raw=balance_raw,
                source_file=file_path,
                extraction_confidence=confidence,
            )
        )

    extraction_status = (
        "failed"
        if not transactions
        else ("needs_review" if warnings else "success")
    )

    return ExtractionResult(
        source_file=file_path,
        extractor_type="mpesa_csv",
        row_count=len(transactions),
        extraction_status=extraction_status,
        warnings=warnings,
        raw_transactions=transactions,
    )
