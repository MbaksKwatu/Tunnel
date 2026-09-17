-- PAR-format-desk post-merge fix: pds_parser_requests.created_by does not
-- exist on this database. PR #245 wired every insert/enrich path to write
-- it, on the assumption (from supabase/migrations/015_pds_parser_requests.sql)
-- that the column already existed with an RLS policy already scoping reads
-- to it. That assumption was wrong for the live table: pds_parser_requests
-- was never created via backend/migrations/ (only touched by
-- 021_add_storage_path_to_parser_requests.sql, an ALTER on an
-- already-existing table), so it never picked up created_by. Confirmed live:
-- inserting created_by on this table currently fails with
-- "42703: column \"created_by\" of relation \"pds_parser_requests\" does not
-- exist". This adds the missing column so that code now works as intended.
--
-- Note: the existing "Authenticated users can read own parser requests" RLS
-- policy on this table has qual = true (i.e. it does not actually scope by
-- created_by, despite its name) -- left as-is here since fixing that is a
-- separate RLS concern, not part of this fix.

ALTER TABLE public.pds_parser_requests
  ADD COLUMN created_by uuid REFERENCES auth.users(id);

CREATE INDEX idx_pds_parser_requests_created_by ON public.pds_parser_requests(created_by);
