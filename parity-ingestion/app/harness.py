"""
Per-parser-version verification harness.

Ports the check *concepts* named in the Request Parser Pipeline scoping doc's
Phase 0 against this service's own ExtractionResult/RawTransaction models —
it does not import backend/tests_v1/, which checks a later pipeline stage
(classified, role-tagged transactions) that doesn't exist yet at this point
in the pipeline. See the doc's §2b/§8.8 for why these are genuinely different
stages, not duplicated logic.

run_parser_harness() never raises. Each check resolves to True, False, or
the string "skipped" — and "skipped" must only ever mean "not applicable at
this pipeline stage," never "errored." Any exception inside a check is
caught and reported as False with the error message attached, so a bug never
silently presents as a pass.
"""
from __future__ import annotations

from typing import Callable, Optional, Union

from app.extractors.layout_config import LayoutConfig, extract_pdf_by_config
from app.extractors.router import route_extract
from app.models import ExtractionResult

CheckResult = Union[bool, str]


def _run_extraction(sample_file_path: str, config: Optional[LayoutConfig]) -> ExtractionResult:
    if config is None:
        result = route_extract(sample_file_path)
        if isinstance(result, dict):
            raise ValueError(f"route_extract returned UNSUPPORTED_FORMAT: {result}")
        return result
    return extract_pdf_by_config(sample_file_path, config)


def _check_balance_reconciliation(result: ExtractionResult) -> CheckResult:
    """Running balance must equal prev_balance + credit - debit for every
    consecutive pair where both balances parsed cleanly. Skips (does not
    fail) rows where balance_raw is blank or unparseable — that is a
    warning-level extraction-quality issue, tracked by
    _check_fallback_overflow, not a reconciliation break."""
    from app.extractors.layout_config import _try_parse_balance

    txns = result.raw_transactions
    if len(txns) < 2:
        return "skipped"

    prev_cents, _ = _try_parse_balance(txns[0].balance_raw)
    for t in txns[1:]:
        cur_cents, _ = _try_parse_balance(t.balance_raw)
        if prev_cents is None or cur_cents is None:
            prev_cents = cur_cents
            continue
        debit_cents, _ = _try_parse_balance(t.debit_raw)
        credit_cents, _ = _try_parse_balance(t.credit_raw)
        debit_cents = debit_cents or 0
        credit_cents = credit_cents or 0
        expected = prev_cents - debit_cents + credit_cents
        if expected != cur_cents:
            return False
        prev_cents = cur_cents
    return True


def _check_opening_closing_vs_header(result: ExtractionResult) -> CheckResult:
    """Inapplicable at this pipeline stage: ExtractionResult does not carry
    parsed statement header/footer totals to compare against — that data
    only exists in the raw PDF text, which the extractor discards once it
    has assembled transaction rows. Not a gap in this harness; a gap in
    what the extraction stage captures. Tracked, not faked."""
    return "skipped"


def _check_row_coverage(result: ExtractionResult) -> CheckResult:
    """No row should be entirely blank (date, description, debit, credit,
    balance all empty) — a row with nothing extracted is evidence a line was
    seen but silently dropped to noise rather than parsed or warned about."""
    for t in result.raw_transactions:
        if not any([t.date_raw, t.description, t.debit_raw, t.credit_raw, t.balance_raw]):
            return False
    return True


def _check_determinism(sample_file_path: str, config: Optional[LayoutConfig], runs: int = 5) -> CheckResult:
    first = _run_extraction(sample_file_path, config).model_dump_json()
    for _ in range(runs - 1):
        again = _run_extraction(sample_file_path, config).model_dump_json()
        if again != first:
            return False
    return True


def _check_fallback_overflow(result: ExtractionResult, threshold: float = 0.05) -> CheckResult:
    if result.row_count == 0:
        return "skipped"
    ratio = len(result.warnings) / result.row_count
    return ratio <= threshold


def _check_currency_sourced(result: ExtractionResult) -> CheckResult:
    """ExtractionResult.currency defaults to "KES" with no flag distinguishing
    "detected as KES" from "defaulted to KES" — this extractor (router.py's
    ABSA branch) does not yet wire detected currency through to the result.
    Reporting True here would be the exact silent-pass risk this harness is
    meant to prevent, so this is reported as skipped (inapplicable to the
    current extractor wiring) rather than guessed at as pass or fail."""
    return "skipped"


def run_parser_harness(
    sample_file_path: str,
    config: Optional[LayoutConfig] = None,
) -> dict[str, CheckResult]:
    """Run all Phase 0 checks against one extraction. config=None runs the
    live bespoke extractor via route_extract(); a passed config runs the
    new config-driven path via extract_pdf_by_config(). Never raises — any
    check that errors reports False with the error message, never 'skipped'."""
    digest: dict[str, CheckResult] = {}

    checks: list[tuple[str, Callable[[], CheckResult]]] = []

    try:
        result = _run_extraction(sample_file_path, config)
    except Exception as exc:
        return {
            "extraction": False,
            "_error": f"extraction itself failed: {exc}",
        }

    checks = [
        ("balance_reconciliation", lambda: _check_balance_reconciliation(result)),
        ("opening_closing_vs_header", lambda: _check_opening_closing_vs_header(result)),
        ("row_coverage", lambda: _check_row_coverage(result)),
        ("determinism_5x", lambda: _check_determinism(sample_file_path, config)),
        ("fallback_overflow", lambda: _check_fallback_overflow(result)),
        ("currency_sourced", lambda: _check_currency_sourced(result)),
    ]

    for name, fn in checks:
        try:
            digest[name] = fn()
        except Exception as exc:
            digest[name] = False
            digest[f"{name}_error"] = str(exc)

    return digest
