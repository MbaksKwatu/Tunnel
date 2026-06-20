-- Mirrors backend/migrations/014_add_currency_source_to_pds_deals.sql so the
-- self-healing startup runner (backend/migrations/) also covers it.
ALTER TABLE public.pds_deals
  ADD COLUMN IF NOT EXISTS currency_source TEXT NOT NULL DEFAULT 'default'
  CHECK (currency_source IN ('default', 'detected', 'manual'));

UPDATE public.pds_deals SET currency_source = 'detected' WHERE currency IS NOT NULL;
