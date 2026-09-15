-- PAR-125 fix: pds_parser_requests schema was built for the frontend-only flow
-- (bank_name always supplied by the user). The server-side auto-write needs:
--
-- 1. bank_name nullable: auto-created rows don't have a bank name yet (user
--    fills it in via the modal later). NOT NULL with no default breaks the INSERT.
--
-- 2. status column: distinguishes 'new' (auto-created, unsubmitted),
--    'pending' (user submitted form), and 'resolved' states.
--
-- 3. storage_path column: stores the Supabase Storage object path so the
--    retry endpoint can re-download the original file bytes without re-upload.

alter table public.pds_parser_requests
  alter column bank_name drop not null;

alter table public.pds_parser_requests
  add column if not exists status text not null default 'new',
  add column if not exists storage_path text;

comment on column public.pds_parser_requests.status is
  'Row lifecycle: new = auto-created at detection, pending = user submitted form, resolved = parser built.';

comment on column public.pds_parser_requests.storage_path is
  'Supabase Storage object path for the original file (web-upload/{document_id}/filename). Enables retry without re-upload.';
