-- Migration 011: add balance_cents to pds_raw_transactions
-- Required by reconciliation_engine.py for balance-column reconciliation method.
-- Applied directly to prod without a file originally; this backfills the record.
ALTER TABLE public.pds_raw_transactions ADD COLUMN IF NOT EXISTS balance_cents bigint;
