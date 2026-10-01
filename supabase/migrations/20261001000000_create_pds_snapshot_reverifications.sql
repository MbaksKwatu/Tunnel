-- Mirrors backend/migrations/048_create_pds_snapshot_reverifications.sql so the
-- Supabase CLI path also covers it. See that file for the full rationale.
create table pds_snapshot_reverifications (
  id                      uuid primary key default gen_random_uuid(),
  deal_id                 uuid not null references pds_deals(id) on delete cascade,
  snapshot_id             uuid not null references pds_snapshots(id) on delete cascade,
  analysis_run_id         uuid not null references pds_analysis_runs(id) on delete cascade,
  computation_fingerprint text not null,
  verified_at             timestamptz not null,
  created_at              timestamptz not null default now()
);

create index idx_pds_snapshot_reverifications_snapshot
  on pds_snapshot_reverifications (snapshot_id, verified_at desc);

alter table pds_snapshot_reverifications enable row level security;
