import hashlib
import json
import re
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any, Dict, Iterable, List

from openpyxl.utils.datetime import from_excel

from .errors import InvalidSchemaError, CurrencyMismatchError


REQUIRED_HEADERS = {"date", "amount", "description"}
OPTIONAL_HEADERS = {"direction"}

ISO_CURRENCY_RE = re.compile(r"\b[A-Z]{3}\b")


def normalize_header(value: Any) -> str:
    return str(value or "").strip().lower()


def normalize_descriptor(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def parse_date(value: Any) -> str:
    """
    Deterministic date parsing:
    - Excel serials handled via openpyxl from_excel
    - ISO-like strings accepted (yyyy-mm-dd, yyyy/mm/dd)
    - Reject ambiguous dd/mm/yy or mm/dd/yy two-digit years
    """
    if isinstance(value, (datetime, date)):
        return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()

    if isinstance(value, (int, float)):
        # Excel serial
        try:
            dt = from_excel(value)
            return dt.date().isoformat() if isinstance(dt, datetime) else dt.isoformat()
        except Exception as exc:
            raise InvalidSchemaError(f"Invalid Excel date serial: {value}") from exc

    s = str(value or "").strip()
    if not s:
        raise InvalidSchemaError("Missing date value")

    # Reject ambiguous 2-digit-year or 3-part numeric with 2-digit year
    if re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{2}$", s):
        raise InvalidSchemaError(f"Ambiguous date format: {s}")

    # Accept common unambiguous patterns
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


def parse_amount_to_cents(raw_value: Any, deal_currency: str) -> int:
    cents, _ = parse_amount_with_detection(raw_value, deal_currency)
    return cents


def parse_amount_with_detection(raw_value: Any, deal_currency: str) -> (int, str):
    """
    Returns (cents, currency_detection_flag)
    detection_flag: "ambiguous" if symbol-only detected, "unknown" otherwise.
    """
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


def sort_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        rows,
        key=lambda r: (
            r["txn_date"],
            r["account_id"],
            r["signed_amount_cents"],
            r["normalized_descriptor"],
            r["txn_id"],
        ),
    )


def canonical_hash(rows: Iterable[Dict[str, Any]]) -> str:
    payload = json.dumps(list(rows), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
