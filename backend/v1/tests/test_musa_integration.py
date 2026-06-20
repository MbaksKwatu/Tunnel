"""
Tests for the Musa Ventures integration.

Covers:
  - SessionResponse shape consistency (POST ≡ GET status ≡ webhook payload)
  - API key authentication enforcement
  - Country → currency mapping
  - File extension inference
  - Webhook payload structure
  - Error state handling

Run:
    cd backend
    python3 -m pytest v1/tests/test_musa_integration.py -v
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def app():
    """FastAPI test app with in-memory repos injected via app.state."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from v1.integrations.musa_api import router as musa_router

    _app = FastAPI()
    _app.include_router(musa_router)
    return _app


@pytest.fixture()
def client(app):
    return TestClient(app, raise_server_exceptions=False)


VALID_API_KEY = "mklivemH-zWgAzc8Sg9gcpZIm9r-nfZnsSgpr4skCcQuub3r8"
VALID_HEADERS = {"x-api-key": VALID_API_KEY}

VALID_SESSION_BODY = {
    "venture_name":    "Test Venture Ltd",
    "venture_country": "Kenya",
    "document_urls": [
        {
            "url":       "https://example.com/signed/bank_statement.pdf",
            "file_type": "bank_statement",
            "date_from": "2025-01-01",
            "date_to":   "2025-12-31",
        }
    ],
}

# Expected fields in every SessionResponse
_SESSION_RESPONSE_FIELDS = {
    "session_id", "venture_name", "venture_country",
    "status", "status_url",
    "pdf_url", "error_message", "created_at", "completed_at",
}


# ---------------------------------------------------------------------------
# Helper: build a fake musa_sessions row
# ---------------------------------------------------------------------------

def _fake_session_row(
    session_id: str,
    status: str = "processing",
    deal_id: Optional[str] = None,
    venture_country: str = "Kenya",
    error_message: Optional[str] = None,
    completed_at: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "session_id":      session_id,
        "venture_name":    "Test Venture Ltd",
        "venture_country": venture_country,
        "deal_id":         deal_id or str(uuid.uuid4()),
        "status":          status,
        "created_at":      datetime.now(timezone.utc).isoformat(),
        "completed_at":    completed_at,
        "error_message":   error_message,
    }


# ===========================================================================
# 1. Country → currency mapping
# ===========================================================================

class TestCurrencyMapping:
    def test_known_countries(self):
        from v1.integrations.currency_utils import country_to_currency
        assert country_to_currency("Kenya")        == "KES"
        assert country_to_currency("kenya")        == "KES"
        assert country_to_currency("Uganda")       == "UGX"
        assert country_to_currency("Tanzania")     == "TZS"
        assert country_to_currency("Nigeria")      == "NGN"
        assert country_to_currency("Rwanda")       == "RWF"

    def test_unknown_country_raises(self):
        import pytest
        from v1.integrations.currency_utils import country_to_currency
        with pytest.raises(ValueError, match="Cannot resolve country"):
            country_to_currency("Wakanda")
        with pytest.raises(ValueError, match="Cannot resolve country"):
            country_to_currency("")


# ===========================================================================
# 2. File extension inference
# ===========================================================================

class TestExtensionInference:
    def test_pdf_url(self):
        from v1.integrations.musa_file_processor import _infer_extension
        assert _infer_extension("https://s3.amazonaws.com/bucket/file.pdf?X-Amz-Sig=abc", None) == ".pdf"

    def test_csv_url(self):
        from v1.integrations.musa_file_processor import _infer_extension
        assert _infer_extension("https://example.com/mpesa.csv", None) == ".csv"

    def test_xlsx_url(self):
        from v1.integrations.musa_file_processor import _infer_extension
        assert _infer_extension("https://example.com/report.xlsx", None) == ".xlsx"

    def test_unknown_url_falls_back_to_hint(self):
        from v1.integrations.musa_file_processor import _infer_extension
        assert _infer_extension("https://example.com/signed-url-no-ext", "mpesa") == ".csv"
        assert _infer_extension("https://example.com/signed-url-no-ext", "bank_statement") == ".pdf"

    def test_unknown_url_and_no_hint_defaults_to_pdf(self):
        from v1.integrations.musa_file_processor import _infer_extension
        assert _infer_extension("https://example.com/signed-url-no-ext", None) == ".pdf"

    def test_unsupported_extension_falls_back_to_hint(self):
        from v1.integrations.musa_file_processor import _infer_extension
        # .zip is not allowed — should fall back to hint
        assert _infer_extension("https://example.com/archive.zip", "bank_statement") == ".pdf"


# ===========================================================================
# 3. Authentication
# ===========================================================================

class TestAuthentication:
    def _mock_supabase_for_auth(self, monkeypatch, valid: bool):
        """Patch auth.validate_api_key to return valid/invalid."""
        monkeypatch.setattr(
            "v1.integrations.auth.validate_api_key",
            lambda key, partner: valid,
        )

    def test_missing_api_key_returns_422(self, client):
        resp = client.post("/api/musa/sessions", json=VALID_SESSION_BODY)
        assert resp.status_code == 422  # FastAPI: required header missing

    def test_invalid_api_key_returns_401(self, client, monkeypatch):
        monkeypatch.setattr("v1.integrations.auth.validate_api_key", lambda k, p: False)
        resp = client.post(
            "/api/musa/sessions",
            json=VALID_SESSION_BODY,
            headers={"x-api-key": "wrong-key"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid API key"

    def test_invalid_key_on_status_endpoint(self, client, monkeypatch):
        monkeypatch.setattr("v1.integrations.auth.validate_api_key", lambda k, p: False)
        resp = client.get(
            "/api/musa/sessions/some-id/status",
            headers={"x-api-key": "wrong-key"},
        )
        assert resp.status_code == 401


# ===========================================================================
# 4. POST /sessions — response shape
# ===========================================================================

class TestCreateSession:
    def _mock_db(self, monkeypatch, session_id: str, deal_id: str):
        """Patch DB calls so create_session succeeds without a real Supabase."""
        # Patch DealsRepo.create_deal
        monkeypatch.setattr(
            "v1.integrations.musa_api.DealsRepo",
            lambda: MagicMock(create_deal=lambda d: {**d, "id": deal_id}),
        )
        # Patch get_supabase → table → insert → execute
        mock_sb = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"session_id": session_id, "created_at": datetime.now(timezone.utc).isoformat()}]
        )
        monkeypatch.setattr("v1.integrations.musa_api.get_supabase", lambda: mock_sb)
        # Patch auth
        monkeypatch.setattr("v1.integrations.auth.validate_api_key", lambda k, p: True)
        # Suppress background task
        monkeypatch.setattr(
            "v1.integrations.musa_api.process_musa_session",
            lambda **kw: None,
        )

    def test_response_has_all_session_response_fields(self, client, monkeypatch):
        sid = str(uuid.uuid4())
        did = str(uuid.uuid4())
        self._mock_db(monkeypatch, sid, did)

        resp = client.post("/api/musa/sessions", json=VALID_SESSION_BODY, headers=VALID_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert _SESSION_RESPONSE_FIELDS.issubset(data.keys()), (
            f"Missing fields: {_SESSION_RESPONSE_FIELDS - data.keys()}"
        )

    def test_initial_status_is_processing(self, client, monkeypatch):
        sid = str(uuid.uuid4())
        did = str(uuid.uuid4())
        self._mock_db(monkeypatch, sid, did)

        resp = client.post("/api/musa/sessions", json=VALID_SESSION_BODY, headers=VALID_HEADERS)
        assert resp.json()["status"] == "processing"

    def test_pdf_url_is_null_initially(self, client, monkeypatch):
        sid = str(uuid.uuid4())
        did = str(uuid.uuid4())
        self._mock_db(monkeypatch, sid, did)

        resp = client.post("/api/musa/sessions", json=VALID_SESSION_BODY, headers=VALID_HEADERS)
        assert resp.json()["pdf_url"] is None

    def test_status_url_is_well_formed(self, client, monkeypatch):
        sid = str(uuid.uuid4())
        did = str(uuid.uuid4())
        self._mock_db(monkeypatch, sid, did)

        resp = client.post("/api/musa/sessions", json=VALID_SESSION_BODY, headers=VALID_HEADERS)
        status_url = resp.json()["status_url"]
        assert "/api/musa/sessions/" in status_url
        assert "/status" in status_url

    def test_venture_fields_echoed_correctly(self, client, monkeypatch):
        sid = str(uuid.uuid4())
        did = str(uuid.uuid4())
        self._mock_db(monkeypatch, sid, did)

        resp = client.post("/api/musa/sessions", json=VALID_SESSION_BODY, headers=VALID_HEADERS)
        data = resp.json()
        assert data["venture_name"]    == VALID_SESSION_BODY["venture_name"]
        assert data["venture_country"] == VALID_SESSION_BODY["venture_country"]


# ===========================================================================
# 5. GET /sessions/{id}/status — response shape parity
# ===========================================================================

class TestGetStatus:
    def _mock_db(self, monkeypatch, row: Dict[str, Any]):
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[row]
        )
        monkeypatch.setattr("v1.integrations.musa_api.get_supabase", lambda: mock_sb)
        monkeypatch.setattr("v1.integrations.auth.validate_api_key", lambda k, p: True)

    def test_response_has_all_session_response_fields(self, client, monkeypatch):
        sid = str(uuid.uuid4())
        row = _fake_session_row(sid)
        self._mock_db(monkeypatch, row)

        resp = client.get(f"/api/musa/sessions/{sid}/status", headers=VALID_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert _SESSION_RESPONSE_FIELDS.issubset(data.keys()), (
            f"Missing fields: {_SESSION_RESPONSE_FIELDS - data.keys()}"
        )

    def test_status_matches_db_row(self, client, monkeypatch):
        sid = str(uuid.uuid4())
        row = _fake_session_row(sid, status="complete", completed_at=datetime.now(timezone.utc).isoformat())
        self._mock_db(monkeypatch, row)

        resp = client.get(f"/api/musa/sessions/{sid}/status", headers=VALID_HEADERS)
        assert resp.json()["status"] == "complete"

    def test_pdf_url_populated_when_complete(self, client, monkeypatch):
        sid = str(uuid.uuid4())
        did = str(uuid.uuid4())
        row = _fake_session_row(sid, status="complete", deal_id=did)
        self._mock_db(monkeypatch, row)

        resp = client.get(f"/api/musa/sessions/{sid}/status", headers=VALID_HEADERS)
        pdf_url = resp.json()["pdf_url"]
        assert pdf_url is not None
        assert did in pdf_url
        assert "snapshot/pdf" in pdf_url

    def test_pdf_url_null_when_processing(self, client, monkeypatch):
        sid = str(uuid.uuid4())
        row = _fake_session_row(sid, status="processing")
        self._mock_db(monkeypatch, row)

        resp = client.get(f"/api/musa/sessions/{sid}/status", headers=VALID_HEADERS)
        assert resp.json()["pdf_url"] is None

    def test_error_message_surfaced_when_failed(self, client, monkeypatch):
        sid = str(uuid.uuid4())
        row = _fake_session_row(sid, status="failed", error_message="Download timed out")
        self._mock_db(monkeypatch, row)

        resp = client.get(f"/api/musa/sessions/{sid}/status", headers=VALID_HEADERS)
        assert resp.json()["error_message"] == "Download timed out"

    def test_404_for_unknown_session(self, client, monkeypatch):
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )
        monkeypatch.setattr("v1.integrations.musa_api.get_supabase", lambda: mock_sb)
        monkeypatch.setattr("v1.integrations.auth.validate_api_key", lambda k, p: True)

        resp = client.get("/api/musa/sessions/nonexistent/status", headers=VALID_HEADERS)
        assert resp.status_code == 404


# ===========================================================================
# 6. Webhook payload shape parity
# ===========================================================================

class TestWebhookPayload:
    def test_webhook_payload_matches_session_response_fields(self, monkeypatch):
        """
        Verify _send_webhook constructs a dict whose keys are identical to
        the fields in SessionResponse.
        """
        import asyncio
        from unittest.mock import AsyncMock
        from v1.integrations.musa_file_processor import _send_webhook

        monkeypatch.setenv("MUSA_WEBHOOK_URL",        "https://webhook.example.com")
        monkeypatch.setenv("MUSA_WEBHOOK_AUTH_TOKEN", "tok_test")

        mock_response = MagicMock(status_code=200)
        mock_post     = AsyncMock(return_value=mock_response)

        mock_client_instance = AsyncMock()
        mock_client_instance.post = mock_post
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__  = AsyncMock(return_value=False)

        with patch("v1.integrations.musa_file_processor.httpx.AsyncClient",
                   return_value=mock_client_instance):
            asyncio.run(_send_webhook(
                session_id="test-sid",
                venture_name="Acme",
                venture_country="Kenya",
                status="complete",
                status_url="https://parity.io/status",
                pdf_url="https://parity.io/pdf",
                created_at="2026-01-01T00:00:00+00:00",
                completed_at="2026-01-02T00:00:00+00:00",
            ))

        assert mock_post.called, "httpx.AsyncClient.post was not called"
        call_args = mock_post.call_args
        payload = call_args.kwargs.get("json") or call_args.args[1]

        assert _SESSION_RESPONSE_FIELDS.issubset(payload.keys()), (
            f"Webhook missing fields: {_SESSION_RESPONSE_FIELDS - payload.keys()}"
        )

    def test_webhook_skipped_when_env_vars_missing(self, monkeypatch):
        """No HTTP call when MUSA_WEBHOOK_URL is unset."""
        import asyncio
        from v1.integrations.musa_file_processor import _send_webhook

        monkeypatch.delenv("MUSA_WEBHOOK_URL",        raising=False)
        monkeypatch.delenv("MUSA_WEBHOOK_AUTH_TOKEN", raising=False)

        with patch("v1.integrations.musa_file_processor.httpx.AsyncClient") as MockClient:
            asyncio.run(_send_webhook(
                session_id="sid",
                venture_name="X",
                venture_country="Kenya",
                status="complete",
                status_url="https://example.com/status",
            ))
            MockClient.assert_not_called()


# ===========================================================================
# 7. POST/GET shape parity (structural)
# ===========================================================================

class TestShapeParity:
    """
    The fields returned by POST /sessions and GET /sessions/{id}/status
    must be identical — same keys, same types.
    """

    def test_create_and_status_return_identical_field_sets(self, client, monkeypatch):
        sid = str(uuid.uuid4())
        did = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Patch auth
        monkeypatch.setattr("v1.integrations.auth.validate_api_key", lambda k, p: True)

        # Patch for POST
        monkeypatch.setattr(
            "v1.integrations.musa_api.DealsRepo",
            lambda: MagicMock(create_deal=lambda d: {**d, "id": did}),
        )
        mock_sb_post = MagicMock()
        mock_sb_post.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"session_id": sid, "created_at": now}]
        )
        monkeypatch.setattr("v1.integrations.musa_api.get_supabase", lambda: mock_sb_post)
        monkeypatch.setattr("v1.integrations.musa_api.process_musa_session", lambda **kw: None)

        post_resp = client.post("/api/musa/sessions", json=VALID_SESSION_BODY, headers=VALID_HEADERS)
        assert post_resp.status_code == 200
        post_keys = set(post_resp.json().keys())

        # Patch for GET /status
        mock_sb_get = MagicMock()
        mock_sb_get.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[_fake_session_row(sid, deal_id=did)]
        )
        monkeypatch.setattr("v1.integrations.musa_api.get_supabase", lambda: mock_sb_get)

        get_resp = client.get(f"/api/musa/sessions/{sid}/status", headers=VALID_HEADERS)
        assert get_resp.status_code == 200
        get_keys = set(get_resp.json().keys())

        assert post_keys == get_keys, (
            f"Shape mismatch — POST has {post_keys - get_keys} extra, "
            f"GET has {get_keys - post_keys} extra"
        )
