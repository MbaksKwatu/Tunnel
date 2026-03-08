"""
Google Document AI extractor for scanned / image-only PDFs.

Supported bank format: Equity Bank Kenya (Q1 2024 statement layout).
Date format on source document: DD Mon YYYY  e.g. "03 Jan 2024"

Pipeline:
  1. Size guards (18 MB / 15 pages) — oversized files get needs_review.
  2. Read PDF bytes → send to Document AI OCR processor.
  3. For each page: convert token objects to word dicts via _tokens_to_words().
  4. Group words into visual rows via _group_by_line() from shared.py.
  5. Detect column x-boundaries per page via _detect_column_bounds().
  6. Walk rows, detect date-starting rows, assemble RawTransaction objects.

All amounts are stored as raw strings — no float coercion, ever.
"""
from __future__ import annotations

import re

import pdfplumber
from google.cloud import documentai_v1 as documentai

from app.extractors.shared import (
    _assign_column,
    _detect_column_bounds,
    _group_by_line,
    _should_skip_line,
)
from app.models import DocType, ExtractionResult, RawTransaction, WarningItem

# ── Constants ─────────────────────────────────────────────────────────────────

_PROCESSOR_NAME = (
    "projects/paritytunnel/locations/us/processors/d39d4916c90a7a7e"
)

MAX_BYTES = 18 * 1024 * 1024   # 18 MB
MAX_PAGES = 15

_ROW_Y_TOLERANCE = 5.0         # points; slightly looser than SCB (4.0) because
                                # OCR bounding boxes have more vertical jitter

# Equity Bank date pattern: "03 Jan 2024"
_EQUITY_DATE_PAT = re.compile(r"^\d{2}\s[A-Za-z]{3}\s\d{4}$")

# Balance markers to skip
_BALANCE_MARKERS = (
    "OPENING BALANCE",
    "CLOSING BALANCE",
    "BROUGHT FORWARD",
    "BALANCE B/F",
    "BALANCE C/F",
)

# Minimum x0 for the date column (tokens further left than this are noise)
_DATE_MAX_X0_RATIO = 0.25      # fraction of page width

# Description column: x0 must be beyond this ratio of page width
_DESC_MIN_X0_RATIO = 0.20
_DESC_MAX_X0_RATIO = 0.60


# ── Document AI API call ──────────────────────────────────────────────────────

def _call_document_ai(pdf_bytes: bytes) -> documentai.Document:
    client = documentai.DocumentProcessorServiceClient()

    raw_document = documentai.RawDocument(
        content=pdf_bytes,
        mime_type="application/pdf",
    )

    request = documentai.ProcessRequest(
        name=_PROCESSOR_NAME,
        raw_document=raw_document,
    )

    response = client.process_document(request=request)
    return response.document


# ── Token → word dict conversion ─────────────────────────────────────────────

def _tokens_to_words(document: documentai.Document, page_idx: int) -> list[dict]:
    """
    Convert Document AI token objects to word dicts compatible with
    the shared column assignment logic.

    Returns list of {"text": str, "x0": float, "x1": float, "top": float}
    where coordinates are in points (normalised values × page width/height).
    """
    page = document.pages[page_idx]
    page_w = page.dimension.width or 612   # fallback to US Letter points
    page_h = page.dimension.height or 792

    words = []
    for token in page.tokens:
        verts = token.layout.bounding_poly.normalized_vertices
        if len(verts) < 4:
            continue
        x0 = verts[0].x * page_w
        x1 = verts[2].x * page_w
        top = verts[0].y * page_h

        segments = token.layout.text_anchor.text_segments
        if not segments:
            continue
        start = segments[0].start_index
        end = segments[0].end_index
        text = document.text[start:end].strip()
        if text:
            words.append({"text": text, "x0": x0, "x1": x1, "top": top})
    return words


# ── Row-level helpers ─────────────────────────────────────────────────────────

def _is_equity_date(text: str) -> bool:
    return bool(_EQUITY_DATE_PAT.match(text))


def _is_balance_marker(text: str) -> bool:
    upper = text.upper()
    return any(m in upper for m in _BALANCE_MARKERS)


def _flush_pending(
    pending: dict,
    transactions: list[RawTransaction],
    warnings: list[WarningItem],
    filename: str,
) -> None:
    date = pending["date_raw"]
    desc = pending["description"]
    has_amounts = bool(
        pending["debit_raw"] or pending["credit_raw"] or pending["balance_raw"]
    )

    if not date and not desc:
        return

    if date and has_amounts:
        confidence = 1.0
    elif date:
        confidence = 0.8
        warnings.append(
            WarningItem(
                row_index=pending["row_index"],
                message="Transaction row missing all amount fields",
                raw_text=f"{date} | {desc}",
            )
        )
    else:
        confidence = 0.9

    transactions.append(
        RawTransaction(
            row_index=pending["row_index"],
            date_raw=date,
            description=desc,
            debit_raw=pending["debit_raw"],
            credit_raw=pending["credit_raw"],
            balance_raw=pending["balance_raw"],
            source_file=filename,
            extraction_confidence=confidence,
            source_extraction_method="document_ai",
        )
    )


# ── Transaction assembly ──────────────────────────────────────────────────────

def _assemble_transactions(
    document: documentai.Document,
    filename: str,
) -> tuple[list[RawTransaction], list[WarningItem]]:
    """
    Walk all pages of the Document AI result and assemble RawTransaction objects.
    """
    transactions: list[RawTransaction] = []
    warnings: list[WarningItem] = []
    row_idx = 0

    for page_idx in range(len(document.pages)):
        words = _tokens_to_words(document, page_idx)
        if not words:
            continue

        page = document.pages[page_idx]
        page_w = page.dimension.width or 612

        lines = _group_by_line(words, _ROW_Y_TOLERANCE)

        # Detect amount column boundaries for this page from its line data
        bounds = _detect_column_bounds(lines, page_w)
        date_max_x0 = page_w * _DATE_MAX_X0_RATIO
        desc_min_x0 = page_w * _DESC_MIN_X0_RATIO
        desc_max_x0 = page_w * _DESC_MAX_X0_RATIO

        pending: dict | None = None

        for row_words in lines:
            date_parts: list[str] = []
            desc_parts: list[str] = []
            debit_parts: list[str] = []
            credit_parts: list[str] = []
            balance_parts: list[str] = []

            for w in row_words:
                col = _assign_column(w, bounds)
                if col == "debit":
                    debit_parts.append(w["text"])
                elif col == "credit":
                    credit_parts.append(w["text"])
                elif col == "balance":
                    balance_parts.append(w["text"])
                elif w["x0"] < date_max_x0:
                    date_parts.append(w["text"])
                elif desc_min_x0 <= w["x0"] < desc_max_x0:
                    desc_parts.append(w["text"])

            date_str = " ".join(date_parts).strip()
            desc_str = " ".join(desc_parts).strip()
            debit_str = " ".join(debit_parts).strip()
            credit_str = " ".join(credit_parts).strip()
            balance_str = " ".join(balance_parts).strip()

            # Skip blank rows
            if not any([date_str, desc_str, debit_str, credit_str, balance_str]):
                continue

            # Skip header / footer lines
            row_text = " ".join(w["text"] for w in row_words)
            if _should_skip_line(row_text):
                continue

            # Skip balance marker rows
            if _is_balance_marker(row_text):
                if pending is not None:
                    _flush_pending(pending, transactions, warnings, filename)
                    pending = None
                warnings.append(
                    WarningItem(
                        row_index=row_idx,
                        message="Balance marker row skipped",
                        raw_text=row_text[:80],
                    )
                )
                row_idx += 1
                continue

            has_date = _is_equity_date(date_str)
            has_content = bool(desc_str or debit_str or credit_str or balance_str)

            if not has_content and not has_date:
                continue

            if has_date:
                if pending is not None:
                    _flush_pending(pending, transactions, warnings, filename)
                pending = {
                    "row_index": row_idx,
                    "date_raw": date_str,
                    "description": desc_str,
                    "debit_raw": debit_str,
                    "credit_raw": credit_str,
                    "balance_raw": balance_str,
                }
                row_idx += 1
            else:
                # Continuation row — merge into pending
                if pending is not None:
                    if desc_str:
                        pending["description"] = (
                            pending["description"] + " " + desc_str
                        ).strip()
                    if debit_str and not pending["debit_raw"]:
                        pending["debit_raw"] = debit_str
                    if credit_str and not pending["credit_raw"]:
                        pending["credit_raw"] = credit_str
                    if balance_str and not pending["balance_raw"]:
                        pending["balance_raw"] = balance_str

        if pending is not None:
            _flush_pending(pending, transactions, warnings, filename)
            pending = None

    return transactions, warnings


# ── Public interface ──────────────────────────────────────────────────────────

def extract_with_docai(path: str, doc_id: str, filename: str) -> ExtractionResult:
    """
    Extract transactions from a scanned PDF using Google Document AI OCR.

    Returns an ExtractionResult with extractor_type='document_ai' and
    doc_type=DocType.SCANNED_PDF.  All RawTransaction objects carry
    source_extraction_method='document_ai'.

    API failures are caught and returned as extraction_status='failed'.
    Oversized files (>18 MB or >15 pages) return extraction_status='needs_review'
    without calling the API.
    """
    def _needs_review(reason: str) -> ExtractionResult:
        return ExtractionResult(
            source_file=filename,
            extractor_type="document_ai",
            doc_type=DocType.SCANNED_PDF,
            row_count=0,
            extraction_status="needs_review",
            warnings=[
                WarningItem(row_index=0, message=reason, raw_text="")
            ],
            raw_transactions=[],
        )

    # Size guards — read bytes first for byte-count check
    try:
        with open(path, "rb") as fh:
            pdf_bytes = fh.read()
    except OSError as exc:
        return ExtractionResult(
            source_file=filename,
            extractor_type="document_ai",
            doc_type=DocType.SCANNED_PDF,
            row_count=0,
            extraction_status="failed",
            warnings=[
                WarningItem(
                    row_index=0,
                    message=f"Could not read file: {exc}",
                    raw_text="",
                )
            ],
            raw_transactions=[],
        )

    if len(pdf_bytes) > MAX_BYTES:
        return _needs_review(
            f"File exceeds {MAX_BYTES // (1024 * 1024)} MB limit "
            f"({len(pdf_bytes) // (1024 * 1024)} MB) — manual review required"
        )

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) > MAX_PAGES:
            return _needs_review(
                f"File has {len(pdf.pages)} pages — exceeds {MAX_PAGES}-page "
                "limit for Document AI processing"
            )

    # Call Document AI
    try:
        document = _call_document_ai(pdf_bytes)
    except Exception as exc:
        return ExtractionResult(
            source_file=filename,
            extractor_type="document_ai",
            doc_type=DocType.SCANNED_PDF,
            row_count=0,
            extraction_status="failed",
            warnings=[
                WarningItem(
                    row_index=0,
                    message=f"Document AI call failed: {exc}",
                    raw_text="",
                )
            ],
            raw_transactions=[],
        )

    transactions, warnings = _assemble_transactions(document, filename)

    extraction_status = (
        "failed"
        if not transactions
        else ("needs_review" if warnings else "success")
    )

    return ExtractionResult(
        source_file=filename,
        extractor_type="document_ai",
        doc_type=DocType.SCANNED_PDF,
        row_count=len(transactions),
        extraction_status=extraction_status,
        warnings=warnings,
        raw_transactions=transactions,
    )
