# Structure index correctness and scientific review

Baseline QA606ba8f. No production connection, data write, schema change, curated
image regeneration or normalization. Science assumptions are coordinated in #18;
Claude's unpublished helper is not overwritten or treated as available code.

## Implemented C12 increment

Chemistry cache now takes the explicit filtered `(compound_id, original_smiles)`
snapshot. It performs no second global database query, never expands an empty
filter, and keys additions, deletions and structure changes independently of a
remote count/max-timestamp signature. Only molecule/fingerprint/canonical strings
are cached; result metadata joins the current caller's rows, avoiding stale
cached display metadata. Cache TTL is 60 seconds and maximum 16 entries. New tests
show metadata-only edits reuse chemistry while new/deleted/changed structures
produce new cache keys. Invalid/duplicate IDs, unknown modes and nonfinite/out-of-range
thresholds fail closed.

SQLite signatures include main/WAL inode, byte size and nanosecond mtime/ctime.
An actual synthetic WAL commit test proves main mtime stays unchanged while the
signature changes. Snapshot signatures hash the complete sorted CSV inventory,
including deletion and non-max-mtime replacements. No scientific bytes are read
just to construct these signatures. This is correctness/query elimination evidence,
not a claimed wall-clock speedup benchmark.

Limits: the caller's data cache still has its existing 60-second TTL; remote
changes are not instant cross-session invalidation. Supabase count/latest timestamp
is not a transaction/version token and its failure handling remains imperfect;
no production trigger/version migration is introduced. Tests show fresh data passed
by a second session is respected without restart, not immediate detection of every
external write. Resource bounds and explicit keys prevent permanent index staleness.

## C13/C14 executed characterization

RDKit 2026.09.1 synthetic tests run the actual canonicalization, fingerprint,
search and identifier derivation functions. Tested enantiomer vs enantiomer vs
unspecified stereo, acid vs sodium salt, keto/enol representations and invalid
SMILES. Canonical exact matching distinguishes these tested representations;
original SMILES/dataframes remain unchanged. Full derived InChIKeys distinguish
the tested enantiomers and salt, and reproduce from their derived InChI.

Morgan fingerprint similarity returns 1.0 for the tested enantiomers. Existing
substructure defaults do not enforce chirality. Neither is proof of stereo identity.
Canonical identity is representation-level equality and does not establish the
experimental absolute configuration of a curated natural product. Tautomer,
charge/salt standardization and connectivity-only modes remain scientific design
decisions for Claude; none are silently added here.

C14 is not complete: derive_structure_identifiers produces SMILES/InChI/InChIKey,
but does not validate existing curated formula, exact/average mass, missing stereo
evidence or provenance. save_structure_query_to_compound still lacks expected_updated_at
CAS and may generate an orphan image if concurrent metadata changes occur. This
must be fixed as a separate write-integrity concern; do not claim this index PR
prevents that overwrite. Any identifier discrepancy must become a curator finding,
not automatic replacement of drawings/identifiers. NP-MRD #27 source format/license
and dataset provenance decisions remain pending; no external records imported.

Primary references: [RDKit getting started](https://www.rdkit.org/docs/GettingStartedInPython.html)
(canonical/isomeric SMILES, chirality matching), [RDKit Book](https://www.rdkit.org/docs/RDKit_Book.html).

## PR #30 numerical review

The integrated 300-case seeded brute-force assignment oracle, permutations,
translation and decimal endpoint/beyond-endpoint tests pass unchanged. The matcher
maximizes one-to-one cardinality then minimizes total absolute ppm error. These
numeric tests do not validate chemical identification or solvent/experimental
conditions. O(n*m) time/memory remains an input-bound concern.

Confirmed edge: optimal_nmr_peak_matches([0], [5e-13], 0) currently returns a match
because its absolute 1e-12 roundoff allowance includes zero tolerance. The oracle
samples 0.01-grid shifts and has different 1e-14 slack; it does not resolve this
edge. Requested Claude decision in #18 on exact-zero semantics and bounded endpoint
roundoff before changing the scientific predicate. No matcher semantics are changed
by this PR; no score is presented here as confidence/probability.

## Validation and rollback

Run full offline suite plus pinned RDKit science job (added to existing CI).
Tests use synthetic molecules, dummy in-memory dataframes, synthetic SQLite/WAL and
temporary CSVs; no network chemistry resolver or real scientific data. Separate
chemistry job installs RDKit==2026.9.1; ordinary offline jobs may skip chemistry
when absent, while the dedicated job must execute it.

Rollback: revert this isolated index commit in QA, restoring prior API/cache only
if all callers are reverted together. No data/schema rollback. Avoid releasing
an empty-filter bypass as a workaround: disable structure search pending a tested
fix. Keep #14 draft; independent review, #22/#20, actual #24 recovery and browser
acceptance remain release gates.
