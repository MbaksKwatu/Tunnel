-- Mirrors backend/migrations/044_add_user_profiles.sql so the Supabase CLI
-- path also covers it. See that file for the full rationale.

create table if not exists public.user_profiles (
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
