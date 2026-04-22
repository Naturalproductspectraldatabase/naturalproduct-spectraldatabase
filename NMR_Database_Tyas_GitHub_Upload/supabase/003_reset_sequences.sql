select setval(
  pg_get_serial_sequence('public.compounds', 'id'),
  coalesce((select max(id) from public.compounds), 1),
  true
);

select setval(
  pg_get_serial_sequence('public.proton_nmr', 'id'),
  coalesce((select max(id) from public.proton_nmr), 1),
  true
);

select setval(
  pg_get_serial_sequence('public.carbon_nmr', 'id'),
  coalesce((select max(id) from public.carbon_nmr), 1),
  true
);

select setval(
  pg_get_serial_sequence('public.spectra_files', 'id'),
  coalesce((select max(id) from public.spectra_files), 1),
  true
);

select setval(
  pg_get_serial_sequence('public.bioactivity_records', 'id'),
  coalesce((select max(id) from public.bioactivity_records), 1),
  true
);
