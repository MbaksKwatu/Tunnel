-- 047: durable account attribution for parser requests.
--
-- The admin Parser Requests queue labelled every client-table row "Manual" --
-- a hard-coded per-table string, not an account. No existing column can name
-- the client reliably (investigation 2026-10-01: contact_email domain names 1
-- of 10 rows, user_profiles/profiles are empty and carry no organisation,
-- 7 of 13 users are on free-mail domains). So the account is stored, not
-- derived.
--
--   account_name  client/account the request belongs to. NULL = unattributed
--                 (never guessed). Written by the writer that knows it (e.g.
--                 the partner route knows its partner); admin UI shows
--                 "Unattributed" for NULL.
--   is_test       explicit internal/test-row flag so test artifacts are never
--                 presented as real client requests.
--
-- Additive and nullable/defaulted: no existing row, query or policy changes.
-- (RLS from 046 is unchanged; a client can read these two columns on its own
-- rows, which is the same exposure as its other columns.)
--
-- Backfill is by exact row id (prod ifcdbhbuucmjgtjkluna, 2026-10-01) and is
-- a no-op on any database that does not have those rows. Rows not named
-- below keep account_name NULL on purpose.

ALTER TABLE public.pds_parser_requests
  ADD COLUMN IF NOT EXISTS account_name text,
  ADD COLUMN IF NOT EXISTS is_test boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.pds_parser_requests.account_name IS
  'Client/account this request belongs to (e.g. GBFund). NULL = unattributed; never derived from an email domain.';
COMMENT ON COLUMN public.pds_parser_requests.is_test IS
  'True for internal/test submissions so they are not presented as real client requests.';

-- Real GBFund request (SBM Bank, 2026-09-28, gbfund.org submitter).
UPDATE public.pds_parser_requests
   SET account_name = 'GBFund'
 WHERE id = '2f8d962c-7d43-4952-83d4-c03467652bb9'
   AND account_name IS NULL;

-- 2026-09-17 internal tests (2x zanzibar_bank_test.pdf, mail-tester report,
-- one submission with no file).
UPDATE public.pds_parser_requests
   SET is_test = true
 WHERE id IN (
   '51ea6cf5-d585-4384-ac41-184304ad511a',
   '8c228c7e-a43e-496c-8e2a-83bc956310a7',
   '1b53d931-2cbc-4528-b138-5729ee88ce8a',
   'd7078cfe-7cab-408b-a9f1-d5ba4f38b6e6'
 );
