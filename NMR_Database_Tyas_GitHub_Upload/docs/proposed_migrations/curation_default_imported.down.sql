-- Reviewed rollback only: restores the catalog-observed historical default.
-- This restores the historical implicit-trust risk; prefer disabling inserts.
BEGIN;
SET LOCAL lock_timeout = '5s';
ALTER TABLE public.compounds ALTER COLUMN curation_status SET DEFAULT 'curated';
COMMIT;
