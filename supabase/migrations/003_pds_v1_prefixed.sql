-- Parity v1 deterministic schema (prefixed to avoid legacy table collisions)
-- All v1 tables use pds_ prefix; legacy tables (deals, documents, etc.) untouched.

-- Extensions
create extension if not exists "pgcrypto";

-- Enums
do $$
begin
  if not exists (select 1 from pg_type where typname = 'role_enum') then
    create type role_enum as enum (
      'revenue_operational',
      'revenue_non_operational',
      'payroll',
      'supplier',
      'transfer',
      'other'
    );
  end if;

  if not exists (select 1 from pg_type where typname = 'reconciliation_status_enum') then
    create type reconciliation_status_enum as enum ('OK', 'NOT_RUN', 'FAILED_OVERLAP');
  end if;

  if not exists (select 1 from pg_type where typname = 'tier_enum') then
    create type tier_enum as enum ('High', 'Medium', 'Low');
  end if;

  if not exists (select 1 from pg_type where typname = 'document_status_enum') then
    create type document_status_enum as enum ('uploaded', 'processing', 'completed', 'failed');
  end if;

  if not exists (select 1 from pg_type where typname = 'analysis_state_enum') then
    create type analysis_state_enum as enum ('LIVE_DRAFT');
  end if;

  if not exists (select 1 from pg_type where typname = 'run_trigger_enum') then
    create type run_trigger_enum as enum ('parse_complete', 'override_applied', 'manual_rerun');
  end if;
end$$;

-- Tables

create table if not exists pds_deals (
  id uuid primary key default gen_random_uuid(),
  created_by uuid not null,
  currency text not null,
  name text,
  accrual_revenue_cents bigint null,
  accrual_period_start date null,
  accrual_period_end date null,
  accrual_manually_entered boolean not null default true,
  created_at timestamptz not null default now(),
  constraint pds_accrual_period_presence check (
    (accrual_period_start is null and accrual_period_end is null)
    or (accrual_period_start is not null and accrual_period_end is not null)
  ),
  constraint pds_accrual_period_order check (
    accrual_period_start is null
    or accrual_period_end is null
    or accrual_period_end >= accrual_period_start
  )
);

create table if not exists pds_documents (
  id uuid primary key default gen_random_uuid(),
  deal_id uuid not null references pds_deals(id) on delete cascade,
  storage_url text not null,
  file_type text not null,
  status document_status_enum not null default 'uploaded',
  currency_detected text null,
  currency_mismatch boolean not null default false,
  created_by uuid,
  created_at timestamptz not null default now()
);

create table if not exists pds_raw_transactions (
  id uuid primary key default gen_random_uuid(),
  deal_id uuid not null references pds_deals(id) on delete cascade,
  document_id uuid not null references pds_documents(id) on delete cascade,
  account_id text not null,
  txn_date date not null,
  signed_amount_cents bigint not null,
  abs_amount_cents bigint generated always as (abs(signed_amount_cents)) stored,
  raw_descriptor text not null,
  parsed_descriptor text not null,
  normalized_descriptor text not null,
  txn_id text not null,
  is_transfer boolean not null default false,
  transfer_pair_id uuid null,
  created_at timestamptz not null default now(),
  constraint pds_raw_txn_unique_doc_txn unique (document_id, txn_id),
  constraint pds_raw_txn_non_zero check (signed_amount_cents <> 0)
);

create table if not exists pds_transfer_links (
  id uuid primary key default gen_random_uuid(),
  deal_id uuid not null references pds_deals(id) on delete cascade,
  txn_out_id uuid not null references pds_raw_transactions(id),
  txn_in_id uuid not null references pds_raw_transactions(id),
  abs_amount_cents bigint not null,
  match_rule_version text not null,
  created_at timestamptz not null default now(),
  constraint pds_transfer_links_unique_out unique (txn_out_id),
  constraint pds_transfer_links_unique_in unique (txn_in_id)
);

alter table if exists pds_raw_transactions
  add constraint pds_raw_txn_transfer_pair_fk
  foreign key (transfer_pair_id) references pds_transfer_links(id);

create table if not exists pds_entities (
  entity_id text primary key,
  deal_id uuid not null references pds_deals(id) on delete cascade,
  normalized_name text not null,
  display_name text not null,
  strong_identifiers jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint pds_entities_unique_name unique (deal_id, normalized_name)
);

create table if not exists pds_txn_entity_map (
  deal_id uuid not null references pds_deals(id) on delete cascade,
  txn_id uuid primary key references pds_raw_transactions(id) on delete cascade,
  entity_id text not null references pds_entities(entity_id) on delete cascade,
  role role_enum not null,
  role_version text not null,
  created_at timestamptz not null default now()
);

create table if not exists pds_overrides (
  id uuid primary key default gen_random_uuid(),
  deal_id uuid not null references pds_deals(id) on delete cascade,
  entity_id text not null references pds_entities(entity_id) on delete cascade,
  field text not null,
  old_value text null,
  new_value text not null,
  weight numeric(2,1) not null check (weight in (0.5, 1.0)),
  reason text null,
  created_by uuid not null,
  created_at timestamptz not null default now()
);

create table if not exists pds_analysis_runs (
  id uuid primary key default gen_random_uuid(),
  deal_id uuid not null references pds_deals(id) on delete cascade,
  state analysis_state_enum not null default 'LIVE_DRAFT',
  schema_version text not null,
  config_version text not null,
  run_trigger run_trigger_enum not null,
  non_transfer_abs_total_cents bigint not null,
  classified_abs_total_cents bigint not null,
  coverage_pct_bp integer not null,
  missing_month_penalty_bp integer not null,
  override_penalty_bp integer not null,
  reconciliation_pct_bp integer null,
  base_confidence_bp integer not null,
  final_confidence_bp integer not null,
  missing_month_count integer not null,
  reconciliation_status reconciliation_status_enum not null,
  tier tier_enum not null,
  tier_capped boolean not null default false,
  raw_transaction_hash text not null,
  transfer_links_hash text not null,
  entities_hash text not null,
  overrides_hash text not null,
  created_at timestamptz not null default now(),
  constraint pds_coverage_pct_range check (coverage_pct_bp between 0 and 10000),
  constraint pds_missing_penalty_range check (missing_month_penalty_bp between 0 and 5000),
  constraint pds_override_penalty_range check (override_penalty_bp between 0 and 7000),
  constraint pds_reconciliation_pct_range check (reconciliation_pct_bp is null or (reconciliation_pct_bp between 0 and 10000)),
  constraint pds_base_confidence_range check (base_confidence_bp between 0 and 10000),
  constraint pds_final_confidence_range check (final_confidence_bp between 0 and 10000)
);

create table if not exists pds_snapshots (
  id uuid primary key default gen_random_uuid(),
  deal_id uuid not null references pds_deals(id) on delete cascade,
  analysis_run_id uuid not null references pds_analysis_runs(id) on delete restrict,
  schema_version text not null,
  config_version text not null,
  sha256_hash text not null unique,
  canonical_json text not null,
  created_by uuid not null,
  created_at timestamptz not null default now()
);

-- Indexes
create index if not exists idx_pds_raw_txn_deal_date on pds_raw_transactions(deal_id, txn_date);
create index if not exists idx_pds_raw_txn_document on pds_raw_transactions(document_id);
create index if not exists idx_pds_raw_txn_acct_date on pds_raw_transactions(deal_id, account_id, txn_date);
create index if not exists idx_pds_txn_entity_map_deal_role on pds_txn_entity_map(deal_id, role);
create index if not exists idx_pds_overrides_deal_entity on pds_overrides(deal_id, entity_id, created_at desc);
create index if not exists idx_pds_analysis_runs_deal on pds_analysis_runs(deal_id, created_at desc);
create index if not exists idx_pds_snapshots_deal on pds_snapshots(deal_id, created_at desc);

-- RLS
alter table pds_deals enable row level security;
alter table pds_documents enable row level security;
alter table pds_raw_transactions enable row level security;
alter table pds_transfer_links enable row level security;
alter table pds_entities enable row level security;
alter table pds_txn_entity_map enable row level security;
alter table pds_overrides enable row level security;
alter table pds_analysis_runs enable row level security;
alter table pds_snapshots enable row level security;

-- RLS policies: pds_deals
create policy pds_deals_select on pds_deals
  for select using (created_by = auth.uid());
create policy pds_deals_insert on pds_deals
  for insert with check (created_by = auth.uid());
create policy pds_deals_update on pds_deals
  for update using (created_by = auth.uid());

-- RLS policies: pds_documents
create policy pds_documents_select on pds_documents
  for select using (exists (select 1 from pds_deals d where d.id = pds_documents.deal_id and d.created_by = auth.uid()));
create policy pds_documents_insert on pds_documents
  for insert with check (exists (select 1 from pds_deals d where d.id = pds_documents.deal_id and d.created_by = auth.uid()));
create policy pds_documents_update on pds_documents
  for update using (exists (select 1 from pds_deals d where d.id = pds_documents.deal_id and d.created_by = auth.uid()));

-- RLS policies: pds_raw_transactions (insert/select only)
create policy pds_raw_txn_select on pds_raw_transactions
  for select using (exists (select 1 from pds_deals d where d.id = pds_raw_transactions.deal_id and d.created_by = auth.uid()));
create policy pds_raw_txn_insert on pds_raw_transactions
  for insert with check (exists (select 1 from pds_deals d where d.id = pds_raw_transactions.deal_id and d.created_by = auth.uid()));

-- RLS policies: pds_transfer_links (insert/select only)
create policy pds_transfer_links_select on pds_transfer_links
  for select using (exists (select 1 from pds_deals d where d.id = pds_transfer_links.deal_id and d.created_by = auth.uid()));
create policy pds_transfer_links_insert on pds_transfer_links
  for insert with check (exists (select 1 from pds_deals d where d.id = pds_transfer_links.deal_id and d.created_by = auth.uid()));

-- RLS policies: pds_entities
create policy pds_entities_select on pds_entities
  for select using (exists (select 1 from pds_deals d where d.id = pds_entities.deal_id and d.created_by = auth.uid()));
create policy pds_entities_insert on pds_entities
  for insert with check (exists (select 1 from pds_deals d where d.id = pds_entities.deal_id and d.created_by = auth.uid()));

-- RLS policies: pds_txn_entity_map
create policy pds_txn_entity_map_select on pds_txn_entity_map
  for select using (exists (select 1 from pds_deals d where d.id = pds_txn_entity_map.deal_id and d.created_by = auth.uid()));
create policy pds_txn_entity_map_insert on pds_txn_entity_map
  for insert with check (exists (select 1 from pds_deals d where d.id = pds_txn_entity_map.deal_id and d.created_by = auth.uid()));

-- RLS policies: pds_overrides (insert/select only; immutable)
create policy pds_overrides_select on pds_overrides
  for select using (exists (select 1 from pds_deals d where d.id = pds_overrides.deal_id and d.created_by = auth.uid()));
create policy pds_overrides_insert on pds_overrides
  for insert with check (exists (select 1 from pds_deals d where d.id = pds_overrides.deal_id and d.created_by = auth.uid()));

-- RLS policies: pds_analysis_runs (insert/select only)
create policy pds_analysis_runs_select on pds_analysis_runs
  for select using (exists (select 1 from pds_deals d where d.id = pds_analysis_runs.deal_id and d.created_by = auth.uid()));
create policy pds_analysis_runs_insert on pds_analysis_runs
  for insert with check (exists (select 1 from pds_deals d where d.id = pds_analysis_runs.deal_id and d.created_by = auth.uid()));

-- RLS policies: pds_snapshots (insert/select only; immutable)
create policy pds_snapshots_select on pds_snapshots
  for select using (exists (select 1 from pds_deals d where d.id = pds_snapshots.deal_id and d.created_by = auth.uid()));
create policy pds_snapshots_insert on pds_snapshots
  for insert with check (exists (select 1 from pds_deals d where d.id = pds_snapshots.deal_id and d.created_by = auth.uid()));

-- Immutability triggers
create or replace function pds_prevent_mutation()
returns trigger language plpgsql as $$
begin
  raise exception 'Immutable table: updates/deletes are not allowed';
end;
$$;

drop trigger if exists pds_overrides_prevent_mutation on pds_overrides;
create trigger pds_overrides_prevent_mutation
  before update or delete on pds_overrides
  for each row execute function pds_prevent_mutation();

drop trigger if exists pds_snapshots_prevent_mutation on pds_snapshots;
create trigger pds_snapshots_prevent_mutation
  before update or delete on pds_snapshots
  for each row execute function pds_prevent_mutation();
