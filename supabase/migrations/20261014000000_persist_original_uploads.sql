-- Mirrors backend/migrations/049_persist_original_uploads.sql so the Supabase
-- CLI path also covers it. See that file for the full rationale.

INSERT INTO storage.buckets (id, name, public)
VALUES ('uploads', 'uploads', false)
ON CONFLICT (id) DO NOTHING;

ALTER TABLE public.pds_documents
  ADD COLUMN IF NOT EXISTS original_storage_path text;

ALTER TABLE public.pds_audited_financials
  ADD COLUMN IF NOT EXISTS original_storage_path text;
