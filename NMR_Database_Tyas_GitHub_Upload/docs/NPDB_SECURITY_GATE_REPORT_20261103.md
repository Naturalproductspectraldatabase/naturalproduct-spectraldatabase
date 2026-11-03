# Security and database-integrity release gates

Base reviewed: #53 2e884ed9f45f6da43decdb61f5c60b4742d5662f, stacked #47–#53.
Scope is security/integrity only; scientific algorithms/displays unchanged. Work
owns actual recovery/browser acceptance. Reviewer authored earlier security code;
this renewed adversarial validation is not an independent third-party signoff.

## PASS evidence (limited to stated scope)

Actual final backend functions are executed with synthetic accounts, fake HTTP,
empty AppTest databases, synthetic files and isolated SQLite. Full local suite:
238 tests passed, zero skips, Python3.11 with pinned Streamlit/RDKit/openpyxl.
Initial expanded offline CI with pandas3 failed a pre-existing #53 None-vs-NaN
scientific test; other jobs passed. Offline CI is now pinned to the established
full-suite pandas2.2.3 dependency. No scientific assertions or algorithms weakened;
pandas3 compatibility remains unverified and is handed back to the science lane.

Existing tests cover owner/editor/viewer/unauthenticated GET/HEAD/POST/PATCH/DELETE,
revocation, direct REST/SQLite, private Storage signatures, uploads, GPS CSV/XLSX/
ZIP/JSON, cached dataframe copies, paths/HTTPS, original image bytes/provenance,
CAS races and WAL snapshots. #52/#53 changes retain these passing assertions;
no new mutation/privilege entry point was found in their disclosure/status helpers.
Scientific validity of their displays is outside this lane.

New tests expose and fix raw-call gaps: bypass of the public signing wrapper's
300-second cap; caller overrides of privileged identity/method headers; raw upsert
requests bypassing no-overwrite wrapper; quoted/whitespace GPS aliases; private
HTTP error bodies echoed into application errors. Tests use only synthetic markers.
Raw-call behavior is not proof of a remotely exploitable web endpoint.

## Live metadata / least-privileged plan evidence (read-only)

Catalog inspection found SELECT grants for anon/authenticated on import_batches
and import_records, RLS enabled and not forced; both roles NOSUPERUSER/NOBYPASSRLS.
The only matching SELECT policies observed were PERMISSIVE USING(false).
Read-only transactions SET LOCAL ROLE anon/authenticated and EXPLAIN without
ANALYZE returned Result / One-Time Filter:false for import_records. The tool exposes
only the final statement's result; no independent plan output is claimed for
import_batches. No import rows, private data or credentials were read. RLS alone
is not the evidence: the actual policy predicates and effective role plans matter.

Disposable PostgreSQL CI creates both tables with synthetic rows, grants SELECT,
sets non-bypass anon/authenticated fixture roles and verifies zero rows. A second
synthetic policy USING(true) demonstrates permissive OR composition can reopen
access. This is a regression/future-policy hazard, not a current live exposure.
Actual signed-token/Data API gateway behavior is not certified by EXPLAIN.

## Unapplied reversible default proposal

Live column metadata confirms curation_status DEFAULT 'curated'::text and nullable.
Draft up/down SQL is under docs/proposed_migrations, outside automatic migration
discovery. UP changes only DEFAULT to imported; DOWN restores the observed curated
default. No UPDATE, row relabeling, new constraint, NULL conversion or privileges.
PostgreSQL synthetic tests execute the actual files, verify omitted-field insert,
explicit reviewed/NULL behavior, unchanged historical rows and rollback/readback.
Explicit NULL still remains NULL: default changes do not imply a NOT NULL policy.
This does not stop an independently privileged writer explicitly setting curated.

DO NOT APPLY to production until Work verifies #24 recovery, independent review and
explicit release authorization. Before authorized execution, recheck catalog default,
constraints/server version and capture rollback SQL; register the approved proposal
using the current migration tooling. Synthetic PostgreSQL18 CI is not production
PostgreSQL17.6 validation or actual recovery. No production DDL/DML was executed.

## BLOCK / unresolved gates

#17/#22 are NOT complete release gates: independent review, legacy file compatibility
and safely isolated browser roles/downloads remain pending. #24 actual complete
PostgreSQL + private Storage byte backup, checksums/offsite and independent restore
remain mandatory and owned by Work. #19 browser acceptance is not performed here.
#43 requires owner-approved locality/depth/sample-code/date policy; no fields or
stored scientific information are silently deleted. Arbitrary attachment/EXIF,
free-text locations, historical session state and complex API expressions are not
certified by column redaction. Shared raw server caches are internal; viewer-first
read cache may omit GPS for an owner until refresh. Durable transactional audit and
independent scientific provenance approval remain unresolved.

No merge, deployment, main/other-owner branch changes, production credentials,
scientific records/files, actual backup files, paid services or subscriptions.
All synthetic jobs are enabled for PRs targeting the exact #53 branch; exact head
CI run links and any failures are recorded in the PR and #17 after completion.

## Rollback

Close this unmerged draft. If integrated later, revert its single source/test/CI
commit with dependency review; source changes require no data rollback. Migration
is not applied. If later authorized and applied, DOWN restores only the prior
default and preserves rows; that also restores implicit-trust risk, so prefer
pausing omitted-status inserts until a corrected default is reviewed. Never undo
historical scientific rows as part of this rollback. Do not merge without review.
