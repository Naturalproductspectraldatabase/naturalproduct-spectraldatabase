-- Restricted-access hardening for NPDB while the database is invite-only.
-- Apply only after Streamlit has SUPABASE_SERVICE_ROLE_KEY configured server-side.
-- The Streamlit app reads/writes with the service role, while direct anon REST reads are blocked.

alter table public.compounds enable row level security;
alter table public.proton_nmr enable row level security;
alter table public.carbon_nmr enable row level security;
alter table public.spectra_files enable row level security;
alter table public.bioactivity_records enable row level security;

drop policy if exists "viewer read compounds" on public.compounds;
drop policy if exists "viewer read proton_nmr" on public.proton_nmr;
drop policy if exists "viewer read carbon_nmr" on public.carbon_nmr;
drop policy if exists "viewer read spectra_files" on public.spectra_files;
drop policy if exists "viewer read bioactivity_records" on public.bioactivity_records;

drop policy if exists "service role manages compounds" on public.compounds;
create policy "service role manages compounds"
on public.compounds
for all
to service_role
using (true)
with check (true);

drop policy if exists "service role manages proton_nmr" on public.proton_nmr;
create policy "service role manages proton_nmr"
on public.proton_nmr
for all
to service_role
using (true)
with check (true);

drop policy if exists "service role manages carbon_nmr" on public.carbon_nmr;
create policy "service role manages carbon_nmr"
on public.carbon_nmr
for all
to service_role
using (true)
with check (true);

drop policy if exists "service role manages spectra_files" on public.spectra_files;
create policy "service role manages spectra_files"
on public.spectra_files
for all
to service_role
using (true)
with check (true);

drop policy if exists "service role manages bioactivity_records" on public.bioactivity_records;
create policy "service role manages bioactivity_records"
on public.bioactivity_records
for all
to service_role
using (true)
with check (true);

update storage.buckets
set public = false
where id in ('structures', 'spectra');

drop policy if exists "Public can read structures bucket" on storage.objects;
drop policy if exists "Public can read spectra bucket" on storage.objects;
