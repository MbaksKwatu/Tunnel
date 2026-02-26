# Parity v1 — Pilot Onboarding Checklist

Purpose: A step-by-step checklist for taking a fund from zero → deal → ingest → LIVE_DRAFT analysis → overrides → immutable snapshot, with deterministic guarantees and clear failure semantics.

## Pre-flight
- [ ] Migration applied: `003_pds_v1_prefixed.sql` (base schema)
- [ ] Migration applied: `004_financial_state_hash.sql` (dual-hash column + guard)
- [ ] Backfill run (if existing snapshots): `python -m backend.v1.scripts.backfill_financial_state_hash`
- [ ] Environment vars set: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`

## Flow (Happy Path)
1) Create deal
- [ ] POST `/v1/deals` with `currency` set
- Expected state: deal exists, `created_by` set, currency uppercased.

2) Upload document
- [ ] POST `/v1/deals/{deal_id}/documents` (CSV/XLSX)
- Expected: status `completed`; `currency_mismatch = false`; `raw_transaction_hash` returned; no floats (integer cents).
- Failure surfaces:
  - `CURRENCY_MISMATCH` (409) if ISO code conflicts with deal currency.
  - `INVALID_SCHEMA` (400) if headers missing or ambiguous dates.

3) Fetch document status + transactions
- [ ] GET `/v1/documents/{document_id}/status`
- [ ] GET `/v1/documents/{document_id}/transactions`
- Verify: integer cents, sign convention (inflows positive, outflows negative).

4) Fetch latest analysis (LIVE_DRAFT)
- [ ] GET `/v1/deals/{deal_id}/analysis/latest`
- Expected: LIVE_DRAFT exists (seeded on ingest); `reconciliation_status` likely `NOT_RUN` until export.

5) Export snapshot (idempotent by sha256_hash)
- [ ] POST `/v1/deals/{deal_id}/export`
- Expected: returns `analysis_run` + `snapshot` with both `sha256_hash` (provenance) and `financial_state_hash` (outcome-only).
- [ ] Re-export with no changes → same `snapshot.id` (idempotent on `sha256_hash`).

6) Optional overrides
- [ ] POST `/v1/deals/{deal_id}/overrides` (weight 0.5 or 1.0)
- [ ] Re-export → new snapshot with different `sha256_hash`, different `financial_state_hash`.
- [ ] Apply revert override (weight 0.0) → export again:
  - `financial_state_hash` matches pre-override state.
  - `sha256_hash` remains different (provenance preserved).

7) Metrics surface
- [ ] GET `/v1/system/health` (identity only)
- [ ] GET `/v1/system/metrics` (pipeline version + last export ms/at; deterministic and non-hashing)

## Allowed Failures & Expected Errors
- Currency conflict: 409 `CURRENCY_MISMATCH`
- Schema invalid: 400 `INVALID_SCHEMA`
- Missing deal/doc/snapshot: 404 `NOT_FOUND`
- No transactions on export: 400 `BAD_REQUEST` with `next_action=upload_new_file`
- Immutable tables: attempts to update/delete snapshots/overrides → `Immutable table: updates/deletes are not allowed`

## What to verify (per pilot run)
- [ ] `coverage_pct_bp` and `final_confidence_bp` are integers; tier in {Low, Medium, High}.
- [ ] `raw_transaction_hash` stable across re-ingests of the same content.
- [ ] `financial_state_hash` stable after apply→revert; differs when overrides change outcome.
- [ ] `sha256_hash` changes whenever override history changes (provenance).
- [ ] Transfer matching: no links when ambiguity exists (2+ candidates).
- [ ] No floats in any money field; no runtime dependence on ordering (sorted before hashing).

## Time Targets (non-binding, local/in-memory)
- Parse + export 500 txns: < 5 seconds (TestPerformance guardrail)
- Single export request: typically tens to hundreds of ms in-memory; network/storage not included.

## Smoke Commands
```bash
python3 -m pytest backend/tests_v1/test_pilot_onboarding_flow.py -v
python3 -m pytest backend/tests_v1/test_v1_stress_harness.py -v  # includes perf guardrail
python3 -m pytest backend/tests_v1/ -q                          # full suite (Supabase tests may skip)
```
