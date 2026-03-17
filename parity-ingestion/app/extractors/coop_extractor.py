"""
Co-operative Bank Kenya PDF statement extractor.

Columns: Transaction Date | Value Date | Transaction Details | Reference Number | Debit | Credit | Balance
Date format: DD/MM/YYYY → ISO
"""
from __future__ import annotations

import re as _re
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
            has_layout_b = (
                "TRANS" in text_upper
                and "CHANNEL" in text_upper
                and "BOOK BALANCE" in text_upper
                and "MSME" in text_upper
            )
            return bool(
                (has_stmt and (has_bank or has_marker))
                or has_layout_b
            )
    except Exception:
        return False


def _parse_coop_date(raw: str) -> str | None:
    """Parse DD/MM/YYYY or DD-M-YYYY to ISO YYYY-MM-DD. Returns None on failure."""
    if not raw or not raw.strip():
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _detect_pattern(description: str, channel: str = "") -> tuple[str, str]:
    """
    Returns (classification_status, pattern_hint) for a transaction.
    AUTO_CLASSIFIED = system is confident.
    PENDING_CLASSIFICATION = analyst must resolve.
    """
    desc_upper = (description or "").upper()
    chan_upper = (channel or "").upper()

    if "REVERSED :" in desc_upper:
        return ("PENDING_CLASSIFICATION", "REVERSAL_PAIR")

    if desc_upper.startswith("POSAG") or "~POS" in desc_upper:
        return ("PENDING_CLASSIFICATION", "POS_RECEIPT")

    if "PESALINK" in desc_upper and ("COMMISSION" in desc_upper or "CHARGE" in desc_upper or "EXCISE" in desc_upper):
        return ("AUTO_CLASSIFIED", "BANK_CHARGE")

    if "PESALINK" in desc_upper:
        return ("PENDING_CLASSIFICATION", "PESALINK_TRANSFER")

    if "MPESA C2B" in desc_upper or "MPESAC2B" in desc_upper:
        return ("AUTO_CLASSIFIED", "MPESA_C2B")

    if "KPLC" in desc_upper and "PREPAID" in desc_upper:
        return ("AUTO_CLASSIFIED", "KPLC_PREPAID")

    if "KPLCPREPAIDCOMM" in desc_upper or "EXCISE DUTY OMNI" in desc_upper:
        return ("AUTO_CLASSIFIED", "BANK_CHARGE")

    if "MSME_BRONZE_MAINT" in desc_upper or "MONTHLY MAINTENANCE FEE" in desc_upper:
        return ("AUTO_CLASSIFIED", "BANK_CHARGE")

    if "EXCISE" in desc_upper and ("CHARGES" in desc_upper or "CHANNEL" in chan_upper):
        return ("AUTO_CLASSIFIED", "BANK_CHARGE")

    if "DEBIT ALERT CRG" in desc_upper or "DEBIT CRG" in desc_upper:
        return ("AUTO_CLASSIFIED", "BANK_CHARGE")

    if "CASH WITHDRAWAL FEE" in desc_upper:
        return ("AUTO_CLASSIFIED", "BANK_CHARGE")

    if "EXCISE CASH WITHDRAWAL" in desc_upper:
        return ("AUTO_CLASSIFIED", "BANK_CHARGE")

    if "CASH WITHDRAWAL" in desc_upper and "FEE" not in desc_upper:
        return ("AUTO_CLASSIFIED", "CASH_WITHDRAWAL")

    if "CREDIT ALERT CRG" in desc_upper or "CREDIT CRG EXCISE" in desc_upper or "CREDIT CRG" in desc_upper:
        return ("AUTO_CLASSIFIED", "BANK_CHARGE")

    if "INWARD EFT CHARGES" in desc_upper or "INWARD EFT CHARGE" in desc_upper:
        return ("AUTO_CLASSIFIED", "BANK_CHARGE")

    if "MPESA BANK COMMISSION" in desc_upper or "EXCISE MPESA BANK" in desc_upper:
        return ("AUTO_CLASSIFIED", "BANK_CHARGE")

    if "TRANSFER TO M-PESA" in desc_upper:
        return ("AUTO_CLASSIFIED", "MPESA_TRANSFER")

    if "SAFARICOM AIRTIME" in desc_upper or "AIRTIME PURCHASE" in desc_upper:
        return ("AUTO_CLASSIFIED", "AIRTIME_PURCHASE")

    if "INWARD EFT CREDIT" in desc_upper:
        return ("PENDING_CLASSIFICATION", "INWARD_EFT_CREDIT")

    if any(x in desc_upper for x in ["SHOPIFY", "ALIEXPRESS", "AMAZON", "QUICK LIMITED", "NEXGEN"]):
        return ("PENDING_CLASSIFICATION", "CARD_PURCHASE")

    if ">" in desc_upper and ("KE " in desc_upper or " GB " in desc_upper or " IE " in desc_upper):
        return ("PENDING_CLASSIFICATION", "CARD_PURCHASE")

    if "INT.COLL" in desc_upper or "INTEREST RUN" in desc_upper:
        return ("AUTO_CLASSIFIED", "INTEREST")

    if "SAFEWAYS EXPRESS" in desc_upper or "097431/480248" in desc_upper:
        return ("AUTO_CLASSIFIED", "SAFEWAYS_WITHDRAWAL")

    if "FOURTH GENERATION CAPITAL" in desc_upper or "SOMO AFRICA TRUST" in desc_upper:
        return ("AUTO_CLASSIFIED", "FUND_INFLOW")

    words = desc_upper.strip().split()
    if len(words) <= 4 and all(w.isalpha() for w in words):
        return ("PENDING_CLASSIFICATION", "NAMED_PERSON_TRANSFER")

    return ("PENDING_CLASSIFICATION", "UNCLASSIFIED")


def _is_header_row(row: list) -> bool:
    """True if row is the column header."""
    if not row or len(row) < 5:
        return False
    first = (row[0] or "").upper()
    second = (row[1] or "").upper()
    return (
        "TRANSACTIO" in first
        or "VALUE DATE" in second
        or (first == "TRANS" and "DETAILS" in second)
    )


def _detect_layout(row: list) -> str:
    """
    Detect column layout from header row.
    Returns 'A' for 7-col layout (Transaction Date | Value Date | Details | Reference | Debit | Credit | Balance)
    Returns 'B' for 8-col layout (Trans | Details | Channel | Value | Reference | Credit | Debit | Book Balance)
    """
    if not row or len(row) < 5:
        return "A"
    first = (row[0] or "").upper()
    if first == "TRANS" and len(row) >= 8:
        return "B"
    return "A"


def _extract_row_fields(row: list, layout: str) -> dict:
    """
    Extract named fields from a raw table row based on layout.
    Layout A: Transaction Date | Value Date | Details | Reference | Debit | Credit | Balance
    Layout B: Trans | Details | Channel | Value | Reference | Credit | Debit | Book Balance
    """
    if layout == "B":
        return {
            "tx_date_raw": (row[0] or "").strip(),
            "value_date_raw": (row[3] or "").strip(),
            "details": (row[1] or "").strip().replace("\n", " "),
            "channel": (row[2] or "").strip(),
            "ref": (row[4] or "").strip().replace("\n", " "),
            "credit_raw": (row[5] or "").strip(),
            "debit_raw": (row[6] or "").strip(),
            "balance_raw": (row[7] or "").strip(),
        }
    else:
        return {
            "tx_date_raw": (row[0] or "").strip(),
            "value_date_raw": (row[1] or "").strip(),
            "details": (row[2] or "").strip().replace("\n", " "),
            "channel": "",
            "ref": (row[3] or "").strip().replace("\n", " "),
            "debit_raw": (row[4] or "").strip(),
            "credit_raw": (row[5] or "").strip(),
            "balance_raw": (row[6] or "").strip(),
        }



def _is_footer_row(description: str) -> bool:
    """Strip rows containing regulated-by text."""
    return "regulated by" in (description or "").lower()


_DATE_PAT = r'\d{1,2}-\d{1,2}-\d{4}'
_CHANNEL_PAT = r'(?:MPESA C2B|OMNI|CHANNEL|POS|Core)'
_AMOUNT_PAT = r'[\d,]+\.\d{2}'
_REF_PAT = r'[A-Z0-9]+'
_BALANCE_PAT = r'[\d,]+\.\d{2} (?:CR|DR)'

_LINE_B_RE = _re.compile(
    rf'^({_DATE_PAT})\s+'
    rf'(.+?)\s+'
    rf'({_CHANNEL_PAT})\s+'
    rf'({_DATE_PAT})\s+'
    rf'({_REF_PAT})\s+'
    rf'({_AMOUNT_PAT})\s+'
    rf'({_AMOUNT_PAT})\s+'
    rf'({_BALANCE_PAT})\s*$'
)

_SKIP_LINE_RE = _re.compile(
    r'^(Trans\s+Details|Kindly examine|Please note|Statement Date|Statement Period|Branch|Account|Currency|MAUCA|P\.O\.|KENYA|\d{5})',
    _re.IGNORECASE,
)


def _is_layout_b(file_path: str) -> bool:
    """Return True if the PDF uses the 8-column Trans/Details/Channel layout."""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages[:2]:
                tables = page.extract_tables()
                for table in tables or []:
                    for row in table:
                        if row and len(row) >= 8 and (row[0] or "").strip().upper() == "TRANS":
                            return True
    except Exception:
        pass
    return False


def _extract_coop_layout_b(file_path: str) -> tuple:
    """Extract transactions from Co-op 8-column text layout (MAUCABANKCOP style)."""
    transactions: List[RawTransaction] = []
    warnings: List[WarningItem] = []
    row_idx = 0
    pending: dict | None = None

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if _SKIP_LINE_RE.match(line):
                    continue

                m = _LINE_B_RE.match(line)
                if m:
                    if pending:
                        _flush_coop_pending(pending, transactions, warnings)
                    tx_date = m.group(1)
                    description = m.group(2).strip()
                    channel = m.group(3).strip()
                    value_date = m.group(4)
                    ref = m.group(5)
                    credit_raw = m.group(6)
                    debit_raw = m.group(7)
                    balance_raw = m.group(8)
                    iso_date = _parse_coop_date(tx_date) or _parse_coop_date(value_date)
                    pending = {
                        "row_index": row_idx,
                        "date_raw": iso_date or tx_date,
                        "description": description,
                        "debit_raw": debit_raw,
                        "credit_raw": credit_raw,
                        "balance_raw": balance_raw,
                        "source_file": file_path,
                        "ref": ref,
                    }
                    row_idx += 1
                else:
                    if pending:
                        if line and not _SKIP_LINE_RE.match(line):
                            pending["description"] = (
                                pending["description"] + " " + line
                            ).strip()

    if pending:
        _flush_coop_pending(pending, transactions, warnings)

    return transactions, warnings


def extract_coop_pdf(file_path: str) -> ExtractionResult:
    transactions: List[RawTransaction] = []
    warnings: List[WarningItem] = []
    row_idx = 0

    if _is_layout_b(file_path):
        transactions, warnings = _extract_coop_layout_b(file_path)
    else:
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

    classification_status, pattern_hint = _detect_pattern(desc)

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
            classification_status=classification_status,
            pattern_hint=pattern_hint,
        )
    )
