# Cumulative candidate for independent review

Base #57 fee5d3fdc021d2f7c21112f85cde2a24a00f85fe; retains the entire #14–#57
stack without merging any PR. Candidate targets the QA branch, not main. Review
5775168596 was COMMENT/non-approval; this candidate is not represented as approved.

Reconciliation: #20's approved-user capability is incorporated and superseded by
current configured identity/credential-revision checks and action guards (#39).
#35's descriptor reader is incorporated in npdb_asset_paths with subsequent
content/size/writer/HTTPS guards (#38), wired into actual readers and #57 account
checks. #38 exact commit is not an ancestor because of cherry-pick/integration;
matching functionality is established by source and boundary regressions, not SHA
ancestry alone. #47 contains the combined implementation; #48 serializer/raw API,
#54 request hardening/default proposal, #55 dependency bound, #56 chemistry and
#57 read gates are preserved. No parallel patch is blindly applied again.

Legacy duplicate definitions remain in app.py: loaders, compound/child mutation,
get_db_signature, load_search_index and several helpers have earlier shadowed
versions. Python uses the final definitions; security tests extract those final
functions and full-script AppTest runs the application. Removing legacy duplicates
is deferred to a separate refactor, not mixed into release reconciliation.

Indirect-reader audit: get_full_file_path has one application caller,
validate_spectrum_entry, which checks presence only. local_asset_available is used
by this compatibility locator and library availability checks. Actual structure,
spectrum, specimen and ZIP sinks consume authorized bytes; they do not dereference
returned raw locators. Trusted branding reads remain separate for login. Owner-only
SQLite backup uses the WAL-aware helper. New static regression audits locator
callers/sinks; actual-function tests verify saved locator plus revocation, preview
refusal, separate session identity, and unchanged authorized bytes.

Evidence levels: AST/call-site assertions are STATIC; fake transport/synthetic
account functions are UNIT/BOUNDARY tests; real SQLite WAL/readback and synthetic
PostgreSQL dump/restore are INTEGRATION tests; Streamlit AppTest uses a temporary
empty database and blocked network. None is a real browser acceptance. Work's #19
browser observations concern deployed main (exact SHA unverified), not this
candidate. No new browser pass is claimed. Exact candidate CI results are appended
in PR comments; all gates must be evaluated against that SHA.

Open: independent approval, Work browser role/attachment tests, EXIF/legacy file
contents, session/browser cache history, locality policy #43, scientific signoff,
and genuine isolated production restore #24. Encrypted exports/Drive checks passed
as recorded by owner; no backups downloaded or used in CI. No production/main,
schema, credentials, scientific data or deployment changed. All automatic schema
migration proposals stay unapplied.

Rollback: close unmerged candidate; no schema/data reversal. If later integrated,
revert the candidate changes and reviewed dependencies together; preserve guarded
read/write boundaries. Next: independent cumulative review, then separately review
the #19 browser fix. Do not merge superseded parallel drafts independently.
