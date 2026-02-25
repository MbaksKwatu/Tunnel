# Parity v1 Deterministic Pipeline Rules

## Transfer Detection (Locked)
- Pair only if all are true:
  - Same absolute amount
  - Opposite sign
  - Within 2 calendar days
  - Different `account_id`
  - Exactly one candidate match
- If more than one candidate matches, no pairing; all remain non-transfer.

## Coverage Calculation
- Denominator: `non_transfer_abs_total = Σ abs(signed_amount_cents)` over non-transfer txns.
- Numerator: `classified_abs_total = Σ abs(signed_amount_cents)` over non-transfer txns where role != `other`.
- `coverage_pct = classified_abs_total / non_transfer_abs_total` (handled as basis points in analysis_runs).
- If `non_transfer_abs_total == 0`: coverage_pct = 0; reconciliation.status = NOT_RUN; final_confidence_pct = 0; tier = Low.

## Missing Months Penalty
- Active period: earliest txn_date → latest txn_date (all accounts).
- Missing months counted only for full calendar months strictly inside active period.
- Penalty: 10% per missing month, capped at 50%.
- Leading/trailing partial months ignored; no expected-month heuristics.

## Override Penalty
- Major override (weight = 1.0): crossing revenue ↔ non-revenue boundary.
- Minor override (weight = 0.5): within non-revenue roles, or other ↔ non-revenue (excluding revenue).
- Impact formula (entity-level only):
  - `OverrideImpact = Σ (entity_abs_value / non_transfer_abs_total) × weight`
  - `entity_abs_value`: sum abs of non-transfer txns for the entity after overrides.
  - Cap: override_penalty_pct ≤ 70%.
- Only the latest override per entity applies; no txn-level weighting; no count weighting.

## Reconciliation Inputs (Accrual)
- Stored on deals:
  - `accrual_revenue_cents BIGINT`
  - `accrual_period_start DATE`
  - `accrual_period_end DATE`
  - `accrual_manually_entered BOOLEAN DEFAULT true`
- Reconciliation pct is only computed when accrual exists, overlap ≥ 60%, and accrual > 0; otherwise reconciliation_status = NOT_RUN or FAILED_OVERLAP.

## Confidence and Tier (Recap)
- base_confidence_pct = min(coverage_pct, reconciliation_pct) if reconciliation ok, else coverage_pct.
- Subtract penalties: missing_month_penalty (max 50%), override_penalty (max 70%).
- Clamp to ≥ 0; map to High/Medium/Low; if reconciliation not OK and tier would be High, cap to Medium (numeric unchanged).

## Canonical Sorting (Before Hashing)
- Sort transactions by: txn_date ASC, account_id ASC, signed_amount_cents ASC, normalized_descriptor ASC, txn_id ASC.
- Apply sorting before hashing or aggregation to ensure deterministic raw_transaction_hash.
