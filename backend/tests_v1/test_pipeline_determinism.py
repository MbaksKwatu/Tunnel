import unittest

from backend.v1.core.pipeline import run_pipeline
from backend.v1.core.snapshot_engine import build_pds_payload, canonicalize_payload


def sample_txn(txn_date, amt, desc, account="A", txn_id=None):
    return {
        "id": txn_id or None,
        "txn_date": txn_date,
        "signed_amount_cents": amt,
        "abs_amount_cents": abs(amt),
        "raw_descriptor": desc,
        "parsed_descriptor": desc,
        "normalized_descriptor": desc.lower(),
        "account_id": account,
        "is_transfer": False,
        "txn_id": txn_id or f"{txn_date}-{account}-{amt}-{desc}",
    }


class TestPipelineDeterminism(unittest.TestCase):
    def test_transfer_multi_match_no_pair(self):
        # two possible matches for +100 -> should pair none
        txs = [
            sample_txn("2024-01-01", 10000, "X", account="A", txn_id="t1"),
            sample_txn("2024-01-02", -10000, "Y", account="B", txn_id="t2"),
            sample_txn("2024-01-02", -10000, "Z", account="C", txn_id="t3"),
        ]
        run, links, _, _ = run_pipeline(deal_id="d1", raw_transactions=txs, overrides=[], accrual={})
        self.assertEqual(len(links), 0)
        self.assertTrue(all(not t.get("is_transfer") for t in txs))
        self.assertEqual(run["transfer_links_hash"], "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945")  # sha256("[]")

    def test_overlap_failed_caps_high(self):
        txs = [
            sample_txn("2024-01-01", 10000, "rev", account="A", txn_id="t1"),
        ]
        accrual = {
            "accrual_revenue_cents": 10000,
            "accrual_period_start": "2024-02-01",
            "accrual_period_end": "2024-02-28",
        }
        run, _, _, _ = run_pipeline(deal_id="d1", raw_transactions=txs, overrides=[], accrual=accrual)
        self.assertEqual(run["reconciliation_status"], "FAILED_OVERLAP")
        self.assertEqual(run["tier"], "Medium")  # cap if would have been High

    def test_zero_denominator(self):
        txs = []  # no transactions -> denominator 0
        run, _, _, _ = run_pipeline(deal_id="d1", raw_transactions=txs, overrides=[], accrual={})
        self.assertEqual(run["final_confidence_bp"], 0)
        self.assertEqual(run["tier"], "Low")
        self.assertEqual(run["reconciliation_status"], "NOT_RUN")

    def test_missing_months_interior_only(self):
        txs = [
            sample_txn("2024-01-15", 10000, "rev", account="A", txn_id="t1"),
            sample_txn("2024-03-15", 10000, "rev", account="A", txn_id="t2"),
        ]
        run, _, _, _ = run_pipeline(deal_id="d1", raw_transactions=txs, overrides=[], accrual={})
        self.assertGreaterEqual(run["missing_month_penalty_bp"], 1000)  # February missing

    def test_override_cap(self):
        txs = [
            sample_txn("2024-01-01", 50000, "rev", account="A", txn_id="t1"),
            sample_txn("2024-01-02", 50000, "rev", account="A", txn_id="t2"),
        ]
        ov = [
            {"entity_id": "e1", "weight": 1.0},
        ]
        run, _, entities, txn_map = run_pipeline(deal_id="d1", raw_transactions=txs, overrides=ov, accrual={})
        self.assertLessEqual(run["override_penalty_bp"], 7000)

    def test_snapshot_hash_idempotent(self):
        txs = [
            sample_txn("2024-01-01", 10000, "rev", account="A", txn_id="t1"),
        ]
        run, links, entities, txn_map = run_pipeline(deal_id="d1", raw_transactions=txs, overrides=[], accrual={})
        payload = build_pds_payload(
            schema_version="v1",
            config_version="v1",
            deal_id="d1",
            currency="USD",
            raw_transactions=txs,
            transfer_links=links,
            entities=entities,
            txn_entity_map=txn_map,
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
        canon1, sha1 = canonicalize_payload(payload)
        canon2, sha2 = canonicalize_payload(payload)
        self.assertEqual(canon1, canon2)
        self.assertEqual(sha1, sha2)

    def test_accrual_zero_not_run(self):
        txs = [
            sample_txn("2024-01-01", 10000, "rev", account="A", txn_id="t1"),
        ]
        accrual = {
            "accrual_revenue_cents": 0,
            "accrual_period_start": "2024-01-01",
            "accrual_period_end": "2024-01-31",
        }
        run, _, _, _ = run_pipeline(deal_id="d1", raw_transactions=txs, overrides=[], accrual=accrual)
        self.assertEqual(run["reconciliation_status"], "NOT_RUN")

    def test_duplicate_export_hash_same_input(self):
        txs = [
            sample_txn("2024-01-01", 10000, "rev", account="A", txn_id="t1"),
            sample_txn("2024-01-02", -1000, "cost", account="B", txn_id="t2"),
        ]
        run, links, entities, txn_map = run_pipeline(deal_id="d1", raw_transactions=txs, overrides=[], accrual={})
        payload = build_pds_payload(
            schema_version="v1",
            config_version="v1",
            deal_id="d1",
            currency="USD",
            raw_transactions=txs,
            transfer_links=links,
            entities=entities,
            txn_entity_map=txn_map,
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
        canon1, sha1 = canonicalize_payload(payload)
        canon2, sha2 = canonicalize_payload(payload)
        self.assertEqual(sha1, sha2)


if __name__ == "__main__":
    unittest.main()
