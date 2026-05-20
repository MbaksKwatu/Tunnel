"""
Proactive analysis — unit tests.
Run with: python -m pytest tests_v1/test_proactive_analysis.py -v
"""
import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from v1.parity_review.proactive_analysis import (
    generate_proactive_analysis,
    _identify_critical_issues,
    _identify_key_risks,
    _identify_strengths,
    _generate_recommendations,
)
from v1.parity_review.context import (
    _build_txn_role_map,
    _tag_transactions,
    _compute_entity_breakdown,
    _compute_monthly_cashflow,
)

_REVENUE_ROLES  = frozenset({"revenue_operational", "revenue_non_operational"})
_SUPPLIER_ROLES = frozenset({"supplier_payment"})
_PAYROLL_ROLES  = frozenset({"payroll"})
_TAX_ROLES      = frozenset({"tax_payment", "kra_payment"})
_REVIEW_ROLES   = frozenset({"needs_review", "other"})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_BUILDEX_CANONICAL = {
    "company_name": "Buildex Ltd",
    "transactions": [
        {"txn_id": "t001", "id": "t001", "signed_amount_cents": 109465000,
         "txn_date": "2025-02-10", "description": "Transfer from Joyce Mwanziu Avia"},
        {"txn_id": "t002", "id": "t002", "signed_amount_cents": 50000000,
         "txn_date": "2025-03-15", "description": "Payment received"},
        {"txn_id": "t003", "id": "t003", "signed_amount_cents": -200000000,
         "txn_date": "2025-04-01", "description": "RTGS: RTOBZN04517099"},
        {"txn_id": "t004", "id": "t004", "signed_amount_cents": -28733980,
         "txn_date": "2025-05-05", "description": "Loan repayment KCB"},
        {"txn_id": "t005", "id": "t005", "signed_amount_cents": -15000000,
         "txn_date": "2025-06-30", "description": "Salary payroll June"},
        {"txn_id": "t006", "id": "t006", "signed_amount_cents": -5000000,
         "txn_date": "2025-06-20", "description": "KRA tax payment"},
        {"txn_id": "t007", "id": "t007", "signed_amount_cents": 99900000,
         "txn_date": "2025-06-23", "description": "Peter Karanja A7F73Bce25E",
         "anomalies": [
             {"type": "POSSIBLE_CAPITAL_INJECTION", "severity": "CRITICAL",
              "reason": "Large inflow from rare entity with no reciprocal payments"}
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
        "revenue_growth_bps": -5140,
        "loan_repayment_burden_bps": 100,
        "payroll_stability": "SPARSE",
        "payroll_months_detected": 1,
        "kra_compliance": "PARTIAL",
        "statement_months": 12,
    },
    "currency": "KES",
}


def _build_deal_data(canonical=None):
    canonical = canonical or _BUILDEX_CANONICAL
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

    loan_total = sum(
        abs(t["signed_amount_cents"]) for t in tagged
        if t["role"] == "loan_repayment" and t["signed_amount_cents"] < 0
    )
    payroll_months = len({
        t["txn_date"][:7] for t in tagged
        if t["role"] in _PAYROLL_ROLES and t["txn_date"] and len(t["txn_date"]) >= 7
    })
    tax_months = len({
        t["txn_date"][:7] for t in tagged
        if t["role"] in _TAX_ROLES and t["txn_date"] and len(t["txn_date"]) >= 7
    })

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
        "loan_repayment_total_cents": loan_total,
        "payroll_months": payroll_months,
        "tax_months": tax_months,
        "n_months": canonical["metrics"]["statement_months"],
        "currency": "KES",
    }


@pytest.fixture
def deal_data():
    return _build_deal_data()


# ---------------------------------------------------------------------------
# Tests — generate_proactive_analysis
# ---------------------------------------------------------------------------

class TestGenerateProactiveAnalysis:
    def test_full_analysis_contains_key_sections(self, deal_data):
        analysis = generate_proactive_analysis(deal_data)
        assert "CRITICAL ISSUES" in analysis or "KEY RISKS" in analysis or "STRENGTHS" in analysis
        assert "FINANCIAL SUMMARY" in analysis
        assert "What would you like to explore further?" in analysis

    def test_markdown_formatted(self, deal_data):
        analysis = generate_proactive_analysis(deal_data)
        assert "##" in analysis
        assert "•" in analysis

    def test_company_name_from_canonical(self, deal_data):
        analysis = generate_proactive_analysis(deal_data)
        assert "Buildex" in analysis


# ---------------------------------------------------------------------------
# Tests — _identify_critical_issues
# ---------------------------------------------------------------------------

class TestCriticalIssues:
    def test_revenue_decline_flagged(self, deal_data):
        from v1.parity_review.tools.financial_metrics import calculate_financial_metrics
        from v1.parity_review.tools.operational_metrics import calculate_operational_metrics
        financial = calculate_financial_metrics(deal_data)
        operational = calculate_operational_metrics(deal_data)
        issues = _identify_critical_issues(deal_data, financial, operational)
        assert any("revenue" in i.lower() and "decline" in i.lower() for i in issues)

    def test_weak_dscr_flagged(self):
        financial = {"dscr": {"value": 1.1}, "revenue_growth": {"value_pct": 5.0},
                     "burn_rate": {"negative_months": 0, "total_months": 12}}
        issues = _identify_critical_issues({"tagged": [], "currency": "KES"}, financial, {})
        assert any("dscr" in i.lower() for i in issues)

    def test_capital_injection_anomaly_flagged(self, deal_data):
        from v1.parity_review.tools.financial_metrics import calculate_financial_metrics
        from v1.parity_review.tools.operational_metrics import calculate_operational_metrics
        financial = calculate_financial_metrics(deal_data)
        operational = calculate_operational_metrics(deal_data)
        issues = _identify_critical_issues(deal_data, financial, operational)
        assert any("peter karanja" in i.lower() for i in issues)


# ---------------------------------------------------------------------------
# Tests — _identify_key_risks
# ---------------------------------------------------------------------------

class TestKeyRisks:
    def test_customer_concentration(self, deal_data):
        from v1.parity_review.tools.operational_metrics import calculate_operational_metrics
        operational = calculate_operational_metrics(deal_data)
        risks = _identify_key_risks(deal_data, operational)
        assert any("concentration" in r.lower() for r in risks)
        assert any("Joyce Mwanziu" in r for r in risks)

    def test_sparse_payroll_flagged(self, deal_data):
        from v1.parity_review.tools.operational_metrics import calculate_operational_metrics
        operational = calculate_operational_metrics(deal_data)
        risks = _identify_key_risks(deal_data, operational)
        assert any("payroll" in r.lower() for r in risks)


# ---------------------------------------------------------------------------
# Tests — _identify_strengths
# ---------------------------------------------------------------------------

class TestStrengths:
    def test_strong_dscr_highlighted(self):
        financial = {"dscr": {"value": 2.5}, "revenue_growth": {"value_pct": 0},
                     "loan_burden": {"value_pct": 1.0},
                     "cash_flow_volatility": {"assessment": "Stable (<25%)"}}
        strengths = _identify_strengths(
            {"csi": {}, "metrics": {}, "tax_months": 0}, financial, {}
        )
        assert any("dscr" in s.lower() and "strong" in s.lower() for s in strengths)

    def test_low_loan_burden_highlighted(self):
        financial = {"dscr": {"value": None}, "revenue_growth": {"value_pct": 0},
                     "loan_burden": {"value_pct": 2.0},
                     "cash_flow_volatility": {"assessment": ""}}
        strengths = _identify_strengths(
            {"csi": {}, "metrics": {}, "tax_months": 0}, financial, {}
        )
        assert any("loan burden" in s.lower() for s in strengths)


# ---------------------------------------------------------------------------
# Tests — _generate_recommendations
# ---------------------------------------------------------------------------

class TestRecommendations:
    def test_critical_issues_trigger_recommendations(self):
        issues = ["Revenue declined 51.4% — needs explanation"]
        recs = _generate_recommendations(issues, [])
        assert any("critical" in r.lower() for r in recs)
        assert any("revenue" in r.lower() for r in recs)

    def test_no_issues_positive_guidance(self):
        recs = _generate_recommendations([], [])
        assert any("healthy" in r.lower() for r in recs)

    def test_concentration_risk_recommendation(self):
        risks = ["Joyce represents 68.6% of revenue (HIGH customer concentration)"]
        recs = _generate_recommendations([], risks)
        assert any("concentration" in r.lower() for r in recs)


# ---------------------------------------------------------------------------
# Integration — proactive analysis on Buildex-like data
# ---------------------------------------------------------------------------

class TestProactiveIntegration:
    def test_buildex_analysis_surfaces_key_findings(self, deal_data):
        analysis = generate_proactive_analysis(deal_data)

        assert "🔴" in analysis
        assert "⚠️" in analysis
        assert "DSCR" in analysis
        assert "Revenue" in analysis

        print("\n=== PROACTIVE ANALYSIS OUTPUT ===")
        print(analysis)


if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v", "--tb=short"])
