-- Migration 049: keep the original uploaded files.
--
-- Problem: bank statements (POST /deals/{id}/documents and /documents/batch)
-- and audited financials (POST /deals/{id}/upload-financials) were parsed in
-- memory and discarded. pds_documents.storage_url only ever held
-- "inline://<filename>", and pds_audited_financials kept only the extracted
-- figures, so an analyst could never retrieve the source document later.
--
-- Fix: the API now writes the original bytes to the private `uploads` bucket
-- at a deal-scoped path (<deal_id>/<document_id>/<filename>, or
-- <deal_id>/audited-financials/<uuid>/<filename>) and records that path here.
--
-- pds_documents.storage_url is deliberately left as "inline://<filename>":
-- reconciliation_engine dedups re-uploaded statements and derives bank labels
-- from it, so turning it into a unique per-document path would change
-- reconciliation output. The new column carries the retrievable path instead.
--
-- Both columns are nullable with no backfill: rows uploaded before this change
-- have no stored file, and a failed Storage write also leaves NULL. Neither
-- column is part of any hashed payload (financial_state_hash / sha256_hash).

-- The `uploads` bucket already exists in prod (private, no size or MIME
-- limit); create it where it is missing (staging, test DBs).
INSERT INTO storage.buckets (id, name, public)
VALUES ('uploads', 'uploads', false)
ON CONFLICT (id) DO NOTHING;

ALTER TABLE public.pds_documents
  ADD COLUMN IF NOT EXISTS original_storage_path text;

ALTER TABLE public.pds_audited_financials
  ADD COLUMN IF NOT EXISTS original_storage_path text;
