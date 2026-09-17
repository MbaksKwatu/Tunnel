-- Mirrors backend/migrations/045_add_created_by_to_pds_parser_requests.sql
-- so the Supabase CLI path also covers it. See that file for the full
-- rationale (pds_parser_requests.created_by was assumed to already exist
-- from supabase/migrations/015_pds_parser_requests.sql, but that migration
-- was never applied to the live table -- confirmed via a live insert probe
-- that failed with 42703: column "created_by" does not exist).

ALTER TABLE public.pds_parser_requests
  ADD COLUMN IF NOT EXISTS created_by uuid REFERENCES auth.users(id);

CREATE INDEX IF NOT EXISTS idx_pds_parser_requests_created_by ON public.pds_parser_requests(created_by);
