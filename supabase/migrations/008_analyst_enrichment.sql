-- Analyst enrichment layer on top of deterministic base snapshots.
-- Base snapshots remain immutable; enrichments are append-only per analyst.

-- Table 1: Enrichment records — one per analyst session on a base snapshot
create table if not exists pds_snapshot_enrichments (
  id uuid primary key default gen_random_uuid(),
  base_snapshot_id uuid not null references pds_snapshots(id),
  enriched_hash text not null,
  analyst_id text not null,
  analyst_name text,
  narrative text,
  enrichment_reason text,
  is_final boolean not null default false,
  created_at timestamptz not null default now(),
  constraint pds_enrichments_unique_hash unique (enriched_hash)
);

create index if not exists idx_pds_enrichments_base on pds_snapshot_enrichments(base_snapshot_id);
create index if not exists idx_pds_enrichments_analyst on pds_snapshot_enrichments(analyst_id);
create index if not exists idx_pds_enrichments_final on pds_snapshot_enrichments(is_final) where is_final = true;

comment on table pds_snapshot_enrichments is
  'Analyst-added layer on top of deterministic snapshots. Preserves base immutability.';
comment on column pds_snapshot_enrichments.enriched_hash is
  'SHA256(base_snapshot.sha256_hash + sorted overrides + sorted flags + narrative)';
comment on column pds_snapshot_enrichments.is_final is
  'TRUE when analyst marks this enrichment ready for client export.';


-- Table 2: Per-transaction classification overrides within an enrichment
create table if not exists pds_classification_overrides (
  id uuid primary key default gen_random_uuid(),
  enrichment_id uuid not null references pds_snapshot_enrichments(id) on delete cascade,
  txn_id uuid not null references pds_raw_transactions(id),
  original_role text not null,
  original_reason text,
  override_role text not null,
  override_reason text not null,
  overridden_by text not null,
  overridden_at timestamptz not null default now(),
  constraint pds_classification_overrides_unique_txn unique (enrichment_id, txn_id)
);

create index if not exists idx_pds_cls_overrides_enrichment on pds_classification_overrides(enrichment_id);
create index if not exists idx_pds_cls_overrides_txn on pds_classification_overrides(txn_id);

comment on table pds_classification_overrides is
  'Analyst reclassifications of individual transactions. Original classification preserved.';


-- Table 3: Analyst-defined threshold flags and custom checks
create table if not exists pds_custom_flags (
  id uuid primary key default gen_random_uuid(),
  enrichment_id uuid not null references pds_snapshot_enrichments(id) on delete cascade,
  flag_type text not null,        -- 'threshold', 'pattern', 'compliance', 'custom'
  flag_name text not null,
  flag_severity text not null,    -- 'info', 'warning', 'critical'
  flag_description text not null,
  criteria jsonb not null,
  triggered boolean not null,
  trigger_count int not null default 0,
  trigger_details jsonb not null default '[]'::jsonb,
  created_by text not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_pds_custom_flags_enrichment on pds_custom_flags(enrichment_id);
create index if not exists idx_pds_custom_flags_type on pds_custom_flags(flag_type);
create index if not exists idx_pds_custom_flags_severity on pds_custom_flags(flag_severity) where triggered = true;

comment on table pds_custom_flags is
  'Analyst-defined threshold alerts and custom checks. Not part of deterministic pipeline.';


-- RLS: enrichments are visible to deal owners only
alter table pds_snapshot_enrichments enable row level security;
alter table pds_classification_overrides enable row level security;
alter table pds_custom_flags enable row level security;

create policy pds_enrichments_select on pds_snapshot_enrichments
  for select using (
    exists (
      select 1 from pds_snapshots s
      join pds_deals d on d.id = s.deal_id
      where s.id = pds_snapshot_enrichments.base_snapshot_id
        and d.created_by = auth.uid()
    )
  );

create policy pds_enrichments_insert on pds_snapshot_enrichments
  for insert with check (
    exists (
      select 1 from pds_snapshots s
      join pds_deals d on d.id = s.deal_id
      where s.id = base_snapshot_id
        and d.created_by = auth.uid()
    )
  );

-- Allow analysts to mark is_final on their own enrichments
create policy pds_enrichments_update_final on pds_snapshot_enrichments
  for update using (analyst_id = auth.uid()::text)
  with check (analyst_id = auth.uid()::text);

create policy pds_cls_overrides_select on pds_classification_overrides
  for select using (
    exists (
      select 1 from pds_snapshot_enrichments e
      join pds_snapshots s on s.id = e.base_snapshot_id
      join pds_deals d on d.id = s.deal_id
      where e.id = pds_classification_overrides.enrichment_id
        and d.created_by = auth.uid()
    )
  );

create policy pds_cls_overrides_insert on pds_classification_overrides
  for insert with check (
    exists (
      select 1 from pds_snapshot_enrichments e
      join pds_snapshots s on s.id = e.base_snapshot_id
      join pds_deals d on d.id = s.deal_id
      where e.id = enrichment_id
        and d.created_by = auth.uid()
    )
  );

create policy pds_custom_flags_select on pds_custom_flags
  for select using (
    exists (
      select 1 from pds_snapshot_enrichments e
      join pds_snapshots s on s.id = e.base_snapshot_id
      join pds_deals d on d.id = s.deal_id
      where e.id = pds_custom_flags.enrichment_id
        and d.created_by = auth.uid()
    )
  );

create policy pds_custom_flags_insert on pds_custom_flags
  for insert with check (
    exists (
      select 1 from pds_snapshot_enrichments e
      join pds_snapshots s on s.id = e.base_snapshot_id
      join pds_deals d on d.id = s.deal_id
      where e.id = enrichment_id
        and d.created_by = auth.uid()
    )
  );
