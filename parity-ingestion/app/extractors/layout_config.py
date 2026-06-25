"""
Config-driven PDF extraction for the fixed-threshold column pattern.

Scope (Phase 1 pilot, see Request Parser Pipeline scoping doc §1): expresses
a bank PDF layout as data (column x-thresholds, date format, header/footer
skip phrases) instead of a bespoke per-bank Python module. Covers only the
fixed-threshold column-assignment pattern used by most existing extractors
(e.g. absa_extractor.py) — the dynamic x-position-clustering pattern in
shared.py's _detect_column_bounds is a separate, later pass.

extract_pdf_by_config() reproduces extract_absa_pdf()'s algorithm exactly,
parameterized by LayoutConfig, so a config can be checked for byte-identical
output against the bespoke extractor it's meant to replace.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List, Literal, Optional, Tuple, Union

import pdfplumber
from pydantic import BaseModel

from app.models import ExtractionResult, RawTransaction, WarningItem
from app.extractors.shared import _group_by_line

_AMOUNT_PAT = re.compile(r"^[\d,]+\.\d{2}$")

ColumnField = Literal["date", "description", "debit", "credit", "balance"]


class ColumnBound(BaseModel):
    field: ColumnField
    x_max: float  # word assigned to this field if x0 < x_max and no earlier bound claimed it


FooterPhrase = Union[str, List[str]]
"""A plain str is a single substring (OR semantics across the list). A
list[str] is an AND-group: all substrings in it must be present for that
entry to match. Needed because some banks' footer markers are multi-token
(e.g. ABSA's "Page X of Y" requires both "PAGE" and "OF"), and a single
substring would be either too broad (matches "PAGE" alone, e.g. inside a
real transaction description) or too narrow (an exact phrase match misses
formatting variation). See Phase 0+1 PR review note: this is flagged as a
near-term schema question if more banks need multi-marker AND groups, not
re-derived per bank ad hoc."""


class LayoutConfig(BaseModel):
    bank_name: str
    extractor_type: str  # matches app.models.ExtractionMethod values
    detection_text_markers: List[str]  # any marker present in first 3 pages → detected
    date_format: str  # strptime pattern, e.g. "%d/%m/%Y"
    column_bounds: List[ColumnBound]  # ordered left-to-right, first match wins
    header_skip_phrases: List[str]
    footer_skip_phrases: List[FooterPhrase]
    row_tolerance: float = 5.0


def detect_by_config(file_path: str, config: LayoutConfig) -> bool:
    try:
        with pdfplumber.open(file_path) as pdf:
            text = ""
            for page in pdf.pages[:3]:
                t = page.extract_text()
                if t:
                    text += t + " "
            return any(marker in text for marker in config.detection_text_markers)
    except Exception:
        return False


def _parse_date_by_config(raw: str, date_format: str) -> Optional[str]:
    if not raw or not raw.strip():
        return None
    try:
        dt = datetime.strptime(raw.strip(), date_format)
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def _try_parse_balance(raw: str) -> Tuple[Optional[int], Optional[str]]:
    """Identical to absa_extractor._try_parse_balance — not duplicated by
    import to avoid coupling this module to one bank's extractor module."""
    if not raw or raw.strip() in ("", "nan"):
        return None, None

    clean = raw.replace(",", "").strip()
    if clean.startswith("-"):
        clean = clean[1:]
    elif clean.startswith("+"):
        clean = clean[1:]
    if not clean:
        return None, f"empty balance: {raw!r}"

    try:
        if "." in clean:
            whole_str, frac_str = clean.split(".", 1)
            frac_str = frac_str.ljust(2, "0")[:2]
            whole = int(whole_str) if whole_str else 0
            frac = int(frac_str)
            return whole * 100 + frac, None
        return int(clean) * 100, None
    except ValueError:
        return None, f"malformed balance: {raw!r}"


def _is_header_row(text: str, config: LayoutConfig) -> bool:
    upper = text.upper()
    return any(phrase.upper() in upper for phrase in config.header_skip_phrases)


def _is_footer_or_marketing(text: str, config: LayoutConfig) -> bool:
    """OR across config.footer_skip_phrases entries; for an entry that's a
    list[str] (an AND-group, e.g. ["PAGE", "OF"]), all substrings in that
    group must be present — matches absa_extractor.py's original
    `"PAGE" in t and "OF" in t` exactly, rather than the looser "PAGE" alone
    a naive flattening would produce."""
    upper = (text or "").upper()
    for phrase in config.footer_skip_phrases:
        if isinstance(phrase, list):
            if all(p.upper() in upper for p in phrase):
                return True
        elif phrase.upper() in upper:
            return True
    return False


def _assign_word_column(word: dict, config: LayoutConfig) -> Optional[ColumnField]:
    text = word.get("text", "")
    x0 = word.get("x0", 0)
    is_amount = bool(_AMOUNT_PAT.match(text))

    for bound in config.column_bounds:
        if bound.field in ("debit", "credit", "balance"):
            if is_amount and x0 < bound.x_max:
                return bound.field
        else:
            if not is_amount and x0 < bound.x_max:
                return bound.field
    return None


def _flush_pending(
    pending: dict,
    transactions: List[RawTransaction],
    warnings: List[WarningItem],
) -> None:
    _, balance_warn = _try_parse_balance(pending.get("balance_raw", ""))
    if balance_warn:
        warnings.append(
            WarningItem(
                row_index=pending["row_index"],
                message=balance_warn,
                raw_text=pending.get("balance_raw", ""),
            )
        )

    transactions.append(
        RawTransaction(
            row_index=pending["row_index"],
            date_raw=pending["date_raw"],
            description=pending["description"] or "",
            debit_raw=pending["debit_raw"],
            credit_raw=pending["credit_raw"],
            balance_raw=pending["balance_raw"],
            source_file=pending["source_file"],
            extraction_confidence=1.0,
        )
    )


def extract_pdf_by_config(file_path: str, config: LayoutConfig) -> ExtractionResult:
    """Reproduces extract_absa_pdf()'s row-assembly algorithm, parameterized
    by config instead of ABSA's hardcoded constants. column_bounds for
    "debit"/"credit" are checked in array order — for ABSA's three-amount-
    column layout, list debit before credit before balance so narrower
    x_max thresholds are tried first."""
    transactions: List[RawTransaction] = []
    warnings: List[WarningItem] = []
    row_idx = 0

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            if not words:
                continue

            rows = _group_by_line(words, config.row_tolerance)
            pending: Optional[dict] = None

            for row_words in rows:
                date_parts: List[str] = []
                desc_parts: List[str] = []
                debit = ""
                credit = ""
                balance_raw = ""

                for w in row_words:
                    col = _assign_word_column(w, config)
                    if col == "date":
                        date_parts.append(w["text"])
                    elif col == "description":
                        desc_parts.append(w["text"])
                    elif col == "debit":
                        debit = w["text"]
                    elif col == "credit":
                        credit = w["text"]
                    elif col == "balance":
                        balance_raw = w["text"]

                date_str = " ".join(date_parts).strip()
                desc_str = " ".join(desc_parts).strip()
                combined = f"{date_str} {desc_str}".strip()

                if _is_header_row(combined, config):
                    continue
                if _is_footer_or_marketing(desc_str, config):
                    continue
                if not date_str and not desc_str and not debit and not credit:
                    continue

                iso_date = _parse_date_by_config(date_str, config.date_format) or ""

                if date_str and _parse_date_by_config(date_str, config.date_format):
                    if pending:
                        _flush_pending(pending, transactions, warnings)
                        pending = None
                    pending = {
                        "row_index": row_idx,
                        "date_raw": iso_date,
                        "description": desc_str,
                        "debit_raw": debit.replace(",", "").lstrip("-") if debit else "",
                        "credit_raw": credit.replace(",", "") if credit else "",
                        "balance_raw": balance_raw,
                        "source_file": file_path,
                    }
                    row_idx += 1
                else:
                    if pending:
                        if desc_str:
                            pending["description"] = (
                                (pending["description"] or "") + " " + desc_str
                            ).strip()
                        if debit and not pending["debit_raw"]:
                            pending["debit_raw"] = debit.replace(",", "").lstrip("-")
                        if credit and not pending["credit_raw"]:
                            pending["credit_raw"] = credit.replace(",", "")
                        if balance_raw and not pending["balance_raw"]:
                            pending["balance_raw"] = balance_raw

            if pending:
                _flush_pending(pending, transactions, warnings)
                pending = None

    has_warnings = len(warnings) > 0
    return ExtractionResult(
        source_file=file_path,
        extractor_type=config.extractor_type,
        row_count=len(transactions),
        extraction_status="needs_review" if has_warnings else "success",
        warnings=warnings,
        raw_transactions=transactions,
    )
