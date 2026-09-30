"""
Auth + ownership gate on GET /v1/deals/{deal_id}/analytics/* (PAR-86, 2026-09-30).

Before this fix all three analytics routes (loan-drawdowns, monthly-cashflow,
credit-scoring-inputs) returned a deal's financial data with HTTP 200 and no
credential at all. The gate (_require_deal_owner, api.py) requires authentication
AND ownership:
  - valid admin-scoped x-api-key            -> allowed (admin panel proxy)
  - verified JWT whose sub owns the deal    -> allowed
  - verified JWT of a DIFFERENT account     -> 404 (same as a missing deal)
  - anything else / no credential           -> 401, checked BEFORE the deal lookup
A Musa partner key is deliberately not accepted.

Also locks the PR #255 disclosure: the gate adds no change to any response.

Run:
    cd backend && python3 -m pytest tests_v1/test_analytics_routes_auth.py -v
"""
import json
import os
import sys
import unittest
import uuid
from unittest.mock import patch

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_ROOT = os.path.abspath(os.path.join(_BACKEND, os.pardir))
for p in (_BACKEND, _ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.v1 import analytics as A
from backend.v1.api import router as v1_router
from backend.v1.db.memory_repositories import build_memory_repos
from tests_v1.jwt_test_utils import PUBLIC_JWKS, bearer, forged_bearer

ADMIN_KEY = "admin-real-key"
MUSA_KEY = "musa-real-key"
OWNER = "owner-user-1"
OTHER = "other-user-2"

ROUTES = ("loan-drawdowns", "monthly-cashflow", "credit-scoring-inputs")

# needs_review + transfer credits so PR #255's excluded-credits disclosure is exercised
_TXNS = [
    {"id": "t1", "txn_date": "2025-03-05", "signed_amount_cents": 5_000_000, "normalized_descriptor": "customer a"},
    {"id": "t2", "txn_date": "2025-03-06", "signed_amount_cents": 3_000_000, "normalized_descriptor": "big unknown credit"},
    {"id": "t3", "txn_date": "2025-03-07", "signed_amount_cents": 700_000, "normalized_descriptor": "own transfer"},
    {"id": "t4", "txn_date": "2025-03-08", "signed_amount_cents": -2_000_000, "normalized_descriptor": "supplier x"},
    {"id": "t5", "txn_date": "2025-04-02", "signed_amount_cents": 1_000_000, "normalized_descriptor": "loan disbursement"},
]
_MAP = [
    {"txn_id": "t1", "role": "revenue_operational", "entity_id": "e1"},
    {"txn_id": "t2", "role": "needs_review", "entity_id": "e2"},
    {"txn_id": "t3", "role": "transfer", "entity_id": "e3"},
    {"txn_id": "t4", "role": "supplier", "entity_id": "e4"},
    {"txn_id": "t5", "role": "loan_inflow", "entity_id": "e5"},
]
_ENT = [{"entity_id": f"e{i}", "display_name": f"Entity {i}"} for i in range(1, 6)]


def _tagged():
    role = {m["txn_id"]: m["role"] for m in _MAP}
    return [{"role": role[t["id"]], "amount_cents": t["signed_amount_cents"],
             "txn_date": t["txn_date"], "txn_id": t["id"]} for t in _TXNS]


class _Base(unittest.TestCase):
    def setUp(self):
        self.repos = build_memory_repos()
        app = FastAPI()
        app.state.repos_factory = lambda: self.repos
        app.include_router(v1_router)
        self.client = TestClient(app)
        for p in (
            patch("backend.v1.api._get_jwks", return_value=PUBLIC_JWKS),
            patch("backend.v1.integrations.auth.validate_api_key",
                  lambda key, partner: partner == "Musa Ventures" and key == MUSA_KEY),
            patch("backend.v1.integrations.auth.validate_scoped_api_key",
                  lambda key, key_type: key_type == "admin" and key == ADMIN_KEY),
        ):
            p.start()
            self.addCleanup(p.stop)

        # A deal owned by OWNER (created through the real route, so user_id comes from the JWT).
        r = self.client.post("/v1/deals", data={"currency": "KES"}, headers=bearer(OWNER))
        self.assertEqual(r.status_code, 200, r.text)
        self.deal = r.json()["deal"]
        self.deal_id = self.deal["id"]
        self.assertEqual(self.deal["user_id"], OWNER)
        self._seal(self.deal_id)

    def _seal(self, deal_id):
        self.repos["snapshots"].insert_snapshot({
            "id": str(uuid.uuid4()), "deal_id": deal_id, "sha256_hash": uuid.uuid4().hex,
            "canonical_json": json.dumps({"transactions": _TXNS, "txn_entity_map": _MAP, "entities": _ENT}),
        })

    def _get(self, route, deal_id=None, headers=None):
        return self.client.get(f"/v1/deals/{deal_id or self.deal_id}/analytics/{route}", headers=headers or {})


class TestAuthenticationRequired(_Base):
    def test_no_credential_returns_401_on_every_analytics_route(self):
        for route in ROUTES:
            with self.subTest(route=route):
                self.assertEqual(self._get(route).status_code, 401)

    def test_no_credential_on_a_nonexistent_deal_is_also_401_not_404(self):
        """Auth is checked before the deal lookup: an unauthenticated caller
        cannot use 401-vs-404 to learn which deal ids exist."""
        ghost = str(uuid.uuid4())
        for route in ROUTES:
            with self.subTest(route=route):
                self.assertEqual(self._get(route, deal_id=ghost).status_code, 401)

    def test_forged_and_wrong_credentials_return_401(self):
        for route in ROUTES:
            with self.subTest(route=route):
                self.assertEqual(self._get(route, headers=forged_bearer(OWNER)).status_code, 401)
                self.assertEqual(self._get(route, headers={"x-api-key": "wrong"}).status_code, 401)
                self.assertEqual(self._get(route, headers={"authorization": "Bearer not-a-jwt"}).status_code, 401)

    def test_musa_partner_key_is_not_accepted(self):
        for route in ROUTES:
            with self.subTest(route=route):
                self.assertEqual(self._get(route, headers={"x-api-key": MUSA_KEY}).status_code, 401)


class TestOwnership(_Base):
    def test_owner_jwt_gets_200_on_every_route(self):
        for route in ROUTES:
            with self.subTest(route=route):
                self.assertEqual(self._get(route, headers=bearer(OWNER)).status_code, 200)

    def test_valid_jwt_of_a_different_account_cannot_read_the_deal(self):
        """A valid token is not enough: OTHER is authenticated but does not own the deal."""
        missing = self._get("monthly-cashflow", deal_id=str(uuid.uuid4()), headers=bearer(OTHER))
        for route in ROUTES:
            with self.subTest(route=route):
                resp = self._get(route, headers=bearer(OTHER))
                self.assertEqual(resp.status_code, 404, resp.text)
                self.assertNotIn("inflow", resp.text)
        # indistinguishable from a deal that does not exist (no existence leak)
        self.assertEqual(self._get("monthly-cashflow", headers=bearer(OTHER)).json()["detail"]["error_code"],
                         missing.json()["detail"]["error_code"])

    def test_admin_key_reads_any_deal(self):
        for route in ROUTES:
            with self.subTest(route=route):
                self.assertEqual(self._get(route, headers={"x-api-key": ADMIN_KEY}).status_code, 200)

    def test_legacy_deal_without_user_id_falls_back_to_created_by(self):
        legacy = self.repos["deals"].create_deal({"id": str(uuid.uuid4()), "currency": "KES", "created_by": OWNER})
        self._seal(legacy["id"])
        self.assertEqual(self._get("monthly-cashflow", legacy["id"], bearer(OWNER)).status_code, 200)
        self.assertEqual(self._get("monthly-cashflow", legacy["id"], bearer(OTHER)).status_code, 404)

    def test_client_supplied_created_by_cannot_grant_access_to_someone_elses_deal(self):
        """created_by is a client form field; user_id (verified JWT) wins. A deal owned
        by OWNER stays unreadable by OTHER even if some row claims created_by=OTHER."""
        row = self.repos["deals"].get_deal(self.deal_id)
        self.assertEqual(row["user_id"], OWNER)
        row["created_by"] = OTHER  # tamper with the untrusted field
        self.assertEqual(self._get("monthly-cashflow", headers=bearer(OTHER)).status_code, 404)
        self.assertEqual(self._get("monthly-cashflow", headers=bearer(OWNER)).status_code, 200)

    def test_deal_with_neither_owner_field_is_unreachable_to_jwt_users(self):
        orphan = self.repos["deals"].create_deal({"id": str(uuid.uuid4()), "currency": "KES"})
        self._seal(orphan["id"])
        self.assertEqual(self._get("monthly-cashflow", orphan["id"], bearer(OWNER)).status_code, 404)


class TestResponseUnchangedByTheGate(_Base):
    """The fix only adds an auth gate; PR #255's response shape and logic are untouched."""

    def test_monthly_cashflow_body_equals_the_ungated_computation(self):
        body = self._get("monthly-cashflow", headers=bearer(OWNER)).json()
        rows, excluded = A.monthly_cashflow(_tagged()), A.monthly_excluded_credits(_tagged())
        self.assertEqual(set(body), {"monthly_cashflow", "count", "excluded_credits",
                                     "excluded_credits_total_cents", "pending_classification_total_cents"})
        self.assertEqual(body["monthly_cashflow"], rows)
        self.assertEqual(body["excluded_credits"], excluded)
        self.assertEqual(body["excluded_credits_total_cents"], 3_700_000)      # needs_review 3.0M + transfer 0.7M
        self.assertEqual(body["pending_classification_total_cents"], 3_000_000)
        self.assertEqual(body["count"], len(rows))
        # PR #255 invariant: inflow + excluded == all credits
        credits = sum(t["signed_amount_cents"] for t in _TXNS if t["signed_amount_cents"] > 0)
        self.assertEqual(sum(r["inflow_cents"] for r in rows) + body["excluded_credits_total_cents"], credits)

    def test_credit_scoring_inputs_body_equals_the_ungated_computation(self):
        body = self._get("credit-scoring-inputs", headers=bearer(OWNER)).json()
        self.assertEqual(body, A.credit_scoring_inputs(_tagged()))

    def test_admin_and_owner_get_identical_bodies(self):
        for route in ROUTES:
            with self.subTest(route=route):
                self.assertEqual(self._get(route, headers=bearer(OWNER)).json(),
                                 self._get(route, headers={"x-api-key": ADMIN_KEY}).json())


if __name__ == "__main__":
    unittest.main()
