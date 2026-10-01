"""
Parser-request lifecycle (migration 046) -- backend writers.

* POST /v1/api/request-parser (GBFund's audited-financials failure path) now
  writes `pds_parser_requests`, never `parser_requests`.
* PATCH /v1/deals/{id}/pds-parser-requests/{rid} (deal-page modal enrich) no
  longer writes status='pending'; submission goes to submitted_at, and the
  account's contact email is captured for the resolve notification.
"""
import os
import sys
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_ROOT = os.path.abspath(os.path.join(_BACKEND, os.pardir))
for p in (_BACKEND, _ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.v1.api import router as v1_router
from backend.v1.db.memory_repositories import build_memory_repos
from backend.v1.parser_request_fields import build_enrich_fields, build_partner_api_row

ALLOWED_STATUSES = {"new", "in_progress", "testing", "resolved"}
USER = "11111111-1111-1111-1111-111111111111"


def _make_app():
    repos = build_memory_repos()
    app = FastAPI()
    app.state.repos_factory = lambda: repos
    app.include_router(v1_router)
    return app, repos


def _no_lookup(_user_id):
    return None


class TestGbfundRouteWritesPdsTable(unittest.TestCase):
    def setUp(self):
        self.app, self.repos = _make_app()
        self.client = TestClient(self.app)

    def test_writes_pds_parser_requests_not_parser_requests(self):
        with patch("backend.v1.api._extract_user_id_from_request", return_value=None):
            res = self.client.post(
                "/v1/api/request-parser",
                json={"bank_name": "Stanbic", "market": "KE", "deal_id": "deal-9",
                      "document_url": "https://example.test/af.pdf"},
            )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"status": "received"})
        rows = self.repos["pds_parser_requests"].all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(self.repos["parser_requests"]._store, [])
        row = rows[0]
        self.assertEqual(row["status"], "new")
        self.assertEqual(row["bank_name"], "Stanbic")
        self.assertEqual(row["country"], "KE")
        self.assertEqual(row["deal_id"], "deal-9")
        self.assertIn("Partner: gbfund", row["notes"])
        self.assertIn("Document URL: https://example.test/af.pdf", row["notes"])
        self.assertTrue(row["submitted_at"])
        self.assertNotIn("created_by", row)

    def test_attributes_and_captures_account_email_when_caller_verified(self):
        self.repos["pds_parser_requests"].account_emails[USER] = "owner@client.test"
        with patch("backend.v1.api._extract_user_id_from_request", return_value=USER):
            self.client.post("/v1/api/request-parser", json={"bank_name": "Stanbic"})
        row = self.repos["pds_parser_requests"].all()[0]
        self.assertEqual(row["created_by"], USER)
        self.assertEqual(row["contact_email"], "owner@client.test")

    def test_never_writes_a_status_outside_the_vocabulary(self):
        row = build_partner_api_row({"partner": "gbfund", "status": "pending"}, None, _no_lookup)
        self.assertIn(row["status"], ALLOWED_STATUSES)


class TestPdsEnrichNoLongerWritesPending(unittest.TestCase):
    def setUp(self):
        self.app, self.repos = _make_app()
        self.client = TestClient(self.app)
        self.repos["deals"].create_deal({"id": "deal-1", "company_name": "Buildex"})
        self.row = self.repos["pds_parser_requests"].insert(
            {"deal_id": "deal-1", "document_id": "doc-1", "bank_name": None, "status": "new"}
        )

    def _patch(self, body, user=None):
        with patch("backend.v1.api._extract_user_id_from_request", return_value=user):
            return self.client.patch(
                f"/v1/deals/deal-1/pds-parser-requests/{self.row['id']}", json=body
            )

    def test_status_stays_new_and_submitted_at_is_set(self):
        res = self._patch({"bank_name": "SBM Bank", "country": "KE"})
        self.assertEqual(res.status_code, 200)
        updated = res.json()["parser_request"]
        self.assertEqual(updated["status"], "new")
        self.assertEqual(updated["bank_name"], "SBM Bank")
        self.assertTrue(updated["submitted_at"])

    def test_backfills_owner_and_contact_email_from_verified_caller(self):
        self.repos["pds_parser_requests"].account_emails[USER] = "owner@client.test"
        updated = self._patch({"bank_name": "SBM Bank"}, user=USER).json()["parser_request"]
        self.assertEqual(updated["created_by"], USER)
        self.assertEqual(updated["contact_email"], "owner@client.test")

    def test_404_for_request_on_another_deal(self):
        self.repos["deals"].create_deal({"id": "deal-2", "company_name": "Other"})
        with patch("backend.v1.api._extract_user_id_from_request", return_value=None):
            res = self.client.patch(
                f"/v1/deals/deal-2/pds-parser-requests/{self.row['id']}", json={"bank_name": "X"}
            )
        self.assertEqual(res.status_code, 404)


class TestBuildEnrichFields(unittest.TestCase):
    def test_does_not_overwrite_existing_submission_or_contact(self):
        existing = {"submitted_at": "2026-09-01T00:00:00Z", "contact_email": "typed@client.test",
                    "created_by": USER}
        fields = build_enrich_fields(existing, {"bank_name": "KCB"}, None, lambda _: "login@client.test")
        self.assertNotIn("submitted_at", fields)
        self.assertNotIn("contact_email", fields)
        self.assertNotIn("status", fields)

    def test_typed_contact_email_wins_over_account_email(self):
        fields = build_enrich_fields({"created_by": USER}, {"contact_email": " typed@client.test "},
                                     None, lambda _: "login@client.test")
        self.assertEqual(fields["contact_email"], "typed@client.test")

    def test_never_overwrites_existing_owner(self):
        fields = build_enrich_fields({"created_by": "someone-else"}, {}, USER, _no_lookup)
        self.assertNotIn("created_by", fields)


if __name__ == "__main__":
    unittest.main()
