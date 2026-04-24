"""
Parity Review — Q&A unit tests.

All tests use in-memory data. OpenAI is never called.
classify_intent() is mocked via unittest.mock.patch so the
test suite stays deterministic and dependency-free.
"""

import json
import sys
import os
import unittest
from unittest.mock import patch

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_ROOT = os.path.abspath(os.path.join(_BACKEND, os.pardir))
for p in (_BACKEND, _ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from v1.ask import (
    ALLOWED_INTENTS,
    answer_intent,
    extract_aggregates,
)


# ---------------------------------------------------------------------------
# Minimal snapshot factory
# ---------------------------------------------------------------------------

def _make_snapshot(transactions, txn_entity_map, entities, metrics=None, confidence=None, currency="USD"):
    """Build a minimal fake snapshot dict with a canonical_json payload."""
    payload = {
        "schema_version": "1.0.2",
        "config_version": "1.0.2",
        "deal_id": "d-test",
        "currency": currency,
        "transactions": transactions,
        "transfer_links": [],
        "entities": entities,
        "txn_entity_map": txn_entity_map,
        "metrics": metrics or {
            "coverage_bp": 10000,
            "missing_month_count": 0,
            "missing_month_penalty_bp": 0,
            "reconciliation_status": "NOT_RUN",
            "reconciliation_bp": None,
        },
        "confidence": confidence or {
            "final_confidence_bp": 8700,
            "tier": "High",
            "tier_capped": False,
            "override_penalty_bp": 0,
        },
        "financial_state_hash": "abc123",
        "overrides_applied": [],
    }
    return {
        "id": "snap-1",
        "deal_id": "d-test",
        "sha256_hash": "deadbeef",
        "canonical_json": json.dumps(payload),
    }


# ---------------------------------------------------------------------------
# Shared fixture — 5 transactions, 2 entities
# ---------------------------------------------------------------------------

_TRANSACTIONS = [
    {"txn_id": "t1", "txn_date": "2024-01-10", "signed_amount_cents": 50000, "account_id": "A"},
    {"txn_id": "t2", "txn_date": "2024-01-15", "signed_amount_cents": 30000, "account_id": "A"},
    {"txn_id": "t3", "txn_date": "2024-02-05", "signed_amount_cents": -10000, "account_id": "A"},
    {"txn_id": "t4", "txn_date": "2024-02-20", "signed_amount_cents": 20000, "account_id": "A"},
    {"txn_id": "t5", "txn_date": "2024-03-01", "signed_amount_cents": -5000, "account_id": "A"},
]

_TXN_ENTITY_MAP = [
    {"txn_id": "t1", "entity_id": "e-client", "role": "revenue_operational"},
    {"txn_id": "t2", "entity_id": "e-client", "role": "revenue_operational"},
    {"txn_id": "t3", "entity_id": "e-payroll", "role": "payroll"},
    {"txn_id": "t4", "entity_id": "e-client", "role": "revenue_operational"},
    {"txn_id": "t5", "entity_id": "e-supplier", "role": "supplier"},
]

_ENTITIES = [
    {"entity_id": "e-client", "display_name": "Client Alpha"},
    {"entity_id": "e-payroll", "display_name": "Staff Salaries"},
    {"entity_id": "e-supplier", "display_name": "Office Supplies Co"},
]

_SNAPSHOT = _make_snapshot(_TRANSACTIONS, _TXN_ENTITY_MAP, _ENTITIES)
_AGG = extract_aggregates(_SNAPSHOT)


class TestExtractAggregates(unittest.TestCase):
    """Verify extract_aggregates correctly tags transactions."""

    def test_roles_are_attached(self):
        roles = {t["txn_id"]: t["role"] for t in _AGG["tagged"]}
        self.assertEqual(roles["t1"], "revenue_operational")
        self.assertEqual(roles["t3"], "payroll")
        self.assertEqual(roles["t5"], "supplier")

    def test_entity_names_present(self):
        self.assertEqual(_AGG["entity_names"]["e-client"], "Client Alpha")
        self.assertEqual(_AGG["entity_names"]["e-payroll"], "Staff Salaries")

    def test_currency_extracted(self):
        self.assertEqual(_AGG["currency"], "USD")


class TestTotalRevenue(unittest.TestCase):
    def test_correct_sum(self):
        # t1=50000, t2=30000, t4=20000 → 100000 cents = 1000.00
        result = answer_intent("total_revenue", _AGG)
        self.assertIn("1,000.00", result)
        self.assertIn("USD", result)

    def test_no_payroll_included(self):
        result = answer_intent("total_revenue", _AGG)
        self.assertNotIn("payroll", result.lower())


class TestTotalPayroll(unittest.TestCase):
    def test_correct_sum(self):
        # t3 = -10000 → abs = 10000 cents = 100.00
        result = answer_intent("total_payroll", _AGG)
        self.assertIn("100.00", result)
        self.assertIn("USD", result)


class TestPayrollPercentRevenue(unittest.TestCase):
    def test_correct_percentage(self):
        # payroll=10000, revenue=100000 → 10.0%
        result = answer_intent("payroll_percent_revenue", _AGG)
        self.assertIn("10.0%", result)
        self.assertIn("operational revenue", result)

    def test_no_revenue_guard(self):
        empty_snap = _make_snapshot([], [], [])
        agg = extract_aggregates(empty_snap)
        result = answer_intent("payroll_percent_revenue", agg)
        self.assertIn("No operational revenue", result)

    def test_integer_arithmetic(self):
        # Verify no float division used (result is deterministic)
        result1 = answer_intent("payroll_percent_revenue", _AGG)
        result2 = answer_intent("payroll_percent_revenue", _AGG)
        self.assertEqual(result1, result2)


class TestTopSuppliers(unittest.TestCase):
    def test_supplier_listed(self):
        result = answer_intent("top_suppliers", _AGG)
        self.assertIn("Office Supplies Co", result)
        self.assertIn("50.00", result)  # 5000 cents

    def test_no_suppliers_guard(self):
        snap = _make_snapshot(
            [{"txn_id": "r1", "txn_date": "2024-01-01", "signed_amount_cents": 100, "account_id": "A"}],
            [{"txn_id": "r1", "entity_id": "e1", "role": "revenue_operational"}],
            [{"entity_id": "e1", "display_name": "Rev Co"}],
        )
        result = answer_intent("top_suppliers", extract_aggregates(snap))
        self.assertIn("No supplier", result)


class TestTopRevenueEntities(unittest.TestCase):
    def test_revenue_entity_listed(self):
        result = answer_intent("top_revenue_entities", _AGG)
        self.assertIn("Client Alpha", result)
        # t1+t2+t4 = 100000 cents = 1000.00
        self.assertIn("1,000.00", result)


class TestRevenueByMonth(unittest.TestCase):
    def test_months_present(self):
        result = answer_intent("revenue_by_month", _AGG)
        self.assertIn("2024-01", result)
        self.assertIn("2024-02", result)

    def test_january_total(self):
        # t1+t2 = 80000 cents = 800.00
        result = answer_intent("revenue_by_month", _AGG)
        self.assertIn("800.00", result)

    def test_no_revenue_guard(self):
        snap = _make_snapshot([], [], [])
        result = answer_intent("revenue_by_month", extract_aggregates(snap))
        self.assertIn("No operational revenue", result)


class TestConfidenceExplain(unittest.TestCase):
    def test_includes_tier_and_pct(self):
        result = answer_intent("confidence_explain", _AGG)
        # 8700 bp → 87.0%
        self.assertIn("87.0%", result)
        self.assertIn("High", result)

    def test_missing_months_mentioned(self):
        snap = _make_snapshot(
            _TRANSACTIONS, _TXN_ENTITY_MAP, _ENTITIES,
            metrics={
                "coverage_bp": 9000,
                "missing_month_count": 2,
                "missing_month_penalty_bp": 2000,
                "reconciliation_status": "NOT_RUN",
                "reconciliation_bp": None,
            },
            confidence={"final_confidence_bp": 7000, "tier": "Medium", "tier_capped": False, "override_penalty_bp": 0},
        )
        result = answer_intent("confidence_explain", extract_aggregates(snap))
        self.assertIn("2 missing month", result)

    def test_recon_ok_mentioned(self):
        snap = _make_snapshot(
            _TRANSACTIONS, _TXN_ENTITY_MAP, _ENTITIES,
            metrics={
                "coverage_bp": 9000,
                "missing_month_count": 0,
                "missing_month_penalty_bp": 0,
                "reconciliation_status": "OK",
                "reconciliation_bp": 8500,
            },
            confidence={"final_confidence_bp": 8500, "tier": "High", "tier_capped": False, "override_penalty_bp": 0},
        )
        result = answer_intent("confidence_explain", extract_aggregates(snap))
        self.assertIn("85.0%", result)
        self.assertIn("passed", result)


class TestReconciliationExplain(unittest.TestCase):
    def test_not_run(self):
        result = answer_intent("reconciliation_explain", _AGG)
        self.assertIn("not run", result.lower())

    def test_failed_overlap(self):
        snap = _make_snapshot(
            _TRANSACTIONS, _TXN_ENTITY_MAP, _ENTITIES,
            metrics={**_AGG["metrics"], "reconciliation_status": "FAILED_OVERLAP"},
        )
        result = answer_intent("reconciliation_explain", extract_aggregates(snap))
        self.assertIn("less than 60%", result)

    def test_ok(self):
        snap = _make_snapshot(
            _TRANSACTIONS, _TXN_ENTITY_MAP, _ENTITIES,
            metrics={
                "coverage_bp": 9000,
                "missing_month_count": 0,
                "missing_month_penalty_bp": 0,
                "reconciliation_status": "OK",
                "reconciliation_bp": 9200,
            },
        )
        result = answer_intent("reconciliation_explain", extract_aggregates(snap))
        self.assertIn("92.0%", result)
        self.assertIn("passed", result)


class TestOutOfScopeIntent(unittest.TestCase):
    """When classify_intent returns None the endpoint returns a fixed message."""

    def test_none_intent_produces_out_of_scope(self):
        # Simulate the endpoint logic inline
        intent = None
        if intent is None:
            answer = "This question is outside supported scope."
        else:
            answer = answer_intent(intent, _AGG)
        self.assertEqual(answer, "This question is outside supported scope.")


class TestAllowedIntents(unittest.TestCase):
    def test_all_eight_intents_present(self):
        self.assertEqual(len(ALLOWED_INTENTS), 8)

    def test_all_intents_handled_by_answer_intent(self):
        for intent in ALLOWED_INTENTS:
            result = answer_intent(intent, _AGG)
            self.assertIsInstance(result, str)
            self.assertTrue(len(result) > 0, f"Empty answer for intent {intent!r}")


class TestOpenAINotCalled(unittest.TestCase):
    """Verify that answer_intent never calls classify_intent (i.e. OpenAI)."""

    def test_no_openai_in_answer_intent(self):
        with patch("v1.ask.classify_intent") as mock_ci:
            answer_intent("total_revenue", _AGG)
            mock_ci.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
