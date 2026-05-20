"""
Parity Review AI — unit tests for all 4 tools + context builder.

Uses a synthetic Buildex-style snapshot so no DB or API key is needed.
Run with: python -m pytest tests_v1/test_parity_review.py -v
"""
import json
import sys
import os

import pytest

# Ensure backend root is on sys.path so relative imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from v1.parity_review.tools.financial_metrics import calculate_financial_metrics
from v1.parity_review.tools.operational_metrics import calculate_operational_metrics
from v1.parity_review.tools.entity_details import get_entity_details
from v1.parity_review.tools.explain_flags import explain_flagged_item


# ---------------------------------------------------------------------------
# Synthetic deal_data fixture (mirrors parse_snapshot() output)
# ---------------------------------------------------------------------------

_BUILDEX_CANONICAL = {
    "transactions": [
        # Revenue — Joyce Mwanziu
        {"txn_id": "t001", "id": "t001", "signed_amount_cents": 109465000,
         "txn_date": "2025-02-10", "description": "Transfer from Joyce Mwanziu Avia"},
        # Revenue — small client
        {"txn_id": "t002", "id": "t002", "signed_amount_cents": 50000000,
         "txn_date": "2025-03-15", "description": "Payment received"},
        # Supplier payment
        {"txn_id": "t003", "id": "t003", "signed_amount_cents": -200000000,
         "txn_date": "2025-04-01", "description": "RTGS: RTOBZN04517099"},
        # Loan repayment
        {"txn_id": "t004", "id": "t004", "signed_amount_cents": -28733980,
         "txn_date": "2025-05-05", "description": "Loan repayment KCB"},
        # Payroll
        {"txn_id": "t005", "id": "t005", "signed_amount_cents": -15000000,
         "txn_date": "2025-06-30", "description": "Salary payroll June"},
        # KRA tax
        {"txn_id": "t006", "id": "t006", "signed_amount_cents": -5000000,
         "txn_date": "2025-06-20", "description": "KRA tax payment"},
        # Needs-review / possible capital injection
        {"txn_id": "t007", "id": "t007", "signed_amount_cents": 99900000,
         "txn_date": "2025-06-23", "description": "Peter Karanja A7F73Bce25E",
         "anomalies": [
             {
                 "type": "POSSIBLE_CAPITAL_INJECTION",
                 "severity": "CRITICAL",
                 "reason": "Large inflow from rare entity with no reciprocal payments",
             }
         ]},
    ],
    "entities": [
        {"entity_id": "e001", "display_name": "Joyce Mwanziu Avia"},
        {"entity_id": "e002", "display_name": "Small Client Ltd"},
        {"entity_id": "e003", "display_name": "RTGS: RTOBZN04517099"},
        {"entity_id": "e004", "display_name": "KCB Bank"},
        {"entity_id": "e005", "display_name": "Staff Payroll"},
        {"entity_id": "e006", "display_name": "KRA"},
        {"entity_id": "e007", "display_name": "Peter Karanja A7F73Bce25E"},
    ],
    "txn_entity_map": [
        {"txn_id": "t001", "entity_id": "e001", "role": "revenue_operational"},
        {"txn_id": "t002", "entity_id": "e002", "role": "revenue_operational"},
        {"txn_id": "t003", "entity_id": "e003", "role": "supplier_payment"},
        {"txn_id": "t004", "entity_id": "e004", "role": "loan_repayment"},
        {"txn_id": "t005", "entity_id": "e005", "role": "payroll"},
        {"txn_id": "t006", "entity_id": "e006", "role": "tax_payment"},
        {"txn_id": "t007", "entity_id": "e007", "role": "needs_review"},
    ],
    "metrics": {
        "average_monthly_inflow_cents": 29994060,
        "average_monthly_outflow_cents": 29619165,
        "average_net_monthly_cents": 374895,
        "median_monthly_inflow_cents": 28000000,
        "revenue_growth_bps": -5140,   # -51.4%
        "loan_repayment_burden_bps": 100,
        "payroll_stability": "SPARSE",
        "payroll_months_detected": 1,
        "kra_compliance": "PARTIAL",
        "statement_months": 12,
    },
    "currency": "KES",
}

# Build deal_data manually (mirrors parse_snapshot output)
from v1.parity_review.context import (
    _build_txn_role_map, _tag_transactions, _compute_entity_breakdown,
    _compute_monthly_cashflow,
)

_REVENUE_ROLES  = frozenset({"revenue_operational", "revenue_non_operational"})
_SUPPLIER_ROLES = frozenset({"supplier_payment"})
_PAYROLL_ROLES  = frozenset({"payroll"})
_TAX_ROLES      = frozenset({"tax_payment", "kra_payment"})
_REVIEW_ROLES   = frozenset({"needs_review", "other"})


def _build_deal_data():
    canonical = _BUILDEX_CANONICAL
    txn_role_map = _build_txn_role_map(canonical)
    entity_names = {
        str(e["entity_id"]): (e.get("display_name") or str(e["entity_id"]))
        for e in canonical["entities"]
    }
    tagged = _tag_transactions(canonical, txn_role_map, entity_names)
    monthly = _compute_monthly_cashflow(canonical)
    entity_breakdown = _compute_entity_breakdown(canonical, txn_role_map)

    top_suppliers = [r for r in entity_breakdown if r["role"] in _SUPPLIER_ROLES][:10]
    top_revenue   = [r for r in entity_breakdown if r["role"] in _REVENUE_ROLES][:10]
    review_ents   = [r for r in entity_breakdown if r["role"] in _REVIEW_ROLES][:20]

    loan_repayment_total = sum(
        abs(t["signed_amount_cents"]) for t in tagged
        if t["role"] == "loan_repayment" and t["signed_amount_cents"] < 0
    )
    payroll_months_set = {
        t["txn_date"][:7] for t in tagged
        if t["role"] in _PAYROLL_ROLES and t["txn_date"] and len(t["txn_date"]) >= 7
    }
    tax_months_set = {
        t["txn_date"][:7] for t in tagged
        if t["role"] in _TAX_ROLES and t["txn_date"] and len(t["txn_date"]) >= 7
    }

    return {
        "canonical": canonical,
        "tagged": tagged,
        "entity_names": entity_names,
        "monthly": monthly,
        "entity_breakdown": entity_breakdown,
        "top_suppliers": top_suppliers,
        "top_revenue": top_revenue,
        "review_ents": review_ents,
        "metrics": canonical["metrics"],
        "csi": canonical["metrics"],
        "loan_repayment_total_cents": loan_repayment_total,
        "payroll_months": len(payroll_months_set),
        "tax_months": len(tax_months_set),
        "n_months": canonical["metrics"]["statement_months"],
        "currency": "KES",
    }


@pytest.fixture
def deal_data():
    return _build_deal_data()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFinancialMetrics:
    def test_dscr_calculated(self, deal_data):
        result = calculate_financial_metrics(deal_data)
        dscr = result["dscr"]
        assert dscr["value"] is not None
        assert dscr["value"] > 1.0, "DSCR should be above 1.0 with this fixture"
        print(f"\nDSCR: {dscr['value']} — {dscr['assessment']}")

    def test_revenue_growth_negative(self, deal_data):
        result = calculate_financial_metrics(deal_data)
        growth = result["revenue_growth"]
        # -5140 bps = -51.4%
        assert growth["value_pct"] == pytest.approx(-51.4, abs=0.5)
        assert "Declining" in growth["assessment"]
        print(f"\nRevenue growth: {growth['value_pct']}% — {growth['assessment']}")

    def test_loan_burden(self, deal_data):
        result = calculate_financial_metrics(deal_data)
        burden = result["loan_burden"]
        assert burden["value_pct"] == pytest.approx(1.0, abs=0.1)
        assert "Healthy" in burden["assessment"]

    def test_summary_present(self, deal_data):
        result = calculate_financial_metrics(deal_data)
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0

    def test_burn_rate_no_negative_months(self, deal_data):
        result = calculate_financial_metrics(deal_data)
        burn = result["burn_rate"]
        # All transactions are positive net or single-month — check it runs
        assert "negative_months" in burn


class TestOperationalMetrics:
    def test_supplier_concentration(self, deal_data):
        result = calculate_operational_metrics(deal_data)
        sup = result["supplier_concentration"]
        assert sup["top_supplier_name"] is not None
        assert sup["top_supplier_pct"] == pytest.approx(100.0, abs=0.1)  # only one supplier
        print(f"\nTop supplier: {sup['top_supplier_name']} ({sup['top_supplier_pct']}%) — {sup['risk_level']}")

    def test_customer_concentration(self, deal_data):
        result = calculate_operational_metrics(deal_data)
        cust = result["customer_concentration"]
        # Joyce is top revenue source
        assert cust["top_customer_name"] == "Joyce Mwanziu Avia"
        assert cust["top_customer_pct"] > 50  # dominates with 109M out of 159M revenue
        assert cust["risk_level"] == "HIGH RISK"
        print(f"\nTop customer: {cust['top_customer_name']} ({cust['top_customer_pct']}%) — {cust['risk_level']}")

    def test_payroll_stability(self, deal_data):
        result = calculate_operational_metrics(deal_data)
        payroll = result["payroll_stability"]
        assert payroll["months_with_payroll"] == 1
        print(f"\nPayroll: {payroll['assessment']}")

    def test_summary_contains_risk_flags(self, deal_data):
        result = calculate_operational_metrics(deal_data)
        summary = result["summary"]
        assert "⚠️" in summary or "✓" in summary


class TestEntityDetails:
    def test_find_joyce(self, deal_data):
        result = get_entity_details("Joyce Mwanziu", deal_data)
        assert result["found"] is True
        assert result["entity_type"] == "Revenue Source (Customer)"
        assert result["profile"]["total_transactions"] == 1
        assert result["profile"]["total_credit_kes"] == pytest.approx(1094650.0, abs=1)
        print(f"\nJoyce: {result['entity_type']}, {result['profile']['pct_of_category']:.1f}% of revenue")

    def test_find_supplier(self, deal_data):
        result = get_entity_details("RTOBZN04517099", deal_data)
        assert result["found"] is True
        assert result["entity_type"] == "Supplier/Vendor"
        print(f"\nRTGS supplier: {result['entity_type']}, KES {result['profile']['total_debit_kes']:,.0f}")

    def test_entity_not_found(self, deal_data):
        result = get_entity_details("Nonexistent Entity XYZ", deal_data)
        assert result["found"] is False
        assert "suggestion" in result

    def test_risk_assessment_high_concentration(self, deal_data):
        result = get_entity_details("Joyce Mwanziu", deal_data)
        assert "⚠️" in result["risk_assessment"]

    def test_recent_transactions_present(self, deal_data):
        result = get_entity_details("Peter Karanja", deal_data)
        assert result["found"] is True
        assert len(result["recent_transactions"]) >= 1
        assert result["recent_transactions"][0]["amount_kes"] == pytest.approx(999000.0, abs=1)


class TestExplainFlags:
    def test_peter_karanja_flagged(self, deal_data):
        result = explain_flagged_item("Peter Karanja", deal_data)
        assert result["flagged"] is True
        assert result["total_flagged_transactions"] >= 1
        assert result["anomalies_by_severity"]["critical"] >= 1
        print(f"\n{result['entity_name']} — {result['total_flagged_transactions']} flagged txns")
        print(f"Recommended: {result['recommended_action']}")

    def test_explanation_contains_entity_name(self, deal_data):
        result = explain_flagged_item("Peter Karanja", deal_data)
        assert "Peter Karanja" in result["explanation"]

    def test_recommended_action_capital_injection(self, deal_data):
        result = explain_flagged_item("Peter Karanja", deal_data)
        assert "CLASSIFY" in result["recommended_action"] or "INVESTIGATE" in result["recommended_action"]

    def test_unflagged_entity(self, deal_data):
        result = explain_flagged_item("KCB Bank", deal_data)
        # KCB is loan_repayment — not in _REVIEW_ROLES, no anomalies
        assert result["flagged"] is False

    def test_entity_not_found(self, deal_data):
        result = explain_flagged_item("Nobody Here", deal_data)
        assert result["flagged"] is False
        assert "not found" in result["message"]


class TestContextBuilder:
    def test_context_string_generated(self, deal_data):
        from v1.parity_review.context import build_snapshot_context
        ctx = build_snapshot_context(deal_data)
        assert "DEAL SNAPSHOT CONTEXT" in ctx
        assert "KES" in ctx
        assert "DSCR" in ctx or "calculate_financial_metrics" in ctx

    def test_context_contains_key_figures(self, deal_data):
        from v1.parity_review.context import build_snapshot_context
        ctx = build_snapshot_context(deal_data)
        # Revenue growth -51.4%
        assert "-51.4" in ctx
        # Joyce should appear as top revenue
        assert "Joyce Mwanziu" in ctx


# ---------------------------------------------------------------------------
# Integration smoke test — full tool chain
# ---------------------------------------------------------------------------

class TestFullToolChain:
    def test_all_tools_run_without_error(self, deal_data):
        """Ensures all four tools execute on the same deal_data without raising."""
        fm = calculate_financial_metrics(deal_data)
        om = calculate_operational_metrics(deal_data)
        ed = get_entity_details("Joyce Mwanziu", deal_data)
        ef = explain_flagged_item("Peter Karanja", deal_data)

        assert fm["dscr"]["value"] is not None
        assert om["customer_concentration"]["top_customer_name"] == "Joyce Mwanziu Avia"
        assert ed["found"] is True
        assert ef["flagged"] is True

        print("\n=== INTEGRATION PASS ===")
        print(f"DSCR: {fm['dscr']['value']} — {fm['dscr']['assessment']}")
        print(f"Revenue: {fm['revenue_growth']['value_pct']}% — {fm['revenue_growth']['assessment']}")
        print(f"Top customer: {om['customer_concentration']['top_customer_name']} ({om['customer_concentration']['top_customer_pct']}%)")
        print(f"Joyce: {ed['profile']['pct_of_category']:.1f}% of revenue")
        print(f"Peter Karanja: {ef['total_flagged_transactions']} flagged txns")
        print(f"Operational summary: {om['summary']}")
        print(f"Financial summary: {fm['summary']}")


if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v", "--tb=short"])
