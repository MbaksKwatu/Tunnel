"""
Parity Review — declaration vs detection reconciliation.

Compares analyst-declared financials against what the pipeline detected.
All amounts in integer cents. Variance in basis points (1 bps = 0.01%).
No floats anywhere.
"""
from __future__ import annotations


def reconcile_declarations(
    declared_annual_revenue_cents: int | None,
    detected_annual_revenue_cents: int,
    declared_loans: list[dict] | None,
    detected_loan_drawdowns: list[dict],
    declared_kra_compliant: bool | None,
    detected_kra_compliance: str,
) -> dict:
    """
    Compare declared vs detected. Returns variance report.

    All amounts integer cents. Variance in basis points (1 bps = 0.01%).
    Revenue status: OK if variance <= 500 bps (5%), MATERIAL_VARIANCE otherwise.
    KRA reconciliation: CONFLICT, CONSISTENT, or None if not declared.
    """
    result: dict = {
        "revenue_reconciliation": None,
        "loan_reconciliation": None,
        "kra_reconciliation": None,
    }

    # Revenue variance
    if declared_annual_revenue_cents is not None and declared_annual_revenue_cents > 0:
        variance_cents = detected_annual_revenue_cents - declared_annual_revenue_cents
        variance_bps = (abs(variance_cents) * 10000) // declared_annual_revenue_cents
        result["revenue_reconciliation"] = {
            "declared_cents": declared_annual_revenue_cents,
            "detected_cents": detected_annual_revenue_cents,
            "variance_cents": variance_cents,
            "variance_bps": variance_bps,
            "status": "OK" if variance_bps <= 500 else "MATERIAL_VARIANCE",
            "direction": "OVER" if variance_cents > 0 else "UNDER",
        }

    # KRA reconciliation
    if declared_kra_compliant is not None:
        if declared_kra_compliant and detected_kra_compliance == "NOT_DETECTED":
            result["kra_reconciliation"] = {
                "status": "CONFLICT",
                "note": "Declared compliant but no KRA payments detected in statements.",
            }
        elif not declared_kra_compliant and detected_kra_compliance == "COMPLIANT":
            result["kra_reconciliation"] = {
                "status": "CONFLICT",
                "note": "Declared non-compliant but KRA payments found in statements.",
            }
        else:
            result["kra_reconciliation"] = {"status": "CONSISTENT"}

    return result
