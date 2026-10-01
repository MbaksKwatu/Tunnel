"""POST /v1/harness -- detection + run_parser_harness() over HTTP, for the admin
parser-request queue's "Test against submitted file" button."""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
from fastapi.testclient import TestClient

from app.main import app

_GENERATOR = pathlib.Path(__file__).parent / "fixtures" / "generate_absa_synthetic.py"


@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def absa_synthetic_pdf(tmp_path_factory):
    pytest.importorskip("reportlab")
    spec = importlib.util.spec_from_file_location("generate_absa_synthetic", _GENERATOR)
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    return gen.build(tmp_path_factory.mktemp("harness_ep") / "absa_synthetic.pdf")


def test_detected_file_returns_harness_digest(client, absa_synthetic_pdf):
    with open(absa_synthetic_pdf, "rb") as fh:
        res = client.post("/v1/harness", files={"file": ("statement.pdf", fh, "application/pdf")})
    assert res.status_code == 200
    body = res.json()
    assert body["detected"] is True
    assert body["status"] == "DETECTED"
    assert body["extractor_type"] == "absa_pdf"
    assert body["row_count"] > 0
    assert body["harness"]["balance_reconciliation"] is True


def test_unreadable_pdf_is_a_reported_detection_failure(client):
    res = client.post("/v1/harness", files={"file": ("bad.pdf", b"not a pdf", "application/pdf")})
    assert res.status_code == 200
    body = res.json()
    assert body["detected"] is False
    assert body["status"] == "INVALID_DOCUMENT"
    assert "harness" not in body


def test_unsupported_extension_is_reported_not_raised(client):
    res = client.post("/v1/harness", files={"file": ("rows.csv", b"a,b\n1,2\n", "text/csv")})
    assert res.status_code == 200
    body = res.json()
    assert body["detected"] is False
    assert body["status"] == "UNSUPPORTED_FILE_TYPE"
