# Backend security review — 2026-11-03 JST

Baseline: QA `606ba8f7decdd3767a93b64ac8a3a2896d6e8bd9` (draft #14).
Editor branch reviewed: `af134f3a7740e2300b589470c74c91f2f1b2053f` (#20).
NMR #30 head: `8da2589bd5ca04e0262d7caee3e3a34d9a625eec`, already merged into QA.

No production connections, records, credentials, deployment, schema or paid resources
were changed by this work. app.py was NOT edited: its ownership remains with #20.
This is an incremental helper and audit PR, NOT closure of #22.

## Local reader inventory (QA baseline line numbers)

| Entry/sink | Finding / required integration |
| --- | --- |
| get_full_file_path (5440) | Returns arbitrary absolute paths; joins relative paths without containment. Do not treat a Path return as authorization. |
| validate_spectrum_entry (4588), library presence checks (11967) | Resolve record paths; presence checks must use same root policy without disclosing filesystem details. |
| load_standardized_structure_image (5751), source loader (5806) | Pillow opens path; read approved bytes first, then decode BytesIO and preserve curated image authority. |
| _asset_bytes_from_source (8699) | Full-record ZIP can read arbitrary local bytes via read_bytes; use bounded reader before adding any member. |
| spectrum detail (9032–9088) | st.image path and open for PDF/other downloads; pass approved bytes, never re-open a validated path. |
| render_asset_preview (9141–9153), final structure renderer (14244) | Image/specimen previews and downloads also need central byte reads. |
| branding (920,944) | Trusted configured assets, separate from record-controlled science roots; do not widen roots to whole project for branding. |
| SQLite export (5846), backup functions (6404 onward) | Intentional privileged data access, NOT scientific attachments; require owner capability, never add database/backups to attachment roots. |
| save_uploaded_asset (12917), generated structures (13973) | Write boundaries need authorized curation, upload content/size validation and safe filename policy; new reader is not a writer guard. |

Approved root proposal: data/structures, data/spectra, data/specimens only;
select the minimum relevant subset per consumer. Do NOT allow project, data,
configuration, database, submissions, backups or exports wholesale. Inventory
legacy values privately before rollout. Rejecting a path does not rewrite or
remove its scientific metadata. Curator must intentionally relocate any legitimate
out-of-root file; no fallback search by basename.

## Implemented primitive and tests

`npdb_asset_paths.read_local_asset` accepts project-relative and contained absolute
paths, explicit roots, per-context suffix allowlist and byte limit. POSIX descriptor
walking pins directories and uses O_NOFOLLOW on each component, including roots.
It rejects traversal, Windows/UNC syntax, remote/encoded paths, hidden components,
symlinks (even contained ones), hardlinks, devices/FIFOs, missing/directory files,
wrong suffixes and oversized/changed files. Generic errors exclude original paths.
Unsupported OS capability fails closed. No cache or filesystem mutation is used.

Synthetic fixtures cover secrets/unrelated files outside roots, prefix siblings,
leaf/directory/root symlinks, hardlinks, race substitution immediately before open,
exact byte limit, FIFO, legitimate unchanged scientific bytes, and refreshed reads.

Trust boundary: roots and limits come from trusted server configuration, not record
metadata. OS users must not be able to write arbitrary files into the asset roots.
Suffixes are not MIME validation: consumers must decode images safely and enforce
format-specific upload checks. Large legitimate scientific files require an explicit
reviewed limit/streaming design. Remote HTTPS and private Storage URL authorization
are separate outstanding reviews; this module does not fetch or sign URLs.

## Backend authorization: reproduced finding, not hypothetical

Run `python NMR_Database_Tyas_GitHub_Upload/scripts/npdb_security_boundary_probe.py`.
The probe extracts the final live function definitions via AST, executes the real
readiness/delete functions with fake transport and synthetic session state, and
exits **1** on findings. No application initialization or credential loading occurs.

On both baseline QA and #20, viewer, editor and unauthenticated states all reach a
fake REST DELETE through `delete_compound_record`. This proves missing function-boundary
checks; it does NOT demonstrate a remotely exploitable production request.
`ensure_write_target_ready` checks backend availability, not role authorization.
PR #20 improves a server-configured menu capability but leaves this defect present.

Required follow-up in coordinated app.py integration:
- Check server-backed authenticated/revoked role at each mutation boundary.
- Separate owner-only delete, account management, approvals, backup/admin from editor curation.
- Gate lower REST/SQLite mutation helpers and upload handlers as defense in depth;
  ensure audit-internal writes have narrowly scoped explicit context, not blanket bypass.
- Test real insert/update/upload/delete functions with fake transport and disposable DB,
  including revoked users, mismatched role, stale authenticated state and no config.
- Keep npdb_tjomori configuration out of Git and never share the owner's credential.

## Scientific/cache review

C12: final get_db_signature uses Supabase count/latest updated_at (30-second cached
signature), snapshot max mtime or SQLite main-file mtime. In-process mutations clear
structure caches. This does not prove cross-process/WAL freshness or detect edits
that fail to update timestamps. Structure resource cache has no TTL. Prefer an
explicit mutation/version token and bounded refresh; do not cache failures as empty
valid datasets. Benchmark before query changes. No unmeasured optimization shipped.

C13: source uses canonical SMILES for Identity, default Morgan fingerprints for
similarity, and HasSubstructMatch without useChirality for substructure. These modes
must not share a chemical-identity claim. An empty filtered ID set bypasses the
`if allowed_ids` restriction and can search all indexed candidates. RDKit unavailable
in this local environment: no executed chemistry validation claimed. Claude retains
scientific helper ownership; require enantiomer/unknown stereo/salt/tautomer fixtures
and an explicit normalization contract, preserving original structures.

C14: save_structure_query_to_compound derives identifiers but its update does not
pass expected_updated_at (unlike ordinary record update). Concurrent structure saves
can overwrite newer structure metadata and upload a now-orphaned generated image.
Keep existing CAS protections and extend them here before optimizing writes.

#30: reran the 300-case exhaustive small-assignment oracle, permutation/translation,
invalid input and endpoint tests in the regression suite. Algorithm uses O(n*m)
time/memory; large input bounds remain necessary. New independent edge probe:
`optimal_nmr_peak_matches([0], [5e-13], 0)` returns a match. The 1e-12 absolute slack
also applies to zero tolerance; relative slack grows with extreme tolerance values.
The current oracle uses 1e-14 slack and a 0.01-grid, so it does not test that gap.
Request Claude agreement on exact-zero versus decimal-roundoff semantics before
changing the scientific predicate. Numeric matching is not compound confidence.

## Validation and rollback

Reproduce: `python -m unittest discover -s NMR_Database_Tyas_GitHub_Upload/tests -v`.
Initial run: 127 tests, 122 passed / 5 Streamlit tests skipped (dependency absent).
Final dependency-installed run and exact PR commit are recorded in the PR comments.
The security probe intentionally reports three findings per reviewed revision;
it must not be described as passing authorization acceptance.

Rollback: close this unmerged helper PR. If integrated into QA, revert its isolated
commit; it has no schema/data migration and no app.py call sites. Once callers are
integrated, do not restore unsafe reads as a workaround: disable affected downloads
until a fixed reader is validated. No production rollback is performed here.

Release remains BLOCKED: #22 integration, #20 backend authorization, independent
review, exact-head CI, actual complete DB+Storage restore (#24), and owner/editor/viewer
browser acceptance. Synthetic PostgreSQL restore tools do not satisfy actual recovery.
