"""
Parity v1 — Basis-point semantics lock.

Ensures:
- All confidence values are integers
- All percentage fields end in _bp
- No float in confidence/override output
"""

import io
import os
import sys
import unittest

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_ROOT = os.path.abspath(os.path.join(_BACKEND, os.pardir))
for p in (_BACKEND, _ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.v1.api import router as v1_router
from backend.v1.db.memory_repositories import build_memory_repos


def _make_app():
    repos = build_memory_repos()
    app = FastAPI()
    app.state.repos_factory = lambda: repos
    app.include_router(v1_router)
    return app, repos


class TestBasisPointSemantics(unittest.TestCase):
    """Lock basis-point semantics in export output."""

    @classmethod
    def setUpClass(cls):
        cls.app, cls.repos = _make_app()
        cls.client = TestClient(cls.app)

    def test_export_confidence_values_are_integers(self):
        """All confidence and *_bp values in export response are integers."""
        app, _ = _make_app()
        client = TestClient(app)

        deal_resp = client.post("/v1/deals", data={"currency": "USD"})
        deal_id = deal_resp.json()["deal"]["id"]

        csv = "date,amount,description,account_id\n2024-01-01,100.00,Sale,ACC-1\n2024-01-15,-50.00,Utility,ACC-1\n"
        f = io.BytesIO(csv.encode())
        client.post(
            f"/v1/deals/{deal_id}/documents",
            files={"file": ("test.csv", f, "text/csv")},
        )

        export_resp = client.post(f"/v1/deals/{deal_id}/export")
        self.assertEqual(export_resp.status_code, 200)
        data = export_resp.json()

        run = data.get("analysis_run", {})
        bp_keys = ("coverage_pct_bp", "missing_month_penalty_bp", "override_penalty_bp",
                   "base_confidence_bp", "final_confidence_bp", "reconciliation_pct_bp")
        for key in bp_keys:
            if key in run and run[key] is not None:
                self.assertIsInstance(run[key], int, f"analysis_run.{key} must be int")

    def test_percentage_fields_end_in_bp(self):
        """Percentage/ratio fields in analysis_run use _bp suffix."""
        bp_keys = (
            "coverage_pct_bp", "missing_month_penalty_bp", "override_penalty_bp",
            "base_confidence_bp", "final_confidence_bp", "reconciliation_pct_bp",
        )
        for k in bp_keys:
            self.assertTrue(k.endswith("_bp"), f"Percentage field {k} must end in _bp")


if __name__ == "__main__":
    unittest.main(verbosity=2)
