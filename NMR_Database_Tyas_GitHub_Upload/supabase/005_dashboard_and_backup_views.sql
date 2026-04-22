create or replace view public.npdb_dashboard_metrics as
select
  (select count(*) from public.compounds) as compounds_total,
  (select count(*) from public.proton_nmr) as proton_nmr_total,
  (select count(*) from public.carbon_nmr) as carbon_nmr_total,
  (select count(*) from public.spectra_files) as spectra_total,
  (select count(*) from public.bioactivity_records) as bioactivity_total,
  (select count(*) from public.compounds where coalesce(trim(smiles), '') <> '' or coalesce(trim(inchi), '') <> '' or coalesce(trim(inchikey), '') <> '') as structure_ready_total,
  (select max(updated_at) from public.compounds) as latest_compound_update;

create or replace view public.npdb_compound_readiness as
select
  c.id,
  c.trivial_name,
  c.sample_code,
  c.compound_class,
  c.source_category,
  c.updated_at,
  case
    when coalesce(trim(c.smiles), '') <> ''
      or coalesce(trim(c.inchi), '') <> ''
      or coalesce(trim(c.inchikey), '') <> ''
    then true
    else false
  end as has_structure_identifier,
  exists (
    select 1
    from public.spectra_files s
    where s.compound_id = c.id
  ) as has_spectra_file,
  exists (
    select 1
    from public.bioactivity_records b
    where b.compound_id = c.id
  ) as has_bioactivity_record
from public.compounds c;
