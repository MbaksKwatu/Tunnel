-- Migration 013: add user association and deal metadata to pds_deals
-- Mirrors supabase/migrations/011_add_user_association.sql so the
-- self-healing startup runner (backend/migrations/) also covers it.
ALTER TABLE public.pds_deals ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id);
ALTER TABLE public.pds_deals ADD COLUMN IF NOT EXISTS company_name TEXT;
ALTER TABLE public.pds_deals ADD COLUMN IF NOT EXISTS analyst_initials VARCHAR(3);

CREATE INDEX IF NOT EXISTS idx_deals_user_id ON public.pds_deals(user_id);
