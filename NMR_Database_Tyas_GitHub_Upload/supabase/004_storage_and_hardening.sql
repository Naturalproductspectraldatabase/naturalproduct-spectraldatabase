create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_compounds_set_updated_at on public.compounds;
create trigger trg_compounds_set_updated_at
before update on public.compounds
for each row
execute function public.set_updated_at();

create index if not exists idx_compounds_lower_inchikey
on public.compounds (lower(trim(inchikey)))
where inchikey is not null and trim(inchikey) <> '';

create index if not exists idx_compounds_lower_doi
on public.compounds (lower(trim(doi)))
where doi is not null and trim(doi) <> '';

create index if not exists idx_compounds_lower_sample_code
on public.compounds (lower(trim(sample_code)))
where sample_code is not null and trim(sample_code) <> '';

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  (
    'structures',
    'structures',
    true,
    10485760,
    array['image/png', 'image/jpeg', 'image/webp', 'image/svg+xml', 'application/pdf']
  ),
  (
    'spectra',
    'spectra',
    true,
    52428800,
    array['image/png', 'image/jpeg', 'image/webp', 'application/pdf', 'text/plain', 'text/csv', 'application/octet-stream']
  ),
  (
    'exports',
    'exports',
    false,
    20971520,
    array['application/zip', 'application/json', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'text/csv', 'application/octet-stream']
  ),
  (
    'backups',
    'backups',
    false,
    52428800,
    array['application/zip', 'application/json', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'text/csv', 'application/octet-stream']
  )
on conflict (id) do update
set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "Public can read structures bucket" on storage.objects;
create policy "Public can read structures bucket"
on storage.objects
for select
using (bucket_id = 'structures');

drop policy if exists "Public can read spectra bucket" on storage.objects;
create policy "Public can read spectra bucket"
on storage.objects
for select
using (bucket_id = 'spectra');

drop policy if exists "Service role manages structures bucket" on storage.objects;
create policy "Service role manages structures bucket"
on storage.objects
for all
to service_role
using (bucket_id = 'structures')
with check (bucket_id = 'structures');

drop policy if exists "Service role manages spectra bucket" on storage.objects;
create policy "Service role manages spectra bucket"
on storage.objects
for all
to service_role
using (bucket_id = 'spectra')
with check (bucket_id = 'spectra');

drop policy if exists "Service role manages exports bucket" on storage.objects;
create policy "Service role manages exports bucket"
on storage.objects
for all
to service_role
using (bucket_id = 'exports')
with check (bucket_id = 'exports');

drop policy if exists "Service role manages backups bucket" on storage.objects;
create policy "Service role manages backups bucket"
on storage.objects
for all
to service_role
using (bucket_id = 'backups')
with check (bucket_id = 'backups');
