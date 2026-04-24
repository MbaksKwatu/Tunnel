"""
Deterministic helpers for XLSX row hashing and ordering — aligned with
backend/v1/parsing/common.py (subset used by xlsx_parser).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, List


def compute_txn_id(row: Dict[str, Any], document_id: str) -> str:
    basis = "|".join(
        [
            document_id or "",
            row.get("account_id", ""),
            row.get("txn_date", ""),
            str(row.get("signed_amount_cents", "")),
            row.get("normalized_descriptor", ""),
        ]
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def deduplicate_structural_duplicates(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not rows:
        return rows

    import datetime as _dt

    deduped = [rows[0]]

    for i in range(1, len(rows)):
        prev = deduped[-1]
        curr = rows[i]

        prev_desc = (prev.get("normalized_descriptor") or "").strip().lower()
        curr_desc = (curr.get("normalized_descriptor") or "").strip().lower()

        same_identity = (
            curr.get("account_id") == prev.get("account_id")
            and curr.get("signed_amount_cents") == prev.get("signed_amount_cents")
            and curr_desc == prev_desc
        )

        prev_date_s = prev.get("txn_date")
        curr_date_s = curr.get("txn_date")
        date_gap = None
        if prev_date_s and curr_date_s:
            try:
                prev_date = _dt.datetime.strptime(str(prev_date_s), "%Y-%m-%d").date()
                curr_date = _dt.datetime.strptime(str(curr_date_s), "%Y-%m-%d").date()
                date_gap = (curr_date - prev_date).days
            except ValueError:
                date_gap = None

        is_same_day_duplicate = same_identity and curr.get("txn_date") == prev.get("txn_date")
        is_cross_day_carryover = same_identity and date_gap is not None and 0 < date_gap <= 2

        if is_same_day_duplicate or is_cross_day_carryover:
            continue

        deduped.append(curr)

    return deduped


def sort_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows_sorted = sorted(
        rows,
        key=lambda r: (
            r["txn_date"],
            r["account_id"],
            r["signed_amount_cents"],
            r["normalized_descriptor"],
            r["txn_id"],
        ),
    )
    return deduplicate_structural_duplicates(rows_sorted)


def canonical_hash(rows: Iterable[Dict[str, Any]]) -> str:
    payload = json.dumps(list(rows), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
