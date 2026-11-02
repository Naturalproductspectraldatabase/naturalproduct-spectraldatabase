# NPDB Quality & Operations Center — Security & Implementation Specification

**Status: DRAFT PROTOTYPE ONLY.** Proposed 2026-11-02. The owner approved a separate branch, owner-only and curator task demos, dummy-data tests, and non-mutating review. **Do not merge/deploy, modify production SQL/auth/Storage, enable any agent automation, grant Jomori-sensei editor access, send real emails, or execute production actions without fresh, specific owner approval.** This document is not an operational alert system.

## 1. Objectives and navigation

Embed both experiences in the **existing Streamlit NPDB website**, not a new paid website:

- **Owner → Quality & Operations Center**: actionable queue of scientific quality, integrity, security, uptime, capacity, references, images, NMR and curation issues; view per-record evidence; filter by status, assignee, priority, last observation and source; see admin notifications and human approval requests.
- **Jomori-sensei → My Curation Tasks**: only issues explicitly assigned to authenticated editor \`npdb_tjomori\`, with evidence and a proposed change; own task status and human approval request workflow. No access to full administrator logs, project security settings or other users' confidential work.
- **Optional owner preview** of curator tasks using the owner account, without impersonation.
- Separate authentication, provider settings, scientific-data editing and platform deployment controls remain outside these pages.

The initial prototype lives in \`scripts/npdb_quality_center.py\`. It contains **synthetic, clearly labeled demo records** and pure deterministic filtering/approval-preview functions. It must NEVER silently mix demo and live production records. Synthetic IDs all begin \`DEMO-\`. In the prototype, every \"Approve\" / \"Reject\" action says \"Simulate\" and has **no effective permission**, no persistent status and no effect on Supabase or user accounts.

## 2. Real production issue model — proposed schema only

After approved migrations, consider a small set of tables with **owner-only** data access and append-only history. Do not create these now.

\`quality_issues\` (logical entity):
- \`issue_id\` UUID; deterministic \`fingerprint\` (rule ID + resource type/ID + normalized rule-specific key), with dedupe/unique index;
- \`rule_id\`, \`rule_version\`, \`severity\` P0/P1/P2/P3, \`category\`, \`title\`, short redacted \`description\`;
- \`record_id\` (nullable), \`resource_type\`, \`evidence_ref\` to a protected evidence object, \`recommended_action\`;
- \`source\` (automated rule / manual report / approved incident / provider), \`confidence\`, \`last_check_at\`, \`last_observed_at\`, \`created_at\`, \`updated_at\`;
- \`status\` (open, in_review, blocked, resolved, false_positive), \`assignee_id\` (nullable), \`resolution_note\`, \`resolved_by\`, \`resolved_at\`;
- optional \`data_visibility\` and owner-only \`requires_approval\` flags; avoid arbitrary JSON payloads carrying confidential scientific data.

\`issue_history\`:
- append-only event ID, issue ID, actor, UTC time, action, previous/new status, reason, revision and optional approval ID. No unredacted passwords, keys, cookies, raw request bodies, personal contact information or private spectra.

\`approval_requests\`:
- request ID, originating user/AI agent identity, intended action type, exact record/field targets, before/after preview, risk level, required permissions, expiration, idempotency key, state, owner ID, decision time and reasoning.
- A notification/in-app approval button **must never directly trigger unchecked SQL/write tools**. An authenticated owner decision only authorizes the exact, still-valid action. Before execution, re-check the request's immutable payload hash, owner identity, authorization scope, expiry, record revision and RBAC; enforce policy server-side and record a durable audit.
- For **AI actions**: default mandatory per-operation approval, including private-resource reads as requested by owner. No previous approval can be reused as permanent blanket authorization.
- For **Jomori-sensei**: owner can grant defined *curation capabilities* with audit+email on every successful change, while sensitive operations (permanent deletion, role/security, bulk irreversible edits) still require per-action approval. Owner chooses which metadata field categories require additional approval; do not infer automatically.
- Rejections and withdrawn/expired approvals must block execution. Version conflicts must request a fresh, reviewed proposal.

\`owner_notifications\` and \`notification_outbox\`:
- A notification for each committed change or owner action request, including source event ID, actor, resource/record ID, safe field names, outcome, created UTC time, read_at and owner ID.
- Durable transactionally created outbox intent for approved email transport. Send only after database commit, retry/deduplicate by event ID, expose failed delivery in the owner UI and avoid secrets/unpublished structures in email body.
- Exactly-once *delivery* is not guaranteed; duplicate email risk must be acknowledged. Batch actions may use one itemized notification/email with all record IDs, if owner explicitly approves.

## 3. Priority and action guidance

**P0** — confirmed/well-supported risk of data overwrite, loss, critically incorrect scientific identity displayed as verified, serious unauthorized access or data disclosure. Route to owner immediately and consider blocking editing pending review.

**P1** — significant integrity warning, broken provenance or authorization/logging, major reproducible scientific search failure. Curator reviews underlying primary source; owner decides release.

**P2** — missing images/references, incomplete metadata, unreviewed structure, accessibility obstacles or recoverable file-preview errors.

**P3** — cosmetic issues, low-risk duplicates, optimization opportunities and documentation cleanup.

Rules should provide a **concrete recommended action**, source and confidence; no rule should automatically rewrite chemical structure, SMILES/InChI, stereochemical assignment, NMR peak attribution, specimen coordinates or copyrighted images.

A formula-vs-InChI checker is a **screen** not a proof; salts, adducts, protonation and charge states can produce legitimate differences. Separate genuine likely mismatch, complex/ion cases, not comparable and missing-value categories. Review source publications and curated PNGs before any correction.

No issue count may be described as a count of unique affected compounds without deduplicating compound IDs; one record may have multiple issues.

## 4. Data sources and freshness

- Initial audited **2026-11-02 read-only baseline** (not injected as active production issue rows):
  - 4,063 compounds;
  - 4,035 generated image references, 5 curated PNG references and 20 without image references;
  - 4,040 formula–InChI comparisons, 108 screened discrepancies (21 simple candidates, 87 complex/salt/charge cases);
  - 64 CAS-like trivial names; 27 apparently unlinked generated assets;
  - C1/C2 cache/concurrency risks and potential scientific identity mismatches.
- Before publishing live dashboards, add a **manually triggered, read-only, server-side issue scanner** with strict query count/time limits, stable page size and clear UTC \`last_checked\`. Only a separately approved automation could refresh on a schedule.
- Do **not** scan private raw PNGs or spectra without an explicit reason and approved scope. Persist redacted evidence/provenance and access it only for authorized users.
- Provider-native GitHub, Streamlit and Supabase admin activity cannot all be attributed from NPDB's app audit table. Display coverage gaps and \`monitoring inactive\` or \`unknown\` rather than a misleading \"healthy\" status.
- Use UTC in storage, render dates in Asia/Tokyo. No current production scan, notifications or scheduler is implemented by this prototype.

## 5. Production security design and privacy

- **Never trust only hidden Streamlit sidebar items.** Every page route checks authenticated identity + role. Every actual query, export, role change or write performs backend authorization and row-level checks as applicable.
- Owner identity is currently \`npdb_tyas\`; intended curator identity is \`npdb_tjomori\`. Naming an account in a demo is not activation or proof of account security.
- Do not expose a server service-role key to user browsers. For eventual database production changes, review existing shared-service-key approach and migrate toward least privilege and careful server-side authorization.
- Global read access to an audit queue, other users' tasks, signed URLs, private GPS or unpublished metadata is not allowed.
- The curator's future role should permit creating/editing/uploading/archiving selected scientific records only with full audit, change history and owner email, **not** credential/schema administration or permanent deletion.
- An owner must be able to block, revoke or expire proposed actions. The system must keep a tamper-evident audit export/backup. Plain Postgres tables are not inherently immutable to privileged admins.
- Require MFA on owner and editor accounts if supported. Investigate provider security advisor warnings, private file URLs, backups, cache correctness and access log retention before public rollout.

## 6. Interface and accessibility

Tabs:
1. **Issues & Action Queue** — severity/status/category/assignee filters, paginated issues, evidence, recommended action, assign/triage/resolve after confirmation.
2. **Scientific Curation** — molecular formula/SMILES/InChI, curated PNG provenance, source DOI, NMR and stereochemical warnings; per-record diff and source comparison.
3. **System Health** — PostgreSQL/Storage usage, last valid backup, Streamlit memory, cloud connectivity, audit delivery, rate limits and data freshness; label unmeasured metrics as unknown.
4. **Activity & Approvals** — owner-only email/in-app notification state, reviewable task proposals, explicit Approve / Reject / Request changes and full, filterable audit history.

Prioritize readable dark-theme typography and 4.5:1 WCAG text contrast; keyboard access, screen-reader labels, confirmations, pages of limited size and sensible empty states. Prefer built-in Streamlit components where possible.

Buttons in **this demo** must remain visibly labeled \`Simulate\` or \`Preview\` and cannot execute/authorize changes. When production buttons are implemented in a separate approved stage, require strong identity, durable signature/approval receipts, atomic write+audit and verified notification delivery.

## 7. Verification and rollout gates

**Prototype (this PR):** pure dummy fixtures; owner/editor/viewer permission guards and router checks; priority queue and tests; approval previews with no effective permission; no live backend, SQL migrations, email or automatic jobs.

**Before opening live editing to sensei:** complete C1/C2 tests + independent PR #3 review, complete structure image preservation PR #4 tests, fix hardcoded owner-only edit restrictions with audited RBAC, add reliable audit/write transactions, stage 2-editor concurrency tests and provider-reviewed notification delivery. Only then seek separate owner permission for staging and production release.

**Before connecting live checks:** define and approve scanner SQL, rate limits, privacy filtering, read-only identity, freshness display and issue merge/dedupe logic. Preserve existing audit history. Do not auto-delete duplicates, redraw curated PNGs or rewrite structures.

**Required checks against a full checkout:**

\`\`\`bash
python -m unittest discover -s NMR_Database_Tyas_GitHub_Upload/tests -p 'test_quality_center.py' -v
python -m py_compile NMR_Database_Tyas_GitHub_Upload/scripts/npdb_quality_center.py
python -m py_compile NMR_Database_Tyas_GitHub_Upload/scripts/app.py
\`\`\`

Review unauthorized direct-navigation attempts and Streamlit widget interactions in staging with dummy credentials. No production writes or real notifications are permitted from this prototype.

## 8. Cost and maintenance

Keep this feature inside existing Streamlit, GitHub and Supabase architecture; introduce no second paid website. Prototype performs **zero production scans** and negligible demo compute. Future scanner/notification worker costs depend on actual scheduled frequency, query bandwidth, log volumes and email provider quotas; obtain pricing approval before enabling.

A monthly manual quality scan initially may be safer and cheaper than a continuous cloud agent. Consider 12 months online audit retention plus independently controlled archival after privacy review. The owner retains ultimate authority over security and scientific changes.

## 9. Release coordination

This branch starts independently from production \`main\`. PR #2 (agent governance), PR #3 (C1/C2 editing), and PR #4 (curated PNG integrity) also remain draft. Their changes touch the large \`app.py\`; do not merge or cherry-pick all concurrently without conflict resolution and full tests. Merge/deployment remain separate consent gates.

\`npdb_quality_center.py\` is isolated so it can be reviewed and later integrated safely. The UI entry points must never load all compound records just to display this dashboard. Never claim demo approval buttons send real email, persist approval, or authorize an actual change.
