-- Add structured error taxonomy columns for failed documents
-- error_type, error_stage, next_action support deterministic diagnostics

alter table if exists pds_documents
  add column if not exists error_type text,
  add column if not exists error_stage text,
  add column if not exists next_action text;
