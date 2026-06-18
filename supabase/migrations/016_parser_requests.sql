create table if not exists public.parser_requests (
  id uuid primary key default gen_random_uuid(),
  partner text not null,
  market text,
  bank_name text,
  document_url text,
  session_id uuid,
  deal_id uuid,
  error_message text,
  status text not null default 'pending',
  requested_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_parser_requests_partner_status on public.parser_requests (partner, status);
create index if not exists idx_parser_requests_requested_at on public.parser_requests (requested_at desc);
