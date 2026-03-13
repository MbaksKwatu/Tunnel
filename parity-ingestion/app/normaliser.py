"""
Phase 3 Normaliser: RawTransaction → NormalisedTransaction

Rules (non-negotiable):
  - No float coercion anywhere. Amounts are parsed via string arithmetic only.
  - Date formats are explicit — no dateutil guessing.
  - debit_cents and credit_cents are always positive integers (sign = field name).
  - balance_cents may be signed (negative balance is valid in some accounts).
  - If any field cannot be parsed, normalisation_status = NEEDS_REVIEW.

Supported date formats:
  SCB Kenya PDF  : DD/Mon/YYYY       e.g. "06/Jan/2022"     → strptime "%d/%b/%Y"
  Equity/NCBA    : DD Mon YYYY       e.g. "03 Jan 2024"     → strptime "%d %b %Y"
  NCBA           : DD/MM/YYYY        e.g. "20/07/2023"      → strptime "%d/%m/%Y"
  M-Pesa CSV     : YYYY-MM-DDT...    e.g. "2024-04-23T00:00:00 16:08:03.005000"
  M-Pesa legacy  : YYYY-MM-DD HH:MM  e.g. "2023-09-30 22:16:49"
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple

from app.models import (
    ExtractionMethod,
    ExtractionResult,
    NormalisationStatus,
    NormalisedTransaction,
    RawTransaction,
)

# ── Date format strings (explicit — no guessing) ─────────────────────────────

_FMT_SCB = "%d/%b/%Y"       # 06/Jan/2022
_FMT_EQUITY = "%d %b %Y"    # 03 Jan 2024
_FMT_NCBA_DDMMYYYY = "%d/%m/%Y"   # 20/07/2023
_FMT_ISO_DATE = "%Y-%m-%d"  # 2024-04-23  (extracted from ISO prefix)


def _parse_date(raw: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Return (iso_date, warning_message).
    iso_date is YYYY-MM-DD string or None.
    warning_message is None on success.
    """
    if not raw or not raw.strip():
        return None, "empty date field"

    s = raw.strip()

    # SCB Kenya: DD/Mon/YYYY
    try:
        dt = datetime.strptime(s, _FMT_SCB)
        return dt.strftime("%Y-%m-%d"), None
    except ValueError:
        pass

    # Equity Bank Kenya / NCBA: DD Mon YYYY
    try:
        dt = datetime.strptime(s, _FMT_EQUITY)
        return dt.strftime("%Y-%m-%d"), None
    except ValueError:
        pass

    # NCBA: DD/MM/YYYY
    try:
        dt = datetime.strptime(s, _FMT_NCBA_DDMMYYYY)
        return dt.strftime("%Y-%m-%d"), None
    except ValueError:
        pass

    # M-Pesa: starts with YYYY-MM-DD (with T or space separator after date part)
    # e.g. "2024-04-23T00:00:00 16:08:03.005000" or "2023-09-30 22:16:49"
    date_part = s.split("T")[0] if "T" in s else s.split(" ")[0]
    try:
        dt = datetime.strptime(date_part, _FMT_ISO_DATE)
        return dt.strftime("%Y-%m-%d"), None
    except ValueError:
        pass

    return None, f"cannot parse date: {raw!r}"


# ── Amount parser (no floats) ─────────────────────────────────────────────────

def _parse_cents(raw: str) -> Tuple[Optional[int], Optional[str]]:
    """
    Return (cents, warning_message).
    cents is a non-negative integer or None.
    Negative signs (from M-Pesa withdrawn column) are stripped — callers
    interpret debit vs credit from field assignment, not sign.
    """
    if not raw or raw.strip() in ("", "nan"):
        return None, None

    clean = raw.replace(",", "").strip()

    # Strip sign — debit/credit semantics come from field name
    if clean.startswith("-"):
        clean = clean[1:]
    elif clean.startswith("+"):
        clean = clean[1:]

    if not clean:
        return None, f"empty amount after stripping sign: {raw!r}"

    try:
        if "." in clean:
            whole_str, frac_str = clean.split(".", 1)
            # Pad or truncate fractional part to exactly 2 digits
            frac_str = frac_str.ljust(2, "0")[:2]
            whole = int(whole_str) if whole_str else 0
            frac = int(frac_str)
            return whole * 100 + frac, None
        else:
            return int(clean) * 100, None
    except ValueError:
        return None, f"cannot parse amount: {raw!r}"


# ── Public interface ──────────────────────────────────────────────────────────

def normalise(
    raw: RawTransaction,
    extraction_method: ExtractionMethod,
) -> NormalisedTransaction:
    """Convert a single RawTransaction to a NormalisedTransaction."""
    warnings: list[str] = []

    # Date
    iso_date, date_warn = _parse_date(raw.date_raw)
    if date_warn:
        warnings.append(f"row {raw.row_index} date: {date_warn}")

    # Amounts — all stored as positive integers; sign semantics = field name
    debit_cents, debit_warn = _parse_cents(raw.debit_raw)
    if debit_warn:
        warnings.append(f"row {raw.row_index} debit: {debit_warn}")

    credit_cents, credit_warn = _parse_cents(raw.credit_raw)
    if credit_warn:
        warnings.append(f"row {raw.row_index} credit: {credit_warn}")

    balance_cents, balance_warn = _parse_cents(raw.balance_raw)
    if balance_warn:
        warnings.append(f"row {raw.row_index} balance: {balance_warn}")

    # Warn if no amounts at all
    if debit_cents is None and credit_cents is None and balance_cents is None:
        if raw.debit_raw or raw.credit_raw or raw.balance_raw:
            warnings.append(
                f"row {raw.row_index}: all amount fields unparseable "
                f"(debit={raw.debit_raw!r} credit={raw.credit_raw!r} balance={raw.balance_raw!r})"
            )

    status = (
        NormalisationStatus.NEEDS_REVIEW if warnings else NormalisationStatus.OK
    )

    return NormalisedTransaction(
        row_index=raw.row_index,
        source_extraction_method=extraction_method,
        date=iso_date,
        description=raw.description,
        debit_cents=debit_cents,
        credit_cents=credit_cents,
        balance_cents=balance_cents,
        currency="KES",
        raw_date=raw.date_raw or None,
        raw_debit=raw.debit_raw or None,
        raw_credit=raw.credit_raw or None,
        raw_balance=raw.balance_raw or None,
        row_confidence=raw.extraction_confidence,
        normalisation_status=status,
        normalisation_warnings=warnings,
    )


def normalise_all(result: ExtractionResult) -> ExtractionResult:
    """
    Run normalise() over every RawTransaction in result and attach the
    NormalisedTransaction list + aggregated warnings to result in place.
    Returns the same result object.
    """
    normalised: list[NormalisedTransaction] = []
    all_warnings: list[str] = []

    for raw in result.raw_transactions:
        txn = normalise(raw, result.extractor_type)
        normalised.append(txn)
        all_warnings.extend(txn.normalisation_warnings)

    result.normalised_transactions = normalised
    result.normalisation_warnings = all_warnings
    return result
