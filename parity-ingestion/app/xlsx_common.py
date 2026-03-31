"""
Deterministic date/amount helpers for XLSX — ported from backend/v1/parsing/common.py
(only what xlsx extraction needs).
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

from openpyxl.utils.datetime import from_excel

from app.parsing_errors import CurrencyMismatchError, InvalidSchemaError

REQUIRED_HEADERS = frozenset({"date", "amount", "description"})
OPTIONAL_HEADERS = frozenset({"direction"})

ISO_CURRENCY_RE = re.compile(r"\b[A-Z]{3}\b")


def normalize_header(value: Any) -> str:
    return str(value or "").strip().lower()


def normalize_descriptor(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def parse_date(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()

    if isinstance(value, (int, float)):
        try:
            dt = from_excel(value)
            return dt.date().isoformat() if isinstance(dt, datetime) else dt.isoformat()
        except Exception as exc:
            raise InvalidSchemaError(f"Invalid Excel date serial: {value}") from exc

    s = str(value or "").strip()
    if not s:
        raise InvalidSchemaError("Missing date value")

    if re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{2}$", s):
        raise InvalidSchemaError(f"Ambiguous date format: {s}")

    patterns = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m-%d-%Y",
        "%m/%d/%Y",
    ]
    for fmt in patterns:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    raise InvalidSchemaError(f"Unparseable date: {s}")


def _strip_currency_symbols(s: str) -> str:
    return s.replace(",", "").replace(" ", "").replace("$", "").replace("€", "").replace("£", "")


def check_currency_conflict(raw: str, deal_currency: str) -> None:
    match = ISO_CURRENCY_RE.search(raw or "")
    if match:
        iso = match.group(0)
        if deal_currency and iso.upper() != deal_currency.upper():
            raise CurrencyMismatchError(f"Currency mismatch: found {iso}, expected {deal_currency}")


def parse_amount_with_detection(raw_value: Any, deal_currency: str) -> tuple[int, str]:
    raw_str = str(raw_value).strip()
    if not raw_str:
        raise InvalidSchemaError("Amount is empty")

    check_currency_conflict(raw_str, deal_currency)
    detection = "unknown"
    if any(sym in raw_str for sym in ["$", "€", "£"]):
        detection = "ambiguous"

    cleaned = _strip_currency_symbols(raw_str)
    if not cleaned:
        raise InvalidSchemaError("Amount missing after cleaning")

    try:
        value = Decimal(cleaned)
    except Exception as exc:
        raise InvalidSchemaError(f"Non-numeric amount: {raw_str}") from exc

    cents = int((value * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
    if cents == 0:
        raise InvalidSchemaError("Zero-value transactions are not allowed")
    return cents, detection
