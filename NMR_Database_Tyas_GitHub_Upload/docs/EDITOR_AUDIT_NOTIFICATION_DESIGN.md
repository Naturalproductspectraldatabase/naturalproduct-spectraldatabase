# NPDB editor audit and owner notifications — technical design

**Status: PROPOSAL ONLY, not implemented.** Date: 2026-11-02.
This document records the owner's decision to allow the NPDB account npdb_tjomori to curate data through the website, with **an email for every successful individual change**, an owner-only in-app notification, and an owner-accessible activity log. For a bulk job, one itemized email with every affected record is acceptable. Editing permissions do not include account administration, system configuration, or permanent deletion. Archive/soft delete is preferred.

**Current authorization:** a separate GitHub branch containing isolated C1/C2 tests and this design; open as a draft PR for review. No production data/schema/access/deployment changes, no real email, no automation. This document is not itself approval for implementation. Shared agent policies AGENTS.md, CLAUDE.md and NPDB_SECURITY_AND_AUDIT_POLICY.md currently reside in independent draft PR #2 and are not yet merged to main.

## 1. Verified existing code and prerequisites

- Owner/editor control is currently tied to the owner username. Changing the role label for npdb_tjomori in a secret alone does not enable editor rights.
- The app's current UPDATE request filters by row ID, not a concurrent-edit record version. Streamlit form state may outlive Supabase outage recovery.
- Streamlit ignores the parameter named _db_signature in cached function keys. This allows stale snapshot cache results after recovering the cloud connection.
- A transient network error in supabase_column_available can be cached as a false "column absent" check, causing curation_status to be silently omitted from write payloads.
- Audit events are currently recorded for successful insert/update/delete but recording failures are swallowed. Audit does not yet cover every login, download, viewing action, denied attempt or storage change.
- Supabase service-role/secret keys are highly privileged and do not provide per-user RLS enforcement. Keep them only server-side, use narrowly authorized application operations, and never expose keys to editor clients.

**Required sequencing:** Fix C1/C2 and write authorization before enabling multiple users to edit production. Record-version conflict detection is required regardless of a successful audit log.

## 2. Proposed role matrix

| Operation | Viewer | Jomori-sensei editor | Owner |
| --- | --- | --- | --- |
| Search/browse permitted data | Yes | Yes | Yes |
| Add/update compound, NMR, bioactivity, specimen metadata | No | Yes | Yes |
| Upload/replace approved supporting files | No | Yes | Yes |
| Archive/soft-delete and restore | No | Archive; restore subject to policy | Yes |
| Permanently delete record or storage object | No | No | Owner-only with extra confirmation |
| See owner notifications and full activity history | No | No; optionally own actions | Yes |
| Change accounts, roles, secrets, schema, RLS or deployment | No | No | Owner-only |

Do not share the owner login with sensei. Each user must have a distinct authenticated identity. MFA for owner/editor is recommended before activation. Every write requires a **server-side** role and resource check, not merely hiding buttons from viewers.

## 3. Proposed durable audit event model

Create a controlled **append-only event journal** (exact schema requires a separately approved migration). Suggested fields:

- event UUID, server UTC timestamp, actor user ID/name/role, opaque session/correlation ID;
- operation ID, action (create/update/upload/replace/archive/restore/denied), resource type and ID;
- outcome and failure category; changed field **names**; approval reference where required;
- optionally a restricted, redacted before/after diff for non-sensitive metadata.

Do not store passwords, hashes, service-role/anon API keys, tokens, cookies, signed URLs, raw spectra, or nonpublic research contents in audit events. Store timestamps in UTC; render them in Asia/Tokyo for the owner.

Prefer an audit insert **in the same database transaction as a metadata write**, using a narrowly scoped RPC/trigger or equivalent. If a required audit insert cannot be committed, **fail closed** for editor metadata changes. A regular table is not immutable to a privileged database administrator; independently retained, tamper-evident backup of the audit log should be evaluated separately.

Direct access to Supabase/GitHub/Streamlit by administrators or AI cannot be fully attributed by app-level audit alone. Separate provider-native logs and individual service identities are required. The current app's shared server key is not sufficient to identify an individual user inside database logs.

## 4. Notification outbox and delivery guarantees

The metadata-write transaction should create a **notification intent** in the same transaction. Suggested outbox fields: unique event ID (idempotency key), owner recipient ID, delivery channel, status, attempt count, next retry time, provider message ID, last redacted error, and send time.

After the write has committed, a restricted dispatcher sends an email to the privately configured owner address. Email includes actor, operation, resource identifier, changed-field names, JST timestamp and a secure link to the audit detail—not the unpublished chemical data or confidential file contents.

**No guarantee of exactly-once email:** retries may produce duplicates, and providers can report delayed delivery. Use idempotency support when available, retry/backoff, delivery-status logs, and a visible alert on repeated failure. A bulk action can produce one email listing the full set of record IDs and count instead of flooding the inbox.

An authenticated owner-only **in-app notification bell** separately lists unread events, persists read/unread state across owner sessions and links to the full audit history. Fetch a bounded page of events; do not re-download the entire event log on each Streamlit rerun. A failure to deliver email must not erase the audit event or in-app notification.

**Storage uploads require special handling:** storage file bytes and relational metadata cannot be committed atomically in one PostgreSQL transaction. Propose a reconciled two-step upload with a pending state, verified object upload, committed metadata/audit/outbox, and a safe cleanup path for failure. Report only completed, confirmed operations.

## 5. Required C1/C2 data-integrity behavior

- Cache identity includes the active read source, not an underscore-prefixed ignored parameter. On snapshot → cloud recovery, refresh cached DataFrames and clear/reconcile keyed editor widgets.
- An editor cannot save rows loaded from recovery snapshot as though they were current cloud records.
- Fetch the latest authoritative row before saving, compare an optimistic concurrency token such as updated_at or version **atomically** in the PATCH predicate, and PATCH only fields deliberately changed.
- Zero matched rows on a conditional PATCH must produce a visible **conflict**, not a silent success or an automatic overwrite.
- A transient schema probe error must never be cached as absence of curation_status. Fail closed when the status of a column is uncertain; do not silently drop data fields.
- Integrate tests for two editors updating a single dummy record, including both success and conflict paths; make sure audit and notifications reflect the true committed result.

## 6. Security, privacy, retention and cost

- Keep Supabase Storage buckets private. Use scoped short-lived signed URLs after authorization; uploads must validate MIME, size and destination path.
- Display audit history only to owner; restrict editor access to personal events if that feature is explicitly approved later.
- Retain searchable audit events with pagination and indexes, define a practical retention/archival period (initial proposal: 12 months online), protect backups, minimize personal data, and document the privacy notice. Do not log raw search strings by default.
- Both scheduled dispatchers and email providers have service costs/quotas. Check pricing and free-tier constraints before enabling; never silently activate a recurring job.
- Require distinct scoped owner approval before changing any live auth configuration, GitHub rules, Streamlit deployment setting, database schema, Storage policy, secret, email integration, cron job, or user role.

## 7. Acceptance tests — isolated dummy environment only

**C1/C2:** snapshot → cloud switches refresh list and record cache; stale editor session refuses saving; transient network failure does not permanently cache "column missing"; uncertainty blocks save; concurrent editor conflict is detected and the earlier data is preserved.

**Roles and auditing:** Viewer cannot call any write API, including direct action handlers. Editor can create/update/upload/archive dummy records but cannot hard-delete or administer users. Every committed change creates one event with actor, UTC time, action, record, changed fields and outcome; failed/denied actions are also recorded safely. Simulated audit failure prevents a protected write.

**Notifications:** A successful isolated write creates one outbox event and one owner-in-app notification; the dummy mailer receives one privacy-safe message only after commit. Retries are idempotent where supported, failure is visible, unread/read state persists, and viewers/editors cannot view owner notifications. A failed upload or rolled-back write does **not** generate a success email. Bulk operations yield correct itemized notification details.

No tests may contact production. Use fake services and dummy identities only. Do not send test emails to real accounts without a separate consent.

## 8. Separate approval gates

**Current scope:** this design and tests on a feature branch and a draft pull request; no merge or deploy.

**Next, only after approval:** implement C1/C2 fixes in app code with non-production tests, then a separate independent code review.

**Later, separate approval:** implement role enforcement, audit transaction, outbox and dashboard in staging; verify using synthetic accounts/records and sandbox mail.

**Production approval after staging:** back up and verify recovery, review all SQL/auth/storage changes and email transport, apply migration and activate Jomori-sensei's editor account in separate operations, then deploy. Confirm delivery of a safe test notification and audit events before granting regular write access.

This design is not proof that auditing, email notifications, owner alerts, backup automation, or editor capabilities currently exist.
