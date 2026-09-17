-- PAR-125: retry mechanism and pds_parser_request linkage for web-upload parser-request flow.
--
-- retry_count: tracks how many times this document has been retried through the
-- parser (Category B / unsupported-bank documents only). Capped at 3 by the backend.
--
-- pds_parser_request_id: links a failed Category B document to the pds_parser_requests
-- row auto-created at detection time (server-side, regardless of modal interaction).
-- Previously this row was only created if the user submitted the modal form. This column
-- closes the PAR-66 gap: the record exists the moment the system knows it's a real
-- unsupported-bank case.

alter table public.pds_documents
  add column if not exists retry_count int not null default 0,
  add column if not exists pds_parser_request_id uuid references public.pds_parser_requests(id) on delete set null;

comment on column public.pds_documents.retry_count is
  'Number of retry attempts for Category B (unsupported bank) failures. Capped at 3.';

comment on column public.pds_documents.pds_parser_request_id is
  'Links to the pds_parser_requests row auto-created at Category B detection time (PAR-125).';
