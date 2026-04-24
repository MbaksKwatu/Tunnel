-- Dual-hash hardening: add financial_state_hash to pds_snapshots
-- Scope:
--   - financial_state_hash: outcome-only hash (excludes override audit trail)
--   - sha256_hash: provenance hash (includes overrides_applied)
-- Idempotent: IF NOT EXISTS guards used.

-- 1) Add column (nullable for backfill), then index for same-state lookup
alter table if exists pds_snapshots
  add column if not exists financial_state_hash text;

create index if not exists idx_pds_snapshots_fin_state
  on pds_snapshots(deal_id, financial_state_hash);

-- 2) Immutability with controlled backfill:
--    Allow a single-field update from NULL -> NOT NULL on financial_state_hash
--    while keeping all other columns identical. All other updates/deletes remain blocked.
create or replace function pds_snapshots_mutation_guard()
returns trigger language plpgsql as $$
begin
  if tg_op = 'UPDATE' then
    if old.financial_state_hash is null
       and new.financial_state_hash is not null
       and old.sha256_hash = new.sha256_hash
       and old.canonical_json = new.canonical_json
       and old.deal_id = new.deal_id
       and old.analysis_run_id = new.analysis_run_id
       and old.schema_version = new.schema_version
       and old.config_version = new.config_version
       and old.created_by = new.created_by
       and old.created_at = new.created_at then
         return new;
    end if;
    raise exception 'Immutable table: updates/deletes are not allowed';
  elsif tg_op = 'DELETE' then
    raise exception 'Immutable table: updates/deletes are not allowed';
  end if;
  return new;
end;
$$;

drop trigger if exists pds_snapshots_prevent_mutation on pds_snapshots;
create trigger pds_snapshots_prevent_mutation
  before update or delete on pds_snapshots
  for each row execute function pds_snapshots_mutation_guard();

-- Note: pds_overrides immutability trigger remains unchanged.
