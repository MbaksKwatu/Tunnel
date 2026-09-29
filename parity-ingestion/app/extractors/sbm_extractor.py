"""
SBM Bank (Kenya) PDF statement extractor.

Columns: Transaction Date | Transaction Details | Ref Number | Instrument Code |
         Value Date | Debit | Credit | Balance
Date: DD-MON-YY (e.g. "04-MAR-26") → ISO.

Layout facts confirmed against a real 90-page business-current-account
statement (real text layer, PDFium producer, Helvetica, no embedded fonts):

  * Every transaction is ONE text line under pdfplumber's `extract_text()`:
    date, details head, ref number, value date, debit, credit, balance.
    The rest of "Transaction Details" (payment reference, counterparty, ...)
    wraps onto 1-4 following lines that carry no date — appended to the
    pending row, same pattern as the ABSA / I&M extractors.
  * The ref number is not one shape: "000MPDT260633439",
    "003CSFPKES 00001" (with an instrument code), "0003607260760460 000001"
    (cheque number), "003RTIN261320011 FTC260512L".
  * Debits are printed NEGATIVE ("-1,000.00"). A POSITIVE figure in the
    Debit column is a reversal (money back in): the real file has one
    (23-MAR-26, a full 4-line M-Pesa withdrawal + 3 fee reversal). The
    normaliser strips signs and derives direction from the field name, so a
    positive "debit" is emitted as credit_raw, otherwise every downstream
    total would be wrong. The direction is proven by the balance chain; the
    REVERSAL_PAIR label is not (one real example), so it is only applied
    when the row undoes an earlier debit with the same ref and amount —
    otherwise UNCLASSIFIED plus a warning (needs_review).
  * An M-Pesa withdrawal is 4 separate rows sharing one ref number
    (withdrawal, Safaricom charge, Mfukoni charge, excise tax). They are kept
    as 4 rows (each moves the running balance) and the shared ref is appended
    to every description so the bundle stays traceable.
  * The header's "Opening Balance" is blank on a statement that starts from
    zero; it is derived from the first row's balance movement when absent.
    Header "Total Debits" is NET of reversals.
  * "SBM Bank (Kenya) Limited ..." boilerplate is the footer of pages 2..N
    only — page 1 has no footer, so detection keys on the page-1 header
    fields instead (see detect_sbm).
"""
from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Union

from app.models import ExtractionResult, RawTransaction, WarningItem
from app.extractors.pdf_document import NormalizedDocument, as_document

_MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

_AMT = r"-?[\d,]+\.\d{2}"
_DATE = r"\d{2}-[A-Z]{3}-\d{2}"
_ROW_PAT = re.compile(
    rf"^(?P<date>{_DATE}) (?P<desc>.+?) "
    r"(?P<ref>\d{3}[A-Z0-9]{5,}(?: [A-Z0-9]{4,})?) "
    rf"(?P<value_date>{_DATE}) "
    rf"(?P<debit>{_AMT}) (?P<credit>{_AMT}) (?P<balance>{_AMT})\s*$"
)
_PAGE_MARKER_PAT = re.compile(r"^Page \d+ of \d+$")

# Repeated column-header rows and the page footer — never description text.
_SKIP_LINE_PREFIXES = (
    "Transaction Transaction Details",
    "Date Code",
    "SBM Bank (Kenya) Limited is regulated",
    "Centre via e-mail",
)

# Header fields that together fingerprint the SBM statement (page 1).
_DETECT_TOKENS = (
    "Uncleared Balance",
    "Available Balance",
    "Total Debits",
    "Total Credits",
    "Transaction Details",
    "Ref Number",
    "Instrument",
)


def detect_sbm(source: Union[str, NormalizedDocument]) -> bool:
    """Return True if the PDF appears to be an SBM Bank (Kenya) statement.

    Keys on the page-1 header block ("Uncleared Balance" + "Available
    Balance" + "Total Debits/Credits" + the "Ref Number"/"Instrument Code"
    column headers), NOT on the "SBM Bank (Kenya) Limited" footer: that
    footer is absent from page 1, and can also appear as counterparty text
    inside another bank's statement.
    """
    try:
        with as_document(source) as doc:
            text = doc.text_upto(2)
            return all(tok in text for tok in _DETECT_TOKENS)
    except Exception:
        return False


def _parse_sbm_date(raw: str) -> Optional[str]:
    """Parse DD-MON-YY (e.g. 04-MAR-26) to ISO YYYY-MM-DD."""
    m = re.fullmatch(r"(\d{2})-([A-Za-z]{3})-(\d{2})", (raw or "").strip())
    if not m:
        return None
    mon = _MONTH_MAP.get(m.group(2).upper())
    if mon is None:
        return None
    return f"{2000 + int(m.group(3)):04d}-{mon:02d}-{int(m.group(1)):02d}"


def _dec(raw: str) -> Decimal:
    return Decimal(raw.replace(",", ""))


def _amt_str(d: Decimal) -> str:
    """Positive amount string without thousands separators; '' for zero."""
    return "" if d == 0 else f"{abs(d):.2f}"


def _parse_header(text: str) -> Dict[str, Optional[str]]:
    def grab(pattern: str) -> Optional[str]:
        m = re.search(pattern, text)
        return m.group(1).strip() if m else None

    amt = r"([\d,]+\.\d{2})"
    return {
        "account_name": grab(r"Account Name:\s*(.+?)\s+Opening Balance:"),
        "account_number": grab(r"Account Number:\s*(\d+)"),
        "currency": grab(r"Currency:\s*([A-Z]{3})\b"),
        "opening_balance": grab(rf"Opening Balance:\s*{amt}"),
        "total_debits": grab(rf"Total Debits:\s*{amt}"),
        "total_credits": grab(rf"Total Credits:\s*{amt}"),
        "available_balance": grab(rf"Available Balance:\s*{amt}"),
    }


# ── pattern_hint (same vocabulary as the Co-op extractor) ────────────────────

def _detect_pattern(desc: str) -> Tuple[str, str]:
    """Returns (classification_status, pattern_hint) from the transaction type."""
    d = (desc or "").upper()
    if any(k in d for k in ("CHARGE", "FEE", "EXCISE")):
        return ("AUTO_CLASSIFIED", "BANK_CHARGE")
    if d.startswith("MPESA DEPOSIT"):
        return ("PENDING_CLASSIFICATION", "MPESA_C2B")
    if d.startswith("INCOMING PESALINK"):
        return ("PENDING_CLASSIFICATION", "PESALINK_TRANSFER")
    if d.startswith("INCOMING RTGS") or d.startswith("OUTWARD REMITTANCE"):
        return ("PENDING_CLASSIFICATION", "RTGS_TRANSFER")
    if d.startswith("IB MPESA WITHDRAWAL"):
        return ("PENDING_CLASSIFICATION", "MPESA_TRANSFER")
    return ("PENDING_CLASSIFICATION", "UNCLASSIFIED")


# ── Reconciliation ───────────────────────────────────────────────────────────

def reconcile_balances(
    transactions: List[RawTransaction],
    opening_balance: Optional[Decimal],
) -> Tuple[List[int], Optional[Decimal]]:
    """Walk the running balance: prev + credit - debit must equal each row's
    printed balance. Returns (row indexes that do not reconcile, opening
    balance used). When `opening_balance` is None it is derived from the first
    row's own movement. Exact Decimal arithmetic — no floats."""
    bad: List[int] = []
    prev = opening_balance
    for t in transactions:
        debit = _dec(t.debit_raw) if t.debit_raw else Decimal(0)
        credit = _dec(t.credit_raw) if t.credit_raw else Decimal(0)
        bal = _dec(t.balance_raw)
        if prev is None:
            prev = bal - credit + debit
            opening_balance = prev
        if prev + credit - debit != bal:
            bad.append(t.row_index)
        prev = bal
    return bad, opening_balance


def extract_sbm_pdf(file_path: str) -> ExtractionResult:
    transactions: List[RawTransaction] = []
    warnings: List[WarningItem] = []
    # All positive-Debit rows (paired or not): header Total Debits nets them all.
    reversal_rows: set = set()
    open_debits: Counter = Counter()
    header: Dict[str, Optional[str]] = {}
    pending: Optional[dict] = None

    def flush() -> None:
        nonlocal pending
        if pending is None:
            return
        desc = " ".join(pending["desc_parts"]).strip()
        pattern_src = pending["type"]
        status, hint = _detect_pattern(pattern_src)
        if pending["reversal"]:
            status, hint = (
                ("PENDING_CLASSIFICATION", "REVERSAL_PAIR") if pending["paired"]
                else ("PENDING_CLASSIFICATION", "UNCLASSIFIED")
            )
        transactions.append(
            RawTransaction(
                row_index=pending["row_index"],
                date_raw=pending["date_raw"],
                description=f"{desc} [ref {pending['ref']}]",
                debit_raw=pending["debit_raw"],
                credit_raw=pending["credit_raw"],
                balance_raw=pending["balance_raw"],
                source_file=file_path,
                extraction_confidence=1.0,
                classification_status=status,
                pattern_hint=hint,
            )
        )
        pending = None

    with as_document(file_path) as doc:
        for page in doc.pages:
            text = page.text
            if page.page_number == 1:
                header = _parse_header(text)

            for line in text.split("\n"):
                line = line.strip()
                if not line or _PAGE_MARKER_PAT.match(line):
                    continue
                if line.startswith(_SKIP_LINE_PREFIXES):
                    continue

                m = _ROW_PAT.match(line)
                if m:
                    flush()
                    iso = _parse_sbm_date(m.group("date"))
                    debit = _dec(m.group("debit"))
                    credit = _dec(m.group("credit"))
                    row_idx = len(transactions)
                    # Debit column is printed negative; a positive figure there
                    # is a reversal (money in), not a debit.
                    reversal = debit > 0
                    key = (m.group("ref"), abs(debit))
                    paired = False
                    if reversal:
                        credit_raw, debit_raw = _amt_str(debit), ""
                        # Only label REVERSAL_PAIR when it undoes an earlier
                        # debit with the same ref and amount (consumed 1:1).
                        # Direction stays credit either way — the balance
                        # chain proves it; only the label is conditional.
                        paired = open_debits[key] > 0
                        if paired:
                            open_debits[key] -= 1
                        else:
                            warnings.append(WarningItem(
                                row_index=row_idx,
                                message="positive debit (money in) with no earlier debit of the same ref and amount — not labelled as a reversal",
                                raw_text=line,
                            ))
                        if credit != 0:
                            warnings.append(WarningItem(
                                row_index=row_idx,
                                message="positive debit and non-zero credit on one row",
                                raw_text=line,
                            ))
                    else:
                        credit_raw, debit_raw = _amt_str(credit), _amt_str(debit)
                        if debit < 0:
                            open_debits[key] += 1
                    if not iso:
                        warnings.append(WarningItem(
                            row_index=row_idx,
                            message=f"unparseable date: {m.group('date')!r}",
                            raw_text=line,
                        ))
                    if not debit_raw and not credit_raw:
                        warnings.append(WarningItem(
                            row_index=row_idx,
                            message="row has neither a debit nor a credit amount",
                            raw_text=line,
                        ))
                    pending = {
                        "row_index": row_idx,
                        "date_raw": iso or m.group("date"),
                        "type": m.group("desc"),
                        "desc_parts": [m.group("desc")],
                        "ref": m.group("ref"),
                        "debit_raw": debit_raw,
                        "credit_raw": credit_raw,
                        "balance_raw": m.group("balance").replace(",", ""),
                        "reversal": reversal,
                        "paired": paired,
                    }
                    if reversal:
                        reversal_rows.add(row_idx)
                elif pending is not None and not re.match(rf"^{_DATE} ", line):
                    # Wrapped tail of "Transaction Details" (reference,
                    # counterparty, ...). May sit across a page break.
                    pending["desc_parts"].append(line)
                elif re.match(rf"^{_DATE} ", line):
                    # Dated line that is not a well-formed row: never drop silently.
                    warnings.append(WarningItem(
                        row_index=len(transactions) + (1 if pending else 0),
                        message="dated line did not match the SBM row layout",
                        raw_text=line,
                    ))
            page.flush_cache()
        flush()

    # ── Statement-level validation (header vs extracted rows) ───────────────
    opening = _dec(header["opening_balance"]) if header.get("opening_balance") else None
    bad_rows, opening_used = reconcile_balances(transactions, opening)
    for idx in bad_rows:
        t = transactions[idx]
        warnings.append(WarningItem(
            row_index=idx,
            message="running balance does not reconcile with debit/credit",
            raw_text=f"{t.date_raw} {t.description} dr={t.debit_raw} cr={t.credit_raw} bal={t.balance_raw}",
        ))

    def stmt_warn(msg: str) -> None:
        warnings.append(WarningItem(row_index=-1, message=msg, raw_text=""))

    if not transactions:
        stmt_warn("no transaction rows extracted")
    else:
        rev_in = sum((_dec(transactions[i].credit_raw) for i in reversal_rows), Decimal(0))
        gross_out = sum((_dec(t.debit_raw) for t in transactions if t.debit_raw), Decimal(0))
        credits = sum((_dec(t.credit_raw) for t in transactions if t.credit_raw), Decimal(0)) - rev_in
        if header.get("total_debits") and gross_out - rev_in != _dec(header["total_debits"]):
            stmt_warn(f"net debits {gross_out - rev_in} != header Total Debits {header['total_debits']}")
        if header.get("total_credits") and credits != _dec(header["total_credits"]):
            stmt_warn(f"credits {credits} != header Total Credits {header['total_credits']}")
        if header.get("available_balance") and _dec(transactions[-1].balance_raw) != _dec(header["available_balance"]):
            stmt_warn(
                f"closing balance {transactions[-1].balance_raw} != header Available Balance {header['available_balance']}"
            )

    return ExtractionResult(
        source_file=file_path,
        extractor_type="sbm_pdf",
        row_count=len(transactions),
        extraction_status="needs_review" if warnings else "success",
        warnings=warnings,
        raw_transactions=transactions,
        currency=header.get("currency") or "KES",
    )
