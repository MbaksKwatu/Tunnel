import pytest

from backend.routes.deals import normalize_evidence_payload


def test_unreadable_flag_set_for_pdf_with_short_text():
    payload = normalize_evidence_payload(
        deal_id="deal-1",
        evidence_type="financial",
        source="pdf",
        data={"text": ""},
        meta={"filename": "scan.pdf"},
        confidence=0.5,
        document_id="doc-1",
    )

    extracted = payload.get("extracted_data") or {}
    meta = extracted.get("meta") or {}

    assert meta.get("unreadable") is True
    assert meta.get("fallback_method") is None


def test_unreadable_flag_false_for_pdf_with_long_text():
    long_text = "This is a readable PDF with actual content " * 5
    payload = normalize_evidence_payload(
        deal_id="deal-1",
        evidence_type="financial",
        source="pdf",
        data={"text": long_text},
        meta={"filename": "statement.pdf"},
        confidence=0.5,
        document_id="doc-1",
    )

    extracted = payload.get("extracted_data") or {}
    meta = extracted.get("meta") or {}

    assert meta.get("unreadable") is False
    assert meta.get("fallback_method") is None

