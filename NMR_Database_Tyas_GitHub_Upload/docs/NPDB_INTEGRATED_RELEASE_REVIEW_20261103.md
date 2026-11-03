# Integrated release validation

Reviewed base: 35c0d583eb8f3a63681acdb21d6467535451bbc0 (#47).
Issues #17/#22/#24/#43/#44 and source PRs #38–#42/#45 read before changes.
Reviewer previously authored some originating changes: this fresh validation is
not an independent third-party sign-off. Another reviewer is required.

## Confirmed findings and changes

1. Generic CSV/XLSX serializers accepted raw owner dataframes. GPS redaction at
specific read wrappers/export builders did not protect these alternate sinks.
Redact copied canonical/renamed GPS columns and Field/Value metadata tables at
CSV, XLSX and full-record workbook serialization. Owner/editor access remains;
revoked identity fails closed; input scientific frames are never mutated.
2. Raw GET/HEAD dispatcher attached privileged headers with no account check.
A viewer could reach private backup Storage and audit routes through this internal
function. All read requests now require current authenticated read capability;
non-science/admin routes and private backup/export buckets require owner access.
Non-JSON raw REST downloads require owner permission. These are reproduced internal
code paths, not proof of a remotely exploitable public endpoint.
3. Storage sign route treated any non-GET method as signing/read authorization.
Require POST explicitly. Existing write/delete guards remain intact.
4. Raw science REST JSON responses could bypass dataframe GPS wrappers. Redact
nested canonical GPS keys and ordinary PostgREST GPS aliases at response return.
No real service/key/response is used in tests.
5. Candidate CI filters did not include PRs targeting the integrated branch.
Enable existing Python/Streamlit/RDKit/PostgreSQL, GPS and WAL synthetic workflows
for that target; add openpyxl to jobs running actual XLSX negative tests.

## Reproductions and validation

New actual-function synthetic tests cover owner-to-viewer CSV/XLSX and metadata
workbook serialization, revoked-owner output, raw private Storage/admin GET/HEAD,
signing DELETE, unauthenticated science reads, nested/aliased REST GPS and input
preservation. Existing full suite covers path traversal, symlink/hardlink/file swaps,
HTTPS redirects/type/size guards, private signing, stale login, direct mutation,
ZIP attachments, curated drawings, structure filter/cache, structure-save CAS,
WAL-consistent SQLite readback, legacy numerical matcher and randomized oracle.
No NPDB application initialization against real data/services occurs; AppTest uses
empty disposable local databases and blocked network. PostgreSQL verification runs
only in the existing disposable synthetic CI service; no local PostgreSQL tools
were available here. Exact local and CI results are recorded in PR comments.

## Remaining release blockers and limits

#24 actual PostgreSQL + private Storage backup/restore remains mandatory and untouched.
#19 browser owner/editor/viewer acceptance and #43 location-publication policy are
pending. Precise data in arbitrary free text, historical attachment bytes/EXIF,
nonstandard query expressions and historical session-state contents cannot be
certified by column-based redaction. Shared raw caches remain server-internal;
viewer-first cache population may omit GPS for a later owner until refresh.
Current synthetic tests do not prove broad browser/session-state non-disclosure.
No claim of complete GPS confidentiality for every legacy attachment is made.
Source aliases/joins beyond ordinary GPS aliases need further policy/review.
Existing best-effort audit is not transactional. Scientific formula/mass/provenance,
unknown stereo/tautomer semantics, NMR input bounds/zero-tolerance edge and #44
legacy dataset provenance remain unresolved; successful numeric tests do not prove
chemical identification or experimental provenance. No automatic scientific data
repair, unit filling or normalization is introduced.

No production, main, Supabase credentials, scientific files, actual backups, paid
services or deployments touched. Only new branch/source/tests/CI/docs changed.
Rollback: close unmerged draft. If later integrated, revert this isolated commit
with CI/dependency review; no data/schema rollback. Keep affected exports/admin
reads disabled during a production rollback until corrected guards pass review.
Do not merge #47 or this draft without independent review and release gates.
