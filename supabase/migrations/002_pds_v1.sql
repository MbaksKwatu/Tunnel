-- Parity v1 deterministic schema
-- Applies enums, tables, constraints, indexes, RLS, and immutability guards

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

create table if not exists deals (
  id uuid primary key default gen_random_uuid(),
  created_by uuid not null,
  currency text not null,
  name text,
  accrual_revenue_cents bigint null,
  accrual_period_start date null,
  accrual_period_end date null,
  accrual_manually_entered boolean not null default true,
  created_at timestamptz not null default now(),
  constraint accrual_period_presence check (
    (accrual_period_start is null and accrual_period_end is null)
    or (accrual_period_start is not null and accrual_period_end is not null)
  ),
  constraint accrual_period_order check (
    accrual_period_start is null
    or accrual_period_end is null
    or accrual_period_end >= accrual_period_start
  )
);

create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  deal_id uuid not null references deals(id) on delete cascade,
  storage_url text not null,
  file_type text not null,
  status document_status_enum not null default 'uploaded',
  currency_detected text null,
  currency_mismatch boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists raw_transactions (
  id uuid primary key default gen_random_uuid(),
  deal_id uuid not null references deals(id) on delete cascade,
  document_id uuid not null references documents(id) on delete cascade,
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
  constraint raw_transactions_unique_doc_txn unique (document_id, txn_id),
  constraint raw_transactions_non_zero check (signed_amount_cents <> 0)
);

create table if not exists transfer_links (
  id uuid primary key default gen_random_uuid(),
  deal_id uuid not null references deals(id) on delete cascade,
  txn_out_id uuid not null references raw_transactions(id),
  txn_in_id uuid not null references raw_transactions(id),
  abs_amount_cents bigint not null,
  match_rule_version text not null,
  created_at timestamptz not null default now(),
  constraint transfer_links_unique_out unique (txn_out_id),
  constraint transfer_links_unique_in unique (txn_in_id)
);

-- Add FK after both tables exist to avoid creation order issues
alter table if exists raw_transactions
  add constraint raw_transactions_transfer_pair_fk
  foreign key (transfer_pair_id) references transfer_links(id);

create table if not exists entities (
  entity_id text primary key,
  deal_id uuid not null references deals(id) on delete cascade,
  normalized_name text not null,
  display_name text not null,
  strong_identifiers jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint entities_unique_name unique (deal_id, normalized_name)
);

create table if not exists txn_entity_map (
  deal_id uuid not null references deals(id) on delete cascade,
  txn_id uuid primary key references raw_transactions(id) on delete cascade,
  entity_id text not null references entities(entity_id) on delete cascade,
  role role_enum not null,
  role_version text not null,
  created_at timestamptz not null default now()
);

create table if not exists overrides (
  id uuid primary key default gen_random_uuid(),
  deal_id uuid not null references deals(id) on delete cascade,
  entity_id text not null references entities(entity_id) on delete cascade,
  field text not null,
  old_value text null,
  new_value text not null,
  weight numeric(2,1) not null check (weight in (0.5, 1.0)),
  reason text null,
  created_by uuid not null,
  created_at timestamptz not null default now()
);

create table if not exists analysis_runs (
  id uuid primary key default gen_random_uuid(),
  deal_id uuid not null references deals(id) on delete cascade,
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
  constraint coverage_pct_range check (coverage_pct_bp between 0 and 10000),
  constraint missing_penalty_range check (missing_month_penalty_bp between 0 and 5000),
  constraint override_penalty_range check (override_penalty_bp between 0 and 7000),
  constraint reconciliation_pct_range check (reconciliation_pct_bp is null or (reconciliation_pct_bp between 0 and 10000)),
  constraint base_confidence_range check (base_confidence_bp between 0 and 10000),
  constraint final_confidence_range check (final_confidence_bp between 0 and 10000)
);

create table if not exists snapshots (
  id uuid primary key default gen_random_uuid(),
  deal_id uuid not null references deals(id) on delete cascade,
  analysis_run_id uuid not null references analysis_runs(id) on delete restrict,
  schema_version text not null,
  config_version text not null,
  sha256_hash text not null unique,
  canonical_json text not null,
  created_by uuid not null,
  created_at timestamptz not null default now()
);

-- Indexes
create index if not exists idx_raw_transactions_deal_date on raw_transactions(deal_id, txn_date);
create index if not exists idx_raw_transactions_document on raw_transactions(document_id);
create index if not exists idx_raw_transactions_acct_date on raw_transactions(deal_id, account_id, txn_date);

create index if not exists idx_txn_entity_map_deal_role on txn_entity_map(deal_id, role);
create index if not exists idx_overrides_deal_entity_created_at on overrides(deal_id, entity_id, created_at desc);
create index if not exists idx_analysis_runs_deal_created_at on analysis_runs(deal_id, created_at desc);
create index if not exists idx_snapshots_deal_created_at on snapshots(deal_id, created_at desc);

-- RLS
alter table deals enable row level security;
alter table documents enable row level security;
alter table raw_transactions enable row level security;
alter table transfer_links enable row level security;
alter table entities enable row level security;
alter table txn_entity_map enable row level security;
alter table overrides enable row level security;
alter table analysis_runs enable row level security;
alter table snapshots enable row level security;

-- Ownership helper predicate (inline via EXISTS)

-- deals
create policy deals_select_owner on deals
  for select using (created_by = auth.uid());
create policy deals_insert_owner on deals
  for insert with check (created_by = auth.uid());
create policy deals_update_owner on deals
  for update using (created_by = auth.uid());

-- documents
create policy documents_select_owner on documents
  for select using (exists (select 1 from deals d where d.id = documents.deal_id and d.created_by = auth.uid()));
create policy documents_insert_owner on documents
  for insert with check (exists (select 1 from deals d where d.id = documents.deal_id and d.created_by = auth.uid()));
create policy documents_update_owner on documents
  for update using (exists (select 1 from deals d where d.id = documents.deal_id and d.created_by = auth.uid()));

-- raw_transactions (insert/select only)
create policy raw_transactions_select_owner on raw_transactions
  for select using (exists (select 1 from deals d where d.id = raw_transactions.deal_id and d.created_by = auth.uid()));
create policy raw_transactions_insert_owner on raw_transactions
  for insert with check (exists (select 1 from deals d where d.id = raw_transactions.deal_id and d.created_by = auth.uid()));

-- transfer_links (insert/select only)
create policy transfer_links_select_owner on transfer_links
  for select using (exists (select 1 from deals d where d.id = transfer_links.deal_id and d.created_by = auth.uid()));
create policy transfer_links_insert_owner on transfer_links
  for insert with check (exists (select 1 from deals d where d.id = transfer_links.deal_id and d.created_by = auth.uid()));

-- entities
create policy entities_select_owner on entities
  for select using (exists (select 1 from deals d where d.id = entities.deal_id and d.created_by = auth.uid()));
create policy entities_insert_owner on entities
  for insert with check (exists (select 1 from deals d where d.id = entities.deal_id and d.created_by = auth.uid()));

-- txn_entity_map
create policy txn_entity_map_select_owner on txn_entity_map
  for select using (exists (select 1 from deals d where d.id = txn_entity_map.deal_id and d.created_by = auth.uid()));
create policy txn_entity_map_insert_owner on txn_entity_map
  for insert with check (exists (select 1 from deals d where d.id = txn_entity_map.deal_id and d.created_by = auth.uid()));

-- overrides (insert/select only; immutable)
create policy overrides_select_owner on overrides
  for select using (exists (select 1 from deals d where d.id = overrides.deal_id and d.created_by = auth.uid()));
create policy overrides_insert_owner on overrides
  for insert with check (exists (select 1 from deals d where d.id = overrides.deal_id and d.created_by = auth.uid()));

-- analysis_runs (insert/select only)
create policy analysis_runs_select_owner on analysis_runs
  for select using (exists (select 1 from deals d where d.id = analysis_runs.deal_id and d.created_by = auth.uid()));
create policy analysis_runs_insert_owner on analysis_runs
  for insert with check (exists (select 1 from deals d where d.id = analysis_runs.deal_id and d.created_by = auth.uid()));

-- snapshots (insert/select only; immutable)
create policy snapshots_select_owner on snapshots
  for select using (exists (select 1 from deals d where d.id = snapshots.deal_id and d.created_by = auth.uid()));
create policy snapshots_insert_owner on snapshots
  for insert with check (exists (select 1 from deals d where d.id = snapshots.deal_id and d.created_by = auth.uid()));

-- Immutability triggers for overrides and snapshots
create or replace function prevent_mutation()
returns trigger language plpgsql as $$
begin
  raise exception 'Immutable table: updates/deletes are not allowed';
end;
$$;

drop trigger if exists overrides_prevent_mutation on overrides;
create trigger overrides_prevent_mutation
  before update or delete on overrides
  for each row execute function prevent_mutation();

drop trigger if exists snapshots_prevent_mutation on snapshots;
create trigger snapshots_prevent_mutation
  before update or delete on snapshots
  for each row execute function prevent_mutation();

