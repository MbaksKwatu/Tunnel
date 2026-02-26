"""
Phase 2 + Phase 4 — Runtime response validation against OpenAPI schemas
and error semantics regression tests.

Every v1 endpoint response is validated against the component schemas
defined in docs/openapi/v1.openapi.json.

No Supabase required — uses in-memory repositories via TestClient.
"""

import io
import json
import os
import sys
import unittest

# ---------------------------------------------------------------------------
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_ROOT = os.path.abspath(os.path.join(_BACKEND, os.pardir))
for p in (_BACKEND, _ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jsonschema import validate, ValidationError

from backend.v1.api import router as v1_router
from backend.v1.db.memory_repositories import build_memory_repos

# ---------------------------------------------------------------------------
# Spec loader
# ---------------------------------------------------------------------------
_SPEC_PATH = os.path.join(_ROOT, "docs", "openapi", "v1.openapi.json")


def _load_spec():
    with open(_SPEC_PATH, "r") as f:
        return json.load(f)


_SPEC = _load_spec()
_SCHEMAS = _SPEC["components"]["schemas"]


def _resolve_ref(ref: str):
    """Resolve a $ref like '#/components/schemas/DealResponse'."""
    parts = ref.lstrip("#/").split("/")
    obj = _SPEC
    for part in parts:
        obj = obj[part]
    return obj


def _expand(schema: dict) -> dict:
    """Recursively expand $ref in a schema for jsonschema.validate."""
    if "$ref" in schema:
        return _expand(_resolve_ref(schema["$ref"]))
    out = {}
    for k, v in schema.items():
        if isinstance(v, dict):
            out[k] = _expand(v)
        elif isinstance(v, list):
            out[k] = [_expand(i) if isinstance(i, dict) else i for i in v]
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# App factory for tests
# ---------------------------------------------------------------------------
_REPOS = None


def _make_app():
    global _REPOS
    _REPOS = build_memory_repos()
    app = FastAPI()
    app.state.repos_factory = lambda: _REPOS
    app.include_router(v1_router)
    return app


# ---------------------------------------------------------------------------
# CSV fixture (valid)
# ---------------------------------------------------------------------------
VALID_CSV = "date,amount,description,account_id\n2024-01-01,100.00,Revenue Alpha,ACC-1\n2024-01-15,-50.00,Supplier Beta,ACC-1\n2024-02-01,200.00,Revenue Gamma,ACC-2\n"

INVALID_CSV = "foo,bar\nbaz,qux\n"

CURRENCY_MISMATCH_CSV = "date,amount,description\n2024-01-01,EUR 100.00,Revenue\n"


# ===================================================================
# Contract validation tests
# ===================================================================

class TestContractValidation(unittest.TestCase):
    """Validate every endpoint response against OpenAPI component schemas."""

    @classmethod
    def setUpClass(cls):
        cls.app = _make_app()
        cls.client = TestClient(cls.app)
        # Seed a deal
        resp = cls.client.post("/v1/deals", data={"currency": "USD", "name": "Test Deal"})
        cls.deal = resp.json()["deal"]
        cls.deal_id = cls.deal["id"]
        cls.created_by = cls.deal["created_by"]

    def _validate(self, data, schema_name):
        schema = _expand(_SCHEMAS[schema_name])
        try:
            validate(instance=data, schema=schema)
        except ValidationError as e:
            self.fail(f"Schema validation failed for {schema_name}: {e.message}\nData: {json.dumps(data, indent=2)[:500]}")

    # --- Deals ---

    def test_create_deal_schema(self):
        resp = self.client.post("/v1/deals", data={"currency": "GBP"})
        self.assertEqual(resp.status_code, 200)
        self._validate(resp.json(), "DealResponse")

    def test_list_deals_schema(self):
        resp = self.client.get(f"/v1/deals?created_by={self.created_by}")
        self.assertEqual(resp.status_code, 200)
        self._validate(resp.json(), "DealsListResponse")

    def test_get_deal_schema(self):
        resp = self.client.get(f"/v1/deals/{self.deal_id}")
        self.assertEqual(resp.status_code, 200)
        self._validate(resp.json(), "DealDetailResponse")

    # --- Documents ---

    def test_upload_document_schema(self):
        f = io.BytesIO(VALID_CSV.encode())
        resp = self.client.post(
            f"/v1/deals/{self.deal_id}/documents",
            files={"file": ("test.csv", f, "text/csv")},
        )
        self.assertEqual(resp.status_code, 200)
        self._validate(resp.json(), "IngestionResponse")

    def test_list_documents_schema(self):
        resp = self.client.get(f"/v1/deals/{self.deal_id}/documents")
        self.assertEqual(resp.status_code, 200)
        self._validate(resp.json(), "DocumentsListResponse")

    # --- Overrides ---

    def test_list_overrides_schema(self):
        resp = self.client.get(f"/v1/deals/{self.deal_id}/overrides")
        self.assertEqual(resp.status_code, 200)
        self._validate(resp.json(), "OverridesListResponse")

    # --- Analysis ---

    def test_latest_analysis_null_schema(self):
        """No analysis yet — should return null."""
        deal_resp = self.client.post("/v1/deals", data={"currency": "EUR"})
        did = deal_resp.json()["deal"]["id"]
        resp = self.client.get(f"/v1/deals/{did}/analysis/latest")
        self.assertEqual(resp.status_code, 200)
        self._validate(resp.json(), "LatestAnalysisResponse")
        self.assertIsNone(resp.json()["analysis_run"])

    # --- Export ---

    def test_export_schema(self):
        # Ensure data exists
        f = io.BytesIO(VALID_CSV.encode())
        self.client.post(
            f"/v1/deals/{self.deal_id}/documents",
            files={"file": ("export_test.csv", f, "text/csv")},
        )
        resp = self.client.post(f"/v1/deals/{self.deal_id}/export")
        self.assertEqual(resp.status_code, 200)
        self._validate(resp.json(), "ExportResponse")
        body = resp.json()
        run = body["analysis_run"]
        self.assertIsInstance(run["non_transfer_abs_total_cents"], int)
        self.assertIsInstance(run["final_confidence_bp"], int)
        self.assertIn(run["tier"], ["Low", "Medium", "High"])
        self.assertIn(run["reconciliation_status"], ["NOT_RUN", "OK", "FAILED_OVERLAP"])
        self.assertIn("bank_operational_inflow_cents", run)
        self.assertIsInstance(run["bank_operational_inflow_cents"], int)
        self.assertGreaterEqual(run["bank_operational_inflow_cents"], 0)
        snapshot = body["snapshot"]
        self.assertIn("financial_state_hash", snapshot)
        self.assertIsNotNone(snapshot["financial_state_hash"])

    def test_list_snapshots_schema(self):
        resp = self.client.get(f"/v1/deals/{self.deal_id}/snapshots")
        self.assertEqual(resp.status_code, 200)
        self._validate(resp.json(), "SnapshotsListResponse")

    # --- System Metrics ---

    def test_system_metrics_schema(self):
        resp = self.client.get("/v1/system/metrics")
        self.assertEqual(resp.status_code, 200)
        self._validate(resp.json(), "SystemMetricsResponse")
        body = resp.json()
        self.assertIn("schema_version", body)
        self.assertIn("config_version", body)

    # --- System Health ---

    def test_system_health_schema(self):
        resp = self.client.get("/v1/system/health")
        self.assertEqual(resp.status_code, 200)
        self._validate(resp.json(), "SystemHealthResponse")
        body = resp.json()
        self.assertIs(body["deterministic_mode"], True)
        self.assertIn("schema_version", body)
        self.assertIn("config_version", body)
        extra = set(body.keys()) - {"schema_version", "config_version", "git_commit", "build_timestamp", "deterministic_mode"}
        self.assertEqual(extra, set(), f"Unexpected fields: {extra}")


# ===================================================================
# Dual-hash regression: apply → revert → idempotency
# ===================================================================


class TestDualHashRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = _make_app()
        cls.client = TestClient(cls.app)
        cls.repos = cls.app.state.repos_factory()

    def test_apply_revert_dual_hash(self):
        deal_resp = self.client.post("/v1/deals", data={"currency": "USD"})
        deal_id = deal_resp.json()["deal"]["id"]

        # Upload
        f = io.BytesIO(VALID_CSV.encode())
        self.client.post(
            f"/v1/deals/{deal_id}/documents",
            files={"file": ("dh.csv", f, "text/csv")},
        )

        # Export A
        resp_a = self.client.post(f"/v1/deals/{deal_id}/export")
        snap_a = resp_a.json()["snapshot"]
        sha_a = snap_a["sha256_hash"]
        fin_a = snap_a["financial_state_hash"]

        # Grab an entity_id from repo
        entities = self.repos["entities"].list_by_deal(deal_id)
        self.assertGreater(len(entities), 0)
        entity_id = entities[0]["entity_id"]

        # Apply override
        self.client.post(
            f"/v1/deals/{deal_id}/overrides",
            data={"entity_id": entity_id, "weight": 1.0, "new_value": "payroll"},
        )

        # Export B (after override)
        resp_b = self.client.post(f"/v1/deals/{deal_id}/export")
        snap_b = resp_b.json()["snapshot"]
        sha_b = snap_b["sha256_hash"]
        fin_b = snap_b["financial_state_hash"]

        self.assertNotEqual(fin_a, fin_b)
        self.assertNotEqual(sha_a, sha_b)

        # Revert override (weight=0.0) and export C
        self.client.post(
            f"/v1/deals/{deal_id}/overrides",
            data={"entity_id": entity_id, "weight": 0.0, "new_value": "payroll"},
        )
        resp_c = self.client.post(f"/v1/deals/{deal_id}/export")
        snap_c = resp_c.json()["snapshot"]
        sha_c = snap_c["sha256_hash"]
        fin_c = snap_c["financial_state_hash"]

        self.assertEqual(fin_c, fin_a, "Outcome-only hash should revert after neutralizing override")
        self.assertNotEqual(sha_c, sha_a, "Provenance hash must differ when override history differs")

        # Idempotency: re-export with no changes → same sha/snapshot id as C
        resp_d = self.client.post(f"/v1/deals/{deal_id}/export")
        snap_d = resp_d.json()["snapshot"]
        self.assertEqual(snap_d["id"], snap_c["id"])
        self.assertEqual(snap_d["sha256_hash"], sha_c)

    def test_export_entities_match_snapshot_payload(self):
        """Export response entities and txn_entity_map must exactly match those in canonical_json."""
        deal_resp = self.client.post("/v1/deals", data={"currency": "USD"})
        deal_id = deal_resp.json()["deal"]["id"]
        f = io.BytesIO(VALID_CSV.encode())
        self.client.post(
            f"/v1/deals/{deal_id}/documents",
            files={"file": ("purity.csv", f, "text/csv")},
        )
        resp = self.client.post(f"/v1/deals/{deal_id}/export")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        entities_resp = sorted(body.get("entities", []), key=lambda e: e.get("entity_id", ""))
        txn_map_resp = sorted(body.get("txn_entity_map", []), key=lambda m: m.get("txn_id", ""))
        canonical = json.loads(body["snapshot"]["canonical_json"])
        entities_canon = sorted(canonical.get("entities", []), key=lambda e: e.get("entity_id", ""))
        txn_map_canon = sorted(canonical.get("txn_entity_map", []), key=lambda m: m.get("txn_id", ""))
        self.assertEqual(entities_resp, entities_canon, "Export entities must match snapshot payload")
        self.assertEqual(txn_map_resp, txn_map_canon, "Export txn_entity_map must match snapshot payload")

    def test_override_weight_major_boundary_crossing(self):
        """Override crossing revenue boundary must derive weight=1.0."""
        deal_resp = self.client.post("/v1/deals", data={"currency": "USD"})
        deal_id = deal_resp.json()["deal"]["id"]
        f = io.BytesIO(VALID_CSV.encode())
        self.client.post(
            f"/v1/deals/{deal_id}/documents",
            files={"file": ("major.csv", f, "text/csv")},
        )
        self.client.post(f"/v1/deals/{deal_id}/export")
        entities = self.repos["entities"].list_by_deal(deal_id)
        revenue_entity = next((e for e in entities if "Revenue" in (e.get("display_name") or "")), entities[0])
        entity_id = revenue_entity["entity_id"]
        resp = self.client.post(
            f"/v1/deals/{deal_id}/overrides",
            data={"entity_id": entity_id, "new_value": "supplier"},
        )
        self.assertEqual(resp.status_code, 200)
        ov = resp.json()["override"]
        self.assertEqual(ov["weight"], 1.0, "Revenue->supplier must derive weight=1.0")

    def test_override_weight_minor_transition(self):
        """Override within same boundary (supplier->payroll) must derive weight=0.5."""
        deal_resp = self.client.post("/v1/deals", data={"currency": "USD"})
        deal_id = deal_resp.json()["deal"]["id"]
        f = io.BytesIO(VALID_CSV.encode())
        self.client.post(
            f"/v1/deals/{deal_id}/documents",
            files={"file": ("minor.csv", f, "text/csv")},
        )
        self.client.post(f"/v1/deals/{deal_id}/export")
        entities = self.repos["entities"].list_by_deal(deal_id)
        supplier_entity = next((e for e in entities if "Supplier" in (e.get("display_name") or "")), entities[0])
        entity_id = supplier_entity["entity_id"]
        resp = self.client.post(
            f"/v1/deals/{deal_id}/overrides",
            data={"entity_id": entity_id, "new_value": "payroll"},
        )
        self.assertEqual(resp.status_code, 200)
        ov = resp.json()["override"]
        self.assertEqual(ov["weight"], 0.5, "Supplier->payroll must derive weight=0.5")

    def test_override_weight_is_never_0_unless_revert(self):
        """If new_value != effective_current_role, weight must be in {0.5, 1.0}."""
        deal_resp = self.client.post("/v1/deals", data={"currency": "USD"})
        deal_id = deal_resp.json()["deal"]["id"]
        f = io.BytesIO(VALID_CSV.encode())
        self.client.post(
            f"/v1/deals/{deal_id}/documents",
            files={"file": ("guard.csv", f, "text/csv")},
        )
        self.client.post(f"/v1/deals/{deal_id}/export")
        entities = self.repos["entities"].list_by_deal(deal_id)
        revenue_entity = next((e for e in entities if "Revenue" in (e.get("display_name") or "")), entities[0])
        entity_id = revenue_entity["entity_id"]
        resp = self.client.post(
            f"/v1/deals/{deal_id}/overrides",
            data={"entity_id": entity_id, "new_value": "supplier"},
        )
        self.assertEqual(resp.status_code, 200)
        ov = resp.json()["override"]
        self.assertIn(
            ov["weight"],
            (0.5, 1.0),
            "Non-revert override (revenue->supplier) must derive weight 0.5 or 1.0, never 0.0",
        )


# ===================================================================
# Error semantics regression tests (Phase 4)
# ===================================================================

class TestErrorSemantics(unittest.TestCase):
    """Verify standardised error responses for every error path."""

    @classmethod
    def setUpClass(cls):
        cls.app = _make_app()
        cls.client = TestClient(cls.app)

    def _assert_error(self, resp, expected_code, expected_status):
        self.assertEqual(resp.status_code, expected_status, f"Expected {expected_status}, got {resp.status_code}: {resp.text}")
        body = resp.json()
        if "detail" in body and isinstance(body["detail"], dict):
            detail = body["detail"]
        else:
            detail = body
        self.assertEqual(detail.get("error_code"), expected_code)
        self.assertIn("error_message", detail)
        self.assertIn("next_action", detail)
        self.assertIn("details", detail)

    # --- 404 paths ---

    def test_get_deal_not_found(self):
        resp = self.client.get("/v1/deals/00000000-0000-0000-0000-000000000000")
        self._assert_error(resp, "NOT_FOUND", 404)

    def test_upload_to_missing_deal(self):
        f = io.BytesIO(b"date,amount,description\n2024-01-01,100,X\n")
        resp = self.client.post(
            "/v1/deals/00000000-0000-0000-0000-000000000000/documents",
            files={"file": ("t.csv", f, "text/csv")},
        )
        self._assert_error(resp, "NOT_FOUND", 404)

    def test_export_missing_deal(self):
        resp = self.client.post("/v1/deals/00000000-0000-0000-0000-000000000000/export")
        self._assert_error(resp, "NOT_FOUND", 404)

    def test_snapshot_not_found(self):
        resp = self.client.get("/v1/snapshots/00000000-0000-0000-0000-000000000000")
        self._assert_error(resp, "NOT_FOUND", 404)

    def test_list_overrides_missing_deal(self):
        resp = self.client.get("/v1/deals/00000000-0000-0000-0000-000000000000/overrides")
        self._assert_error(resp, "NOT_FOUND", 404)

    # --- 400 paths ---

    def test_list_deals_no_created_by(self):
        resp = self.client.get("/v1/deals")
        self._assert_error(resp, "BAD_REQUEST", 400)

    def test_export_no_transactions(self):
        deal_resp = self.client.post("/v1/deals", data={"currency": "USD"})
        did = deal_resp.json()["deal"]["id"]
        resp = self.client.post(f"/v1/deals/{did}/export")
        self._assert_error(resp, "BAD_REQUEST", 400)

    def test_export_documents_not_ready(self):
        deal_resp = self.client.post("/v1/deals", data={"currency": "USD"})
        did = deal_resp.json()["deal"]["id"]
        # create processing doc directly in repo
        doc = {
            "id": "doc-wip",
            "deal_id": did,
            "storage_url": "inline://x",
            "file_type": "csv",
            "status": "processing",
            "currency_mismatch": False,
            "created_by": deal_resp.json()["deal"]["created_by"],
        }
        self.app.state.repos_factory()["documents"].create_document(doc)
        resp = self.client.post(f"/v1/deals/{did}/export")
        self._assert_error(resp, "DOCUMENTS_NOT_READY", 409)

    def test_invalid_schema_upload(self):
        deal_resp = self.client.post("/v1/deals", data={"currency": "USD"})
        did = deal_resp.json()["deal"]["id"]
        f = io.BytesIO(INVALID_CSV.encode())
        resp = self.client.post(
            f"/v1/deals/{did}/documents",
            files={"file": ("bad.csv", f, "text/csv")},
        )
        self._assert_error(resp, "INVALID_SCHEMA", 400)

    # --- 200 empty arrays ---

    def test_list_deals_empty(self):
        resp = self.client.get("/v1/deals?created_by=00000000-0000-0000-0000-999999999999")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["deals"], [])

    def test_list_snapshots_empty(self):
        deal_resp = self.client.post("/v1/deals", data={"currency": "USD"})
        did = deal_resp.json()["deal"]["id"]
        resp = self.client.get(f"/v1/deals/{did}/snapshots")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["snapshots"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
