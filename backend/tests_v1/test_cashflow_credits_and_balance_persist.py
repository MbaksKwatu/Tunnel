"""
PAR-86 (2026-09-30) — GBFund/Anthony accuracy report, two systemic bugs:

  Bug 1  monthly_cashflow() dropped every credit outside CASHFLOW_INFLOW_ROLES
         with no trace. monthly_excluded_credits() now reports the remainder.
  Bug 2  _parity_result_to_rows() dropped balance_cents, so year-end cash always
         fell back to fiscal-year net flow. Balance is now carried through, and
         the year-end read chains statements / resolves same-day order.

Pure-function tests plus one run of calculate_cash_position_reconciliation()
against an in-memory fake of the Supabase query builder.
"""
import os
import random
import sys

import pytest

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_ROOT = os.path.abspath(os.path.join(_BACKEND, os.pardir))
for p in (_BACKEND, _ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.v1.analytics import (
    CASHFLOW_INFLOW_ROLES,
    monthly_cashflow,
    monthly_excluded_credits,
)
from backend.v1.analysis import reconciliation_engine as re_
from backend.v1.parsing.parity_ingestion_client import _parity_result_to_rows, _raw_hash
from backend.v1.parsing.common import sort_rows


def _t(date, amt, role):
    return {"txn_id": f"{date}{amt}{role}", "txn_date": date, "amount_cents": amt, "role": role}


# ── Bug 1 ─────────────────────────────────────────────────────────────────────

def test_excluded_credits_reports_what_monthly_cashflow_drops():
    txns = [
        _t("2025-09-03", 1_000_000, "revenue_operational"),
        _t("2025-09-05", 1_376_771_300, "needs_review"),
        _t("2025-09-06", 500, "reversal_credit"),
        _t("2025-09-07", 700, "transfer"),
        _t("2025-09-08", 900, ""),
        _t("2025-09-09", -1_000, "supplier"),
        _t("2025-10-01", 200, "needs_review"),
    ]
    excl = monthly_excluded_credits(txns)
    assert [r["month"] for r in excl] == ["2025-09", "2025-10"]
    sep = excl[0]
    assert sep["excluded_credit_cents"] == 1_376_771_300 + 500 + 700 + 900
    # needs_review + unclassified are "pending"; reversal/transfer are classified non-inflow
    assert sep["pending_classification_cents"] == 1_376_771_300 + 900
    assert sep["by_role"] == {
        "needs_review": 1_376_771_300, "reversal_credit": 500,
        "transfer": 700, "unclassified": 900,
    }


def test_inflow_plus_excluded_equals_all_credits_every_month():
    rng = random.Random(7)
    roles = sorted(CASHFLOW_INFLOW_ROLES) + ["needs_review", "transfer", "reversal_credit", "other", ""]
    txns = [
        _t(f"2025-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}", rng.randint(-5_000_000, 5_000_000) or 1, rng.choice(roles))
        for _ in range(3000)
    ]
    cash = {r["month"]: r["inflow_cents"] for r in monthly_cashflow(txns)}
    excl = {r["month"]: r["excluded_credit_cents"] for r in monthly_excluded_credits(txns)}
    credits: dict = {}
    for t in txns:
        if t["amount_cents"] > 0:
            m = t["txn_date"][:7]
            credits[m] = credits.get(m, 0) + t["amount_cents"]
    for m, total in credits.items():
        assert cash.get(m, 0) + excl.get(m, 0) == total


def test_monthly_cashflow_contract_unchanged_by_this_fix():
    rows = monthly_cashflow([_t("2025-01-05", 500_000, "needs_review")])
    assert rows[0]["inflow_cents"] == 0  # still allow-listed; exclusion is reported, not re-included
    assert set(rows[0]) == {"month", "inflow_cents", "outflow_cents", "net_cents", "mom_change_bps", "mom_reliable"}


def test_excluded_credits_rejects_float_and_ignores_debits_and_undated():
    with pytest.raises(ValueError):
        monthly_excluded_credits([_t("2025-01-05", 1.5, "needs_review")])
    assert monthly_excluded_credits([_t("2025-01-05", -5, "needs_review"), {"amount_cents": 5, "role": "x"}]) == []


# ── Bug 2: mapper ─────────────────────────────────────────────────────────────

def _norm(date, debit, credit, balance):
    return {"date": date, "description": "X", "debit_cents": debit, "credit_cents": credit, "balance_cents": balance}


def test_mapper_carries_balance_and_omits_when_absent():
    rows = _parity_result_to_rows({"normalised_transactions": [
        _norm("2025-01-01", 0, 500, 10_500),
        _norm("2025-01-02", 200, 0, None),
    ]}, "doc-1")
    assert rows[0]["balance_cents"] == 10_500 and rows[0]["signed_amount_cents"] == 500
    assert "balance_cents" not in rows[1] and rows[1]["signed_amount_cents"] == -200


def test_raw_hash_is_identical_with_or_without_balance():
    """Hash contract: persisting balance must not change raw_transaction_hash."""
    with_bal = _parity_result_to_rows({"normalised_transactions": [
        _norm("2025-01-01", 0, 500, 10_500), _norm("2025-01-02", 200, 0, 10_300)]}, "doc-1")
    without = _parity_result_to_rows({"normalised_transactions": [
        _norm("2025-01-01", 0, 500, None), _norm("2025-01-02", 200, 0, None)]}, "doc-1")
    assert _raw_hash(sort_rows(with_bal)) == _raw_hash(sort_rows(without))
    assert [r["txn_id"] for r in with_bal] == [r["txn_id"] for r in without]  # txn ids unaffected


# ── Bug 2: balance helpers ────────────────────────────────────────────────────

def _r(i, date, signed, bal):
    return {"id": f"{i:04d}", "txn_date": date, "signed_amount_cents": signed, "balance_cents": bal}


def test_same_day_closing_row_is_order_independent():
    # opening 1000; three same-day rows: +500 -> 1500, -200 -> 1300, -400 -> 900
    day = [_r(1, "2025-12-31", 500, 1500), _r(2, "2025-12-31", -200, 1300), _r(3, "2025-12-31", -400, 900)]
    for seed in range(25):
        shuffled = [dict(r) for r in day]
        random.Random(seed).shuffle(shuffled)
        # random uuids: the old "order by id desc limit 1" would pick an arbitrary row
        for k, r in enumerate(shuffled):
            r["id"] = f"{random.Random(seed * 10 + k).randint(0, 9999):04d}"
        ye = re_._year_end_balance(shuffled, "2025-12-31")
        assert ye["balance_cents"] == 900 and ye["ambiguous"] is False


def test_same_day_cycle_is_flagged_ambiguous_not_silently_picked():
    # day nets to zero (1000 -> 1500 -> 1300 -> 1000): order genuinely unrecoverable
    day = [_r(1, "2025-12-31", 500, 1500), _r(2, "2025-12-31", -200, 1300), _r(3, "2025-12-31", -300, 1000)]
    assert re_._year_end_balance(day, "2025-12-31")["ambiguous"] is True


def test_year_end_ignores_rows_after_fiscal_end_and_none_if_all_after():
    rows = [_r(1, "2025-12-30", 100, 900), _r(2, "2026-01-02", 50, 950)]
    assert re_._year_end_balance(rows, "2025-12-31")["balance_cents"] == 900
    assert re_._year_end_balance([_r(1, "2026-01-02", 50, 950)], "2025-12-31") is None


def test_monthly_statements_of_one_account_chain_and_other_bank_stays_separate():
    jan = [_r(1, "2025-01-10", 100, 1100), _r(2, "2025-01-31", -100, 1000)]          # 1000 -> 1000
    feb = [_r(3, "2025-02-05", 500, 1500), _r(4, "2025-02-28", -250, 1250)]          # 1000 -> 1250
    mar = [_r(5, "2025-03-15", 750, 2000)]                                            # 1250 -> 2000
    other = [_r(6, "2025-02-01", 10, 90_010), _r(7, "2025-03-20", 5, 90_015)]         # separate bank
    spans = {d: re_._statement_span(r) for d, r in
             {"jan": jan, "feb": feb, "mar": mar, "other": other}.items()}
    chains = re_._chain_documents(spans)
    assert sorted(map(tuple, chains)) == [("jan", "feb", "mar"), ("other",)]


def test_document_with_no_continuity_is_its_own_account():
    a = [_r(1, "2025-01-31", 100, 1000)]
    b = [_r(2, "2025-02-28", 100, 7777)]  # opening 7677 != 1000
    spans = {"a": re_._statement_span(a), "b": re_._statement_span(b)}
    assert len(re_._chain_documents(spans)) == 2


# ── Bug 2: calculate_cash_position_reconciliation end-to-end (fake Supabase) ──

class _Q:
    def __init__(self, rows):
        self.rows, self._f, self._order, self._rng, self._neg = rows, [], [], None, False

    # builder
    def select(self, *_): return self
    def eq(self, c, v): self._f.append(lambda r: r.get(c) == v); return self
    def gte(self, c, v): self._f.append(lambda r: str(r.get(c)) >= v); return self
    def lte(self, c, v): self._f.append(lambda r: str(r.get(c)) <= v); return self
    def in_(self, c, vs): self._f.append(lambda r: r.get(c) in vs); return self
    def order(self, c, desc=False): self._order.append((c, desc)); return self
    def limit(self, n): self._rng = (0, n - 1); return self
    def range(self, a, b): self._rng = (a, b); return self
    def single(self): return self

    @property
    def not_(self): self._neg = True; return self
    def is_(self, c, _v):
        neg, self._neg = self._neg, False
        self._f.append((lambda r: r.get(c) is not None) if neg else (lambda r: r.get(c) is None))
        return self

    def execute(self):
        out = [r for r in self.rows if all(f(r) for f in self._f)]
        for c, d in reversed(self._order):
            out.sort(key=lambda r: str(r.get(c)), reverse=d)
        if self._rng:
            out = out[self._rng[0]: self._rng[1] + 1]
        return type("R", (), {"data": out})


class _FakeSB:
    def __init__(self, tables): self.t = tables
    def table(self, n): return _Q(self.t[n])


def _run(monkeypatch, docs, txns, declared=0):
    monkeypatch.setattr(re_, "_get_audited_financials", lambda _d: {
        "financial_year_start": "2025-01-01", "financial_year_end": "2025-12-31",
        "cash_and_equivalents_cents": declared, "cash_breakdown": {}})
    monkeypatch.setattr(re_, "_get_supabase", lambda: _FakeSB({"pds_documents": docs, "pds_raw_transactions": txns}))
    return re_.calculate_cash_position_reconciliation("deal-1")


def _tx(i, doc, date, signed, bal):
    return {"id": f"{i:05d}", "deal_id": "deal-1", "document_id": doc, "txn_date": date,
            "signed_amount_cents": signed, "balance_cents": bal}


def test_e2e_reads_statement_balance_not_net_flow_and_chains_monthly_pdfs(monkeypatch):
    docs = [{"id": "jan", "deal_id": "deal-1", "storage_url": "inline://jan.pdf"}, {"id": "feb", "deal_id": "deal-1", "storage_url": "inline://feb.pdf"}]
    txns = [
        _tx(1, "jan", "2025-01-10", -4_000, 96_000),   # opening 100_000
        _tx(2, "feb", "2025-02-10", -6_000, 90_000),   # continues: opening 96_000
        _tx(3, "feb", "2025-02-28", 10_000, 100_000),
    ]
    out = _run(monkeypatch, docs, txns, declared=100_000)
    assert out["method"] == "balance_column"
    assert out["total_bank_kes"] == 1000.0            # one account, closing balance — not 96_000 + 100_000
    assert [b["method"] for b in out["bank_balances"]] == ["balance_column"]
    assert out["variance_kes"] == 0.0


def test_e2e_flow_fallback_only_for_documents_with_no_balance(monkeypatch):
    docs = [{"id": "pdf", "deal_id": "deal-1", "storage_url": "inline://a.pdf"}, {"id": "csv", "deal_id": "deal-1", "storage_url": "inline://b.csv"}]
    txns = [
        _tx(1, "pdf", "2025-06-01", 500, 7_500),
        _tx(2, "csv", "2025-06-02", 300, None),
        _tx(3, "csv", "2025-06-03", -100, None),
    ]
    out = _run(monkeypatch, docs, txns)
    by_src = {b["source"]: b for b in out["bank_balances"]}
    assert by_src["a.pdf"]["method"] == "balance_column" and by_src["a.pdf"]["balance_cents"] == 7_500
    assert by_src["b.csv"]["method"] == "flow_derived" and by_src["b.csv"]["balance_cents"] == 200
    assert out["method"] == "flow_derived"  # downgraded only because a no-balance doc exists


def test_e2e_no_balance_anywhere_still_falls_back_exactly_as_before(monkeypatch):
    docs = [{"id": "d", "deal_id": "deal-1", "storage_url": "inline://x.pdf"}]
    txns = [_tx(1, "d", "2025-03-01", 800, None), _tx(2, "d", "2025-03-02", -300, None)]
    out = _run(monkeypatch, docs, txns)
    assert out["method"] == "flow_derived" and out["total_bank_kes"] == 5.0


# ── account grouping robustness (rows without a printed balance, concurrency) ──

def _span(rows, ub=None):
    return re_._statement_span(rows, ub)


def test_adjacent_statements_group_even_when_boundary_balance_is_missing():
    # Continuity cannot be proven (Feb's first balanced row is not Jan's closing), but the
    # ranges are contiguous and nothing runs concurrently -> one account.
    jan = [_r(1, "2025-01-10", 100, 1100), _r(2, "2025-01-31", -100, 1000)]
    feb = [_r(3, "2025-02-01", 500, 9999), _r(4, "2025-02-28", -250, 9749)]
    chains = re_._chain_documents({"jan": _span(jan), "feb": _span(feb)})
    assert sorted(map(tuple, chains)) == [("jan", "feb")]


def test_adjacency_is_disabled_when_documents_run_concurrently():
    # bank B overlaps bank A's later statements; adjacency must not link jan -> other
    jan = [_r(1, "2025-01-10", 100, 1100), _r(2, "2025-01-31", -100, 1000)]
    feb = [_r(3, "2025-02-05", 500, 1500), _r(4, "2025-02-28", -250, 1250)]
    other = [_r(6, "2025-02-01", 10, 90_010), _r(7, "2025-03-20", 5, 90_015)]
    chains = re_._chain_documents({"jan": _span(jan), "feb": _span(feb), "other": _span(other)})
    assert sorted(map(tuple, chains)) == [("feb", "jan"), ("other",)] or sorted(map(tuple, chains)) == [("jan", "feb"), ("other",)]


def test_overlapping_reupload_of_same_account_shares_rows_and_groups():
    a = [_r(1, "2025-01-10", 100, 1100), _r(2, "2025-06-30", -100, 1000)]
    b = [_r(2, "2025-06-30", -100, 1000), _r(3, "2025-12-31", 50, 1050)]  # same printed row
    assert len(re_._chain_documents({"a": _span(a), "b": _span(b)})) == 1


def test_days_with_unbalanced_rows_are_flagged_ambiguous():
    day = [_r(1, "2025-12-31", 500, 1500), _r(2, "2025-12-31", -400, 1100)]
    assert re_._year_end_balance(day, "2025-12-31")["ambiguous"] is False
    assert re_._year_end_balance(day, "2025-12-31", {"2025-12-31": 2})["ambiguous"] is True
