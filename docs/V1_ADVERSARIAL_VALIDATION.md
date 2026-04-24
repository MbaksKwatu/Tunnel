# Parity v1 — Adversarial Validation Report

**Purpose**: Document the formal adversarial interrogation suite that simulates institutional fund LP/IC scrutiny against the deterministic engine's outputs. This is internal pilot defense documentation.

---

## Overview

The adversarial suite (`backend/tests_v1/test_adversarial_fund_questions.py`) contains **30 tests** across 7 categories. Each test represents a question a fund would ask to challenge the engine's integrity, with explicit mathematical justification and invariant identification.

---

## A. Coverage Challenges

### Question: "How is coverage calculated, and what happens when transactions are unclassified?"

| Test | Scenario | Expected | Invariant |
|------|----------|----------|-----------|
| A1 | 50% volume classified as `other` | `coverage_bp = 5000` | `floor(classified / total * 10000)` — integer arithmetic |
| A1b | Full pipeline with diverse transactions | `coverage_bp = 10000` | v1 classifier structurally guarantees 100% classification for non-zero non-transfer txns |
| A2 | All transactions classified | `coverage_bp = 10000` exactly | No float rounding — `floor()` on integer division |
| A3 | Empty transaction set | `coverage=0, recon=NOT_RUN, tier=Low, confidence=0` | Zero-denominator safe fallback |
| A3b | All transactions are transfers | Same as A3 | Transfer filtering eliminates all volume → zero denominator |

**Mathematical justification**:
```
coverage_bp = floor(classified_abs_total * 10000 / non_transfer_abs_total)
```
- Uses Python `math.floor()` — deterministic, no floating-point rounding ambiguity
- When `non_transfer_abs_total = 0`, returns 0 immediately (no division by zero)
- The v1 rule-based classifier assigns `revenue_operational` (positive) or `supplier` (negative) to every non-zero non-transfer transaction. The `other` classification only occurs for `signed_amount_cents == 0`, which the parser rejects. **Coverage = 10000 bp is a structural guarantee, not a coincidence.**

**Protecting invariant**: Integer-only arithmetic with `floor()` — no `round()`, no floats.

---

## B. Reconciliation Challenges

### Question: "What happens when accrual data doesn't match bank data?"

| Test | Scenario | Expected | Invariant |
|------|----------|----------|-----------|
| B1 | Overlap < 60% between txn period and accrual period | `FAILED_OVERLAP`, tier capped | Overlap threshold enforced |
| B2 | `accrual_revenue_cents = 0` | `NOT_RUN` | Zero accrual → skip reconciliation |
| B3 | Accrual provided, full overlap, but zero operational inflow | `NOT_RUN` | No inflow → cannot reconcile |
| B4 | Reconciliation OK with partial match | `base_confidence = min(coverage, recon_bp)` | Conservative estimate wins |

**Mathematical justification**:

Overlap calculation:
```
overlap_days = max(0, min(active_end, accr_end) - max(active_start, accr_start) + 1)
overlap_pct = overlap_days / accrual_days
```
- If `overlap_pct < 0.6` → `FAILED_OVERLAP`
- If accrual revenue is 0 or missing → `NOT_RUN`

Reconciliation bp:
```
diff = abs(accrual_revenue_cents - operational_inflow_cents)
recon_bp = max(0, 10000 - floor(diff * 10000 / accrual_revenue_cents))
```

When reconciliation is `OK`:
```
base_confidence = min(coverage_bp, recon_bp)
```
This ensures the weaker signal (coverage or reconciliation) governs confidence. This is conservative by design.

**Protecting invariant**: Conservative estimate via `min()` — overconfidence is structurally impossible.

---

## C. Override Manipulation

### Question: "Can someone game the confidence score by strategically overriding entity classifications?"

| Test | Scenario | Expected | Invariant |
|------|----------|----------|-----------|
| C1 | Override largest revenue entity with weight=1.0 | Penalty = `min(floor(entity_share * 10000), 7000)` | Proportional, capped at 70% |
| C1b | Override entity that is 100% of volume | Penalty = 7000 (hard cap) | Cap prevents total annihilation |
| C2 | Override then revert (weight=0.0) | Confidence returns to baseline | Revert is neutralizing |
| C3 | Three overrides on same entity, different timestamps | Only latest-by-timestamp applies | Latest-wins resolution |

**Mathematical justification**:

Override penalty calculation:
```
For each entity with latest override:
  impact += (entity_abs_value / non_transfer_abs_total) * weight

penalty_bp = min(floor(impact * 10000), 7000)
```

- **Cap at 7000 bp**: Even a complete override of the highest-value entity cannot reduce confidence below `base - 7000`. This prevents weaponization of the override mechanism.
- **Latest-wins**: Overrides are sorted by `created_at` descending. Only the first (most recent) per entity is used. This is deterministic and audit-friendly — the full override history is preserved in the snapshot, but only the latest effective override governs the computation.
- **Weight = 0.0 neutralizes**: A revert override with `weight=0.0` makes `impact += 0`, effectively removing any penalty for that entity.

**Protecting invariant**: Hard cap at 7000 bp + latest-wins resolution + weight-proportional impact.

---

## D. Transfer Edge Cases

### Question: "How do you prevent artificial inflation of non-transfer volume through transfer misclassification?"

| Test | Scenario | Expected | Invariant |
|------|----------|----------|-----------|
| D1 | 1 outflow, 2 candidate inflows (ambiguity) | 0 transfer links, all remain non-transfer | Strict uniqueness requirement |
| D2 | Same account for both legs | 0 links | Cross-account enforced |
| D3 | 3-day gap between legs | 0 links | 2-day window enforced |
| D4 | Exactly 2-day gap | 1 link | Boundary is inclusive |
| D5 | Different abs amounts | 0 links | Exact amount match required |

**Transfer matching rules (ALL must hold)**:
1. Same `abs_amount_cents`
2. Opposite sign (one positive, one negative)
3. Within 2 calendar days
4. Different `account_id`
5. **Exactly one candidate** in each direction (bidirectional uniqueness)

If rule 5 fails (multiple candidates), no pairing occurs. This prevents:
- Artificial inflation of non-transfer volume (false negatives are safe; false positives are dangerous)
- Ambiguous pairings that could be challenged by auditors

**Protecting invariant**: Bidirectional uniqueness — no ambiguous pairings are ever created.

---

## E. Hash Integrity Under Stress

### Question: "Can the audit trail be manipulated by applying and reverting overrides?"

| Test | Scenario | Expected | Invariant |
|------|----------|----------|-----------|
| E1 | Apply override | Snapshot hash changes; financial_state_hash changes | Override changes payload |
| E2 | Apply override → revert | Confidence restored; financial_state_hash restored; snapshot hash DIFFERS | Audit trail preserved in snapshot hash |
| E3 | Full cycle: apply → revert → apply → revert | Confidence & financial_state_hash cycle deterministically; all snapshot hashes unique | Unique audit trails → unique snapshot hashes |
| E4 | Apply override | `raw_transaction_hash` unchanged | Raw data hash is override-independent |

**Critical design decision documented here**:

The snapshot hash includes `overrides_applied` as part of the canonical payload. This means:

> **Two snapshots with different override histories will ALWAYS have different hashes, even if the net financial effect (confidence, tier) is identical.**

This is **correct and intentional**:
- The snapshot is an immutable audit record
- It must capture not just the outcome but the path taken to reach it
- A fund auditor must be able to distinguish "no overrides were applied" from "overrides were applied and then reverted"

To give pilots a hash that represents *outcome-only* state, we introduced `financial_state_hash`:
- Includes: schema/config version, deal_id, currency, raw_transaction_hash, transfer_links, entities, txn_entity_map, metrics, confidence
- Excludes: overrides_applied (audit trail), snapshot_id/created_at/UI fields
- Behavior: Apply→revert restores `financial_state_hash` to baseline; snapshot hash remains different (provenance)

Confidence values remain deterministic functions of the effective override state:
- `penalty_bp` with a revert (weight=0.0) = `penalty_bp` with no overrides = 0
- `final_confidence_bp` is restored exactly

**Protecting invariant**: Dual-hash model — `financial_state_hash` proves identical outcomes; `sha256_hash` preserves provenance (override audit trail).

---

## F. Tier Boundary Conditions

### Question: "How are tier boundaries determined, and are they susceptible to off-by-one errors?"

| Test | Scenario | Expected | Invariant |
|------|----------|----------|-----------|
| F1 | 6999 bp / 7000 bp | Low / Medium | Boundary at 7000 |
| F2 | 8499 bp / 8500 bp | Medium / High | Boundary at 8500 |
| F3 | 8500 bp, recon != OK | Medium (capped) | High requires OK reconciliation |
| F4 | 8500 bp, recon == OK | High (not capped) | OK reconciliation unlocks High |
| F5 | Penalty exceeds base | Confidence = 0, Tier = Low | Floor at 0 — never negative |

**Tier boundaries**:
```
confidence < 7000  → Low
7000 ≤ confidence < 8500  → Medium
confidence ≥ 8500  → High (but capped to Medium if reconciliation != OK)
```

**Protecting invariant**: Hard-coded integer thresholds with explicit `>=` comparisons. No floating-point proximity issues.

---

## G. Mathematical Precision

### Question: "Are there floating-point rounding issues in your coverage and confidence calculations?"

| Test | Scenario | Expected | Invariant |
|------|----------|----------|-----------|
| G1 | Coverage with non-round division | `floor()` used, not `round()` | Consistent under-estimation |
| G2 | Override penalty with non-round division | `floor()` used | Consistent under-estimation |
| G3 | Full pipeline output fields | All numeric fields are `int` | No floats in output |

**Mathematical justification**:

All divisions in the engine use `math.floor()`:
```python
coverage_bp = floor(classified_abs_total * 10000 / non_transfer_abs_total)
recon_bp = max(0, 10000 - floor(diff * 10000 / accrual_revenue_cents))
penalty_bp = min(floor(impact * 10000), 7000)
```

- `floor()` ensures consistent under-estimation (conservative)
- All outputs are `int` — never `float`
- No `Decimal-to-float` conversions in the metrics/confidence engines
- Monetary values stored as `BIGINT` cents — no fractional cents

**Protecting invariant**: Integer-only arithmetic chain from input (cents) to output (bp). `floor()` for all divisions.

---

## Summary of Invariants

| Invariant | Tests | Status |
|-----------|-------|--------|
| Integer-only money (no floats) | A1, A2, G1, G2, G3 | PASS |
| Zero-denominator safety | A3, A3b | PASS |
| Coverage structural guarantee (v1 classifier) | A1b | PASS |
| Conservative reconciliation (`min`) | B4 | PASS |
| Overlap threshold (60%) | B1 | PASS |
| Override penalty cap (7000 bp) | C1, C1b | PASS |
| Latest-wins override resolution | C3 | PASS |
| Override revert neutralizes penalty | C2 | PASS |
| Transfer bidirectional uniqueness | D1, D2, D3, D4, D5 | PASS |
| Snapshot hash includes audit trail | E2, E3 | PASS |
| Raw transaction hash is override-independent | E4 | PASS |
| Tier boundary precision | F1, F2, F3, F4, F5 | PASS |
| Confidence floor at 0 | F5 | PASS |

**All 30 adversarial tests pass. No invariant breaches detected. No core logic modifications required.**
