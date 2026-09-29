"""Tests for app.harness.run_parser_harness().

Two tiers:
  1. Unit tests against synthetic RawTransaction/ExtractionResult objects —
     no PDF fixture needed, run everywhere, include the negative cases.
  2. An integration test against a fabricated ABSA-format statement
     (no real customer data, generator carried over from PR #27), built at
     test time with reportlab and run through the live route_extract() path.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

from app.harness import (
    _check_balance_reconciliation,
    _check_currency_sourced,
    _check_fallback_overflow,
    _check_opening_closing_vs_header,
    _check_row_coverage,
    _parse_amount,
    run_parser_harness,
)
from app.models import ExtractionResult, RawTransaction, WarningItem

_GENERATOR = pathlib.Path(__file__).parent / "fixtures" / "generate_absa_synthetic.py"


def _result(*txns: RawTransaction, warnings: list[WarningItem] | None = None) -> ExtractionResult:
    return ExtractionResult(
        source_file="synthetic",
        extractor_type="absa_pdf",
        row_count=len(txns),
        extraction_status="success",
        warnings=warnings or [],
        raw_transactions=list(txns),
    )


def _txn(row_index: int, debit: str = "", credit: str = "", balance: str = "") -> RawTransaction:
    return RawTransaction(
        row_index=row_index,
        date_raw="2024-01-01",
        description="txn",
        debit_raw=debit,
        credit_raw=credit,
        balance_raw=balance,
        source_file="synthetic",
    )


class TestParseAmount:
    def test_plain(self):
        assert str(_parse_amount("1,500.25")) == "1500.25"

    def test_leading_minus_kept(self):
        assert str(_parse_amount("-385.95")) == "-385.95"

    def test_cr_dr_suffix(self):
        assert str(_parse_amount("1,500.00CR")) == "1500.00"
        assert str(_parse_amount("280.95DR")) == "-280.95"
        assert str(_parse_amount("280.95 DR")) == "-280.95"

    def test_blank_and_garbage(self):
        assert _parse_amount("") is None
        assert _parse_amount("nan") is None
        assert _parse_amount("n/a") is None


class TestBalanceReconciliation:
    def test_reconciles_clean_sequence(self):
        result = _result(
            _txn(0, balance="1000.00"),
            _txn(1, debit="100.00", balance="900.00"),
            _txn(2, credit="50.00", balance="950.00"),
        )
        assert _check_balance_reconciliation(result) is True

    def test_catches_broken_sequence(self):
        """Negative case: balance column doesn't match debit/credit math —
        this is the harness's teeth. A harness that always reports True
        regardless of input would pass this test incorrectly, which is
        exactly the failure mode this case exists to catch."""
        result = _result(
            _txn(0, balance="1000.00"),
            _txn(1, debit="100.00", balance="850.00"),  # should be 900.00
        )
        assert _check_balance_reconciliation(result) is False

    def test_catches_misdirected_amount(self):
        """Money in emitted as a debit: balance rises, extractor says debit."""
        result = _result(
            _txn(0, balance="277.00CR"),
            _txn(1, debit="5,360,000.00", balance="5,360,277.00CR"),
        )
        assert _check_balance_reconciliation(result) is False

    def test_overdrawn_minus_sign(self):
        """Original PR #27 parser stripped the minus and failed this."""
        result = _result(
            _txn(0, balance="100.00"),
            _txn(1, debit="300.00", balance="-200.00"),
            _txn(2, credit="250.00", balance="50.00"),
        )
        assert _check_balance_reconciliation(result) is True

    def test_overdrawn_dr_suffix(self):
        result = _result(
            _txn(0, balance="100.00CR"),
            _txn(1, debit="300.00", balance="200.00DR"),
            _txn(2, credit="250.00", balance="50.00CR"),
        )
        assert _check_balance_reconciliation(result) is True

    def test_blank_balance_rows_carried_forward(self):
        result = _result(
            _txn(0, balance="1000.00"),
            _txn(1, debit="100.00"),
            _txn(2, debit="50.00"),
            _txn(3, credit="10.00", balance="860.00"),
        )
        assert _check_balance_reconciliation(result) is True

    def test_blank_balance_rows_still_checked(self):
        result = _result(
            _txn(0, balance="1000.00"),
            _txn(1, debit="100.00"),
            _txn(2, credit="10.00", balance="950.00"),  # should be 910.00
        )
        assert _check_balance_reconciliation(result) is False

    def test_no_comparable_balance_is_not_a_pass(self):
        result = _result(_txn(0), _txn(1, debit="1.00"), _txn(2, credit="1.00"))
        assert _check_balance_reconciliation(result) is False

    def test_skips_single_row(self):
        result = _result(_txn(0, balance="1000.00"))
        assert _check_balance_reconciliation(result) == "skipped"


class TestRowCoverage:
    def test_passes_when_rows_have_content(self):
        result = _result(_txn(0, balance="1000.00"))
        assert _check_row_coverage(result) is True

    def test_fails_on_entirely_blank_row(self):
        blank = RawTransaction(
            row_index=0, date_raw="", description="", debit_raw="",
            credit_raw="", balance_raw="", source_file="synthetic",
        )
        result = _result(blank)
        assert _check_row_coverage(result) is False


class TestFallbackOverflow:
    def test_passes_under_threshold(self):
        result = _result(*[_txn(i, balance="1000.00") for i in range(20)],
                          warnings=[WarningItem(row_index=0, message="m", raw_text="")])
        assert _check_fallback_overflow(result) is True

    def test_fails_over_threshold(self):
        result = _result(*[_txn(i, balance="1000.00") for i in range(10)],
                          warnings=[WarningItem(row_index=i, message="m", raw_text="") for i in range(2)])
        assert _check_fallback_overflow(result) is False


class TestHarnessNeverRaises:
    def test_missing_file_reports_false_not_exception(self):
        digest = run_parser_harness("/nonexistent/path.pdf")
        assert digest["extraction"] is False
        assert "_error" in digest

    def test_skipped_only_means_inapplicable(self):
        """opening_closing_vs_header and currency_sourced are documented as
        always-skipped at this pipeline stage (see harness.py docstrings) —
        confirm they report the string 'skipped', not a silently-swallowed
        False that would have come from an exception."""
        result = _result(_txn(0, balance="1000.00"))
        assert _check_opening_closing_vs_header(result) == "skipped"
        assert _check_currency_sourced(result) == "skipped"


@pytest.fixture(scope="module")
def absa_synthetic_pdf(tmp_path_factory):
    pytest.importorskip("reportlab")
    spec = importlib.util.spec_from_file_location("generate_absa_synthetic", _GENERATOR)
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    return str(gen.build(tmp_path_factory.mktemp("harness") / "absa_synthetic.pdf"))


class TestAbsaSynthetic:
    def test_harness_all_pass(self, absa_synthetic_pdf):
        digest = run_parser_harness(absa_synthetic_pdf)
        failing = {k: v for k, v in digest.items() if v is False}
        assert not failing, f"failed checks: {digest}"
        assert digest["balance_reconciliation"] is True
        assert digest["determinism_5x"] is True
