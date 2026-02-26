"""
Phase 3 — Determinism & performance stress harness (CI-safe).

All tests use in-memory repositories via FastAPI TestClient.
No Supabase, no network, no flaky dependencies.
"""

import ast
import copy
import io
import json
import os
import random
import sys
import time
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
from backend.v1.core.pipeline import run_pipeline
from backend.v1.core.snapshot_engine import build_pds_payload, canonicalize_payload
from backend.v1.parsing.common import canonical_hash, normalize_descriptor

import hashlib
import uuid
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def _make_app():
    repos = build_memory_repos()
    app = FastAPI()
    app.state.repos_factory = lambda: repos
    app.include_router(v1_router)
    return app, repos


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _csv_rows(n: int, seed: int = 42, accounts: int = 2) -> str:
    """Generate a deterministic CSV with n rows."""
    rng = random.Random(seed)
    lines = ["date,amount,description,account_id"]
    for i in range(n):
        month = (i % 12) + 1
        day = (i % 28) + 1
        amt = rng.randint(1, 99999) / 100.0
        sign = rng.choice([1, -1])
        amt_str = f"{sign * amt:.2f}"
        acc = f"ACC-{(i % accounts) + 1}"
        lines.append(f"2024-{month:02d}-{day:02d},{amt_str},Txn {i:04d},{acc}")
    return "\n".join(lines) + "\n"


FIXTURE_CSV = _csv_rows(20)
MEDIUM_CSV = _csv_rows(500)

def _txn(date, cents, desc, account="A", txn_id=None, deal_id="d-test"):
    tid = txn_id or hashlib.sha256(f"{date}|{account}|{cents}|{desc}".encode()).hexdigest()
    return {
        "id": str(uuid.uuid4()),
        "txn_date": date,
        "signed_amount_cents": cents,
        "abs_amount_cents": abs(cents),
        "raw_descriptor": desc,
        "parsed_descriptor": desc.strip(),
        "normalized_descriptor": normalize_descriptor(desc),
        "account_id": account,
        "is_transfer": False,
        "txn_id": tid,
        "deal_id": deal_id,
    }


# ===================================================================
# 3.1 — Hash invariance under shuffle (via API)
# ===================================================================

class TestHashInvarianceAPI(unittest.TestCase):
    """Re-export the same deal → same hashes.
    Note: txn_id is derived from document_id, so different uploads to
    different deals produce different txn_ids (by design).
    Row-order invariance is validated at the parser level (test_parsers.py)
    and pipeline level (test_determinism_stress.py)."""

    def test_reexport_invariance(self):
        app, repos = _make_app()
        client = TestClient(app)

        deal_resp = client.post("/v1/deals", data={"currency": "USD"})
        deal_id = deal_resp.json()["deal"]["id"]

        f1 = io.BytesIO(FIXTURE_CSV.encode())
        client.post(f"/v1/deals/{deal_id}/documents", files={"file": ("a.csv", f1, "text/csv")})

        resp_a = client.post(f"/v1/deals/{deal_id}/export")
        self.assertEqual(resp_a.status_code, 200)
        sha_a = resp_a.json()["snapshot"]["sha256_hash"]
        conf_a = resp_a.json()["analysis_run"]["final_confidence_bp"]
        raw_hash_a = resp_a.json()["analysis_run"]["raw_transaction_hash"]

        resp_b = client.post(f"/v1/deals/{deal_id}/export")
        self.assertEqual(resp_b.status_code, 200)
        sha_b = resp_b.json()["snapshot"]["sha256_hash"]
        conf_b = resp_b.json()["analysis_run"]["final_confidence_bp"]
        raw_hash_b = resp_b.json()["analysis_run"]["raw_transaction_hash"]

        self.assertEqual(raw_hash_a, raw_hash_b, "raw_transaction_hash must be stable across re-exports")
        self.assertEqual(conf_a, conf_b, "final_confidence_bp must be stable across re-exports")
        self.assertEqual(sha_a, sha_b, "snapshot sha256_hash must be stable across re-exports")


# ===================================================================
# 3.2 — Export idempotency
# ===================================================================

class TestExportIdempotency(unittest.TestCase):
    """Export twice with no changes → same snapshot id and sha256."""

    def test_idempotent_export(self):
        app, _ = _make_app()
        client = TestClient(app)

        deal_resp = client.post("/v1/deals", data={"currency": "USD"})
        deal_id = deal_resp.json()["deal"]["id"]

        f = io.BytesIO(FIXTURE_CSV.encode())
        client.post(f"/v1/deals/{deal_id}/documents", files={"file": ("a.csv", f, "text/csv")})

        resp1 = client.post(f"/v1/deals/{deal_id}/export")
        resp2 = client.post(f"/v1/deals/{deal_id}/export")

        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp2.status_code, 200)

        snap1 = resp1.json()["snapshot"]
        snap2 = resp2.json()["snapshot"]

        self.assertEqual(snap1["sha256_hash"], snap2["sha256_hash"], "Idempotent export must produce same hash")
        self.assertEqual(snap1["id"], snap2["id"], "Idempotent export must return same snapshot id")


# ===================================================================
# 3.3 — Override causes new snapshot
# ===================================================================

class TestOverrideCausesNewSnapshot(unittest.TestCase):
    """Apply override → export → new sha256, old snapshot unchanged."""

    def test_override_new_hash(self):
        app, repos = _make_app()
        client = TestClient(app)

        deal_resp = client.post("/v1/deals", data={"currency": "USD"})
        deal_id = deal_resp.json()["deal"]["id"]

        f = io.BytesIO(FIXTURE_CSV.encode())
        client.post(f"/v1/deals/{deal_id}/documents", files={"file": ("a.csv", f, "text/csv")})

        # Export A
        resp_a = client.post(f"/v1/deals/{deal_id}/export")
        snap_a = resp_a.json()["snapshot"]

        # Get entities for override target
        entities = repos["entities"].list_by_deal(deal_id)
        self.assertTrue(len(entities) > 0, "Should have entities after export")
        entity_id = entities[0]["entity_id"]

        # Add override
        client.post(
            f"/v1/deals/{deal_id}/overrides",
            data={"entity_id": entity_id, "weight": "0.5", "new_value": "supplier"},
        )

        # Export B
        resp_b = client.post(f"/v1/deals/{deal_id}/export")
        snap_b = resp_b.json()["snapshot"]

        self.assertNotEqual(snap_a["sha256_hash"], snap_b["sha256_hash"], "Override must change snapshot hash")
        self.assertNotEqual(snap_a["id"], snap_b["id"], "Override must produce new snapshot id")

        # Verify old snapshot unchanged
        old_snap = repos["snapshots"].get_snapshot(snap_a["id"])
        self.assertEqual(old_snap["sha256_hash"], snap_a["sha256_hash"])


# ===================================================================
# 3.4 — Edge invariants
# ===================================================================

class TestEdgeInvariants(unittest.TestCase):
    """Zero-denominator, transfer multi-match, overlap checks."""

    def test_denom_zero_via_pipeline(self):
        run, links, _, _ = run_pipeline(
            deal_id="d-zero",
            raw_transactions=[],
            overrides=[],
            accrual={},
        )
        self.assertEqual(run["coverage_pct_bp"], 0)
        self.assertEqual(run["reconciliation_status"], "NOT_RUN")
        self.assertEqual(run["tier"], "Low")
        self.assertEqual(run["final_confidence_bp"], 0)

    def test_transfer_multi_match_zero_links(self):
        txs = [
            _txn("2024-01-10", -50000, "Out", "A", txn_id="out1"),
            _txn("2024-01-11", 50000, "In X", "B", txn_id="in1"),
            _txn("2024-01-11", 50000, "In Y", "C", txn_id="in2"),
        ]
        run, links, _, _ = run_pipeline(
            deal_id="d-multi",
            raw_transactions=txs,
            overrides=[],
            accrual={},
        )
        self.assertEqual(len(links), 0)
        for tx in txs:
            self.assertFalse(tx.get("is_transfer", False))

    def test_overlap_failed_caps_tier(self):
        txs = [_txn("2024-01-01", 10000, "rev", "A", txn_id="t1")]
        accrual = {
            "accrual_revenue_cents": 10000,
            "accrual_period_start": "2024-06-01",
            "accrual_period_end": "2024-06-30",
        }
        run, _, _, _ = run_pipeline(
            deal_id="d-overlap",
            raw_transactions=txs,
            overrides=[],
            accrual=accrual,
        )
        self.assertEqual(run["reconciliation_status"], "FAILED_OVERLAP")
        self.assertIn(run["tier"], ["Low", "Medium"])


# ===================================================================
# 3.5 — No floats in v1 core
# ===================================================================

class TestNoFloatsInCore(unittest.TestCase):
    """AST scan: no float() in money pipeline files."""

    V1_CORE = os.path.join(_BACKEND, "v1", "core")
    MONEY_FILES = [
        "metrics_engine.py", "pipeline.py", "snapshot_engine.py",
        "transfer_matcher.py", "entities.py", "classifier.py",
    ]

    def test_no_float_calls(self):
        violations = []
        for fname in self.MONEY_FILES:
            fpath = os.path.join(self.V1_CORE, fname)
            if not os.path.exists(fpath):
                continue
            with open(fpath, "r") as f:
                source = f.read()
            try:
                tree = ast.parse(source, filename=fpath)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "float":
                    violations.append(f"{fname}:{node.lineno}")
        self.assertEqual(violations, [], f"float() calls found: {violations}")


# ===================================================================
# 3.6 — Micro performance test (non-flaky)
# ===================================================================

class TestPerformance(unittest.TestCase):
    """Parse + export 500-txn fixture under 5 seconds."""

    THRESHOLD_SECONDS = 5.0

    def test_medium_fixture_latency(self):
        app, _ = _make_app()
        client = TestClient(app)

        deal_resp = client.post("/v1/deals", data={"currency": "USD"})
        deal_id = deal_resp.json()["deal"]["id"]

        start = time.monotonic()
        f = io.BytesIO(MEDIUM_CSV.encode())
        upload_resp = client.post(
            f"/v1/deals/{deal_id}/documents",
            files={"file": ("medium.csv", f, "text/csv")},
        )
        self.assertEqual(upload_resp.status_code, 200)

        export_resp = client.post(f"/v1/deals/{deal_id}/export")
        self.assertEqual(export_resp.status_code, 200)
        elapsed = time.monotonic() - start

        self.assertLess(
            elapsed,
            self.THRESHOLD_SECONDS,
            f"Parse + export of 500 txns took {elapsed:.2f}s (limit: {self.THRESHOLD_SECONDS}s)",
        )


# ===================================================================
# 3.7 — Hash stability under pure pipeline (no API)
# ===================================================================

class TestPipelineHashStability(unittest.TestCase):
    """Run the pipeline 10x with same input → identical hashes every time."""

    @classmethod
    def setUpClass(cls):
        cls._base_fixture = [
            _txn("2024-01-01", 25000, "Alpha Payment", "ACC-1", txn_id="s1"),
            _txn("2024-01-10", -8000, "Utility Bill", "ACC-1", txn_id="s2"),
            _txn("2024-02-01", 50000, "Client X", "ACC-2", txn_id="s3"),
            _txn("2024-02-15", -12000, "Office Rent", "ACC-2", txn_id="s4"),
            _txn("2024-03-01", 30000, "Client Y", "ACC-1", txn_id="s5"),
        ]

    def test_pipeline_stability(self):
        hashes = set()
        confs = set()
        for _ in range(10):
            txs = copy.deepcopy(self._base_fixture)
            run, links, ents, txm = run_pipeline(
                deal_id="d-stable",
                raw_transactions=txs,
                overrides=[],
                accrual={},
            )
            payload = build_pds_payload(
                schema_version="v1", config_version="v1",
                deal_id="d-stable", currency="USD",
                raw_transactions=txs,
                transfer_links=links, entities=ents,
                txn_entity_map=txm,
                metrics={
                    "coverage_bp": run["coverage_pct_bp"],
                    "missing_month_count": run["missing_month_count"],
                    "missing_month_penalty_bp": run["missing_month_penalty_bp"],
                    "reconciliation_status": run["reconciliation_status"],
                    "reconciliation_bp": run["reconciliation_pct_bp"],
                },
                confidence={
                    "final_confidence_bp": run["final_confidence_bp"],
                    "tier": run["tier"],
                    "tier_capped": run["tier_capped"],
                    "override_penalty_bp": run["override_penalty_bp"],
                },
                overrides_applied=[],
            )
            _, sha = canonicalize_payload(payload)
            hashes.add(sha)
            confs.add(run["final_confidence_bp"])

        self.assertEqual(len(hashes), 1, f"Expected 1 unique hash, got {len(hashes)}")
        self.assertEqual(len(confs), 1, f"Expected 1 unique confidence, got {len(confs)}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
