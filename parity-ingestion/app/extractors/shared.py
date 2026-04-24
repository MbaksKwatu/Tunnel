"""
Shared extraction utilities used by pdf_extractor and docai_extractor.

All functions operate on word dicts of the form:
  {"text": str, "x0": float, "x1": float, "top": float}

This is the native shape returned by pdfplumber and the shape produced by
docai_extractor._tokens_to_words().
"""
from __future__ import annotations

import re
from collections import defaultdict

# ── Date patterns ─────────────────────────────────────────────────────────────

_DATE_PAT_SCB = re.compile(r"^\d{2}/[A-Za-z]{3}/\d{4}$")     # 06/Jan/2022
_DATE_PAT_EQUITY = re.compile(r"^\d{2}\s[A-Za-z]{3}\s\d{4}$") # 03 Jan 2024

# ── Amount pattern ────────────────────────────────────────────────────────────

_AMOUNT_PAT = re.compile(r"^[\d,]+\.\d{2}$")

# ── Header / footer markers ───────────────────────────────────────────────────

_SKIP_PHRASES = frozenset({
    "particulars",
    "statement of account",
    "date",
    "trx. date",
    "trx.",
    "balance",
    "debit",
    "credit",
    "description",
    "transaction details",
    "value date",
    "narration",
    "ref no",
    "page",
})


def _group_by_line(words: list[dict], y_tol: float) -> list[list[dict]]:
    """
    Bucket word dicts into visual rows using top-position proximity.

    Words within y_tol points of each other share a bucket.
    Each bucket is sorted left-to-right by x0.
    Returns rows sorted top-to-bottom.
    """
    if not words:
        return []
    buckets: dict[float, list[dict]] = defaultdict(list)
    for w in words:
        bucket_key = round(w["top"] / y_tol) * y_tol
        buckets[bucket_key].append(w)
    return [sorted(ws, key=lambda w: w["x0"]) for _, ws in sorted(buckets.items())]


def _detect_column_bounds(lines: list[list[dict]], page_width: float) -> dict:
    """
    Dynamically infer debit / credit / balance column x-boundaries by
    finding where amount-pattern tokens cluster on the right half of the page.

    Returns a dict:
      {
        "amount_min_x0": float,   # leftmost x0 for any amount token
        "debit_max_centre": float,
        "credit_max_centre": float,
        # balance: centre > credit_max_centre
      }

    Algorithm:
      1. Collect x-centres of all amount-pattern tokens in the right 40% of the
         page (to exclude in-description numbers that appear on the left).
      2. Sort centres.  The rightmost third → balance; middle third → credit;
         leftmost third → debit.
      3. If fewer than 3 amount tokens are found, fall back to proportional
         thresholds based on page_width.
    """
    right_threshold = page_width * 0.60
    amount_centres: list[float] = []

    for row in lines:
        for w in row:
            if _AMOUNT_PAT.match(w["text"]) and w["x0"] >= right_threshold:
                centre = (w["x0"] + w["x1"]) / 2.0
                amount_centres.append(centre)

    if len(amount_centres) >= 3:
        amount_centres_sorted = sorted(amount_centres)
        n = len(amount_centres_sorted)
        debit_max = amount_centres_sorted[n // 3]
        credit_max = amount_centres_sorted[2 * n // 3]
        amount_min_x0 = right_threshold
    else:
        # Proportional fallback
        debit_max = page_width * 0.835
        credit_max = page_width * 0.940
        amount_min_x0 = page_width * 0.60

    return {
        "amount_min_x0": amount_min_x0,
        "debit_max_centre": debit_max,
        "credit_max_centre": credit_max,
    }


def _is_date(text: str) -> bool:
    """True if text matches the SCB Kenya date format DD/Mon/YYYY."""
    return bool(_DATE_PAT_SCB.match(text))


def _is_equity_date(text: str) -> bool:
    """True if text matches the Equity Bank Kenya date format DD Mon YYYY."""
    return bool(_DATE_PAT_EQUITY.match(text))


def _should_skip_line(text: str) -> bool:
    """True if the line text is a known header or footer token."""
    return text.strip().lower() in _SKIP_PHRASES


def _assign_column(word: dict, bounds: dict) -> str | None:
    """
    Map a word to 'debit', 'credit', 'balance', or None.

    bounds must be the dict returned by _detect_column_bounds().
    Words whose x0 is left of bounds['amount_min_x0'] are excluded —
    they belong to the description or date columns.
    """
    if not _AMOUNT_PAT.match(word["text"]):
        return None
    if word["x0"] < bounds["amount_min_x0"]:
        return None
    centre = (word["x0"] + word["x1"]) / 2.0
    if centre <= bounds["debit_max_centre"]:
        return "debit"
    if centre <= bounds["credit_max_centre"]:
        return "credit"
    return "balance"
