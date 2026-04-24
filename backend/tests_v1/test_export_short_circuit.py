"""
Regression test: export short-circuit when state unchanged.
Ensures second export returns existing snapshot without running pipeline.
"""

import io
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

from backend.v1.api import router as v1_router
from backend.v1.db.memory_repositories import build_memory_repos
from backend.v1.core.pipeline import run_pipeline

VALID_CSV = """date,amount,description,account_id
2024-01-01,1000,Revenue,ACC-1
2024-01-02,-400,Supplier,ACC-1
"""


class TestExportShortCircuit(unittest.TestCase):
    """Export short-circuit: second export must not run pipeline."""

    def setUp(self):
        self.repos = build_memory_repos()
        self.app = FastAPI()
        self.app.state.repos_factory = lambda: self.repos
        self.app.include_router(v1_router)
        self.client = TestClient(self.app)

    def test_export_twice_same_snapshot_no_second_pipeline_call(self):
        """Upload, export twice; second export returns same snapshot, pipeline called once."""
        pipeline_call_count = 0

        def counting_run_pipeline(*args, **kwargs):
            nonlocal pipeline_call_count
            pipeline_call_count += 1
            return run_pipeline(*args, **kwargs)

        with patch("backend.v1.api.run_pipeline", side_effect=counting_run_pipeline):
            deal_resp = self.client.post("/v1/deals", data={"currency": "USD"})
            self.assertEqual(deal_resp.status_code, 200)
            deal_id = deal_resp.json()["deal"]["id"]

            up = self.client.post(
                f"/v1/deals/{deal_id}/documents",
                files={"file": ("test.csv", io.BytesIO(VALID_CSV.encode()), "text/csv")},
            )
            self.assertEqual(up.status_code, 200)
            doc_id = up.json()["ingestion"]["document_id"]

            status = self.client.get(f"/v1/documents/{doc_id}/status")
            self.assertEqual(status.json()["status"], "completed")

            exp1 = self.client.post(f"/v1/deals/{deal_id}/export")
            self.assertEqual(exp1.status_code, 200)
            snap1 = exp1.json()["snapshot"]
            snapshot_id_1 = snap1["id"]

            exp2 = self.client.post(f"/v1/deals/{deal_id}/export")
            self.assertEqual(exp2.status_code, 200)
            snap2 = exp2.json()["snapshot"]
            snapshot_id_2 = snap2["id"]

            self.assertEqual(snapshot_id_1, snapshot_id_2, "Second export must return same snapshot")
            self.assertEqual(
                pipeline_call_count,
                1,
                f"Pipeline must run exactly once for two exports (short-circuit on second). Got {pipeline_call_count}",
            )

    def test_override_forces_pipeline_rerun(self):
        """After adding override, export must run pipeline (no short-circuit)."""
        pipeline_call_count = 0

        def counting_run_pipeline(*args, **kwargs):
            nonlocal pipeline_call_count
            pipeline_call_count += 1
            return run_pipeline(*args, **kwargs)

        with patch("backend.v1.api.run_pipeline", side_effect=counting_run_pipeline):
            deal_resp = self.client.post("/v1/deals", data={"currency": "USD"})
            self.assertEqual(deal_resp.status_code, 200)
            deal_id = deal_resp.json()["deal"]["id"]

            up = self.client.post(
                f"/v1/deals/{deal_id}/documents",
                files={"file": ("test.csv", io.BytesIO(VALID_CSV.encode()), "text/csv")},
            )
            self.assertEqual(up.status_code, 200)
            doc_id = up.json()["ingestion"]["document_id"]
            status = self.client.get(f"/v1/documents/{doc_id}/status")
            self.assertEqual(status.json()["status"], "completed")

            exp1 = self.client.post(f"/v1/deals/{deal_id}/export")
            self.assertEqual(exp1.status_code, 200)
            entities = exp1.json()["entities"]
            self.assertGreater(len(entities), 0)
            entity_id = entities[0]["entity_id"]

            self.client.post(
                f"/v1/deals/{deal_id}/overrides",
                data={"entity_id": entity_id, "new_value": "payroll"},
            )

            exp2 = self.client.post(f"/v1/deals/{deal_id}/export")
            self.assertEqual(exp2.status_code, 200)
            self.assertNotEqual(exp1.json()["snapshot"]["id"], exp2.json()["snapshot"]["id"])

            self.assertEqual(
                pipeline_call_count,
                2,
                f"Pipeline must run twice (export, then export after override). Got {pipeline_call_count}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
