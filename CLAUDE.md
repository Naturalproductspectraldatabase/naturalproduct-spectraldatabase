# CLAUDE.md — Claude Code onboarding for NPDB

**Read [AGENTS.md](AGENTS.md) first.** That file is the shared source of truth for project goals, architecture, security boundaries, scientific integrity, and collaborative workflow. Apply the stricter safety rule if instructions conflict.

## Project mission

Natural Products Spectral Database (NPDB) is an established, research-oriented web database for natural products, especially marine organisms. It manages compound names, formulas, structural identifiers and images, biological source/specimen metadata, 1H and 13C NMR data, supporting spectra, and bioactivity records. Scientific accuracy, traceable curation, data consistency, secure user access, and a clear user interface matter more than shipping changes quickly.

**Do not invent or silently change scientific data.** This is not a new app to be rebuilt from scratch.

## Where to work

- GitHub repository: https://github.com/Naturalproductspectraldatabase/naturalproduct-spectraldatabase
- Deployed app: https://npdb-spectraldatabase.streamlit.app/
- Streamlit app: `NMR_Database_Tyas_GitHub_Upload/scripts/app.py`
- SQL/migrations: `NMR_Database_Tyas_GitHub_Upload/supabase/`
- The production source of truth is **Supabase PostgreSQL**, with **private Supabase Storage** and Streamlit Community Cloud hosting.
- SQLite and CSV snapshot paths are for development/recovery and must not overwrite authoritative cloud data.
- Several older Markdown guides reflect an earlier SQLite/Google Drive setup; verify them against current app code.
- A cloud clone or Claude Code web session does not automatically include the owner's Mac folders, local uncommitted changes, browser sessions, or credentials. Clearly state the access you have.

## Safety rules

1. Start with read-only inspection until the owner authorizes a specific change.
2. Never read, display, copy, commit, or publish secrets, passwords/hashes, private credential CSVs, raw .db files, backups, or nonpublic datasets. Keep `.streamlit/secrets.toml` private.
3. Do not apply production SQL changes, delete records, rotate keys, alter RLS/buckets, make private storage public, disable TLS verification, deploy production, or push to `main` without explicit and specific approval.
4. Keep server-side authorization on writes and signed private-file access, not merely hidden viewer buttons.
5. If cloud health is uncertain, editing stays blocked. Never “repair” an outage by bypassing recovery safeguards.
6. Use dedicated branches and reviewable PRs; coordinate with Codex to prevent simultaneous edits to the same working tree/file.
7. Use fake or staging endpoints and dummy credentials for outage simulation; no intentional disruptions to production.

## Incident context (historical, verify current status)

On 2026-11-02 the NPDB Supabase project was observed `INACTIVE`, and the Streamlit app showed a DNS error and switched to read-only recovery. The original project was restored, subsequently reporting `ACTIVE_HEALTHY`; read-only SQL confirmed cloud records were present. This **does not guarantee that current Streamlit status or individual features are healthy**.

Incident issue: https://github.com/Naturalproductspectraldatabase/naturalproduct-spectraldatabase/issues/1

The independent read-only audit on that date identified a **backlog of issues to investigate with tests**, including:
- Critical: snapshot-derived cached rows and keyed Streamlit editor state could survive backend recovery; full-row PATCH without concurrency check could overwrite current metadata.
- High: failed Supabase `curation_status` column probe could become cached as a permanent “missing column” and cause writes to drop the field.
- High: uncaught errors when generating signed Storage URLs during outages.
- Medium: PDFs/non-images treated as images; old and incomplete recovery snapshot; misleading health notices.
- Maintainability: duplicate function definitions in the large `app.py` and a repository gitlink/submodule anomaly.

Treat production data-loss claims as **potential risks unless actual data loss is established**. Focus first on preventive tests and safeguards. The suggested order is regression tests → stale-write prevention → safe schema/health handling → storage preview resilience → correct recovery messaging/snapshot policy → refactoring and monitoring.

## Expected Claude Code workflow

1. Read `AGENTS.md`, review the current GitHub issue/PRs and precise code paths, and identify any uncommitted local changes if local access is actually granted.
2. Separate proven code defects, demonstrated test failures, and unconfirmed hypotheses.
3. Explain the plan in straightforward language suitable for a non-programmer researcher.
4. Make only scoped changes on your own branch (not `main`), with automated tests using fake/staging services. Test admin/viewer permissions, cloud outage/recovery, stale editing, private file previews, and scientific metadata preservation where relevant.
5. Open a PR documenting what changed, test results, data/security effects, limits, and rollback options. Do not merge/deploy without approval.
6. Tell the owner/coordinator which branch and files you are working on to prevent conflicts with Codex.

### Collaboration

ChatGPT coordinates requirements and reviews evidence through its connected services; Codex can handle owner-approved local development; Claude Code is an independent reviewer or separate implementer. **These are suggested roles, not automatic system-to-system connections or shared permissions.**

Keep this file concise and update it when decisions change. Do not put private research records, secrets, or personal data in instructions committed to this public repository.

## Mandatory owner approval and audit procedures

Read [NPDB_SECURITY_AND_AUDIT_POLICY.md](NPDB_SECURITY_AND_AUDIT_POLICY.md) before taking action. The owner requires specific approval for **each project-affecting operation** (read-only as well as write), or a clearly enumerated and bounded batch. No vague invitation to help grants indefinite authority. State target tools/resources, expected result, data/security impact and rollback. Stop if a step expands beyond approval; provide a result log afterward.

For Claude Code specifically:
- Keep cloud/web repository access distinct from access to the owner's desktop. Never infer prior ChatGPT/Codex permissions also authorize Claude.
- Use the most restrictive available permission mode, avoid bypass/auto-accept/full-computer options, and get separate approval for pushing branches, PR merge, production deployment, schema or credential changes.
- Any future audit implementation must protect privileged logs, record user identities and denied attempts, avoid recording credentials or sensitive search/compound contents, and distinguish app events from provider events.
- Existing `audit_events` records **do not** establish comprehensive viewer/login/download access history, and security alerts are only proposed; never claim monitoring is active without verified tests.
- Work on a separate branch and request owner approval for each new PR/step instead of silently continuing from an old plan.
