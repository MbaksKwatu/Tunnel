"""
Bank format detection and extraction router.

XLSX is routed by extension first. PDF detection order:
KCB → KCB_Online → Equity_CLMS → NCBA → Equity → ABSA → COOP → MPESA_PDF → Stanbic → SCB

Note: Equity_CLMS must precede NCBA because some CLMS statements trigger NCBA detection.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

from app.extractors.kcb_extractor import detect_kcb, extract_kcb_pdf, detect_kcb_online, extract_kcb_online_pdf
from app.extractors.ncba_extractor import detect_ncba, extract_ncba_pdf
from app.extractors.equity_extractor import detect_equity, extract_equity_pdf, detect_equity_clms, extract_equity_clms_pdf
from app.extractors.absa_extractor import detect_absa, extract_absa_pdf
from app.extractors.coop_extractor import detect_coop, extract_coop_pdf
from app.extractors.mpesa_pdf_extractor import detect_mpesa_pdf, extract_mpesa_pdf
from app.extractors.stanbic_extractor import detect_stanbic, extract_stanbic_pdf
from app.extractors.pdf_extractor import extract_scb_pdf
from app.extractors.currency_detector import detect as detect_currency

from app.models import ExtractionResult

logger = logging.getLogger(__name__)

UNSUPPORTED_RESPONSE = {
    "status": "UNSUPPORTED_FORMAT",
    "message": (
        "Bank format not recognised. Supported formats: SCB, Co-op, ABSA, M-Pesa, "
        "Equity Bank, KCB, NCBA, Stanbic"
    ),
}


def _pre_extract_currency(file_path: str) -> Optional[str]:
    """
    Extract text from first 2 pages and run L1 currency detection.
    Returns ISO 4217 code or None. Never raises.
    Used as a pre-routing belt-and-braces check; individual extractors
    retain their own detection as the primary signal.
    """
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            pages_text = [p.extract_text() or "" for p in pdf.pages[:2]]
        combined = " ".join(pages_text)
        return detect_currency(combined)
    except Exception:
        return None


def route_extract(file_path: str) -> Union[ExtractionResult, dict]:
    """
    Detect bank format and run the appropriate extractor.
    Returns ExtractionResult on success, or UNSUPPORTED_RESPONSE dict if no format matches.
    """
    ext = Path(file_path).suffix.lower()
    if ext == ".xlsx":
        from app.extractors.xlsx_extractor import extract_xlsx

        return extract_xlsx(file_path)

    # Pre-extraction: L1 currency detection from first 2 pages.
    # Result is logged for observability; individual parsers use their own detection.
    currency_hint = _pre_extract_currency(file_path)
    if currency_hint:
        logger.debug("Router pre-detected currency=%s for %s", currency_hint, file_path)

    if detect_kcb(file_path):
        return extract_kcb_pdf(file_path)
    if detect_kcb_online(file_path):
        return extract_kcb_online_pdf(file_path)
    if detect_equity_clms(file_path):
        return extract_equity_clms_pdf(file_path)
    if detect_ncba(file_path):
        return extract_ncba_pdf(file_path)
    if detect_equity(file_path):
        return extract_equity_pdf(file_path)
    if detect_absa(file_path):
        return extract_absa_pdf(file_path)
    if detect_coop(file_path):
        return extract_coop_pdf(file_path)
    if detect_mpesa_pdf(file_path):
        return extract_mpesa_pdf(file_path)
    if detect_stanbic(file_path):
        return extract_stanbic_pdf(file_path)

    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            if pdf.pages:
                text = pdf.pages[0].extract_text() or ""
                if "Particulars" in text and "Statement Of Account" in text:
                    return extract_scb_pdf(file_path)
    except Exception:
        pass

    return UNSUPPORTED_RESPONSE
