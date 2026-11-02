# Offline backup inventory and integrity checks (no NPDB production access)

**Target:** a trusted local computer, not GitHub CI and not a public repository. This tooling verifies *local file bytes* against a private manifest and independent expected object counts. It does **not** export NPDB production data and is **not a restore rehearsal**.

## Prerequisites

1. Complete a full SQL backup of NPDB (schema, data, and roles as required by the current Supabase official instructions) to a private directory.
2. Separately export every required Supabase private Storage object byte into a path-preserving local folder.
3. Independently read **current** source inventory counts (live `storage.objects` bucket counts), and check whether any objects changed during export. Snapshot counts from previous days are not proof of completeness.
4. Keep data, manifests and logs confidential and encrypted; never commit these files to GitHub or upload them into public CI.

Example **synthetic directory layout** (not actual production content):

```text
/private/npdb-backup/
  database/
    roles.sql
    schema.sql
    data.sql
  storage/
    structures/
      example/TEST-A.png
    spectra/
      example/TEST-B.dx
  [optional other bucket directories]
/private/npdb-20261103-private-manifest.json
```

## Generate a manifest after source inventory is independently counted

From a trusted machine that has the NPDB repository checked out, and with the real expected counts substituted:

```bash
python NMR_Database_Tyas_GitHub_Upload/scripts/npdb_backup_manifest.py \
  /private/npdb-backup \
  /private/npdb-20261103-private-manifest.json \
  --bucket structures=4076 \
  --bucket spectra=161 \
  --require-db schema.sql \
  --require-db data.sql \
  --require-db roles.sql
```

**Important:** `4076` and `161` are **illustrative historical counts** as of 2026-11-03 JST. Recheck the source *at export time*. Include all other nonempty buckets in scope, using an additional `--bucket bucketname=count`, and ensure there is a directory for each bucket (including empty buckets).

The command writes a **private, non-overwriting manifest** with relative paths, byte lengths and SHA-256. It rejects a manifest saved in the backup root or any Git worktree, wrong bucket counts, absent logical dump parts, zero-byte files and symlinks.

The manifest itself exposes source object paths, so treat it as confidential research metadata.

## Independently verify the local backup

```bash
python NMR_Database_Tyas_GitHub_Upload/scripts/npdb_backup_verify.py \
  /private/npdb-backup \
  /private/npdb-20261103-private-manifest.json \
  --require-bucket structures \
  --require-bucket spectra
```

This fails if any listed object is missing, truncated, changed, duplicated, or if an untracked file is present in a declared bucket. The verifier does not read production Supabase or print private names/paths on failure.

### What success proves

- A local *manifest-selected* set of database export files and Storage objects is present and byte-for-byte consistent with its recorded checksums.
- Counts for selected buckets equal the independent expected values supplied to the generator.
- Basic path traversal, unsafe symlink and duplicate entry hazards are rejected.

### What success **does not** prove

- That the source inventory was complete (if the independent source count is wrong, the tool cannot detect missing remote files).
- That the SQL export was a transaction-consistent snapshot or contains all eight expected NPDB tables, data, grants, extensions, policies, triggers or migration history.
- That actual PostgreSQL restoration will succeed, or that Storage objects will be restored automatically.
- That a production service can safely be redeployed or that downtime/RPO/RTO targets are met.

## Final release gate

Before merging PR #14 or any write-capable production migration: **restore into a separate local PostgreSQL/Supabase-compatible environment**, check each expected table and foreign key, restore Storage bytes independently, confirm sample downloads and permissions, and keep a private signed verification record. Production itself must never be the restore-test target.

Tracking: [Issue #24](https://github.com/Naturalproductspectraldatabase/naturalproduct-spectraldatabase/issues/24). This workflow is free and makes no paid development branches.
