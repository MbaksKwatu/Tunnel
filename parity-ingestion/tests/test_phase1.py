"""
Phase 1 standalone validation script.
Run with: python3 tests/test_phase1.py
No pytest required.
"""
from __future__ import annotations

import re
import sys
import os

# This file is a standalone validation script, not a pytest test module.
# Prevent pytest collection from executing top-level code that depends on
# local machine files and external services.
if __name__ != "__main__":
    import pytest
    pytest.skip("Standalone script; excluded from pytest collection.", allow_module_level=True)

# Allow imports from the parity-ingestion package root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.extractors.pdf_extractor import extract_scb_pdf
from app.extractors.mpesa_extractor import extract_mpesa_csv
from app.extractors.pdf_type_detector import is_scanned_pdf
from app.extractors.docai_extractor import extract_with_docai
from app.normaliser import normalise_all

PDF_PATH = "/Users/mbakswatu/Desktop/TestingDoc/AccountStatement_20250403163616_DHASSAN.pdf"
CSV_PATH = "/Users/mbakswatu/Desktop/Screenshot/M-PESA Statement 12 Months.csv"
SCANNED_PDF_PATH = os.path.join(os.path.dirname(__file__), "scanned_equity_bank_statement.pdf")

DATE_PAT = re.compile(r"^\d{2}/[A-Za-z]{3}/\d{4}$")
AMOUNT_PAT = re.compile(r"^[\d,]+\.\d{2}$")

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  {PASS}  {name}")
    else:
        msg = f"{name}" + (f" — {detail}" if detail else "")
        print(f"  {FAIL}  {msg}")
        failures.append(msg)


# ─────────────────────────────────────────────────────────────────────────────
# PDF TESTS
# ─────────────────────────────────────────────────────────────────────────────
print("\n── SCB Kenya PDF ──────────────────────────────────────────────────────")
pdf_result = extract_scb_pdf(PDF_PATH)

check(
    f"row_count >= 690 (got {pdf_result.row_count})",
    pdf_result.row_count >= 690,
)
check(
    "extraction_status is 'success' or 'needs_review'",
    pdf_result.extraction_status in ("success", "needs_review"),
)
check(
    "extractor_type == 'scb_pdf'",
    pdf_result.extractor_type == "scb_pdf",
)

# Spot-check: all transactions with a non-empty date must match DD/Mon/YYYY
bad_dates = [
    t for t in pdf_result.raw_transactions
    if t.date_raw and not DATE_PAT.match(t.date_raw)
]
check(
    f"all date_raw values match DD/Mon/YYYY (bad: {len(bad_dates)})",
    len(bad_dates) == 0,
    detail=str([t.date_raw for t in bad_dates[:3]]) if bad_dates else "",
)

# Spot-check: amount fields are strings, not floats
float_contamination = [
    t for t in pdf_result.raw_transactions
    if isinstance(t.debit_raw, float)
    or isinstance(t.credit_raw, float)
    or isinstance(t.balance_raw, float)
]
check(
    "no float values in amount fields (all raw strings)",
    len(float_contamination) == 0,
)

# Spot-check: non-empty amounts match amount pattern
bad_amounts = []
for t in pdf_result.raw_transactions:
    for field in (t.debit_raw, t.credit_raw, t.balance_raw):
        if field and not AMOUNT_PAT.match(field):
            bad_amounts.append(field)
check(
    f"non-empty amount fields match numeric pattern (bad: {len(bad_amounts)})",
    len(bad_amounts) == 0,
    detail=str(bad_amounts[:5]) if bad_amounts else "",
)

# Spot-check: no NaN or None in description
bad_desc = [t for t in pdf_result.raw_transactions if t.description is None]
check("no None descriptions", len(bad_desc) == 0)

print(f"\n  Warnings: {len(pdf_result.warnings)}")
for w in pdf_result.warnings[:5]:
    print(f"    row {w.row_index}: {w.message} — {w.raw_text[:60]!r}")

# ─────────────────────────────────────────────────────────────────────────────
# CSV TESTS
# ─────────────────────────────────────────────────────────────────────────────
print("\n── M-Pesa CSV ─────────────────────────────────────────────────────────")
csv_result = extract_mpesa_csv(CSV_PATH)

check(
    f"row_count == 19 (got {csv_result.row_count})",
    csv_result.row_count == 19,
)
check(
    "extraction_status == 'success'",
    csv_result.extraction_status == "success",
    detail=f"got {csv_result.extraction_status!r}, warnings={[w.message for w in csv_result.warnings]}",
)
check(
    "extractor_type == 'mpesa_csv'",
    csv_result.extractor_type == "mpesa_csv",
)

# All rows should have confidence 1.0
low_confidence = [t for t in csv_result.raw_transactions if t.extraction_confidence < 1.0]
check(
    f"all extraction_confidence == 1.0 (low: {len(low_confidence)})",
    len(low_confidence) == 0,
)

# No float contamination
float_contam_csv = [
    t for t in csv_result.raw_transactions
    if isinstance(t.debit_raw, float)
    or isinstance(t.credit_raw, float)
    or isinstance(t.balance_raw, float)
]
check(
    "no float values in M-Pesa amount fields",
    len(float_contam_csv) == 0,
)

# Check that date_raw values are non-empty and contain a date part
bad_csv_dates = [
    t for t in csv_result.raw_transactions
    if not t.date_raw or "T" not in t.date_raw
]
check(
    f"all CSV date_raw values contain ISO date part (bad: {len(bad_csv_dates)})",
    len(bad_csv_dates) == 0,
)

# Each row must have either credit_raw or debit_raw (or both)
no_amounts = [
    t for t in csv_result.raw_transactions
    if not t.credit_raw and not t.debit_raw
]
check(
    f"every CSV row has at least one amount field (missing both: {len(no_amounts)})",
    len(no_amounts) == 0,
)

print(f"\n  Warnings: {len(csv_result.warnings)}")
for w in csv_result.warnings:
    print(f"    row {w.row_index}: {w.message}")

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3 — NORMALISER TESTS
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Phase 3: Normaliser — SCB Kenya PDF ────────────────────────────────")

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Run normaliser over both results (modifies in place)
normalise_all(pdf_result)
normalise_all(csv_result)

check(
    f"PDF normalised_transactions count == raw count ({pdf_result.row_count})",
    len(pdf_result.normalised_transactions) == pdf_result.row_count,
)

# Guard 1: no Python float in any normalised amount field (PDF)
pdf_float_violations = [
    (t.row_index, field, val)
    for t in pdf_result.normalised_transactions
    for field, val in [
        ("debit_cents", t.debit_cents),
        ("credit_cents", t.credit_cents),
        ("balance_cents", t.balance_cents),
    ]
    if isinstance(val, float)
]
check(
    f"no float values in PDF normalised amounts (violations: {len(pdf_float_violations)})",
    len(pdf_float_violations) == 0,
    detail=str(pdf_float_violations[:3]) if pdf_float_violations else "",
)

# Guard 2: all parseable dates are ISO YYYY-MM-DD
pdf_bad_dates = [
    t for t in pdf_result.normalised_transactions
    if t.date is not None and not ISO_DATE_RE.match(t.date)
]
check(
    f"all PDF normalised dates are ISO YYYY-MM-DD (bad: {len(pdf_bad_dates)})",
    len(pdf_bad_dates) == 0,
    detail=str([t.date for t in pdf_bad_dates[:3]]) if pdf_bad_dates else "",
)

# Guard 3: dates that could not be parsed are None (not empty string or garbage)
pdf_none_dates = [t for t in pdf_result.normalised_transactions if t.date is None]
check(
    f"unparseable PDF dates are None, not empty string ({len(pdf_none_dates)} None-date rows)",
    all(t.date is None for t in pdf_none_dates),
)

# Spot check — SCB row: 06/Jan/2022, INWARD CREDIT, credit=371,200.00, balance=763,988.24
try:
    scb_row = next(
        t for t in pdf_result.normalised_transactions
        if t.raw_date == "06/Jan/2022" and t.credit_cents == 37_120_000
    )
    check("SCB spot: date == '2022-01-06'", scb_row.date == "2022-01-06",
          detail=f"got {scb_row.date!r}")
    check("SCB spot: credit_cents == 37120000", scb_row.credit_cents == 37_120_000,
          detail=f"got {scb_row.credit_cents}")
    check("SCB spot: balance_cents == 76398824", scb_row.balance_cents == 76_398_824,
          detail=f"got {scb_row.balance_cents}")
    check("SCB spot: debit_cents is None", scb_row.debit_cents is None,
          detail=f"got {scb_row.debit_cents}")
    check("SCB spot: normalisation_status == 'ok'",
          scb_row.normalisation_status.value == "ok")
except StopIteration:
    check("SCB spot check row found (06/Jan/2022, credit=37120000)", False,
          detail="row not found in normalised_transactions")

print("\n── Phase 3: Normaliser — M-Pesa CSV ──────────────────────────────────")

check(
    f"CSV normalised_transactions count == raw count ({csv_result.row_count})",
    len(csv_result.normalised_transactions) == csv_result.row_count,
)

# Guard 1: no float in CSV normalised amounts
csv_float_violations = [
    (t.row_index, field, val)
    for t in csv_result.normalised_transactions
    for field, val in [
        ("debit_cents", t.debit_cents),
        ("credit_cents", t.credit_cents),
        ("balance_cents", t.balance_cents),
    ]
    if isinstance(val, float)
]
check(
    f"no float values in CSV normalised amounts (violations: {len(csv_float_violations)})",
    len(csv_float_violations) == 0,
)

# Guard 2: all CSV dates are ISO
csv_bad_dates = [
    t for t in csv_result.normalised_transactions
    if t.date is not None and not ISO_DATE_RE.match(t.date)
]
check(
    f"all CSV normalised dates are ISO YYYY-MM-DD (bad: {len(csv_bad_dates)})",
    len(csv_bad_dates) == 0,
)

# Guard 3: every row has a valid date (M-Pesa CSV dates are clean)
csv_none_dates = [t for t in csv_result.normalised_transactions if t.date is None]
check(
    f"all CSV rows have a parseable date (None-date rows: {len(csv_none_dates)})",
    len(csv_none_dates) == 0,
)

# Guard 4: debit_cents always positive (negatives stripped)
csv_negative_debits = [
    t for t in csv_result.normalised_transactions
    if t.debit_cents is not None and t.debit_cents < 0
]
check(
    f"all debit_cents are positive integers (negative: {len(csv_negative_debits)})",
    len(csv_negative_debits) == 0,
)

# Spot check — SDJ3NLJXBL: 2024-04-19, debit=-760, balance=53.75
# Raw: debit_raw="-760" → debit_cents=76000; balance_raw="53.75" → balance_cents=5375
try:
    mpesa_row = next(
        t for t in csv_result.normalised_transactions
        if t.raw_date and "2024-04-19" in t.raw_date and t.debit_cents == 76_000
    )
    check("M-Pesa spot: date == '2024-04-19'", mpesa_row.date == "2024-04-19",
          detail=f"got {mpesa_row.date!r}")
    check("M-Pesa spot: debit_cents == 76000", mpesa_row.debit_cents == 76_000,
          detail=f"got {mpesa_row.debit_cents}")
    check("M-Pesa spot: balance_cents == 5375", mpesa_row.balance_cents == 5_375,
          detail=f"got {mpesa_row.balance_cents}")
    check("M-Pesa spot: currency == 'KES'", mpesa_row.currency == "KES")
    check("M-Pesa spot: normalisation_status == 'ok'",
          mpesa_row.normalisation_status.value == "ok")
except StopIteration:
    check("M-Pesa spot check row found (2024-04-19, debit=76000)", False,
          detail="row not found in normalised_transactions")

# Spot check — credit row: SDN72S2N11, credit=490, date=2024-04-23, balance=526.75
try:
    credit_row = next(
        t for t in csv_result.normalised_transactions
        if t.raw_date and "2024-04-23" in t.raw_date and t.credit_cents == 49_000
    )
    check("M-Pesa credit spot: credit_cents == 49000", credit_row.credit_cents == 49_000,
          detail=f"got {credit_row.credit_cents}")
    check("M-Pesa credit spot: balance_cents == 52675", credit_row.balance_cents == 52_675,
          detail=f"got {credit_row.balance_cents}")
    check("M-Pesa credit spot: debit_cents is None", credit_row.debit_cents is None,
          detail=f"got {credit_row.debit_cents}")
except StopIteration:
    check("M-Pesa credit spot check row found (2024-04-23, credit=49000)", False,
          detail="row not found")

# Final guard: grep-equivalent — no float() in normaliser source
normaliser_src_path = os.path.join(os.path.dirname(__file__), "..", "app", "normaliser.py")
with open(normaliser_src_path) as f:
    normaliser_src = f.read()
float_calls_in_normaliser = [
    (i + 1, line.strip())
    for i, line in enumerate(normaliser_src.splitlines())
    if "float(" in line and not line.strip().startswith("#")
]
check(
    f"no float() calls in normaliser.py (found: {len(float_calls_in_normaliser)})",
    len(float_calls_in_normaliser) == 0,
    detail=str(float_calls_in_normaliser) if float_calls_in_normaliser else "",
)

print(f"\n  PDF normalisation warnings : {len(pdf_result.normalisation_warnings)}")
for w in pdf_result.normalisation_warnings[:3]:
    print(f"    {w}")
print(f"  CSV normalisation warnings : {len(csv_result.normalisation_warnings)}")

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — DOCUMENT AI OCR TESTS
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Phase 2: PDF Type Detector ─────────────────────────────────────────")

check(
    "is_scanned_pdf(scanned_equity_bank_statement.pdf) == True",
    is_scanned_pdf(SCANNED_PDF_PATH) == True,
    detail=f"path={SCANNED_PDF_PATH}",
)
check(
    "is_scanned_pdf(AccountStatement_DHASSAN.pdf) == False",
    is_scanned_pdf(PDF_PATH) == False,
    detail=f"path={PDF_PATH}",
)

print("\n── Phase 2: Document AI Extraction ────────────────────────────────────")

scanned_result = extract_with_docai(
    SCANNED_PDF_PATH,
    doc_id="test-docai-001",
    filename="scanned_equity_bank_statement.pdf",
)

check(
    f"scanned extraction_status != 'failed' (got {scanned_result.extraction_status!r})",
    scanned_result.extraction_status != "failed",
    detail=str([w.message for w in scanned_result.warnings[:3]]),
)
check(
    f"scanned doc_type == 'scanned_pdf' (got {scanned_result.doc_type!r})",
    str(scanned_result.doc_type) == "DocType.SCANNED_PDF"
    or (scanned_result.doc_type is not None and scanned_result.doc_type.value == "scanned_pdf"),
)
check(
    f"scanned row_count >= 35 (got {scanned_result.row_count})",
    scanned_result.row_count >= 35,
)

source_methods = [
    t.source_extraction_method for t in scanned_result.raw_transactions
]
bad_methods = [m for m in source_methods if m != "document_ai"]
check(
    f"all raw_transactions have source_extraction_method == 'document_ai' (bad: {len(bad_methods)})",
    len(bad_methods) == 0,
    detail=str(bad_methods[:3]) if bad_methods else "",
)

print("\n── Phase 2: Normalisation of scanned transactions ──────────────────────")

normalise_all(scanned_result)

dates = [t.date for t in scanned_result.normalised_transactions if t.date]
check(
    f"normalised date count >= 35 (got {len(dates)})",
    len(dates) >= 35,
)

bad_date_fmt = [d for d in dates if not d.startswith("2024-0")]
check(
    f"all dates start with '2024-0' (bad: {len(bad_date_fmt)})",
    len(bad_date_fmt) == 0,
    detail=str(bad_date_fmt[:5]) if bad_date_fmt else "",
)

scanned_float_violations = [
    (t.row_index, field, val)
    for t in scanned_result.normalised_transactions
    for field, val in [
        ("debit_cents", t.debit_cents),
        ("credit_cents", t.credit_cents),
        ("balance_cents", t.balance_cents),
    ]
    if isinstance(val, float)
]
check(
    f"no float values in scanned normalised amounts (violations: {len(scanned_float_violations)})",
    len(scanned_float_violations) == 0,
    detail=str(scanned_float_violations[:3]) if scanned_float_violations else "",
)

print(f"\n  Scanned PDF warnings        : {len(scanned_result.warnings)}")
for w in scanned_result.warnings[:5]:
    print(f"    row {w.row_index}: {w.message} — {w.raw_text[:60]!r}")
print(f"  Scanned normalisation warns : {len(scanned_result.normalisation_warnings)}")

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "─" * 68)
if failures:
    print(f"\n{FAIL}  {len(failures)} check(s) failed:")
    for f in failures:
        print(f"  • {f}")
    sys.exit(1)
else:
    print(f"\n{PASS}  All checks passed.")
    print(f"  PDF rows            : {pdf_result.row_count}")
    print(f"  PDF normalised rows : {len(pdf_result.normalised_transactions)}")
    print(f"  CSV rows            : {csv_result.row_count}")
    print(f"  CSV normalised rows : {len(csv_result.normalised_transactions)}")
    print(f"  Scanned rows        : {scanned_result.row_count}")
    print(f"  Scanned normalised  : {len(scanned_result.normalised_transactions)}")
    sys.exit(0)
