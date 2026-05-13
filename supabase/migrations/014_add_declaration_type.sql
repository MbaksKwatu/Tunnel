-- Migration 014: Add declaration_type to pds_audited_financials
--
-- Differentiates audited statements (externally audited, higher trust) from
-- management accounts (internally prepared, requires Parity Review before
-- snapshot generation).

alter table pds_audited_financials
  add column if not exists declaration_type text
    not null default 'audited'
    check (declaration_type in ('audited', 'management'));

create index if not exists idx_pds_af_declaration_type
  on pds_audited_financials(deal_id, declaration_type);

comment on column pds_audited_financials.declaration_type is
  'audited = externally audited statements; management = internally prepared accounts. '
  'Management accounts require Parity Review before snapshot generation.';
