"""
Adversarial Engine Validation — Parity v1

Simulates institutional fund scrutiny against deterministic outputs.
Every test represents a question a fund LP/IC would ask to challenge
the engine's integrity.

No core logic modifications.  If a test reveals a breach, it is
logged, fixed, and a regression test is added.
"""

import copy
import hashlib
import os
import sys
import unittest
import uuid
from math import floor
from typing import Any, Dict, List, Optional, Tuple

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_ROOT = os.path.abspath(os.path.join(_BACKEND, os.pardir))
for p in (_BACKEND, _ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.v1.core.pipeline import run_pipeline
from backend.v1.core.snapshot_engine import build_pds_payload, canonicalize_payload
from backend.v1.core.metrics_engine import compute_metrics
from backend.v1.core.confidence_engine import (
    compute_override_penalty_bp,
    compute_tier,
    finalize_confidence,
)
from backend.v1.core.transfer_matcher import match_transfers
from backend.v1.core.classifier import classify
from backend.v1.parsing.common import canonical_hash, normalize_descriptor


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _txn(
    date: str,
    cents: int,
    desc: str,
    account: str = "ACC-1",
    txn_id: Optional[str] = None,
    deal_id: str = "d-adv",
) -> Dict[str, Any]:
    tid = txn_id or hashlib.sha256(
        f"{date}|{account}|{cents}|{desc}".encode()
    ).hexdigest()
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


def _run_full(txs, overrides=None, accrual=None, deal_id="d-adv", currency="USD"):
    overrides = overrides or []
    accrual = accrual or {}
    run, links, ents, txm = run_pipeline(
        deal_id=deal_id,
        raw_transactions=txs,
        overrides=overrides,
        accrual=accrual,
    )
    payload = build_pds_payload(
        schema_version=run["schema_version"],
        config_version=run["config_version"],
        deal_id=deal_id,
        currency=currency,
        raw_transactions=txs,
        transfer_links=links,
        entities=ents,
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
        overrides_applied=overrides,
    )
    _, sha = canonicalize_payload(payload)
    fin_hash = payload["financial_state_hash"]
    return run, links, ents, txm, sha, fin_hash


# ===================================================================
# A. COVERAGE CHALLENGES
# ===================================================================


class TestCoverageChallenges(unittest.TestCase):
    """
    Fund question: "How do you calculate coverage, and what happens
    when half the volume is unclassified?"
    """

    def test_A1_partial_classification_drops_coverage(self):
        """
        Metrics engine with 50% volume in 'other' role.
        coverage_bp must equal floor(classified / total * 10000).

        The v1 classifier never produces 'other' for non-zero amounts,
        so we test the metrics engine directly with pre-classified data
        to prove the math is correct.
        """
        txs = [
            {"txn_date": "2024-01-01", "signed_amount_cents": 10000,
             "abs_amount_cents": 10000, "is_transfer": False, "role": "revenue_operational"},
            {"txn_date": "2024-01-02", "signed_amount_cents": -10000,
             "abs_amount_cents": 10000, "is_transfer": False, "role": "other"},
        ]
        metrics = compute_metrics(txs, {})

        non_transfer_total = 10000 + 10000
        classified_total = 10000
        expected_coverage = floor(classified_total * 10000 / non_transfer_total)

        self.assertEqual(metrics["non_transfer_abs_total_cents"], non_transfer_total)
        self.assertEqual(metrics["classified_abs_total_cents"], classified_total)
        self.assertEqual(metrics["coverage_bp"], expected_coverage)
        self.assertEqual(metrics["coverage_bp"], 5000)
        self.assertIsInstance(metrics["coverage_bp"], int)

    def test_A1b_classifier_guarantees_full_classification(self):
        """
        With the v1 rule-based classifier, ALL non-transfer non-zero
        transactions are classified (revenue_operational or supplier).
        This means the pipeline always yields coverage = 10000 bp.
        This is a structural guarantee, not a coincidence.
        """
        txs = [
            _txn("2024-01-01", 50000, "Revenue A", txn_id="c1"),
            _txn("2024-01-02", -30000, "Supplier B", txn_id="c2"),
            _txn("2024-02-01", 80000, "Revenue C", txn_id="c3"),
            _txn("2024-02-15", -20000, "Supplier D", txn_id="c4"),
        ]
        run, _, _, _, _, _ = _run_full(copy.deepcopy(txs))

        self.assertEqual(run["coverage_pct_bp"], 10000,
                         "v1 classifier guarantees 100% classification of non-zero non-transfer txns")
        self.assertEqual(
            run["non_transfer_abs_total_cents"],
            run["classified_abs_total_cents"],
        )

    def test_A2_all_classified_exact_10000(self):
        """All transactions classified → coverage = 10000 bp exactly, no float rounding."""
        txs = [
            {"txn_date": "2024-01-01", "signed_amount_cents": 33333,
             "abs_amount_cents": 33333, "is_transfer": False, "role": "revenue_operational"},
            {"txn_date": "2024-01-02", "signed_amount_cents": -66667,
             "abs_amount_cents": 66667, "is_transfer": False, "role": "supplier"},
        ]
        metrics = compute_metrics(txs, {})
        self.assertEqual(metrics["coverage_bp"], 10000)
        self.assertIsInstance(metrics["coverage_bp"], int)

    def test_A3_zero_denominator(self):
        """non_transfer_abs_total = 0 → safe fallback."""
        run, links, _, _, _, _ = _run_full([])
        self.assertEqual(run["coverage_pct_bp"], 0)
        self.assertEqual(run["reconciliation_status"], "NOT_RUN")
        self.assertEqual(run["tier"], "Low")
        self.assertEqual(run["final_confidence_bp"], 0)

    def test_A3b_all_transfers_zero_denominator(self):
        """Every txn is a transfer → non_transfer total = 0."""
        txs = [
            _txn("2024-01-01", 50000, "Wire Out", "ACC-A", txn_id="xfer-out"),
            _txn("2024-01-01", -50000, "Wire In", "ACC-B", txn_id="xfer-in"),
        ]
        run, links, _, _, _, _ = _run_full(copy.deepcopy(txs))
        self.assertEqual(len(links), 1)
        self.assertEqual(run["non_transfer_abs_total_cents"], 0)
        self.assertEqual(run["coverage_pct_bp"], 0)
        self.assertEqual(run["tier"], "Low")
        self.assertEqual(run["final_confidence_bp"], 0)


# ===================================================================
# B. RECONCILIATION CHALLENGES
# ===================================================================


class TestReconciliationChallenges(unittest.TestCase):
    """
    Fund question: "What happens when the accrual data doesn't match
    the bank data?"
    """

    def test_B1_overlap_below_60_percent(self):
        """
        Transaction date range barely overlaps accrual period.
        overlap < 60% → FAILED_OVERLAP → tier capped if would be High.

        Math:
          txns:    2024-01-01 to 2024-01-31
          accrual: 2024-03-01 to 2024-03-31
          overlap: 0 days / 31 days = 0% < 60%
        """
        txs = [
            _txn("2024-01-01", 100000, "Revenue", txn_id="b1-t1"),
            _txn("2024-01-31", 100000, "Revenue", txn_id="b1-t2"),
        ]
        accrual = {
            "accrual_revenue_cents": 200000,
            "accrual_period_start": "2024-03-01",
            "accrual_period_end": "2024-03-31",
        }
        run, _, _, _, _, _ = _run_full(copy.deepcopy(txs), accrual=accrual)

        self.assertEqual(run["reconciliation_status"], "FAILED_OVERLAP")
        self.assertIn(run["tier"], ["Low", "Medium"],
                      "FAILED_OVERLAP must prevent High tier")
        if run["final_confidence_bp"] >= 8500:
            self.assertTrue(run["tier_capped"],
                            "If conf >= 8500 with FAILED_OVERLAP, tier must be capped")

    def test_B2_accrual_revenue_zero(self):
        """accrual_revenue_cents = 0 → reconciliation NOT_RUN."""
        txs = [_txn("2024-01-01", 100000, "Revenue", txn_id="b2-t1")]
        accrual = {
            "accrual_revenue_cents": 0,
            "accrual_period_start": "2024-01-01",
            "accrual_period_end": "2024-01-31",
        }
        run, _, _, _, _, _ = _run_full(copy.deepcopy(txs), accrual=accrual)
        self.assertEqual(run["reconciliation_status"], "NOT_RUN")

    def test_B3_accrual_provided_but_zero_inflow(self):
        """
        Accrual provided with good overlap, but all txns are outflows
        (negative) → operational inflow = 0 → recon NOT_RUN.
        base_confidence = coverage_bp (recon not factored in).

        Math:
          txns span 2024-01-01 to 2024-01-31 → full overlap with accrual
          txns: only outflows → role = supplier
          inflow = 0 → reconciliation NOT_RUN
          coverage = 10000 (all classified)
          base_confidence = coverage = 10000
        """
        txs = [
            _txn("2024-01-01", -50000, "Supplier A", txn_id="b3-t1"),
            _txn("2024-01-15", -30000, "Supplier B", txn_id="b3-t2"),
            _txn("2024-01-31", -20000, "Supplier C", txn_id="b3-t3"),
        ]
        accrual = {
            "accrual_revenue_cents": 100000,
            "accrual_period_start": "2024-01-01",
            "accrual_period_end": "2024-01-31",
        }
        run, _, _, _, _, _ = _run_full(copy.deepcopy(txs), accrual=accrual)

        self.assertEqual(run["reconciliation_status"], "NOT_RUN")
        self.assertEqual(run["coverage_pct_bp"], 10000)
        self.assertEqual(run["base_confidence_bp"], 10000)

    def test_B4_reconciliation_ok_uses_min(self):
        """
        When reconciliation is OK, base_confidence = min(coverage, recon_bp).

        Math:
          txns span 2024-01-01 to 2024-01-31 → full overlap with accrual
          inflow = 40000 + 40000 = 80000 cents (revenue_operational)
          accrual = 100000 cents
          diff = |100000 - 80000| = 20000
          recon_bp = max(0, 10000 - floor(20000*10000/100000)) = 10000 - 2000 = 8000
          coverage = 10000 (all classified)
          base_confidence = min(10000, 8000) = 8000
        """
        txs = [
            _txn("2024-01-01", 40000, "Revenue Start", txn_id="b4-t1"),
            _txn("2024-01-31", 40000, "Revenue End", txn_id="b4-t2"),
        ]
        accrual = {
            "accrual_revenue_cents": 100000,
            "accrual_period_start": "2024-01-01",
            "accrual_period_end": "2024-01-31",
        }
        run, _, _, _, _, _ = _run_full(copy.deepcopy(txs), accrual=accrual)

        self.assertEqual(run["reconciliation_status"], "OK")
        self.assertEqual(run["reconciliation_pct_bp"], 8000)
        self.assertEqual(run["base_confidence_bp"], 8000)
        self.assertEqual(run["final_confidence_bp"], 8000)
        self.assertEqual(run["tier"], "Medium")


# ===================================================================
# C. OVERRIDE MANIPULATION
# ===================================================================


class TestOverrideManipulation(unittest.TestCase):
    """
    Fund question: "Can someone game the confidence score by
    strategically overriding entity classifications?"
    """

    DEAL = "d-override-adv"

    def _base_txs(self):
        return [
            _txn("2024-01-01", 100000, "Revenue Alpha", "ACC-1",
                 txn_id="ov-t1", deal_id=self.DEAL),
            _txn("2024-01-15", -20000, "Supplier Beta", "ACC-1",
                 txn_id="ov-t2", deal_id=self.DEAL),
            _txn("2024-02-01", 80000, "Revenue Gamma", "ACC-2",
                 txn_id="ov-t3", deal_id=self.DEAL),
        ]

    def test_C1_override_large_entity_applies_capped_penalty(self):
        """
        Override the largest revenue entity with weight=1.0.
        Penalty must apply proportional to entity volume share
        and be capped at 7000 bp.

        Math:
          Total non-transfer = 100000 + 20000 + 80000 = 200000
          Entity for "Revenue Alpha" volume = 100000
          weight = 1.0
          impact = (100000 / 200000) * 1.0 = 0.5
          penalty_bp = min(floor(0.5 * 10000), 7000) = min(5000, 7000) = 5000
        """
        txs = self._base_txs()
        run_base, _, ents_base, _, _, _ = _run_full(copy.deepcopy(txs), deal_id=self.DEAL)
        base_conf = run_base["final_confidence_bp"]

        revenue_entity = [e for e in ents_base if "alpha" in e["normalized_name"]][0]
        ov = {
            "id": "ov-adv-1",
            "entity_id": revenue_entity["entity_id"],
            "field": "role",
            "old_value": "revenue_operational",
            "new_value": "payroll",
            "weight": 1.0,
            "created_at": "2024-06-01T00:00:00Z",
        }
        run_ov, _, _, _, _, _ = _run_full(copy.deepcopy(txs), overrides=[ov], deal_id=self.DEAL)

        self.assertEqual(run_ov["override_penalty_bp"], 5000)
        self.assertLessEqual(run_ov["override_penalty_bp"], 7000,
                             "Override penalty must never exceed 7000 bp")
        self.assertLess(run_ov["final_confidence_bp"], base_conf,
                        "Override must reduce confidence")

    def test_C1b_extreme_override_capped_at_7000(self):
        """Weight=1.0 on entity that is 100% of volume → capped at 7000."""
        txs = [_txn("2024-01-01", 100000, "Solo Entity", txn_id="cap-t1", deal_id=self.DEAL)]
        run_base, _, ents, _, _, _ = _run_full(copy.deepcopy(txs), deal_id=self.DEAL)

        ov = {
            "id": "ov-cap",
            "entity_id": ents[0]["entity_id"],
            "weight": 1.0,
            "created_at": "2024-06-01T00:00:00Z",
        }
        run_ov, _, _, _, _, _ = _run_full(copy.deepcopy(txs), overrides=[ov], deal_id=self.DEAL)

        self.assertEqual(run_ov["override_penalty_bp"], 7000,
                         "100% volume at weight 1.0 → penalty capped at 7000 bp")

    def test_C2_revert_override_restores_confidence(self):
        """
        Override → revert with weight=0.0 → confidence returns to baseline.
        """
        txs = self._base_txs()
        run_base, _, ents, _, sha_base, fin0 = _run_full(copy.deepcopy(txs), deal_id=self.DEAL)

        entity_id = ents[0]["entity_id"]

        ov1 = {
            "id": "ov-r1",
            "entity_id": entity_id,
            "weight": 0.8,
            "created_at": "2024-06-01T00:00:00Z",
        }
        run_ov, _, _, _, sha_ov, fin1 = _run_full(
            copy.deepcopy(txs), overrides=[ov1], deal_id=self.DEAL
        )
        self.assertNotEqual(run_ov["final_confidence_bp"], run_base["final_confidence_bp"])

        ov2 = {
            "id": "ov-r2",
            "entity_id": entity_id,
            "weight": 0.0,
            "created_at": "2024-06-02T00:00:00Z",
        }
        run_rev, _, _, _, sha_rev, fin2 = _run_full(
            copy.deepcopy(txs), overrides=[ov1, ov2], deal_id=self.DEAL
        )

        self.assertEqual(run_rev["final_confidence_bp"], run_base["final_confidence_bp"],
                         "Reverting override must restore original confidence")
        self.assertEqual(run_rev["override_penalty_bp"], 0)
        self.assertEqual(fin0, fin2, "Financial state hash must revert to baseline")
        self.assertNotEqual(sha_base, sha_rev,
                            "Snapshot hash preserves override provenance even after revert")

    def test_C3_multiple_overrides_latest_wins(self):
        """
        Three overrides on the same entity. Only the latest (by created_at) applies.

        Math:
          ov1: weight=0.5 at T1
          ov2: weight=0.9 at T2
          ov3: weight=0.1 at T3
          Latest = ov3 → effective penalty uses weight=0.1
        """
        txs = self._base_txs()
        _, _, ents, _, _, _ = _run_full(copy.deepcopy(txs), deal_id=self.DEAL)
        entity_id = ents[0]["entity_id"]

        ovs = [
            {"id": "ov-m1", "entity_id": entity_id, "weight": 0.5,
             "created_at": "2024-06-01T00:00:00Z"},
            {"id": "ov-m2", "entity_id": entity_id, "weight": 0.9,
             "created_at": "2024-06-02T00:00:00Z"},
            {"id": "ov-m3", "entity_id": entity_id, "weight": 0.1,
             "created_at": "2024-06-03T00:00:00Z"},
        ]

        run_only_latest = _run_full(
            copy.deepcopy(txs),
            overrides=[{"id": "ov-solo", "entity_id": entity_id, "weight": 0.1,
                        "created_at": "2024-06-03T00:00:00Z"}],
            deal_id=self.DEAL,
        )[0]
        run_all = _run_full(
            copy.deepcopy(txs), overrides=ovs, deal_id=self.DEAL
        )[0]

        self.assertEqual(
            run_all["override_penalty_bp"],
            run_only_latest["override_penalty_bp"],
            "Multiple overrides on same entity: only latest-by-timestamp wins",
        )


# ===================================================================
# D. TRANSFER EDGE CASES
# ===================================================================


class TestTransferEdgeCases(unittest.TestCase):
    """
    Fund question: "How do you prevent artificial inflation of
    non-transfer volume through transfer misclassification?"
    """

    def test_D1_two_possible_matches_no_pairing(self):
        """
        1 outflow, 2 inflow candidates with same abs amount.
        Ambiguity → no pairing. All remain non-transfer.
        """
        txs = [
            _txn("2024-01-10", -50000, "Wire Out", "ACC-A", txn_id="d1-out"),
            _txn("2024-01-11", 50000, "Wire In X", "ACC-B", txn_id="d1-in1"),
            _txn("2024-01-11", 50000, "Wire In Y", "ACC-C", txn_id="d1-in2"),
        ]
        _, links = match_transfers(txs)
        self.assertEqual(len(links), 0, "Multi-match ambiguity must produce 0 links")
        for tx in txs:
            self.assertFalse(tx.get("is_transfer", False),
                             f"{tx['txn_id']} must not be flagged as transfer")

    def test_D2_cross_account_enforced(self):
        """Same account → never matched, even if all other criteria hold."""
        txs = [
            _txn("2024-01-10", -50000, "Wire Out", "ACC-A", txn_id="d2-out"),
            _txn("2024-01-10", 50000, "Wire In", "ACC-A", txn_id="d2-in"),
        ]
        _, links = match_transfers(txs)
        self.assertEqual(len(links), 0,
                         "Same-account transactions must never be paired")

    def test_D3_outside_2_day_window_not_paired(self):
        """3-day gap → outside the 2-day window → not paired."""
        txs = [
            _txn("2024-01-10", -50000, "Wire Out", "ACC-A", txn_id="d3-out"),
            _txn("2024-01-13", 50000, "Wire In", "ACC-B", txn_id="d3-in"),
        ]
        _, links = match_transfers(txs)
        self.assertEqual(len(links), 0,
                         "3-day gap exceeds 2-day window → no pairing")

    def test_D4_exact_2_day_boundary_paired(self):
        """Exactly 2-day gap → within window → should pair."""
        txs = [
            _txn("2024-01-10", -50000, "Wire Out", "ACC-A", txn_id="d4-out"),
            _txn("2024-01-12", 50000, "Wire In", "ACC-B", txn_id="d4-in"),
        ]
        _, links = match_transfers(txs)
        self.assertEqual(len(links), 1, "Exactly 2-day gap → valid pairing")

    def test_D5_different_amounts_not_paired(self):
        """Different abs amounts → never paired."""
        txs = [
            _txn("2024-01-10", -50000, "Wire Out", "ACC-A", txn_id="d5-out"),
            _txn("2024-01-10", 50001, "Wire In", "ACC-B", txn_id="d5-in"),
        ]
        _, links = match_transfers(txs)
        self.assertEqual(len(links), 0,
                         "Different abs amounts → no pairing")


# ===================================================================
# E. HASH INTEGRITY UNDER STRESS
# ===================================================================


class TestHashIntegrityUnderStress(unittest.TestCase):
    """
    Fund question: "Can the audit trail be manipulated by
    applying and reverting overrides?"
    """

    DEAL = "d-hash-adv"

    def _base_txs(self):
        return [
            _txn("2024-01-01", 100000, "Revenue Alpha", "ACC-1",
                 txn_id="h-t1", deal_id=self.DEAL),
            _txn("2024-01-15", -30000, "Supplier Beta", "ACC-1",
                 txn_id="h-t2", deal_id=self.DEAL),
            _txn("2024-02-01", 70000, "Revenue Gamma", "ACC-2",
                 txn_id="h-t3", deal_id=self.DEAL),
        ]

    def test_E1_override_changes_snapshot_hash(self):
        """Apply override → snapshot hash changes."""
        txs = self._base_txs()
        run0, _, ents, _, sha0, fin0 = _run_full(copy.deepcopy(txs), deal_id=self.DEAL)

        ov = {
            "id": "e-ov1",
            "entity_id": ents[0]["entity_id"],
            "weight": 0.5,
            "created_at": "2024-06-01T00:00:00Z",
        }
        run1, _, _, _, sha1, fin1 = _run_full(
            copy.deepcopy(txs), overrides=[ov], deal_id=self.DEAL
        )

        self.assertNotEqual(sha0, sha1, "Override must change snapshot hash")
        self.assertNotEqual(
            run0["final_confidence_bp"], run1["final_confidence_bp"],
            "Override must change confidence",
        )
        self.assertNotEqual(fin0, fin1, "Override must change financial_state_hash when effectual")

    def test_E2_revert_restores_confidence_but_hash_differs(self):
        """
        Override → revert(weight=0) → confidence restored, but snapshot
        hash MUST differ because the overrides_applied audit trail is
        part of the canonical payload.

        This is the correct behavior for institutional audit:
        two snapshots with different override histories must have
        different hashes, even if the net financial effect is identical.
        """
        txs = self._base_txs()
        run0, _, ents, _, sha_original, fin_original = _run_full(copy.deepcopy(txs), deal_id=self.DEAL)
        base_conf = run0["final_confidence_bp"]

        entity_id = ents[0]["entity_id"]

        ov_apply = {
            "id": "e-ov-apply",
            "entity_id": entity_id,
            "weight": 0.7,
            "created_at": "2024-06-01T00:00:00Z",
        }
        run1, _, _, _, sha_override, fin_override = _run_full(
            copy.deepcopy(txs), overrides=[ov_apply], deal_id=self.DEAL
        )
        self.assertNotEqual(sha_original, sha_override)
        self.assertLess(run1["final_confidence_bp"], base_conf)
        self.assertNotEqual(fin_original, fin_override)

        ov_revert = {
            "id": "e-ov-revert",
            "entity_id": entity_id,
            "weight": 0.0,
            "created_at": "2024-06-02T00:00:00Z",
        }
        run2, _, _, _, sha_reverted, fin_reverted = _run_full(
            copy.deepcopy(txs), overrides=[ov_apply, ov_revert], deal_id=self.DEAL
        )

        self.assertEqual(run2["final_confidence_bp"], base_conf,
                         "Reverting override restores confidence to baseline")
        self.assertEqual(run2["override_penalty_bp"], 0,
                         "Reverted override penalty must be 0")
        self.assertNotEqual(sha_original, sha_reverted,
                            "Hash differs because override audit trail is part of payload")
        self.assertNotEqual(sha_override, sha_reverted,
                            "Reverted hash differs from applied-override hash")
        self.assertEqual(fin_original, fin_reverted,
                         "Financial state hash must revert to baseline when override neutralized")

    def test_E3_confidence_cycle_deterministic(self):
        """
        Baseline → override(A) → revert → override(A) → revert.

        Confidence must cycle:  C0, C1, C0, C1, C0.
        Hashes must all be UNIQUE (growing override audit trail).

        The snapshot hash captures the full override history, so each
        state has a distinct hash. But the financial metrics (confidence,
        tier, coverage) are deterministic functions of the effective
        override state alone.
        """
        txs = self._base_txs()
        run0, _, ents, _, sha0, fin0 = _run_full(copy.deepcopy(txs), deal_id=self.DEAL)
        entity_id = ents[0]["entity_id"]
        c0 = run0["final_confidence_bp"]
        t0 = run0["tier"]

        ov = {"id": "e-cycle", "entity_id": entity_id, "weight": 0.6,
              "created_at": "2024-06-01T00:00:00Z"}

        run1, _, _, _, sha1, fin1 = _run_full(
            copy.deepcopy(txs), overrides=[ov], deal_id=self.DEAL
        )
        c1 = run1["final_confidence_bp"]
        self.assertNotEqual(c0, c1, "Override must change confidence")
        self.assertNotEqual(sha0, sha1, "Different override state → different hash")
        self.assertNotEqual(fin0, fin1, "Financial state hash changes when override is effectual")

        revert = {"id": "e-cycle-rev", "entity_id": entity_id, "weight": 0.0,
                  "created_at": "2024-06-02T00:00:00Z"}
        run2, _, _, _, sha2, fin2 = _run_full(
            copy.deepcopy(txs), overrides=[ov, revert], deal_id=self.DEAL
        )
        self.assertEqual(run2["final_confidence_bp"], c0,
                         "Revert restores baseline confidence")
        self.assertEqual(run2["tier"], t0)
        self.assertNotEqual(sha2, sha0, "Audit trail differs → hash differs")
        self.assertNotEqual(sha2, sha1)
        self.assertEqual(fin2, fin0, "Financial state hash returns to baseline on revert")

        ov2 = {"id": "e-cycle2", "entity_id": entity_id, "weight": 0.6,
               "created_at": "2024-06-03T00:00:00Z"}
        run3, _, _, _, sha3, fin3 = _run_full(
            copy.deepcopy(txs), overrides=[ov, revert, ov2], deal_id=self.DEAL
        )
        self.assertEqual(run3["final_confidence_bp"], c1,
                         "Re-applying same weight restores override-state confidence")
        self.assertNotEqual(sha3, sha0)
        self.assertNotEqual(sha3, sha1)
        self.assertNotEqual(sha3, sha2)
        self.assertEqual(fin3, fin1,
                         "Financial state hash matches the effective override state")

        revert2 = {"id": "e-cycle2-rev", "entity_id": entity_id, "weight": 0.0,
                   "created_at": "2024-06-04T00:00:00Z"}
        run4, _, _, _, sha4, fin4 = _run_full(
            copy.deepcopy(txs), overrides=[ov, revert, ov2, revert2], deal_id=self.DEAL
        )
        self.assertEqual(run4["final_confidence_bp"], c0,
                         "Second revert restores baseline confidence")
        all_hashes = {sha0, sha1, sha2, sha3, sha4}
        self.assertEqual(len(all_hashes), 5,
                         "All 5 override states must produce unique hashes (unique audit trails)")
        self.assertEqual(fin4, fin0, "Financial state hash returns to baseline after full cycle")

    def test_E4_raw_transaction_hash_unaffected_by_overrides(self):
        """Overrides must never change the raw_transaction_hash."""
        txs = self._base_txs()
        run0, _, ents, _, _, fin0 = _run_full(copy.deepcopy(txs), deal_id=self.DEAL)

        ov = {"id": "e-raw", "entity_id": ents[0]["entity_id"], "weight": 1.0,
              "created_at": "2024-06-01T00:00:00Z"}
        run1, _, _, _, _, fin1 = _run_full(
            copy.deepcopy(txs), overrides=[ov], deal_id=self.DEAL
        )

        self.assertEqual(
            run0["raw_transaction_hash"], run1["raw_transaction_hash"],
            "raw_transaction_hash must be independent of overrides",
        )
        self.assertNotEqual(fin0, fin1,
                            "Financial state hash still changes when override impacts confidence")


# ===================================================================
# F. TIER BOUNDARY CONDITIONS
# ===================================================================


class TestTierBoundaryConditions(unittest.TestCase):
    """
    Fund question: "How are tier boundaries determined, and
    are they susceptible to off-by-one errors?"
    """

    def test_F1_tier_boundary_low_medium(self):
        """6999 bp → Low,  7000 bp → Medium."""
        tier_6999, _ = compute_tier(6999, "NOT_RUN")
        tier_7000, _ = compute_tier(7000, "NOT_RUN")
        self.assertEqual(tier_6999, "Low")
        self.assertEqual(tier_7000, "Medium")

    def test_F2_tier_boundary_medium_high(self):
        """8499 bp → Medium,  8500 bp → High (capped if recon != OK)."""
        tier_8499, _ = compute_tier(8499, "OK")
        tier_8500, _ = compute_tier(8500, "OK")
        self.assertEqual(tier_8499, "Medium")
        self.assertEqual(tier_8500, "High")

    def test_F3_high_capped_without_reconciliation(self):
        """8500 bp with recon != OK → capped to Medium."""
        tier, capped = compute_tier(8500, "NOT_RUN")
        self.assertEqual(tier, "Medium")
        self.assertTrue(capped)

    def test_F4_high_not_capped_with_ok_reconciliation(self):
        """8500 bp with recon == OK → High, not capped."""
        tier, capped = compute_tier(8500, "OK")
        self.assertEqual(tier, "High")
        self.assertFalse(capped)

    def test_F5_confidence_zero_floor(self):
        """Confidence can never go below 0."""
        result = finalize_confidence(3000, 7000, "NOT_RUN")
        self.assertEqual(result["final_confidence_bp"], 0)
        self.assertEqual(result["tier"], "Low")


# ===================================================================
# G. MATHEMATICAL PRECISION
# ===================================================================


class TestMathematicalPrecision(unittest.TestCase):
    """
    Fund question: "Are there floating-point rounding issues
    in your coverage and confidence calculations?"
    """

    def test_G1_coverage_uses_floor_not_round(self):
        """
        Verify floor() is used, not round().
        classified=33333, total=100000
        exact = 3333.3 bp → floor = 3333, round = 3333
        classified=66667, total=100000
        exact = 6666.7 bp → floor = 6666, round = 6667
        """
        txs = [
            {"txn_date": "2024-01-01", "signed_amount_cents": 66667,
             "abs_amount_cents": 66667, "is_transfer": False, "role": "revenue_operational"},
            {"txn_date": "2024-01-02", "signed_amount_cents": -33333,
             "abs_amount_cents": 33333, "is_transfer": False, "role": "other"},
        ]
        metrics = compute_metrics(txs, {})
        expected = floor(66667 * 10000 / 100000)
        self.assertEqual(metrics["coverage_bp"], expected)
        self.assertEqual(metrics["coverage_bp"], 6666)

    def test_G2_override_penalty_uses_floor(self):
        """
        entity_value=33333, total=100000, weight=1.0
        exact = 0.33333 → floor(3333.3) = 3333 bp
        """
        entity_values = {"e1": 33333}
        ovs = [{"entity_id": "e1", "weight": 1.0, "created_at": "2024-01-01"}]
        penalty = compute_override_penalty_bp(ovs, entity_values, 100000)
        self.assertEqual(penalty, 3333)

    def test_G3_all_integer_outputs(self):
        """Every numeric field from the pipeline must be int, never float."""
        txs = [
            _txn("2024-01-01", 77777, "Revenue", txn_id="g3-t1"),
            _txn("2024-01-15", -33333, "Supplier", txn_id="g3-t2"),
        ]
        run, _, _, _, _, _ = _run_full(copy.deepcopy(txs))
        int_fields = [
            "non_transfer_abs_total_cents", "classified_abs_total_cents",
            "coverage_pct_bp", "missing_month_count", "missing_month_penalty_bp",
            "override_penalty_bp", "base_confidence_bp", "final_confidence_bp",
        ]
        for field in int_fields:
            self.assertIsInstance(run[field], int,
                                 f"{field} must be int, got {type(run[field])}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
