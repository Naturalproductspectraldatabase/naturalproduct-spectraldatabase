# Structure-query identifier save integrity

Base QA606ba8f; independent concern from #38/#39/#40. The query save action now
passes the displayed compound row's original revision to the backend. Missing or
mismatched original IDs/revisions fail closed. Cloud preflight detects known
conflicts before deriving identifiers, and the final PATCH includes an atomic
expected_updated_at predicate, so a concurrent update after preflight is rejected.
SQLite uses BEGIN IMMEDIATE and UPDATE WHERE id AND updated_at, checks rowcount,
and rolls back on a stale/missing record. Only changed identifier fields are sent.
Cloud saves do not rewrite an independent local mirror from an older snapshot.

The action preserves the registered structure drawing/path and makes no generated
asset writes. Structure rendering remains available through existing preview code;
identifier derivation does not create an orphan image or replace curated provenance.
No original scientific data/images/citations are changed by this source-code PR.
No standardization, formula/mass validation or stereochemical interpretation added.
User-initiated identifier changes still require scientific review; see #18.

Synthetic tests execute actual save code with fake cloud transport, inspect CAS
arguments, reject missing revision/wrong record/preflight conflict/final PATCH race,
verify no generated-image call and no-op behavior, and use an independent real
SQLite connection to verify stale updates preserve newer fields and drawing path.
Local Python3.11/pinned Streamlit suite: 124 tests passed, zero skips.
Existing login, CAS, New Submission and all-field SQLite roundtrip tests pass.

Companion #39 supplies current-account authorization, and #38 supplies attachment
containment. Independent review and exact-head CI plus combined tests required;
this PR alone is not a release clearance. No production, credentials, schema,
Supabase data, paid staging, deployment or main/QA merge.

Rollback: close unmerged PR; after QA integration revert this isolated commit and
its caller signature together. No database rollback required. Do not re-enable
unguarded structure saves in production: disable this save action pending a tested
fix. Keep production PR #14 draft until actual #24 restore and browser acceptance.
