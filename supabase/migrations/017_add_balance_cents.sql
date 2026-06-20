-- Adds balance_cents to pds_raw_transactions.
-- Applied directly to prod (no file); this file backfills the migration record.
ALTER TABLE public.pds_raw_transactions ADD COLUMN IF NOT EXISTS balance_cents bigint;
