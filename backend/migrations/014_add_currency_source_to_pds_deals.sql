-- Migration 014: add currency_source to pds_deals
-- Replaces the "is the literal string KES" proxy that set_currency_if_unset() used
-- to decide whether a deal's currency was a creation-time placeholder or a real
-- detection. 'default' = placeholder from deal creation, 'detected' = confirmed by
-- a parsed document, 'manual' = reserved for a future explicit analyst override.
-- Backfill marks every deal that already has a currency as 'detected' so this
-- migration changes zero behavior for existing deals.
ALTER TABLE public.pds_deals
  ADD COLUMN IF NOT EXISTS currency_source TEXT NOT NULL DEFAULT 'default'
  CHECK (currency_source IN ('default', 'detected', 'manual'));

UPDATE public.pds_deals SET currency_source = 'detected' WHERE currency IS NOT NULL;
