-- Migration 012: add analyst_notes to pds_deals
-- Applied directly to prod without a file originally; this backfills the record.
ALTER TABLE public.pds_deals ADD COLUMN IF NOT EXISTS analyst_notes TEXT;
