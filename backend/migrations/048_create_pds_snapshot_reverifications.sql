-- Migration 048: pds_snapshot_reverifications (PAR-86 export freshness loop)
--
-- Problem: POST /export short-circuits only when the latest snapshot looks
-- fresh (api.py _resolve_fresh_export). When a recompute reproduces a byte-
-- identical payload, export_snapshot() correctly reuses the existing snapshot
-- row -- but that row is IMMUTABLE (pds_snapshots_mutation_guard, migration
-- supabase/004), so its created_at, analysis_run_id and computation_fingerprint
-- can never be refreshed. Every freshness gate that reads them then fails
-- forever, and every deal open silently re-runs the ~55s pipeline and appends
-- another pds_analysis_runs row. (PAR-219's attempt to stamp the fingerprint
-- onto the reused row is itself an UPDATE on pds_snapshots and is rejected by
-- the same guard.)
--
-- Fix: record "this sealed snapshot was re-verified at T, by run R, under
-- computation fingerprint F" in a separate APPEND-ONLY table instead of
-- mutating the seal. The freshness check reads the latest row here, falling
-- back to the snapshot's own columns when none exists. Nothing in this table
-- is part of any hashed payload: sha256_hash / financial_state_hash are
-- unaffected.
--
-- Not an audit-grade seal and not exposed to clients: RLS is enabled with no
-- policies, so only the service role (the backend) can read or write it.
create table pds_snapshot_reverifications (
  id                      uuid primary key default gen_random_uuid(),
  deal_id                 uuid not null references pds_deals(id) on delete cascade,
  snapshot_id             uuid not null references pds_snapshots(id) on delete cascade,
  analysis_run_id         uuid not null references pds_analysis_runs(id) on delete cascade,
  computation_fingerprint text not null,
  -- When the verifying recompute STARTED reading its inputs (minus a small
  -- safety margin for clock skew), not when it finished: a document or
  -- override added during the ~55s compute must not be treated as covered.
  verified_at             timestamptz not null,
  created_at              timestamptz not null default now()
);

create index idx_pds_snapshot_reverifications_snapshot
  on pds_snapshot_reverifications (snapshot_id, verified_at desc);

alter table pds_snapshot_reverifications enable row level security;

comment on table pds_snapshot_reverifications is
  'PAR-86: append-only record that a sealed pds_snapshots row was re-verified '
  '(a recompute reproduced its exact sha256_hash). Read by export()''s '
  'freshness check instead of mutating the immutable snapshot. Service-role '
  'only (RLS enabled, no policies). Never part of any hashed payload.';
