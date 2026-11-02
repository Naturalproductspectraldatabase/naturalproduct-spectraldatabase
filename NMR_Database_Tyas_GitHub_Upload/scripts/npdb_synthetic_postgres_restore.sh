#!/usr/bin/env bash
# Fully disposable PostgreSQL dump/restore smoke test on SYNTHETIC data only.
# Never connect this script to production Supabase or external database hosts.
set -euo pipefail

if [[ "${NPDB_SYNTHETIC_RESTORE:-}" != "1" || "${PGHOST:-}" != "127.0.0.1" || "${PGPORT:-}" != "5432" ]]; then
  echo "REFUSING: requires synthetic-only flag and local PostgreSQL at 127.0.0.1:5432" >&2
  exit 2
fi
for required in psql pg_dump pg_restore createdb; do
  command -v "$required" >/dev/null || { echo "Missing PostgreSQL client: $required" >&2; exit 2; }
done

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixture="$project_dir/tests/fixtures/synthetic_pg_restore.sql"
if [[ ! -f "$fixture" ]]; then
  echo "Missing synthetic SQL fixture" >&2
  exit 2
fi
temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT
chmod 700 "$temp_dir"

# Both database names are hardcoded synthetic-only names and unique to this
# throwaway GitHub service container. Never run a restore onto 'postgres',
# Supabase 'npdb', or any externally configured database.
source_db="npdb_synthetic_source"
target_db="npdb_synthetic_restored"

psql -X -q -v ON_ERROR_STOP=1 -d postgres -c   "CREATE ROLE npdb_synthetic_viewer NOLOGIN;"
createdb "$source_db"
createdb "$target_db"

psql -X -q -v ON_ERROR_STOP=1 -d "$source_db" -f "$fixture"

# Physical DB/Storage objects are intentionally NOT part of this drill.
# PostgreSQL custom-format dump includes schema, data, constraints, policies,
# grants and sequence state for the synthetic public schema.
pg_dump -Fc --no-owner --schema=public -f "$temp_dir/synthetic.dump" "$source_db"
test -s "$temp_dir/synthetic.dump"
pg_restore --list "$temp_dir/synthetic.dump" > "$temp_dir/archive-toc.txt"
grep -q "TABLE.*compounds" "$temp_dir/archive-toc.txt"
grep -q "POLICY.*npdb_read_published" "$temp_dir/archive-toc.txt"

pg_restore --exit-on-error --no-owner --clean --if-exists   -d "$target_db" "$temp_dir/synthetic.dump"

tables=(compounds specimens nmr_datasets nmr_peaks spectra_files bioactivity_records audit_events)
for table in "${tables[@]}"; do
  query="SELECT md5(COALESCE(string_agg(row_to_json(t)::text, '|' ORDER BY t.id),'')) FROM public.${table} t;"
  before="$(psql -X -qAt -v ON_ERROR_STOP=1 -d "$source_db" -c "$query")"
  after="$(psql -X -qAt -v ON_ERROR_STOP=1 -d "$target_db" -c "$query")"
  if [[ -z "$before" || "$before" != "$after" ]]; then
    echo "RESTORE FAILED: synthetic table mismatch (${table})" >&2
    exit 1
  fi
done

# Each experimental/solvent-specific NMR measurement must remain separate.
nmr_count="$(psql -X -qAt -d "$target_db" -c "SELECT count(*) FROM public.nmr_datasets;")"
[[ "$nmr_count" == 3 ]] || { echo "RESTORE FAILED: NMR datasets merged or lost" >&2; exit 1; }

# Check schema-level constraints and RLS policies, not merely row counts.
rls="$(psql -X -qAt -d "$target_db" -c "SELECT relrowsecurity FROM pg_class WHERE oid='public.compounds'::regclass;")"
[[ "$rls" == t ]] || { echo "RESTORE FAILED: row-level security not enabled" >&2; exit 1; }
policy="$(psql -X -qAt -d "$target_db" -c "SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename='compounds' AND policyname='npdb_read_published';")"
[[ "$policy" == 1 ]] || { echo "RESTORE FAILED: expected RLS policy absent" >&2; exit 1; }
viewer_count="$(psql -X -qAt -d "$target_db" -c "SET ROLE npdb_synthetic_viewer; SELECT count(*) FROM public.compounds;")"
[[ "$viewer_count" == 1 ]] || { echo "RESTORE FAILED: viewer access or embargo filter" >&2; exit 1; }

# Reproduced foreign keys must reject orphans.
if psql -X -q -v ON_ERROR_STOP=1 -d "$target_db" -c   "INSERT INTO public.nmr_peaks(dataset_id,delta_ppm) VALUES (999999,1.23);"   >/dev/null 2>&1; then
  echo "RESTORE FAILED: orphan synthetic NMR peak was accepted" >&2
  exit 1
fi

# Sequence values must survive an archive restore, so adding another synthetic
# compound must not collide with existing primary keys.
psql -X -q -v ON_ERROR_STOP=1 -d "$target_db" -c   "INSERT INTO public.compounds(trivial_name,published) VALUES ('SYNTHETIC-AFTER-RESTORE',true);"   >/dev/null

echo "PASS: synthetic PostgreSQL dump and independent DB restore; 7 tables, data hashes, RLS, policies, FK, sequence and isolated NMR datasets."
echo "LIMITATION: this does NOT prove any NPDB production dump, Supabase auth/storage restoration, or disaster recovery."
