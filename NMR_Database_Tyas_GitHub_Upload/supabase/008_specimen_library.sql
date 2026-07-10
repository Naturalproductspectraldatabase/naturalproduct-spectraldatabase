-- NPDB specimen library extension.
-- Run after 006/007 hardening when the Supabase project is reachable again.
-- The app uses the server-side service role; direct anon/authenticated access stays blocked.

insert into storage.buckets (id, name, public)
values ('specimens', 'specimens', false)
on conflict (id) do update set public = excluded.public;

create table if not exists public.specimens (
  id bigserial primary key,
  specimen_name text not null,
  scientific_name text,
  specimen_type text,
  image_path text,
  color text,
  texture text,
  traits text,
  collection_location text,
  gps_coordinates text,
  sampling_date text,
  depth_m numeric,
  habitat text,
  collector text,
  note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.specimen_compounds (
  id bigserial primary key,
  specimen_id bigint not null references public.specimens(id) on delete cascade,
  compound_id bigint not null references public.compounds(id) on delete cascade,
  evidence_note text,
  reference_note text,
  created_at timestamptz not null default now(),
  unique (specimen_id, compound_id)
);

create table if not exists public.specimen_1h_extracts (
  id bigserial primary key,
  specimen_id bigint not null references public.specimens(id) on delete cascade,
  extract_label text,
  extract_type text,
  solvent text,
  instrument_mhz numeric,
  file_path text,
  acquisition_date text,
  observed_features text,
  note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_specimens_name
  on public.specimens (lower(specimen_name));

create index if not exists idx_specimens_type
  on public.specimens (lower(specimen_type));

create index if not exists idx_specimen_compounds_specimen
  on public.specimen_compounds (specimen_id);

create index if not exists idx_specimen_compounds_compound
  on public.specimen_compounds (compound_id);

create index if not exists idx_specimen_1h_extracts_specimen
  on public.specimen_1h_extracts (specimen_id);

alter table public.specimens enable row level security;
alter table public.specimen_compounds enable row level security;
alter table public.specimen_1h_extracts enable row level security;

drop policy if exists "service role manages specimens" on public.specimens;
create policy "service role manages specimens"
  on public.specimens
  for all
  to service_role
  using (true)
  with check (true);

drop policy if exists "service role manages specimen_compounds" on public.specimen_compounds;
create policy "service role manages specimen_compounds"
  on public.specimen_compounds
  for all
  to service_role
  using (true)
  with check (true);

drop policy if exists "service role manages specimen_1h_extracts" on public.specimen_1h_extracts;
create policy "service role manages specimen_1h_extracts"
  on public.specimen_1h_extracts
  for all
  to service_role
  using (true)
  with check (true);

revoke all on public.specimens from anon, authenticated;
revoke all on public.specimen_compounds from anon, authenticated;
revoke all on public.specimen_1h_extracts from anon, authenticated;
grant all on public.specimens to service_role;
grant all on public.specimen_compounds to service_role;
grant all on public.specimen_1h_extracts to service_role;

drop policy if exists "service role manages specimens bucket" on storage.objects;
create policy "service role manages specimens bucket"
  on storage.objects
  for all
  to service_role
  using (bucket_id = 'specimens')
  with check (bucket_id = 'specimens');

-- Verification after running:
-- select id, public from storage.buckets where id = 'specimens';
-- select relrowsecurity from pg_class where relname in ('specimens','specimen_compounds','specimen_1h_extracts');
