"""
Pilot onboarding smoke flow (no UI, in-memory repos).
Scenarios:
- Happy path CSV ingest → export → idempotent re-export.
- Currency mismatch rejection.
- Invalid schema rejection (CSV & XLSX-equivalent via CSV headers).
- Transfer ambiguity edge (no pairing when 2 candidates).
- Override apply/revert dual-hash semantics.
"""

import io
import os
import sys
import unittest
from typing import Dict

from fastapi import FastAPI
from fastapi.testclient import TestClient

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_ROOT = os.path.abspath(os.path.join(_BACKEND, os.pardir))
for p in (_BACKEND, _ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.v1.api import router as v1_router
from backend.v1.db.memory_repositories import build_memory_repos


def _make_app():
    repos = build_memory_repos()
    app = FastAPI()
    app.state.repos_factory = lambda: repos
    app.include_router(v1_router)
    return app, repos


VALID_CSV = """date,amount,description,account_id
2024-01-01,1000,Revenue,ACC-1
2024-01-02,-400,Supplier,ACC-1
"""

TRANSFER_AMBIGUOUS_CSV = """date,amount,description,account_id
2024-01-10,-500,Wire Out,ACC-A
2024-01-11,500,Wire In X,ACC-B
2024-01-11,500,Wire In Y,ACC-C
"""

CURRENCY_MISMATCH_CSV = """date,amount,description,account_id
2024-01-01,EUR 100.00,Payment,ACC-1
"""

INVALID_SCHEMA_CSV = """date,amount,account_id
2024-01-01,100,ACC-1
"""


class TestPilotOnboardingFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.repos = _make_app()
        cls.client = TestClient(cls.app)

    def _new_deal(self, currency="USD") -> Dict:
        resp = self.client.post("/v1/deals", data={"currency": currency})
        self.assertEqual(resp.status_code, 200)
        return resp.json()["deal"]

    def test_scenario1_happy_path(self):
        deal = self._new_deal()
        deal_id = deal["id"]

        # Upload document
        f = io.BytesIO(VALID_CSV.encode())
        up = self.client.post(
            f"/v1/deals/{deal_id}/documents",
            files={"file": ("happy.csv", f, "text/csv")},
        )
        self.assertEqual(up.status_code, 200)
        doc_id = up.json()["ingestion"]["document_id"]

        # Document status
        status = self.client.get(f"/v1/documents/{doc_id}/status")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["status"], "completed")

        # Transactions
        tx_resp = self.client.get(f"/v1/documents/{doc_id}/transactions")
        self.assertEqual(tx_resp.status_code, 200)
        txs = tx_resp.json()["transactions"]
        self.assertTrue(all(isinstance(t["signed_amount_cents"], int) for t in txs))

        # Latest analysis (seeded by ingest)
        latest = self.client.get(f"/v1/deals/{deal_id}/analysis/latest")
        self.assertEqual(latest.status_code, 200)
        self.assertIsNotNone(latest.json()["analysis_run"])

        # Export + idempotent re-export
        exp1 = self.client.post(f"/v1/deals/{deal_id}/export")
        self.assertEqual(exp1.status_code, 200)
        snap1 = exp1.json()["snapshot"]
        exp2 = self.client.post(f"/v1/deals/{deal_id}/export")
        self.assertEqual(exp2.status_code, 200)
        snap2 = exp2.json()["snapshot"]
        self.assertEqual(snap1["id"], snap2["id"])
        self.assertIsNotNone(snap1["financial_state_hash"])
        self.assertIsNotNone(snap1["sha256_hash"])

        # Metrics endpoint reflects last export
        metrics = self.client.get("/v1/system/metrics")
        self.assertEqual(metrics.status_code, 200)
        body = metrics.json()
        self.assertIn("schema_version", body)
        self.assertIn("config_version", body)

    def test_scenario2_currency_mismatch(self):
        deal = self._new_deal("USD")
        deal_id = deal["id"]
        f = io.BytesIO(CURRENCY_MISMATCH_CSV.encode())
        resp = self.client.post(
            f"/v1/deals/{deal_id}/documents",
            files={"file": ("mismatch.csv", f, "text/csv")},
        )
        self.assertEqual(resp.status_code, 200)
        doc_id = resp.json()["ingestion"]["document_id"]
        # Background processing sets status=failed for currency mismatch
        status = self.client.get(f"/v1/documents/{doc_id}/status")
        self.assertEqual(status.json()["status"], "failed")
        self.assertTrue(status.json().get("currency_mismatch", False))
        # Ensure no raw transactions written
        self.assertEqual(len(self.repos["raw"].list_by_deal(deal_id)), 0)

    def test_scenario3_invalid_schema(self):
        deal = self._new_deal("USD")
        deal_id = deal["id"]
        f = io.BytesIO(INVALID_SCHEMA_CSV.encode())
        resp = self.client.post(
            f"/v1/deals/{deal_id}/documents",
            files={"file": ("invalid.csv", f, "text/csv")},
        )
        self.assertEqual(resp.status_code, 200)
        doc_id = resp.json()["ingestion"]["document_id"]
        # Background processing sets status=failed for invalid schema
        status = self.client.get(f"/v1/documents/{doc_id}/status")
        self.assertEqual(status.json()["status"], "failed")
        # Ensure no raw transactions written
        self.assertEqual(len(self.repos["raw"].list_by_deal(deal_id)), 0)

    def test_scenario4_transfer_ambiguity(self):
        deal = self._new_deal("USD")
        deal_id = deal["id"]
        f = io.BytesIO(TRANSFER_AMBIGUOUS_CSV.encode())
        up = self.client.post(
            f"/v1/deals/{deal_id}/documents",
            files={"file": ("xfer.csv", f, "text/csv")},
        )
        self.assertEqual(up.status_code, 200)
        exp = self.client.post(f"/v1/deals/{deal_id}/export")
        self.assertEqual(exp.status_code, 200)
        # Ambiguous transfer must yield zero links
        self.assertEqual(len(self.repos["links"].list_by_deal(deal_id)), 0)

    def test_scenario5_override_flow_dual_hash(self):
        deal = self._new_deal("USD")
        deal_id = deal["id"]
        f = io.BytesIO(VALID_CSV.encode())
        self.client.post(
            f"/v1/deals/{deal_id}/documents",
            files={"file": ("ov.csv", f, "text/csv")},
        )

        exp_a = self.client.post(f"/v1/deals/{deal_id}/export")
        snap_a = exp_a.json()["snapshot"]
        sha_a, fin_a = snap_a["sha256_hash"], snap_a["financial_state_hash"]

        entities = self.repos["entities"].list_by_deal(deal_id)
        self.assertGreater(len(entities), 0)
        entity_id = entities[0]["entity_id"]

        self.client.post(
            f"/v1/deals/{deal_id}/overrides",
            data={"entity_id": entity_id, "weight": 1.0, "new_value": "payroll"},
        )
        exp_b = self.client.post(f"/v1/deals/{deal_id}/export")
        snap_b = exp_b.json()["snapshot"]
        sha_b, fin_b = snap_b["sha256_hash"], snap_b["financial_state_hash"]

        self.assertNotEqual(fin_a, fin_b)
        self.assertNotEqual(sha_a, sha_b)

        self.client.post(
            f"/v1/deals/{deal_id}/overrides",
            data={"entity_id": entity_id, "weight": 0.0, "new_value": "payroll"},
        )
        exp_c = self.client.post(f"/v1/deals/{deal_id}/export")
        snap_c = exp_c.json()["snapshot"]
        sha_c, fin_c = snap_c["sha256_hash"], snap_c["financial_state_hash"]

        self.assertEqual(fin_c, fin_a)
        self.assertNotEqual(sha_c, sha_a)
        # Idempotent on latest state
        exp_d = self.client.post(f"/v1/deals/{deal_id}/export")
        self.assertEqual(exp_d.json()["snapshot"]["id"], snap_c["id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
