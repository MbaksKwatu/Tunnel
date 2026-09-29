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

Originally written on PR #27 (21 Jun 2026) alongside the config-driven
extraction pilot. Revived on its own: the `config=` path (layout_config.py)
is not part of this module — run_parser_harness() checks the live extractor
that route_extract() picks. Balance parsing was also corrected here: the
original stripped signs and ignored "CR"/"DR" suffixes, which reported
false reconciliation breaks on any overdrawn statement (verified: ABSA,
Equity F1, Co-op real statements).
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Callable, Optional, Union

from app.extractors.router import route_extract
from app.models import ExtractionResult

CheckResult = Union[bool, str]

_DRCR_SUFFIX = re.compile(r"\s*(CR|DR)$", re.IGNORECASE)


def _run_extraction(sample_file_path: str) -> ExtractionResult:
    result = route_extract(sample_file_path)
    if isinstance(result, dict):
        raise ValueError(f"route_extract returned {result.get('status')}: {result}")
    return result


def _parse_amount(raw: str) -> Optional[Decimal]:
    """Signed exact amount. Keeps a leading "-" (overdrawn balance) and
    treats a "DR" suffix as negative, "CR" as positive (Co-op prints
    "1,500.00CR" / "280.95DR"). Returns None for blank or unparseable."""
    s = (raw or "").replace(",", "").strip()
    if not s or s.lower() == "nan":
        return None
    sign = 1
    m = _DRCR_SUFFIX.search(s)
    if m:
        sign = -1 if m.group(1).upper() == "DR" else 1
        s = s[: m.start()].strip()
    try:
        return sign * Decimal(s)
    except InvalidOperation:
        return None


def _check_balance_reconciliation(result: ExtractionResult) -> CheckResult:
    """Running balance must equal prev_balance + credit - debit, exactly.

    debit_raw/credit_raw are magnitudes (the normaliser's contract: direction
    comes from the field, not the sign), so their signs are dropped;
    balances keep theirs.

    Rows with a blank/unparseable balance don't break the chain: their
    movement is carried forward and checked against the next printed
    balance (SCB prints a balance on only some rows). Fails if the whole
    statement offers no comparable balance at all — no evidence is not a
    pass."""
    txns = result.raw_transactions
    if len(txns) < 2:
        return "skipped"

    prev = _parse_amount(txns[0].balance_raw)
    carried = Decimal(0)
    compared = 0
    for t in txns[1:]:
        debit = abs(_parse_amount(t.debit_raw) or 0)
        credit = abs(_parse_amount(t.credit_raw) or 0)
        carried += credit - debit
        cur = _parse_amount(t.balance_raw)
        if cur is None:
            continue
        if prev is not None:
            compared += 1
            if prev + carried != cur:
                return False
        prev = cur
        carried = Decimal(0)
    return compared > 0


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


def _check_determinism(sample_file_path: str, runs: int = 5) -> CheckResult:
    first = _run_extraction(sample_file_path).model_dump_json()
    for _ in range(runs - 1):
        again = _run_extraction(sample_file_path).model_dump_json()
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
    "detected as KES" from "defaulted to KES". Reporting True here would be
    the exact silent-pass risk this harness is meant to prevent, so this is
    reported as skipped rather than guessed at as pass or fail."""
    return "skipped"


def run_parser_harness(sample_file_path: str) -> dict[str, CheckResult]:
    """Run all Phase 0 checks against the live extractor route_extract()
    picks for this file. Never raises — any check that errors reports False
    with the error message, never 'skipped'."""
    digest: dict[str, CheckResult] = {}

    try:
        result = _run_extraction(sample_file_path)
    except Exception as exc:
        return {
            "extraction": False,
            "_error": f"extraction itself failed: {exc}",
        }

    checks: list[tuple[str, Callable[[], CheckResult]]] = [
        ("balance_reconciliation", lambda: _check_balance_reconciliation(result)),
        ("opening_closing_vs_header", lambda: _check_opening_closing_vs_header(result)),
        ("row_coverage", lambda: _check_row_coverage(result)),
        ("determinism_5x", lambda: _check_determinism(sample_file_path)),
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
