create table if not exists public.pds_parser_requests (
  id uuid primary key default gen_random_uuid(),
  deal_id uuid references public.pds_deals(id) on delete set null,
  bank_name text not null,
  requester_email text,
  sample_file_url text,
  notes text,
  status text not null default 'pending',
  created_at timestamptz not null default now(),
  created_by uuid references auth.users(id) on delete set null
);

alter table public.pds_parser_requests enable row level security;

create policy "Authenticated users can insert parser requests"
  on public.pds_parser_requests for insert
  to authenticated
  with check (true);

create policy "Users can view their own parser requests"
  on public.pds_parser_requests for select
  to authenticated
  using (created_by = auth.uid());
