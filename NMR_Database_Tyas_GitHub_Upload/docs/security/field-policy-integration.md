# Field-provenance integration — development only

Parent: PR66 `298834099a8c9e3926378b315379fad1cf363878`. Earlier heads are unchanged. This document contains implementation evidence and public owner policy, not private independent-review material. Release and genuine production restoration remain BLOCKED.

## Boundary map

- `authorized_read` checks current configured identity and manifest revision before/after reads, then projects AFTER cached lookup. A ContextVar permits internal raw queries within a protected cache body; outer public/cache compatibility wrappers always project copied results. Raw caches are server-internal and never approved DTOs.
- `npdb_field_access.Disclosure` covers compound/specimen/child rows, canonical and explicit field aliases, nested dictionaries/lists, vertical metadata tables and unknown keys/headers. It retains structured chemistry/NMR measurements and references; unreviewed opaque notes/descriptions, specimen labels and attachment references are owner-only. It does not interpret chemical/taxonomic synonyms or infer geography.
- Per-field Evidence binds table, ID, field, exact value digest and revision. Existing `updated_at` is used; legacy child tables without it use a digest of their complete base row. Partial rows without sufficient identity/revision fail closed. Duplicate/conflicting/stale/missing facts never approve publication. A DOI alone is not a grant.
- Raw SQLite reads use query_only plus an authorizer blocking writes, attached databases and unrelated tables. Direct arbitrary SQL is owner-only; viewers/editors use typed protected loaders. Snapshot table names are allowlisted. Search returns are freshly authenticated/projected, including tuple results.
- Export families: name, structure, 1H/13C/combined matches, bioactivity; CSV/XLSX helpers; text summary; full-record ZIP/workbook, including separately projected linked specimen/link/extract tables. Signed process-local DataFrame receipts preserve source context across permitted row filtering, detect relabeling, and are checked again by serializers. Receipts contain no withheld plaintext values.
- Attachment readers require explicit source/content review plus a live value/revision match and SHA256 of original bytes. Existing path, symlink, HTTPS, MIME and size checks remain. A changed file or embedded metadata invalidates approval. Unreviewed original drawings are withheld, never overwritten or silently substituted.
- New direct Storage signing/reads are denied to non-owners outside reviewed internal asset reads. Remote scientific previews use checked bytes rather than browser-direct Storage/Drive URLs. Owner capability links retain their framework/Storage limitations below.
- Editor update payloads omit unseen existing fields rather than writing empty projections. Scientific allowed updates remain available. Current per-project editor grants are not implemented; editors receive only published verified non-sensitive protected fields.

## Private owner-controlled classification workflow

No scientific records, production classifications, schema or settings are modified by these tools. No automatic source verification exists.

1. In a separately authorized private environment, provide an owner-selected JSON list of records to `npdb_provenance_review.py prepare --table TABLE --input PRIVATE_INPUT --output NEW_PRIVATE_PACKET`. For this development/CI lane, inputs are synthetic only. Each enumerated field starts UNKNOWN_UNVERIFIED; the packet includes exact identity, revision and value digest. Output is created with mode0600 and refuses overwrite.
2. A human opens the actual source/supplement, verifies each field value and documented precision, restrictions and specimen identity. Attachments require separate inspection of content, filename and embedded metadata, plus an exact byte digest. DOI grouping is only a review aid.
3. Supply explicit decisions for individual candidate IDs. Each published decision requires classification, VERIFIED status, reviewer, review timestamp, exact source reference/locator, content_reviewed=true and no restrictions. No defaults invent evidence. Changed candidate identity/revision/value, duplicate decisions, missing verification or attachment digests are rejected. Batch approval includes only the explicitly enumerated fields.
4. `approve --input PRIVATE_PACKET --decisions PRIVATE_DECISIONS --output NEW_PRIVATE_PROPOSED_MANIFEST` produces a proposal. It installs nothing. Independent review and new owner authorization are required before any real-record classification or server configuration. Any future trusted server `NPDB_FIELD_PROVENANCE` uses version1/entries; it is never read from user session/form claims. New/changed values or revisions need renewed review.
5. Sample high-impact published location decisions independently; resolve disputes as UNKNOWN. Preserve original records and source precision. No automatic rounding, shifting, region inference, chemical correction or source-record rewrite.

## Delivery limits — mandatory P0 review

`SealedPayload` binds generated bytes to current identity and manifest; stale/cross-role bytes cannot register as a new download. Identity/policy are checked immediately BEFORE `st.download_button`, avoiding reliance solely on an after-call decorator. This does not make Streamlit's subsequent media HTTP endpoint authenticated or revoke previously issued URLs. The isolated browser matrix measures cross-context retrieval after logout, account removal, credential rotation and role change; actual run results are in the PR evidence, not inferred here.

A recipient-authenticated delivery endpoint that revalidates current account, policy and record revision on EVERY HTTP request is required for strict retrieval authorization; no such deployment endpoint is introduced here. Alternatives requiring explicit owner review include disabling restricted native downloads and delivering them through an already authenticated private channel. Short URL expiry reduces exposure but is not recipient binding or guaranteed revocation. No new signing keys/configuration, service or deployment is authorized by this document.

The application adapter does not replace deployed REST/RLS/Storage/RPC authorization. No production policies/grants were queried or changed. Direct privileged transport access and issued Storage links require independent private deployment validation. Native preview/media capability lifecycle remains part of that release gate.

## Evidence and rollback

Synthetic tests open real CSV/XLSX/ZIP bytes; preserve approved published values and chemical/NMR identifiers; reject unknown/internal/restricted fields, nested keys, aliases, tampered receipts, stale/rotated identities, mid-generation revocation and valid concurrent role swaps. They cover actual helper definitions, real Streamlit caches/SQLite and actual browser downloads where executed. Unit/AST tests, full-script AppTest and Chromium are different evidence levels. Unexecuted rows remain UNTESTED.

Existing16 scientific expectations, UI accessibility failures, full runtime-journey acceptance, concurrency/load, deployed API policies and genuine production restore remain separate dependencies. Source inventory is not exhaustive E2E acceptance.

Rollback: close this development draft or revert its commits on an isolated development branch to the exact PR66 parent. No database migration or rollback exists. Reverting restores the parent's incomplete field policy and is not a release recommendation. Never reset/force-push another agent's branch or merge this stack independently into main.
