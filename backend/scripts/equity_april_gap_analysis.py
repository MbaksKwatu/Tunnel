#!/usr/bin/env python3
"""
One-off diagnostic: April Equity PDF — lines after split-date normalisation vs DATE2 pattern.
Does not modify equity_extractor.py (imports read-only helpers).
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

import pdfplumber

# parity-ingestion on sys.path
_TUNNEL = Path(__file__).resolve().parents[2]
_INGEST = _TUNNEL / "parity-ingestion"
if str(_INGEST) not in sys.path:
    sys.path.insert(0, str(_INGEST))

from app.extractors.equity_extractor import (  # noqa: E402
    _AMOUNT_PAT,
    _DATE2_PAT,
    _normalize_equity_split_date_block_lines,
)

APRIL_PDF = Path(
    "/Users/mbakswatu/Desktop/Demofiles/Sassy Cosmetics - Equity Bank - 1180279761781 - Apr 2025.pdf"
)

_PAGE_FOOTER_RE = re.compile(r"^Page\s+\d+\s+of\s+\d+\s*$", re.I)


def _is_header_or_footer_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    if _PAGE_FOOTER_RE.match(s):
        return True
    u = s.upper()
    needles = (
        "ACCOUNT STATEMENT",
        "FROM DATE",
        "TO DATE",
        "REPORT GENERATED",
        "TOTAL SEARCH RESULTS",
        "ACCOUNT NUMBER",
        "LIMITED",
        "SASSY COSMETICS",
        "TRANSACTI",
        "NARRATIVE DEBIT",
        "RUNNING BALANCE",
        "ON DATE DATE",
        "REFERENCE NUMBER",
        "VALUE TRANSACTION",
        "CHEQUE",
    )
    if any(n in u for n in needles):
        return True
    if "EQUITY" in u and "BANK" in u:
        return True
    return False


def _looks_like_transaction_candidate(line: str) -> bool:
    """Heuristic: possible txn-related line, excluding obvious headers/footers."""
    s = line.strip()
    if not s or _is_header_or_footer_line(s):
        return False
    # Must suggest structured data: digits, money, or reference-like token
    if _AMOUNT_PAT.search(s):
        return True
    if re.search(r"\d", s) and (
        re.search(r"[A-Z]{3,}\d", s)  # e.g. TCU..., MPS
        or re.search(r"\d{3,}", s)  # phone / long refs
        or re.match(r"^\d{2}-\d{2}-", s)  # partial date line
    ):
        return True
    if re.match(r"^[A-Z0-9#]{4,}", s):
        return True
    return False


def _first_token_shape(line: str) -> str:
    s = line.strip()
    if not s:
        return "empty"
    tok = s.split()[0]
    if re.match(r"^\d{2}-\d{2}-\d{4}$", tok):
        return "date-like-full"
    if re.match(r"^\d{2}-\d{2}-$", tok) or re.match(r"^\d{2}-\d{2}-\s*$", tok):
        return "date-like-partial"
    if re.match(r"^\d{2}-\d{2}-\d{2}$", tok) or re.match(r"^\d{2}-\d{2}-\d{1,2}$", tok):
        return "date-like-odd"
    if _AMOUNT_PAT.match(tok):
        return "amount-token"
    if re.match(r"^[A-Z]{2,}\d", tok) or re.match(r"^TCU", tok) or re.match(r"^S\d+$", tok):
        return "reference-code-like"
    if re.match(r"^\d+$", tok) or re.match(r"^254\d+$", tok):
        return "numeric-token"
    if re.match(r"^[\d,]+\.\d{2}$", s):
        return "amount-only-line"
    if re.search(r"[A-Za-z]", s) and not re.search(r"\d", s):
        return "narrative-only-no-digits"
    return "other"


def main() -> None:
    if not APRIL_PDF.is_file():
        print(f"ERROR: PDF not found: {APRIL_PDF}", file=sys.stderr)
        sys.exit(1)

    all_normalized_lines: list[str] = []
    per_page_match_counts: list[tuple[int, int]] = []  # (page_index_1based, match_count)
    zero_match_pages: list[tuple[int, list[str]]] = []

    with pdfplumber.open(str(APRIL_PDF)) as pdf:
        for pi, page in enumerate(pdf.pages, start=1):
            raw = page.extract_text() or ""
            raw_lines = raw.split("\n")
            norm = _normalize_equity_split_date_block_lines(raw_lines)
            all_normalized_lines.extend(norm)

            matches = sum(1 for ln in norm if _DATE2_PAT.match(ln.strip()))
            per_page_match_counts.append((pi, matches))
            if matches == 0:
                zero_match_pages.append((pi, raw_lines[:5]))

    matched_lines = [ln for ln in all_normalized_lines if _DATE2_PAT.match(ln.strip())]

    unmatched_candidates: list[str] = []
    for ln in all_normalized_lines:
        st = ln.strip()
        if _DATE2_PAT.match(st):
            continue
        if _looks_like_transaction_candidate(ln):
            unmatched_candidates.append(ln)

    shape_counts = Counter(_first_token_shape(ln) for ln in unmatched_candidates)

    lines_out: list[str] = []
    ap = lines_out.append

    ap("=== Equity April gap analysis ===")
    ap(f"PDF: {APRIL_PDF}")
    ap("")
    ap(f"Total lines after normalisation (all pages, concatenated): {len(all_normalized_lines)}")
    ap(f"Total MATCHED lines (_DATE2_PAT): {len(matched_lines)}")
    ap(f"Total UNMATCHED candidates (heuristic): {len(unmatched_candidates)}")
    ap("")
    ap("--- First 30 UNMATCHED candidate lines (verbatim) ---")
    for i, ln in enumerate(unmatched_candidates[:30], 1):
        ap(f"{i:3d} | {ln}")
    ap("")
    ap("--- UNMATCHED frequency by first-token shape ---")
    for shape, cnt in shape_counts.most_common():
        ap(f"  {shape}: {cnt}")
    ap("")
    ap(f"--- Pages with zero DATE2 matches: {len(zero_match_pages)} ---")
    for pn, first5 in zero_match_pages:
        ap(f"  Page {pn} (first 5 raw lines):")
        for fl in first5:
            ap(f"    {fl!r}")
        ap("")
    ap("=== end ===")

    text = "\n".join(lines_out)
    print(text)

    out_path = Path(__file__).resolve().parent / "equity_april_gap_analysis_output.txt"
    out_path.write_text(text, encoding="utf-8")
    print(f"\n[Written to {out_path}]", file=sys.stderr)


if __name__ == "__main__":
    main()
