# Parity v1 — Pilot Operations Guide

## Prerequisites

- Python 3.9+
- Supabase project with v1 schema migrated (see Migration section)
- Environment variables set

## Environment Variables

```bash
# Required for live operation
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="eyJ..."

# Optional
export OPENAI_API_KEY="sk-..."  # Only needed for legacy endpoints
```

### Supabase-dependent tests

By default, three determinism-hardening tests (DB triggers, RLS) and the live E2E
smoke test are **skipped** when Supabase is not configured. To enable them:

```bash
export SUPABASE_TEST_MODE=1
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="eyJ..."   # service_role (admin): required for trigger + RLS tests
```

| Variable | Purpose |
|----------|---------|
| `SUPABASE_TEST_MODE` | Set to `1` to enable live Supabase tests. When set, connection failures are **hard errors** (no silent skip). |
| `SUPABASE_URL` | Project REST API URL. |
| `SUPABASE_SERVICE_ROLE_KEY` | Service-role key (bypasses RLS). Needed for admin checks (triggers, RLS metadata). |

When all three vars are present the skip count drops to **0**.

Run only Supabase-dependent tests:
```bash
python3 -m pytest backend/tests_v1/test_determinism_stress.py -k "trigger or rls or bypass" -v
python3 -m pytest backend/tests_v1/test_live_supabase_e2e.py -v
```

## Run Backend Locally

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Start server
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The v1 API is available at `http://localhost:8000/v1/`.

## Run Tests

```bash
cd backend

# Run all v1 tests (no Supabase needed — 3 Supabase tests will skip)
python3 -m pytest tests_v1/ -v

# Run specific test phases
python3 -m pytest tests_v1/test_openapi_contract.py -v    # Contract validation
python3 -m pytest tests_v1/test_v1_stress_harness.py -v   # Stress & perf
python3 -m pytest tests_v1/test_determinism_stress.py -v  # Determinism hardening
python3 -m pytest tests_v1/test_live_supabase_e2e.py -v   # Live E2E (needs SUPABASE_TEST_MODE=1)

# Quick smoke test
python3 -m pytest tests_v1/ -q
```

## Database Migration

The v1 schema uses `pds_`-prefixed tables to avoid collision with legacy tables.

### Option A: Supabase CLI

```bash
supabase db push --linked
```

### Option B: SQL Editor

Run the migration SQL in `supabase/migrations/003_pds_v1_prefixed.sql` in the Supabase SQL Editor in 3 blocks:
1. Enums + tables
2. Indexes + RLS policies
3. Immutability triggers

### Verify Migration

```sql
SELECT tablename FROM pg_tables
WHERE schemaname = 'public' AND tablename LIKE 'pds_%'
ORDER BY tablename;
```

Expected: 9 tables (`pds_analysis_runs`, `pds_deals`, `pds_documents`, `pds_entities`, `pds_overrides`, `pds_raw_transactions`, `pds_snapshots`, `pds_transfer_links`, `pds_txn_entity_map`).

### New: Dual-hash column

Apply `supabase/migrations/004_financial_state_hash.sql` to add `financial_state_hash` and the backfill-safe immutability guard.

Backfill instructions (safe to rerun):

```bash
python -m backend.v1.scripts.backfill_financial_state_hash
```

- The script scans all snapshots, recomputes `financial_state_hash` from `canonical_json`, and only fills missing values.
- The new trigger allows a single-field update from NULL -> NOT NULL on `financial_state_hash` only. All other updates/deletes remain blocked.
- For Supabase SQL Editor users: run the migration first, then run the backfill script from a machine with SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY configured.

## Pilot Workflow (Step by Step)

### 1. Create a Deal

```bash
curl -X POST http://localhost:8000/v1/deals \
  -d "currency=USD&name=Acme Corp"
```

### 2. Upload Financial Documents

```bash
curl -X POST http://localhost:8000/v1/deals/{deal_id}/documents \
  -F "file=@bank_statement.csv"
```

Supported formats: CSV, XLSX, PDF.

CSV must have columns: `date`, `amount`, `description`. Optional: `direction`, `account_id`.

### 3. Export (Create Snapshot)

```bash
curl -X POST http://localhost:8000/v1/deals/{deal_id}/export
```

Returns: `analysis_run` (metrics, confidence, tier) + `snapshot` (immutable, sha256-hashed).

### 4. Add Override (Optional)

```bash
curl -X POST http://localhost:8000/v1/deals/{deal_id}/overrides \
  -d "entity_id={entity_id}&weight=0.5&new_value=supplier"
```

Then re-export to get an updated snapshot.

### 5. Retrieve Snapshots

```bash
curl http://localhost:8000/v1/deals/{deal_id}/snapshots
```

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `CURRENCY_MISMATCH` (409) | Document contains ISO currency code different from deal | Re-upload with correct currency file, or create deal with matching currency |
| `INVALID_SCHEMA` (400) | CSV/XLSX missing `date`, `amount`, or `description` columns | Fix file headers |
| `NOT_FOUND` (404) | Deal/document/snapshot ID doesn't exist | Check UUID |
| `Immutable table: updates/deletes not allowed` | Tried to modify a snapshot or override in the DB | This is by design — snapshots and overrides are append-only |
| `abs_amount_cents generated column` | Tried to insert `abs_amount_cents` explicitly | The parser strips this automatically; don't include it |
| Server won't start | Port 8000 in use | `lsof -ti:8000 | xargs kill` |

## Architecture Notes

- **No floats** in the money pipeline. All amounts are `Decimal` → integer cents.
- **Deterministic hashing**: `json.dumps(sort_keys=True, separators=(",",":"))` → SHA-256.
- **Canonical sort order**: transactions sorted by `(txn_date, account_id, signed_amount_cents, normalized_descriptor, txn_id)`.
- **Transfer matching**: strict 1:1 rule (same abs amount, opposite sign, ≤2 day gap, different account, exactly one candidate).
- **Override model**: insert-only log. Latest override per entity (by `created_at`) wins.
