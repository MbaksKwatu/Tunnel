"""
PAR-241 — Top Customers concentration table, in the LIVE render path.

PR #212's Sept 4 fix relabeled "Top revenue entities" -> "Top customers" and
added the 10-row cap + empty-state fallback, but only inside
backend/v1/core/pdf_generator.py — a reportlab generator whose only two call
sites in api.py are commented out. Every real PDF (GET /deals/{id}/report,
POST /deals/{id}/snapshot/pdf/jobs) renders through
snapshot_context.py + snapshot_html_renderer.py + templates/snapshot.html
instead, which had no customer/revenue-entity table at all until this change.

Mirrors test_par226_supplier_ranked_table.py exactly, one section over: same
fixture shape, same assertions, revenue side instead of supplier side.
"""
from __future__ import annotations

from typing import Any, Dict, List

from v1.analysis.snapshot_context import (
    DEFAULT_SUPPLIER_CONCENTRATION_CONFIG,
    CustomerEntry,
    _build_customer_revenue,
)
from v1.analysis.snapshot_html_renderer import _customer_revenue_ctx_from


def _txn(role: str, signed: int, entity_id: str) -> Dict[str, Any]:
    return {"role": role, "signed": signed, "abs": abs(signed), "entity_id": entity_id}


def _real_shape_txns() -> List[Dict[str, Any]]:
    # Same shape as test_par226's supplier fixture (6 named + 20-strong tail),
    # revenue_operational inflows (signed > 0) instead of supplier outflows.
    customers = [
        ("acme_ltd", 20_261_538, 13),
        ("beta_corp", 250_000_000, 1),
        ("gamma_inc", 200_000_000, 1),
        ("delta_co", 25_616_667, 6),
        ("epsilon_llc", 153_500_000, 1),
        ("zeta_ent", 149_600_000, 1),
        # long tail — 20 more small customers, to confirm the top-10 cutoff
        # actually caps the table rather than rendering everything.
    ] + [(f"tail_{i}", 10_000_00, 1) for i in range(20)]

    txns = []
    for eid, amount, count in customers:
        for _ in range(count):
            txns.append(_txn("revenue_operational", amount, eid))
    return txns


def test_top_n_ranked_by_total_desc_capped_at_ten():
    cr = _build_customer_revenue(
        _real_shape_txns(),
        entity_name_by_id={
            "acme_ltd": "ACME LTD PAYMENT REF001",
            "beta_corp": "BETA CORP INVOICE 442",
            "gamma_inc": "GAMMA INC SETTLEMENT",
            "delta_co": "DELTA CO RECURRING",
            "epsilon_llc": "EPSILON LLC TRANSFER",
            "zeta_ent": "ZETA ENTERPRISES",
        },
        config=DEFAULT_SUPPLIER_CONCENTRATION_CONFIG,
    )

    assert cr.available is True
    assert cr.top_n is not None
    # 26 distinct customers computed; table caps at 10, not the full list.
    assert cr.counterparty_count == 26
    assert len(cr.top_n) == 10

    # Ranked strictly descending by total value.
    totals = [row.total.cents for row in cr.top_n]
    assert totals == sorted(totals, reverse=True)

    # Rank #1 matches the largest customer.
    assert cr.top_n[0].name == "ACME LTD PAYMENT REF001"
    assert cr.top_n[0].txn_count == 13

    # Every entry carries name/count/amount only — no interpretive field.
    for row in cr.top_n:
        assert isinstance(row, CustomerEntry)
        assert row.share.value == row.total.cents / cr.total.cents


def test_diversified_narrative_names_the_figure():
    # Many small, roughly-even customers -> DIVERSIFIED bucket (top share < 15%).
    txns = [_txn("revenue_operational", 10_000_00, f"c{i}") for i in range(40)]
    cr = _build_customer_revenue(txns, entity_name_by_id={}, config=DEFAULT_SUPPLIER_CONCENTRATION_CONFIG)

    assert cr.concentration == "DIVERSIFIED"
    top_pct = cr.top_share.value * 100
    assert f"{top_pct:.1f}%" in cr.narrative
    assert str(cr.counterparty_count) in cr.narrative
    assert "customer" in cr.narrative.lower()


def test_renderer_ctx_exposes_rows_for_template():
    cr = _build_customer_revenue(
        _real_shape_txns(),
        entity_name_by_id={"acme_ltd": "ACME LTD"},
        config=DEFAULT_SUPPLIER_CONCENTRATION_CONFIG,
    )
    ctx = _customer_revenue_ctx_from(cr)

    assert len(ctx["rows"]) == 10
    first = ctx["rows"][0]
    assert first["name"] == "ACME LTD"
    assert first["txn_count"] == 13
    assert "KES" in first["total_str"]
    assert first["pct_str"].endswith("%")


def test_unavailable_state_has_no_rows_key_crash():
    cr = _build_customer_revenue([], entity_name_by_id={}, config=DEFAULT_SUPPLIER_CONCENTRATION_CONFIG)
    ctx = _customer_revenue_ctx_from(cr)
    assert ctx == {"available": False}


def test_template_renders_fallback_text_not_silent_vanish():
    """The empty-state branch in templates/snapshot.html must render literal
    'No concentration data available.' rather than the section disappearing
    with no trace — same requirement PAR-241's original fix applied to
    pdf_generator.py, now checked against the file the template actually is."""
    import os
    template_path = os.path.join(
        os.path.dirname(__file__), os.pardir, "v1", "templates", "snapshot.html"
    )
    with open(template_path) as f:
        html = f.read()
    assert "Top Customers" in html
    assert "customer_revenue.available" in html
    assert "No concentration data available." in html
