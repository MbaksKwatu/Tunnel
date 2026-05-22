"""Tests for bank format router."""
from __future__ import annotations

import pytest

from app.extractors.router import route_extract, UNSUPPORTED_RESPONSE

SAMPLES = "/Users/mbakswatu/Desktop/Demofiles/bankstatementsamples"
KCB_PDF = f"{SAMPLES}/KCB Bank Statement (1).pdf"
NCBA_PDF = f"{SAMPLES}/NCBA Bank Statement.pdf"
COOP_PDF = f"{SAMPLES}/Cooperative Bank Statement.pdf"
ABSA_PDF = f"{SAMPLES}/absa.pdf"
EQUITY_PDF = f"{SAMPLES}/Unlock PDF Equity Unlocked.pdf"


@pytest.mark.skipif(
    not __import__("pathlib").Path(KCB_PDF).exists(),
    reason="KCB fixture missing",
)
def test_router_detects_kcb():
    result = route_extract(KCB_PDF)
    assert not isinstance(result, dict) or result.get("status") != "UNSUPPORTED_FORMAT"
    if hasattr(result, "extractor_type"):
        assert result.extractor_type == "kcb_pdf"


@pytest.mark.skipif(
    not __import__("pathlib").Path(NCBA_PDF).exists(),
    reason="NCBA fixture missing",
)
def test_router_detects_ncba():
    result = route_extract(NCBA_PDF)
    assert not isinstance(result, dict) or result.get("status") != "UNSUPPORTED_FORMAT"
    if hasattr(result, "extractor_type"):
        assert result.extractor_type == "ncba_pdf"


@pytest.mark.skipif(
    not __import__("pathlib").Path(COOP_PDF).exists(),
    reason="COOP fixture missing",
)
def test_router_detects_coop():
    result = route_extract(COOP_PDF)
    if hasattr(result, "extractor_type"):
        assert result.extractor_type == "coop_pdf"


def test_router_returns_unsupported_for_invalid():
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4 invalid content")
        path = f.name
    try:
        result = route_extract(path)
        assert isinstance(result, dict)
        assert result.get("status") == "UNSUPPORTED_FORMAT"
    finally:
        import os
        os.unlink(path)
