"""
Admin-only gate on POST /api/musa/admin/sessions/{id}/resend-webhook
(_require_admin_access, musa_api.py; PAR-174 route, PAR-86 fix 2026-10-01).

Before this fix the gate also passed ANY request carrying a verified Supabase
user JWT, so every signed-up client account could trigger webhook resends to
Musa. The JWT branch is gone; the only accepted credential is an
admin-scoped x-api-key (what the admin app's proxy sends):
  - admin-scoped x-api-key                 -> allowed
  - verified JWT of a normal client user   -> 401
  - valid Musa partner key                 -> 401
  - no credential / unknown key            -> 401
Every rejected case also asserts the resend itself never ran.

Run:
    cd backend && python3 -m pytest tests_v1/test_musa_admin_resend_auth.py -v
"""
import os
import sys
import unittest
from unittest.mock import patch

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_ROOT = os.path.abspath(os.path.join(_BACKEND, os.pardir))
for p in (_BACKEND, _ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.v1.integrations import musa_api
from tests_v1.jwt_test_utils import PUBLIC_JWKS, bearer

ADMIN_KEY = "admin-real-key"
MUSA_KEY = "musa-real-key"
URL = "/api/musa/admin/sessions/sid-1/resend-webhook"


def _scoped(key, key_type):
    return key_type == "admin" and key == ADMIN_KEY


def _partner(key, partner):
    return partner == "Musa Ventures" and key == MUSA_KEY


class TestAdminResendWebhookGate(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(musa_api.router)
        self.client = TestClient(app)
        self.resend_calls = []

        async def _fake_resend(session_id, base_url=None):
            self.resend_calls.append(session_id)
            return {
                "session_id": session_id,
                "status": "complete",
                "is_retry": True,
                "resend_count": 1,
                "webhook_status_code": 200,
                "webhook_delivered": True,
            }

        for p in (
            # JWTs are genuinely signed and verified: this is a real, valid
            # client session, not a forged token.
            patch("backend.v1.api._get_jwks", return_value=PUBLIC_JWKS),
            # musa_api binds validate_scoped_api_key at import, so patch it there.
            patch("backend.v1.integrations.musa_api.validate_scoped_api_key", _scoped),
            patch("backend.v1.integrations.auth.validate_scoped_api_key", _scoped),
            patch("backend.v1.integrations.auth.validate_api_key", _partner),
            patch("backend.v1.integrations.musa_api.resend_webhook_for_session", _fake_resend),
        ):
            p.start()
            self.addCleanup(p.stop)

    def test_admin_api_key_passes(self):
        resp = self.client.post(URL, headers={"x-api-key": ADMIN_KEY})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["session_id"], "sid-1")
        self.assertEqual(self.resend_calls, ["sid-1"])

    def test_non_admin_jwt_gets_401(self):
        resp = self.client.post(URL, headers=bearer("ordinary-client-user"))
        self.assertEqual(resp.status_code, 401, resp.text)
        self.assertEqual(self.resend_calls, [])

    def test_musa_partner_key_gets_401(self):
        # Sanity: the key really is a valid Musa partner key.
        self.assertTrue(_partner(MUSA_KEY, "Musa Ventures"))
        resp = self.client.post(URL, headers={"x-api-key": MUSA_KEY})
        self.assertEqual(resp.status_code, 401, resp.text)
        self.assertEqual(self.resend_calls, [])

    def test_jwt_plus_non_admin_key_gets_401(self):
        headers = {**bearer("ordinary-client-user"), "x-api-key": MUSA_KEY}
        resp = self.client.post(URL, headers=headers)
        self.assertEqual(resp.status_code, 401, resp.text)
        self.assertEqual(self.resend_calls, [])

    def test_no_credential_gets_401(self):
        resp = self.client.post(URL)
        self.assertEqual(resp.status_code, 401, resp.text)
        self.assertEqual(self.resend_calls, [])


if __name__ == "__main__":
    unittest.main()
