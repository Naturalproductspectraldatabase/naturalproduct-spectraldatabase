# NPDB backup and disaster-recovery runbook (NO paid staging)

**Status:** Draft operational procedure, NOT evidence a backup has succeeded.  
**Last verified:** 2026-11-03 JST  
**Tracking:** Issue #24 (P0 backup/restore gate); issue #19 (Work owner dashboard); issue #17 (multi-agent coordination).  
**Production:** `npdb`, Supabase project `aquiutmhghrcqwzdwbjq`, region `ap-northeast-2`.  
**Supabase plan:** Free (verified using organization API). **No automatic daily backups** according to Supabase Free-plan documentation.

## Safety constraints

- Do not deploy PR #14 or run destructive production migrations until the backup is actually restorable.
- No paid Supabase staging, development branches, PITR, or subscription changes are authorized.
- Read-only connection and export only. **Never restore onto production to test backups**.
- Do not commit, attach to issues, email openly or upload to public CI: SQL exports, private Storage files, .env, passwords, service keys, credentials, signed URLs, private paths, sensitive coordinates or complete backup manifests.
- Use a trusted local machine/controlled Work computer with sufficient storage, HTTPS/SSL certificate validation, restrictive file permissions and secure encrypted off-site copy.
- Treat an incomplete checkpoint as **partial evidence only**. A successful command exit does not prove recoverability.

## Snapshot of production before backup (read-only SQL as of 2026-11-03)

| Resource | Count | Notes |
| --- | ---: | --- |
| `compounds` | 4,063 | |
| `proton_nmr` | 1,288 | Peak rows |
| `carbon_nmr` | 1,266 | Peak rows |
| `spectra_files` | 105 | DB references, not Storage object bytes |
| `bioactivity_records` | 14,649 | |
| `audit_events` | 6,838 | Last event 2026-06-10 UTC; verify audit coverage |
| `storage.objects` in `structures` | 4,076 | Approximately 298 MB based on object metadata |
| `storage.objects` in `spectra` | 161 | Approximately 29 MB |
| `storage.objects` in `backups` | 20 | Historical objects are not automatically validated backups |
| `storage.objects` in `exports` | 0 | |
| `public` tables | 8 | Also includes `import_batches`, `import_records` |

Re-query counts at export time and after any restore; older expected values are **not immutable checksums**.

## Part A — Production database logical export

Follow the current official Supabase CLI guide:  
https://supabase.com/docs/guides/platform/migrating-within-supabase/backup-restore

1. Verify CLI version and availability: `supabase --version`; `supabase db dump --help`. Use the project's Dashboard > Connect to select the correct **direct** or **session pooler** connection string. A direct IPv6 endpoint can fail from an IPv4-only client; do not keep retrying it indefinitely.
2. On the trusted computer, obtain the secret connection string through a password manager or secure environment variable, **not chat, GitHub or CI logs**. Never use shell tracing (`set -x`) around secrets.
3. In a private, restricted directory, execute the commands from the *current documentation* using the correctly quoted connection URL. Document the CLI/PostgreSQL versions and any warnings. Example output names:
   - `roles.sql`: `supabase db dump --db-url "$NPDB_DB_URL" -f roles.sql --role-only`
   - `schema.sql`: `supabase db dump --db-url "$NPDB_DB_URL" -f schema.sql`
   - `data.sql`: `supabase db dump --db-url "$NPDB_DB_URL" -f data.sql --use-copy --data-only -x "storage.buckets_vectors" -x "storage.vector_indexes"`
4. Validate **every** command exit status and file existence/nonzero size; inspect dump completion and expected tables without exposing record content in output. If connectivity fails, identify DNS/IPv6/TLS/pooler failure and retry from a new trusted connection as appropriate. Do not mark success from the partial Work checkpoint.
5. Supabase-specific objects can require separate treatment: custom auth/storage policy changes, extensions, migration history, credentials, vault/encryption settings, app secrets and platform configuration. Document these gaps. Do **not** copy sensitive authentication material into the dump report.

## Part B — Private Storage object export (separate from SQL)

Supabase documentation states that database backups **do not include Storage objects**. Download bytes individually or via a reputable verified Storage API export client running only in the trusted environment. Do not download buckets through GitHub Actions.

- Record the source bucket and exact object path, object's byte count, MIME type if meaningful, SHA-256 and extraction time in a **private manifest**.
- Inventory every object with pagination and compare exact object IDs/paths, not just total count.
- For each object, verify download completed and SHA-256 matches the local stored bytes; preserve the unmodified original bytes.
- Cover `structures` and `spectra`, plus `backups` and other buckets if their contents are in recovery scope. `exports` is currently empty; check again at backup time.
- Avoid exposing object names or signed URL tokens in PRs, CI logs or issue comments. Object names may contain confidential research metadata.
- Encrypt all copies and keep one off-device. Store decryption instructions in a secure password manager, not inside the public repository.

## Part C — Free local restore rehearsal

A **separate local** compatible PostgreSQL/Supabase environment can be used without paid hosted staging. Establish compatible roles, extensions and Supabase-managed schemas first. Follow the official restore guide and record every warning.

- Do not restore into `npdb` production under any circumstance.
- Restore roles/schema/data as supported, with `ON_ERROR_STOP` and transactional safeguards; special extension and RLS prerequisites may be necessary. The precise command depends on the local target.
- Compare all eight public table row counts, row foreign-key integrity, schema constraints, triggers, function definitions and RLS policies.
- Verify representative permitted compounds, spectra references, NMR data and read/write authorization behavior *against the restored environment* without modifying the original database.
- Verify all backed-up Storage bytes through SHA-256 and representative preview/download paths. Note that restoring PostgreSQL metadata does **not** automatically repopulate hosted Storage objects.
- Document unsupported restore sections and whether auth/config/secrets need manual reconstruction. Partial restore **fails** the release gate.

## Part D — Acceptance report (private)

Record: export start/end UTC, source project reference, backup ID, CLI/PG version, all command exit codes, bytes, SHA-256 for each SQL file, total Storage object count and byte count per bucket, object manifest hash, restore environment, table counts, test outcomes, errors, time to restore, offsite encrypted copy location and authorized reviewer.

Release status:
- **BLOCKED**: export failed or only checkpoint exists; objects missing; no independent restore/verification.
- **CONDITIONAL**: full verified export exists but no restore rehearsal; not sufficient to deploy high-risk data migrations.
- **PASS**: full export, private Storage object preservation, independent local restore/readback, owner-approved release plan.

A successful backup is not the same as a zero-data-loss guarantee. Set acceptable recovery-point and recovery-time objectives and repeat backups regularly.

## Independent evidence vs user-supplied Work report

**Directly verified:** production Free tier; Supabase active; security lints 0; eight public tables; aggregate counts and private Storage inventories; GitHub PR #14's three green tests and draft status.

**Reported by Work; not independently inspected here:** successful owner login in Work's cloud browser; actual Streamlit Cloud settings/logs; connection error during full backup export and partial checkpoint. Those observations should be rechecked from the Work session when available, not presented as verified by a separate connector.

**Do not use this documentation to claim backup completion.** The issue remains open until a verified manifest and restore test exist in a secure non-public location.
