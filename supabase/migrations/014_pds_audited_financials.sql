-- Migration 010: Audited financials + per-transaction balance storage
--
-- 1. pds_audited_financials — stores analyst-uploaded audited financial statements
-- 2. balance_cents on pds_raw_transactions — running balance per row (nullable;
--    populated only for statements whose parser extracts a balance column)

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. pds_audited_financials
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists pds_audited_financials (
  id                              uuid primary key default gen_random_uuid(),
  deal_id                         uuid not null references pds_deals(id) on delete cascade,
  financial_year                  int  not null,
  financial_year_start            date not null,
  financial_year_end              date not null,
  company_name                    text,
  currency                        text not null default 'KES',
  auditor_name                    text,
  extraction_confidence           numeric(5,2),

  -- Income Statement
  turnover_cents                  bigint,
  cost_of_sales_cents             bigint,
  gross_profit_cents              bigint,
  operating_costs_cents           bigint,
  administrative_costs_cents      bigint,
  staff_costs_cents               bigint,
  finance_costs_cents             bigint,
  other_income_cents              bigint,
  profit_before_tax_cents         bigint,
  tax_expense_cents               bigint,
  profit_after_tax_cents          bigint,

  -- Balance Sheet
  property_plant_equipment_cents  bigint,
  intangible_assets_cents         bigint,
  inventory_cents                 bigint,
  trade_receivables_cents         bigint,
  cash_and_equivalents_cents      bigint,
  total_assets_cents              bigint,
  trade_payables_cents            bigint,
  total_liabilities_cents         bigint,
  equity_cents                    bigint,

  -- Cash Flow Statement
  operating_cashflow_cents        bigint,
  investing_cashflow_cents        bigint,
  financing_cashflow_cents        bigint,
  cash_at_start_cents             bigint,
  cash_at_end_cents               bigint,

  -- Per-bank-account cash breakdown ({"KCB": 30312500, "Equity": 155587200, ...})
  cash_breakdown                  jsonb,

  created_at                      timestamptz not null default now(),
  updated_at                      timestamptz not null default now(),

  constraint pds_audited_financials_deal_year unique (deal_id, financial_year)
);

create index if not exists idx_pds_af_deal_id   on pds_audited_financials(deal_id);
create index if not exists idx_pds_af_deal_year on pds_audited_financials(deal_id, financial_year);

alter table pds_audited_financials enable row level security;

create policy pds_af_select on pds_audited_financials
  for select using (
    exists (
      select 1 from pds_deals d
      where d.id = pds_audited_financials.deal_id
        and d.created_by = auth.uid()
    )
  );

create policy pds_af_insert on pds_audited_financials
  for insert with check (
    exists (
      select 1 from pds_deals d
      where d.id = deal_id
        and d.created_by = auth.uid()
    )
  );

create policy pds_af_update on pds_audited_financials
  for update using (
    exists (
      select 1 from pds_deals d
      where d.id = pds_audited_financials.deal_id
        and d.created_by = auth.uid()
    )
  );

comment on table pds_audited_financials is
  'Analyst-uploaded audited financial statements. One row per deal per financial year.';
comment on column pds_audited_financials.cash_breakdown is
  'Per-bank-account cash balances at fiscal year-end, cents. e.g. {"KCB": 30312500}';


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. balance_cents on pds_raw_transactions
-- ─────────────────────────────────────────────────────────────────────────────
-- Running balance per row exactly as printed on the bank statement.
-- NULL when the source document did not include a balance column.
alter table pds_raw_transactions
  add column if not exists balance_cents bigint null;

create index if not exists idx_pds_raw_txn_balance
  on pds_raw_transactions(deal_id, account_id, txn_date)
  where balance_cents is not null;

comment on column pds_raw_transactions.balance_cents is
  'Running balance from the bank statement after this transaction, in cents. '
  'NULL when the parser could not extract a balance column.';
