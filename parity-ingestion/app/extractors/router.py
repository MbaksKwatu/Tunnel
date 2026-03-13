"""
Bank format detection and extraction router.

Detection order (most specific first): KCB → NCBA → Equity → ABSA → COOP → MPESA_PDF → SCB
"""
from __future__ import annotations

from typing import Union

from app.extractors.kcb_extractor import detect_kcb, extract_kcb_pdf
from app.extractors.ncba_extractor import detect_ncba, extract_ncba_pdf
from app.extractors.equity_extractor import detect_equity, extract_equity_pdf
from app.extractors.absa_extractor import detect_absa, extract_absa_pdf
from app.extractors.coop_extractor import detect_coop, extract_coop_pdf
from app.extractors.mpesa_pdf_extractor import detect_mpesa_pdf, extract_mpesa_pdf
from app.extractors.pdf_extractor import extract_scb_pdf

from app.models import ExtractionResult

UNSUPPORTED_RESPONSE = {
    "status": "UNSUPPORTED_FORMAT",
    "message": (
        "Bank format not recognised. Supported formats: SCB, Co-op, ABSA, M-Pesa, "
        "Equity Bank, KCB, NCBA"
    ),
}


def route_extract(file_path: str) -> Union[ExtractionResult, dict]:
    """
    Detect bank format and run the appropriate extractor.
    Returns ExtractionResult on success, or UNSUPPORTED_RESPONSE dict if no format matches.
    """
    if detect_kcb(file_path):
        return extract_kcb_pdf(file_path)
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
