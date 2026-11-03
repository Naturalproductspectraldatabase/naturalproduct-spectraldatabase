-- SYNTHETIC DATABASE ONLY, run by dedicated disposable CI service.
\set ON_ERROR_STOP on
CREATE TABLE public.compounds (id integer PRIMARY KEY, curation_status text DEFAULT 'curated');
INSERT INTO public.compounds VALUES (1, 'curated');
\ir ../docs/proposed_migrations/curation_default_imported.up.sql
INSERT INTO public.compounds (id) VALUES (2);
INSERT INTO public.compounds VALUES (3, 'reviewed'), (4, NULL);
DO $$ BEGIN
 IF (SELECT curation_status FROM public.compounds WHERE id=2) IS DISTINCT FROM 'imported' THEN RAISE EXCEPTION 'omitted field default failed'; END IF;
 IF (SELECT curation_status FROM public.compounds WHERE id=1) IS DISTINCT FROM 'curated' THEN RAISE EXCEPTION 'historical row changed'; END IF;
 IF (SELECT curation_status FROM public.compounds WHERE id=3) IS DISTINCT FROM 'reviewed' THEN RAISE EXCEPTION 'explicit status changed'; END IF;
 IF (SELECT curation_status FROM public.compounds WHERE id=4) IS NOT NULL THEN RAISE EXCEPTION 'NULL unexpectedly rewritten'; END IF;
END $$;
\ir ../docs/proposed_migrations/curation_default_imported.down.sql
INSERT INTO public.compounds (id) VALUES (5);
DO $$ BEGIN
 IF (SELECT curation_status FROM public.compounds WHERE id=5) IS DISTINCT FROM 'curated' THEN RAISE EXCEPTION 'rollback default failed'; END IF;
 IF (SELECT curation_status FROM public.compounds WHERE id=2) IS DISTINCT FROM 'imported' THEN RAISE EXCEPTION 'rollback changed rows'; END IF;
END $$;
CREATE ROLE npdb_gate_anon NOLOGIN NOSUPERUSER NOBYPASSRLS;
CREATE ROLE npdb_gate_authenticated NOLOGIN NOSUPERUSER NOBYPASSRLS;
CREATE TABLE public.import_batches(id integer, private_marker text);
CREATE TABLE public.import_records(id integer, private_marker text);
INSERT INTO public.import_batches VALUES (1,'SYNTHETIC_PRIVATE');
INSERT INTO public.import_records VALUES (1,'SYNTHETIC_PRIVATE');
ALTER TABLE public.import_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.import_records ENABLE ROW LEVEL SECURITY;
GRANT SELECT ON public.import_batches,public.import_records TO npdb_gate_anon,npdb_gate_authenticated;
CREATE POLICY deny_read ON public.import_batches FOR SELECT TO npdb_gate_anon,npdb_gate_authenticated USING(false);
CREATE POLICY deny_read ON public.import_records FOR SELECT TO npdb_gate_anon,npdb_gate_authenticated USING(false);
SET ROLE npdb_gate_anon;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM public.import_batches) OR EXISTS(SELECT 1 FROM public.import_records) THEN RAISE EXCEPTION 'anon RLS leak'; END IF;
END $$;
RESET ROLE;
SET ROLE npdb_gate_authenticated;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM public.import_batches) OR EXISTS(SELECT 1 FROM public.import_records) THEN RAISE EXCEPTION 'authenticated RLS leak'; END IF;
END $$;
RESET ROLE;
-- Demonstrate why permissive false does not protect against a future true policy.
CREATE POLICY synthetic_allow ON public.import_batches FOR SELECT TO npdb_gate_authenticated USING(true);
SET ROLE npdb_gate_authenticated;
DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM public.import_batches) THEN RAISE EXCEPTION 'permissive OR model not reproduced'; END IF;
END $$;
RESET ROLE;
