# NPDB owner approval / audit notification — staging-only gate

**Security status:** non-production prototype; no Streamlit deployment, no Supabase migrations, no live accounts/roles, no email and no automation. This module is never called by the live app.

## Why this exists
The owner requested advance permission for every sensitive action, an owner notification and durable history for changes by the curator `npdb_tjomori`, and a searchable quality queue. The demo enforces an explicit proposal → owner review → separate synthetic execution sequence using a fresh **SQLite `:memory:`** database.

## Implementation
- `scripts/npdb_approval_demo_store.py`: typed dummy role checks, DEMO-prefixed data IDs, assigned task query, exact-proposal hash, expiry time, record version check, atomic transaction, insert-only demo audit, owner notices, and a **pending email outbox that never sends messages**.
- `tests/test_approval_demo_store.py`: 16 offline tests including viewer/editor/owner isolation, no write after proposal, reject/expire/tamper/replay/concurrent-edit refusal, and notification only after successful dummy write.

**Critical honesty:** the roles are passed by a local test caller, not backed by real NPDB authentication. The SQLite audit trigger blocks modifications by normal SQL but a privileged user still controls database state. This is **not a production security boundary**. Do not mount this module under public Streamlit routes or connect it to the Supabase service-role key.

## Future production design (separately approved)
1. Verify actual authenticated identity and role server-side, distinguish owner and editor by durable UID, disallow shared credentials.
2. Stage additively migrated tables (quality issues, assignment history, exact approval requests, audit events, in-app notifications and outbox) with private RLS and provider security review.
3. Approval must authorize **only** immutable action specification/field set/record/version, expire and be single-use. On execution revalidate UID, scope, status, expected revision, signature and session. Atomic write/audit/outbox commit.
4. Record events for denied attempts without exposing secrets or private data. Owner notification requires idempotent provider delivery with retry, backoff and failure visibility.
5. Editor can submit proposals and perform only scoped permitted curation after owner-defined policy; hard deletion, account administration and deployment are owner-only.
6. User-facing **Approve/Reject** buttons must show actor, record ID, changed fields, before/after preview, risks and explicit confirmation. Buttons must be reliable, audited and revocable; never silently approve automatically.
7. Test a failure matrix: wrong role, stolen session, replay, expired approval, concurrent editing, audit write failure, email outage, signed URL failure and bulk actions.
8. Require separate owner authorization before migrations, real account changes, email provider connection, merge and deployment.

## Reviewer commands
```bash
python -m unittest discover -s NMR_Database_Tyas_GitHub_Upload/tests -p 'test_approval_demo_store.py' -v
python -m py_compile NMR_Database_Tyas_GitHub_Upload/scripts/npdb_approval_demo_store.py
```

This isolated test prototype must be reviewed together with the Owner Quality Center draft PR #5 before integration. No production claims of notifications, approval or audit completeness are made.
