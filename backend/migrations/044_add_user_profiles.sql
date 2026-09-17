-- Adds a lightweight per-account contact-email table, decoupled from
-- auth.users.email. Used by the "New Bank Format" request form: Contact
-- Email pre-fills from the signed-in session's login email, but editing it
-- must not trigger an actual login-email change (which writing directly to
-- auth.users.email would do) -- it just updates where parser-request
-- notifications go for that account going forward.

create table public.user_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  contact_email text,
  updated_at timestamptz not null default now()
);

alter table public.user_profiles enable row level security;

create policy "Users can view their own profile"
  on public.user_profiles for select
  to authenticated
  using (user_id = auth.uid());

create policy "Users can upsert their own profile"
  on public.user_profiles for insert
  to authenticated
  with check (user_id = auth.uid());

create policy "Users can update their own profile"
  on public.user_profiles for update
  to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());
