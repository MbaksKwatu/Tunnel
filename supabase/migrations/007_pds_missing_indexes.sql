-- Missing indexes identified in v1 audit
create index if not exists idx_pds_documents_deal on pds_documents(deal_id, created_at desc);
create index if not exists idx_pds_documents_status on pds_documents(status);
