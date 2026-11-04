-- PROPOSAL ONLY. Not in migration discovery. Requires #24 and explicit release approval.
BEGIN;
SET LOCAL lock_timeout = '5s';
ALTER TABLE public.compounds ALTER COLUMN curation_status SET DEFAULT 'imported';
COMMIT;
