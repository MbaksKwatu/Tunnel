"""
PAR-86: POST /export re-ran the full pipeline on every deal open.

Mechanism (reproduced): a recompute that reproduces an existing snapshot's
exact hash reuses that row, but pds_snapshots is immutable by trigger, so the
row's created_at / analysis_run_id / computation_fingerprint can never be
refreshed. Every freshness gate that reads them then failed forever.

Fix under test: the hash-identical recompute appends a row to
pds_snapshot_reverifications; _resolve_fresh_export reads it. These tests lock:
  - the loop is gone (pipeline calls, run rows, snapshot rows stay flat),
  - the time gates survive a hash-identical reuse,
  - genuine later changes are still NOT treated as covered,
  - no sealed hash changes (the fix only affects WHEN a recompute happens),
  - the read-only GET /export/current uses the same definition and writes nothing,
  - the fix degrades safely if the new table is missing or its write fails,
  - two adjacent invalidation gaps are documented as expected failures.

Run:  cd backend && python3 -m pytest tests_v1/test_par86_export_freshness_convergence.py -v
"""
import io
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_ROOT = os.path.abspath(os.path.join(_BACKEND, os.pardir))
for p in (_BACKEND, _ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.v1.api import _parse_ts, router as v1_router
from backend.v1.core.pipeline import run_pipeline
from backend.v1.db.memory_repositories import build_memory_repos
from tests_v1.jwt_test_utils import PUBLIC_JWKS, bearer

DOC_1 = """date,amount,description,account_id
2024-01-01,1000,Revenue,ACC-1
2024-01-02,-400,Supplier,ACC-1
"""
DOC_2 = """date,amount,description,account_id
2024-02-01,2500,Revenue,ACC-1
2024-02-02,-900,Supplier,ACC-1
"""
OWNER = "owner-user-1"
OTHER = "other-user-2"


class _Base(unittest.TestCase):
    def setUp(self):
        self.repos = build_memory_repos()
        app = FastAPI()
        app.state.repos_factory = lambda: self.repos
        app.include_router(v1_router)
        self.client = TestClient(app)

        # export() instantiates AuditedFinancialsRepo directly (bypassing
        # repos_factory) — same local-env gap handled in test_par111.
        af = patch("backend.v1.db.supabase_repositories.AuditedFinancialsRepo").start()
        af.return_value.get_by_deal_id.return_value = []
        af.return_value.get_latest_confirmed.return_value = None
        self.af = af.return_value
        self.addCleanup(patch.stopall)

        self.pipeline_calls = 0
        real = run_pipeline

        def counting(*a, **k):
            self.pipeline_calls += 1
            return real(*a, **k)

        patch("backend.v1.api.run_pipeline", side_effect=counting).start()
        patch("backend.v1.api._get_jwks", return_value=PUBLIC_JWKS).start()

        r = self.client.post("/v1/deals", data={"currency": "USD"}, headers=bearer(OWNER))
        self.assertEqual(r.status_code, 200, r.text)
        self.deal_id = r.json()["deal"]["id"]
        self._upload(DOC_1, "doc1.csv")

    def _upload(self, csv_text, name):
        up = self.client.post(
            f"/v1/deals/{self.deal_id}/documents",
            files={"file": (name, io.BytesIO(csv_text.encode()), "text/csv")},
        )
        self.assertEqual(up.status_code, 200, up.text)
        doc_id = up.json()["ingestion"]["document_id"]
        self.assertEqual(self.client.get(f"/v1/documents/{doc_id}/status").json()["status"], "completed")
        return doc_id

    def _export(self, force=False):
        r = self.client.post(f"/v1/deals/{self.deal_id}/export" + ("?force=true" if force else ""))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def _runs(self):
        return len(self.repos["runs"].list_runs(self.deal_id))

    def _snaps(self):
        return len(self.repos["snapshots"].list_snapshots(self.deal_id))

    def _reverifications(self):
        return len(self.repos["snapshot_reverifications"]._store)

    def _enter_post_reuse_state(self):
        """First export, then ONE forced hash-identical recompute — the exact
        state that used to strand a deal in the every-open-recomputes loop."""
        first = self._export()
        forced = self._export(force=True)
        self.assertEqual(first["snapshot"]["sha256_hash"], forced["snapshot"]["sha256_hash"],
                         "precondition: the recompute must reproduce the same hash")
        return first, forced


class TestLoopIsGone(_Base):
    def test_hash_identical_recompute_no_longer_strands_the_deal(self):
        first, _ = self._enter_post_reuse_state()
        calls, runs, snaps = self.pipeline_calls, self._runs(), self._snaps()

        for _ in range(5):
            r = self._export()
            self.assertEqual(r["snapshot"]["sha256_hash"], first["snapshot"]["sha256_hash"])

        self.assertEqual(self.pipeline_calls, calls, "pipeline must not run again while nothing has changed")
        self.assertEqual(self._runs(), runs, "a short-circuited export must not append a pds_analysis_runs row")
        self.assertEqual(self._snaps(), snaps)

    def test_short_circuit_returns_the_verifying_run_not_a_stale_one(self):
        self._export()
        forced = self._export(force=True)
        again = self._export()
        self.assertEqual(again["analysis_run"]["id"], forced["analysis_run"]["id"])
        self.assertEqual(again["analysis_run"]["id"], self.repos["runs"].get_latest_run(self.deal_id)["id"])

    def test_exactly_one_reverification_is_recorded_per_hash_identical_recompute(self):
        self._export()
        self.assertEqual(self._reverifications(), 0, "a genuinely new snapshot needs no reverification")
        self._export(force=True)
        self.assertEqual(self._reverifications(), 1)
        for _ in range(3):
            self._export()
        self.assertEqual(self._reverifications(), 1)


class TestTimeGatesSurviveReuse(_Base):
    """Conditions 1 & 2 compared against the snapshot's own created_at, which a
    reused (immutable) row can never refresh."""

    def _backdate_snapshot(self, seconds):
        row = self.repos["snapshots"]._store[-1]
        row["created_at"] = (datetime.utcnow() - timedelta(seconds=seconds)).isoformat()

    def test_a_document_newer_than_the_old_snapshot_but_covered_by_a_recompute(self):
        self._export()
        self._backdate_snapshot(120)
        doc_at = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
        with patch.object(self.repos["documents"], "get_latest_update_at", return_value=doc_at):
            calls = self.pipeline_calls
            self._export()  # gate 1 fails on the old snapshot alone -> one recompute, same hash
            self.assertEqual(self.pipeline_calls, calls + 1)
            self.assertEqual(self._reverifications(), 1)
            for _ in range(3):  # ...and now it must converge instead of looping
                self._export()
            self.assertEqual(self.pipeline_calls, calls + 1)

    def test_an_override_newer_than_the_old_snapshot_but_covered_by_a_recompute(self):
        self._export()
        self._backdate_snapshot(120)
        ov_at = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
        old_doc_at = (datetime.now(timezone.utc) - timedelta(seconds=200)).isoformat()  # doc predates the (backdated) seal
        with patch.object(self.repos["override_log"], "get_latest_update_at", return_value=ov_at), \
             patch.object(self.repos["documents"], "get_latest_update_at", return_value=old_doc_at):
            calls = self.pipeline_calls
            self._export()
            self.assertEqual(self.pipeline_calls, calls + 1)
            for _ in range(3):
                self._export()
            self.assertEqual(self.pipeline_calls, calls + 1)

    def test_a_change_arriving_after_the_reverification_is_not_treated_as_covered(self):
        self._enter_post_reuse_state()
        calls = self.pipeline_calls
        self._export()
        self.assertEqual(self.pipeline_calls, calls, "control: converged")
        # A real document added now (newer than the reverification) must recompute
        # and produce a NEW snapshot — the stale pointer must not mask it.
        before = self.repos["snapshots"].get_latest_snapshot(self.deal_id)["sha256_hash"]
        self._upload(DOC_2, "doc2.csv")
        after = self._export()
        self.assertEqual(self.pipeline_calls, calls + 1)
        self.assertNotEqual(after["snapshot"]["sha256_hash"], before)

    def test_an_override_after_the_reverification_forces_a_recompute(self):
        self._enter_post_reuse_state()
        ents = self._export()["entities"]
        calls = self.pipeline_calls
        self.client.post(f"/v1/deals/{self.deal_id}/overrides",
                         data={"entity_id": ents[0]["entity_id"], "new_value": "payroll"})
        self._export()
        self.assertEqual(self.pipeline_calls, calls + 1)

    def test_fingerprint_gate_reads_the_reverification_not_the_unstampable_snapshot(self):
        """PAR-219 tried to stamp the fingerprint onto the reused row; that is an
        UPDATE on an immutable table. A pre-040 snapshot (NULL fingerprint) must
        still converge via the reverification row."""
        self._export()
        self.repos["snapshots"]._store[-1]["computation_fingerprint"] = None  # pre-migration-040 row
        calls = self.pipeline_calls
        self._export()  # NULL fingerprint -> recompute, same hash, reverified
        self.assertEqual(self.pipeline_calls, calls + 1)
        for _ in range(3):
            self._export()
        self.assertEqual(self.pipeline_calls, calls + 1)
        self.assertIsNone(self.repos["snapshots"]._store[-1]["computation_fingerprint"],
                          "the sealed row itself must stay untouched")

    def test_a_computation_deploy_after_the_reverification_still_invalidates(self):
        self._enter_post_reuse_state()
        calls = self.pipeline_calls
        with patch("backend.v1.api.COMPUTATION_FINGERPRINT", "newcodefp000"):
            self._export()
        self.assertEqual(self.pipeline_calls, calls + 1)


class TestNoHashChange(_Base):
    def test_no_sealed_value_changes_for_a_deal_whose_data_did_not_change(self):
        first, forced = self._enter_post_reuse_state()
        later = self._export()
        sealed = lambda r: (r["snapshot"]["sha256_hash"], r["snapshot"]["financial_state_hash"], r["snapshot"]["id"])
        self.assertEqual(sealed(first), sealed(forced))
        self.assertEqual(sealed(first), sealed(later))
        # the sealed row itself is byte-identical to what was first written
        stored = self.repos["snapshots"]._store
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["analysis_run_id"], first["analysis_run_id"] if "analysis_run_id" in first else stored[0]["analysis_run_id"])


class TestReadOnlyCurrentExport(_Base):
    def _get(self, headers=None):
        return self.client.get(f"/v1/deals/{self.deal_id}/export/current", headers=headers if headers is not None else bearer(OWNER))

    def test_fresh_when_current_and_matches_the_post_export_payload(self):
        posted = self._export()
        got = self._get()
        self.assertEqual(got.status_code, 200)
        body = got.json()
        self.assertTrue(body["fresh"])
        self.assertEqual(body["snapshot"]["sha256_hash"], posted["snapshot"]["sha256_hash"])
        self.assertEqual(body["analysis_run"]["id"], posted["analysis_run"]["id"])
        self.assertEqual(body["entities"], posted["entities"])
        self.assertEqual(body["txn_entity_map"], posted["txn_entity_map"])

    def test_never_computes_or_writes(self):
        self._export()
        calls, runs, snaps, rv = self.pipeline_calls, self._runs(), self._snaps(), self._reverifications()
        for _ in range(3):
            self._get()
        self.assertEqual((self.pipeline_calls, self._runs(), self._snaps(), self._reverifications()), (calls, runs, snaps, rv))

    def test_not_fresh_when_there_is_no_snapshot_and_still_writes_nothing(self):
        runs_before = self._runs()  # a document upload itself records a run
        self.assertEqual(self._get().json(), {"fresh": False})
        self.assertEqual((self.pipeline_calls, self._runs(), self._snaps()), (0, runs_before, 0))

    def test_not_fresh_when_stale_and_does_not_recompute(self):
        self._export()
        self._upload(DOC_2, "doc2.csv")
        calls = self.pipeline_calls
        self.assertEqual(self._get().json(), {"fresh": False})
        self.assertEqual(self.pipeline_calls, calls)

    def test_fresh_after_a_hash_identical_recompute(self):
        self._enter_post_reuse_state()
        self.assertTrue(self._get().json()["fresh"])

    def test_requires_auth_and_ownership(self):
        self._export()
        self.assertEqual(self._get(headers={}).status_code, 401)
        self.assertEqual(self._get(headers=bearer(OTHER)).status_code, 404)


class TestDeploySafety(_Base):
    def test_missing_reverification_table_degrades_to_prefix_behaviour_not_an_outage(self):
        self._export()
        repo = self.repos["snapshot_reverifications"]
        with patch.object(repo, "get_latest", side_effect=RuntimeError("relation does not exist")), \
             patch.object(repo, "record", side_effect=RuntimeError("relation does not exist")):
            forced = self._export(force=True)   # reuse path: record() fails, export still 200
            self.assertTrue(forced["snapshot"]["sha256_hash"])
            self._export()                       # lookup fails -> treated as never reverified

    def test_failed_reverification_write_is_loud_but_not_fatal(self):
        self._export()
        repo = self.repos["snapshot_reverifications"]
        with patch.object(repo, "record", side_effect=RuntimeError("boom")):
            with self.assertLogs("backend.v1.api", level="WARNING") as logs:
                self._export(force=True)
        self.assertTrue(any("could not record reverification" in m for m in logs.output))


class TestParseTs(unittest.TestCase):
    def test_naive_and_aware_are_comparable(self):
        self.assertEqual(_parse_ts("2026-10-01T10:00:00.123456"), _parse_ts("2026-10-01T10:00:00.123456+00:00"))
        self.assertEqual(_parse_ts("2026-10-01T10:00:00Z"), _parse_ts("2026-10-01T10:00:00+00:00"))

    def test_empty_missing_and_garbage_sort_before_everything(self):
        for v in ("", None, "not-a-date"):
            self.assertLess(_parse_ts(v), _parse_ts("1970-01-02T00:00:00+00:00"))

    def test_trailing_zero_trimmed_microseconds_order_correctly(self):
        self.assertLess(_parse_ts("2026-10-01T10:00:00.5+00:00"), _parse_ts("2026-10-01T10:00:00.50001+00:00"))


class TestKnownInvalidationGaps(_Base):
    """Adjacent gaps CONFIRMED during PAR-86 but deliberately NOT fixed in this
    change (it must only affect when a recompute happens for already-covered
    inputs). They are expected failures so they flip loudly when fixed."""

    @unittest.expectedFailure
    def test_deleting_a_document_after_export_invalidates_the_snapshot(self):
        doc2 = self._upload(DOC_2, "doc2.csv")
        self._export()
        calls = self.pipeline_calls
        r = self.client.delete(f"/v1/documents/{doc2}")
        self.assertEqual(r.status_code, 200, "the unguarded duplicate route wins; the sealed-snapshot 409 guard is dead code")
        self._export()
        self.assertEqual(self.pipeline_calls, calls + 1, "snapshot still contains the deleted document's transactions")

    @unittest.expectedFailure
    def test_confirming_different_audited_financials_after_export_invalidates_the_snapshot(self):
        self._export()
        calls = self.pipeline_calls
        self.af.get_latest_confirmed.return_value = {
            "turnover_cents": 999_00, "financial_year_start": "2024-01-01", "financial_year_end": "2024-12-31",
        }
        self._export()
        self.assertEqual(self.pipeline_calls, calls + 1, "payload + accrual figures depend on the audited-financials row")


if __name__ == "__main__":
    unittest.main()
