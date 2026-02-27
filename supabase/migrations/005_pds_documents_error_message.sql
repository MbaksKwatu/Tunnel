-- Add error_message to pds_documents for ingestion failure visibility
-- When status = 'failed', error_message contains the specific reason (e.g. "Missing required column: amount")

alter table if exists pds_documents
  add column if not exists error_message text;
