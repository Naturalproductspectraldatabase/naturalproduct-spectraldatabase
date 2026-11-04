# Security and integration review — 5 November 2026 JST

Reviewed issues #17/#19/#22/#24 and draft PRs #14/#20/#35/#38/#39/#45/#47/#48/#54/#56.
Pinned base: #56 02484b64196e191b067ebcf3715651126cfa0e72. Ownership claimed in
#17 before app.py changes; no competing active claim visible in latest coordination.
This lane previously authored security patches; renewed tests do not constitute
independent third-party approval. All PRs remain draft/unmerged.

## Dependency evidence

Current stack is #56 -> #55 -> #54 -> #53 -> #52 -> #51 -> #50 -> #49 -> #48 ->
#47 -> #14 -> main. #47 assembled the earlier asset, role, GPS, CAS and snapshot
changes. Exact #14/#39/#45/#47/#48/#54 heads are ancestors of reviewed #56;
exact #20/#35/#38 heads are not ancestors (some changes were cherry-picked or
integrated through other commits). This does not mean their functionality is
absent. Do not merge old parallel drafts independently or duplicate them onto
main; reconcile the final cumulative diff and preserve capabilities/tests.

#14:606ba8f7decdd3767a93b64ac8a3a2896d6e8bd9
#20:af134f3a7740e2300b589470c74c91f2f1b2053f
#35:e2023defda4f525f52ca0b9ee25a7133b4e832e7
#38:5bd0a7270c016627079d3c834eda9f7ed3dc5988
#39:efbfbf4821f9183a669a37cf99b7e649398ce713
#45:acad4aba8fc3868342c7bfb105e87258d3b8e5d8
#47:35c0d583eb8f3a63681acdb21d6467535451bbc0
#48:0fd7f4018cf5ce3bfe4e982e3d6f5b019ddd4904
#54:9a2091d07fb64c36bda65c2905d44dc0cc2e7cba
#55:eff14ad74ca2b07416492d2371b366259319a94a

Only workflow attached to exact #56 head was Retina run41573817377 (success,
reported247 synthetic tests). Do not infer exact-head PostgreSQL/WAL/GPS/matrix
coverage from an ancestor's checks. This PR enables the existing workflows for
PRs targeting #56; exact new-head outcomes are recorded in PR/#17 comments.

## Confirmed read-boundary defect and scoped fix

Actual read_scientific_asset, read_remote_scientific_asset and
_asset_bytes_from_source lacked current account authorization. The REST signing
and mutation guards did not cover local asset reads or ordinary HTTPS fetches.
A synthetic revoked/anonymous caller reached original attachment bytes or reader
spies through these internal Python functions. This is a callable-boundary defect,
not proof of remotely exploitable browser access. Add require_backend_permission
('read') before I/O/resolution and outside the export helper's broad exception
handler. Authenticated owner/editor/viewer retain their existing read capability;
revoked, rotated-password, promoted-session and anonymous calls fail closed.
No approved roots, format limits, HTTPS policy or scientific bytes are changed.

New tests extract actual final functions; only files and remote transport are
synthetic. Three test methods reproduced seven failing cases before the fix.
After: three new tests +20 asset tests +4 HTTPS tests passed locally. Existing
media fixtures now explicitly use a synthetic authorized owner with real permission
functions, and negative tests bind their actual role/revocation contexts.
Local Python3.14.4/pandas3.0.2/Streamlit1.56 differs from supported pinned runtime;
no complete local candidate-runtime pass claimed. No environment/package install
or PostgreSQL server was attempted on the low-disk Mac. Full pinned CI is required.

Other reviewed gates retain action checks for create/update/delete, direct REST,
SQLite, Storage signing/lifetime/upsert, owner backup/admin, and GPS CSV/XLSX/ZIP/
JSON redaction. Existing tests are rerun, not treated as blanket clearance.
Generic serializers and arbitrary supplied data/free text remain distinct from
protected attachment I/O; full historical/location confidentiality is not proven.
Shared cache/session-history, unusual query aliases, old attachment/EXIF contents,
legacy-format/root compatibility and owner locality policy remain open review gates.

## Recovery evidence and BLOCK status

Owner and issue #24 record completed encrypted PostgreSQL, globals/roles and
all4257 Storage object exports on5 Nov, plus Drive download/checksum comparisons.
Six files remain in restricted Drive; temporary S3 key revoked; primary local
backup directory removed. Do not claim two surviving independent copies.
This lane did not download, decrypt, inspect or copy any real backup/Drive object.
Genuine isolated production restore, managed-schema/Auth nuances, restored object
readback, RPO/RTO and Work's browser acceptance remain BLOCKED. Synthetic CI is not
a substitute. Work retains backup/restore/browser ownership; no server or paid
staging is installed/created by this review.

#17/#22 remain release BLOCK pending independent review and integration, legacy
compatibility and full privacy/browser evidence. #43 locality/depth/date/sample
policy is owner-owned; scientific approval remains with the science lane. The
imported-default proposal in #54 is still unapplied; no production migration is
permitted by this work. Earlier production-change authorization expired3 Nov;
no new production authorization is assumed.

## Reproduction, rollback and next step

Run python -m unittest discover -s NMR_Database_Tyas_GitHub_Upload/tests -v in the
pinned CI runtime. Targeted local cases use test_attachment_read_authorization.py,
test_asset*.py and test_remote_asset_security.py with canonical TMPDIR=/private/tmp.
Full CI includes Python3.11/3.12, Streamlit, RDKit, GPS, WAL, dependency-envelope and
disposable synthetic PostgreSQL restore/default/RLS checks. Exact SHA/results and
any failure diagnosis are appended after completion.

Rollback: close this unmerged PR. After any future authorized integration, revert
this isolated guard/test/CI commit with caller/dependency review; no schema/data
rollback. Keep attachment I/O disabled during a security rollback until reviewed
guards are restored. No main/other-agent branch, scientific data/assets, production
records/configuration, credentials, actual backups, merge/deploy or paid resources
were touched. Sparse code-only checkout limits local disk use.

Next: independently review this cumulative stack's exact final SHA and tests, then
prepare one reviewed integration candidate without merging parallel duplicates.
Keep release blocked until Work can perform a genuine isolated restore with suitable
resources and the owner authorizes subsequent release gates.
