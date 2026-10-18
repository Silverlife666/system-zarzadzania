-- Uruchom ten plik w Supabase: SQL Editor -> New query -> Run.
-- RLS nie ma polityk celowo: publiczny klucz nie ma dostępu do danych.

create table if not exists public.application_state (
  state_key text primary key,
  payload jsonb not null,
  updated_at timestamptz not null default now()
);

alter table public.application_state enable row level security;

revoke all on table public.application_state from anon, authenticated;

comment on table public.application_state is
  'Stan aplikacji zapisywany wyłącznie z backendu Streamlit przez service_role.';
