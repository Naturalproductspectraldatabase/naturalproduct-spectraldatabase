-- NPDB production hardening: audit trail + private cloud asset defaults.
-- Run in Supabase SQL editor after reviewing the comments below.
-- This script does not expose viewer read/write access; the Streamlit server key
-- remains the only writer for curated database tables.

create table if not exists public.audit_events (
  id bigserial primary key,
  event_time timestamptz not null default now(),
  actor_username text,
  actor_role text,
  action text not null,
  table_name text not null,
  row_id bigint,
  backend text not null default 'supabase',
  details jsonb not null default '{}'::jsonb
);

create index if not exists idx_audit_events_time
  on public.audit_events (event_time desc);

create index if not exists idx_audit_events_table_row
  on public.audit_events (table_name, row_id);

alter table public.audit_events enable row level security;

drop policy if exists "service role manages audit_events" on public.audit_events;
create policy "service role manages audit_events"
  on public.audit_events
  for all
  to service_role
  using (true)
  with check (true);

revoke all on public.audit_events from anon, authenticated;
grant all on public.audit_events to service_role;

-- Keep scientific assets private by default. The Streamlit app signs private
-- object URLs server-side, so approved users can still view structures/spectra.
update storage.buckets
set public = false
where id in ('structures', 'spectra', 'exports', 'backups');

drop policy if exists "Public read structures" on storage.objects;
drop policy if exists "Public read spectra" on storage.objects;
drop policy if exists "public read structures" on storage.objects;
drop policy if exists "public read spectra" on storage.objects;
drop policy if exists "public structures read" on storage.objects;
drop policy if exists "public spectra read" on storage.objects;

drop policy if exists "service role manages structures" on storage.objects;
create policy "service role manages structures"
  on storage.objects
  for all
  to service_role
  using (bucket_id = 'structures')
  with check (bucket_id = 'structures');

drop policy if exists "service role manages spectra" on storage.objects;
create policy "service role manages spectra"
  on storage.objects
  for all
  to service_role
  using (bucket_id = 'spectra')
  with check (bucket_id = 'spectra');

drop policy if exists "service role manages exports" on storage.objects;
create policy "service role manages exports"
  on storage.objects
  for all
  to service_role
  using (bucket_id = 'exports')
  with check (bucket_id = 'exports');

drop policy if exists "service role manages backups" on storage.objects;
create policy "service role manages backups"
  on storage.objects
  for all
  to service_role
  using (bucket_id = 'backups')
  with check (bucket_id = 'backups');

-- Verification after running:
-- select relrowsecurity from pg_class where relname = 'audit_events';
-- select id, public from storage.buckets where id in ('structures','spectra','exports','backups');
