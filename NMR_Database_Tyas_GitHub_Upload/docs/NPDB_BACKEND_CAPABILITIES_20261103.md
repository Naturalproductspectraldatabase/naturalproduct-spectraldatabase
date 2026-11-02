# Backend capabilities and editor integration

Base QA606ba8f plus unchanged PR #20 commits (original branch untouched).
Independent #36 mutation assertions are preserved; their harness now compiles
real permission dependencies and supplies synthetic server-approved credentials.

Curation is allowed for an authenticated server-approved editor (including
npdb_tjomori when explicitly configured) and owner. Viewer/anonymous cannot write.
Deletes, replace-all specimen-link operations, bulk import administration,
backup export/save/upload and approvals require owner/admin/owner_editor.
Editors cannot grant reviewed/curated/approved/published status or mutate arbitrary
tables/account configuration. They can curate imported records and update
non-approval fields. No application account-management endpoint was found;
server configuration remains outside the editor's capabilities.

Checks execute at actual compound/child entry points, direct REST mutation
helpers, raw REST dispatcher, SQLite row writers, uploads and generated-structure
saves. They precede health checks, credentials, uploads and database connections.
Internal audit append retains curation authorization; this change does not make
existing best-effort audit durable or transactional. That remains a release concern.

Every action rechecks current server configuration and credential revision;
revocation, role/password changes and missing login proof fail closed. Existing
sessions must sign in again after rollout. Username comparison follows the
case-sensitive login implementation, avoiding slug collisions. Legacy single-user
owner access requires the configured owner username and active credential.
Shared approved-name mode remains viewer only.

Storage signatures require current authenticated read capability at every call,
including after revocation; no shared cache can bypass this check. Scientific
buckets remain private; viewer cannot sign backup/export objects. Signing lifetime
is capped at five minutes. Previously issued signed URLs remain usable until their
expiry; server checks cannot revoke an already-issued bearer URL. Uploads do not
upsert objects and cannot emit public scientific URLs. Object traversal and
unsupported buckets are rejected. Direct HTTPS fetching/redirect restrictions are
reviewed separately from this application authorization change.

Independent tests exercise real functions with fake HTTP and synthetic SQLite:
viewer/anonymous no writes, editor insert/update but no delete, owner allowed;
revoked/mismatched/rotated accounts, absent credential proof, SQL table injection,
approvals/account tables, raw REST bypass, malformed storage paths, private signing,
backups, uploads and replace-all links. Existing CAS/data-integrity/submission
assertions remain unchanged; their fixtures now supply an authorized synthetic
owner using the actual permission functions. Full-script AppTest checks login,
editor/viewer separation, revocation and password rotation with network forbidden.

Rollback: close unmerged PR; after QA integration revert the capability commit
and dependent #20 commits only if no consumers remain. No schema or scientific
record changes require reversal. Do not re-enable unguarded writes as a production
rollback: disable curation/upload/admin operations until corrected authorization
passes independent tests. Original #20 branch is not updated or merged by this PR.
No production Supabase, credentials, paid staging, deployment or main/QA merge.
Keep #14 draft pending independent review, #22, #24 and actual browser role QA.
