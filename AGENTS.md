# AGENTS.md — Natural Products Spectral Database (NPDB)

> Shared project instructions for coding assistants (including Codex and other agents). Read this file before modifying anything in this repository. The owner is a marine natural products chemistry researcher, not a professional software developer: explain changes plainly and provide reproducible steps.

## Purpose and scientific context

NPDB is a research-oriented database for natural products, with an emphasis on marine organisms. It stores and connects compound identities, chemical structures, organism/source and specimen metadata, 1H and 13C NMR data, spectrum files, and bioactivity records. Its design priorities are **scientific accuracy, traceable curation, data integrity, usability, availability, and secure access**, in that order. Never fabricate chemical data, spectra, assay values, structures, or citations.

## Repository and deployment

- GitHub: `Naturalproductspectraldatabase/naturalproduct-spectraldatabase` (public repository; protect nonpublic research data).
- Web app: https://npdb-spectraldatabase.streamlit.app/
- Deployed Streamlit entrypoint: `NMR_Database_Tyas_GitHub_Upload/scripts/app.py` (verify app settings before deployment).
- Application sources: `NMR_Database_Tyas_GitHub_Upload/`; Python/Streamlit primarily in `scripts/app.py`; SQL/migrations under `supabase/`; local data and example backups under `data/` and `database/`.
- Root and nested `requirements.txt` / `runtime.txt` exist; verify which deployment config is actually used before modifying dependencies.
- **Current authoritative production database: Supabase PostgreSQL and private Supabase Storage**, not the bundled local SQLite database or CSV snapshots. Streamlit runs locally for development and on Streamlit Community Cloud for production.
- Legacy deployment/storage guides may reflect an older SQLite/Google Drive setup; compare them against present code and the live environment rather than following them blindly. Google Drive may still be used for linked large/raw files.
- Do not assume an agent's cloud clone has access to the owner's Mac local working tree or uncommitted changes. Confirm Git status locally when that matters.
- `CLAUDE.md` provides Claude-specific onboarding and links back to this document.

## Access and authorization model

- Approved-user login uses password hashes; roles distinguish owner/editor from viewers. Preserve the server-side authorization check on **every** write action, not only the visibility of UI controls.
- Supabase credentials and signed URLs must remain server-side. Storage buckets containing structures, spectra and specimens must remain private unless the owner explicitly approves a reviewed security change.
- Enforce existing RLS, HTTPS/SSL validation, and private-bucket signed-access patterns. Do not replace signed URLs with public bucket access or public read policies.
- A public GitHub repository **is not** a safe place for private compound datasets, backups, credentials, password hashes, or unpublished research.

## Non-negotiable safety boundaries

1. **Never read, print, copy, commit, upload, or transmit actual keys/passwords or private credential files**. Do not inspect secret values unless an authorized task strictly requires it; in reports show only whether a setting is present.
2. Never commit `.streamlit/secrets.toml`, `.env`, `npdb_user_credentials_private.csv`, raw database `.db`/SQLite files, backups, or sensitive exports. Check both root and nested paths, Git diff, and tracked file lists.
3. No destructive SQL, database resets, bulk deletes, schema/RLS changes, public storage access, credential rotation, production deploy, or direct commits to `main` without explicit and specific owner approval.
4. Treat **production data as authoritative**. Never restore, sync, or overwrite it from an old bundled snapshot without a separately approved recovery plan and verified backup.
5. If Supabase is unreachable, keep the app in **read-only recovery mode**. Do not enable edit/submission simply to hide an outage. Show data-source/snapshot age clearly to avoid confusing stale data with live records.
6. All repository changes go through a dedicated feature/fix branch and reviewable pull request. Keep changes narrow and avoid multiple agents editing the same files/working tree concurrently.
7. Prefer read-only diagnosis and isolated tests before changes. Test with dummy secrets and fake/staging services; never intentionally disrupt production to simulate outages.
8. If unsure about the owner's authorization, explain the intended effect and seek approval before an irreversible or sensitive action.

## Critical data-integrity rules

- A return to Supabase after an outage must **invalidate snapshot-derived caches and stale editor form state** before editing is allowed. Do not trust a cached row simply because the health check has become healthy.
- Streamlit `st.cache_data` ignores function arguments whose names start with `_`; ensure the database/source signature participates in cache keys. Explicitly distinguish `supabase`, `snapshot`, and `local` reads.
- A failed schema/column probe must not become a permanently cached “column missing” result. **Fail closed on writes** when metadata is uncertain; never silently discard scientific fields such as `curation_status`.
- Avoid full-row overwrites from stale forms. Prefer changed-field updates plus an appropriate record version / `updated_at` conflict check, tested against the real schema in staging.
- Validate chemical identifiers, quantitative values, units, source/assay metadata, and compound links without inventing missing values; maintain existing attribution and audit trails.
- During network/storage failures, handle private-object signed-link errors gracefully; keep image previews restricted to actual image types and provide safe links for PDFs/other file formats.

## Incident and known technical backlog (historical notes, not current system status)

- On **2026-11-02**, Supabase project `npdb` was confirmed `INACTIVE`, causing Streamlit to display a DNS-resolution error and read-only snapshot fallback. The original project was restored, and its status was subsequently verified as `ACTIVE_HEALTHY`; a read-only query confirmed the main tables were available. **Always re-check current health rather than assuming it remains healthy.**
- See GitHub incident: https://github.com/Naturalproductspectraldatabase/naturalproduct-spectraldatabase/issues/1
- The independent 2026-11-02 code audit flagged: stale snapshot/editor caches and potential overwrite after recovery; permanent caching of failed `curation_status` column checks; uncaught signed-storage-preview failures; non-image files treated as images; incomplete/old public recovery snapshots; confusing outage/credential banners; duplicate definitions in the large `app.py`. These are a **prioritized investigation backlog**: confirm defects with tests, do not assume every symptom has occurred in production.
- Safe implementation order: regression tests → stale-write prevention → resilient schema/health checks → safe storage previews → truthful recovery UI and snapshot policy → maintainability/monitoring. Distinct PRs should be reviewed and merged serially.

## Expected assistant workflow and report

1. At task start, summarize scope, affected files, expected data/security impact, and whether access is local, remote cloud, or GitHub-only.
2. Read code and existing tests; verify active git branch, uncommitted local work, and remote branch head. Do not discard local changes.
3. Reproduce a bug with minimum non-production data and document expected versus observed behavior. Distinguish confirmed defects from hypotheses.
4. Make only the agreed changes on a separate branch; favor small, reviewable patches over broad rewrites of the large Streamlit module.
5. Run focused tests (including admin/viewer permissions, cloud reachable/unreachable/recovered, private storage previews, and save conflicts where relevant); report commands and outcomes, including what could not be tested.
6. Open a PR with a clear summary, tests, rollback plan, and any manual Streamlit/Supabase verification required. Never merge or deploy merely because the code compiles.
7. Communicate in clear language suitable for an owner with limited IT background; avoid asking them to paste secrets.

## Multi-agent collaboration

Recommended division of labor: ChatGPT coordinates requirements and reviews repository/Supabase evidence; Codex handles owner-approved local implementation and tests; Claude Code provides independent code review or a separate PR. These are roles, **not** automatic tool connections or delegated permissions. No assistant can assume another assistant has access to local folders, browser tabs, session history, credentials, or production dashboards.

Before starting a new task, check open issues/PRs to avoid duplicate work. Update project instructions when architecture or approved operating procedures change, without embedding private information.

## Owner-directed AI operation and activity logging policy (2026-11-02)

**Read [NPDB_SECURITY_AND_AUDIT_POLICY.md](NPDB_SECURITY_AND_AUDIT_POLICY.md) before using any tool or changing a project resource.** The owner requires explicit approval for each distinct project-related operation, including private-resource reads. A bounded, enumerated approval covers only the authorized batch, never unrelated later actions. If a task unexpectedly demands additional access, new files/providers, irreversible effects, remote changes or a different approach, **STOP and request renewed consent**.

- Explain before acting: agent/tool identity, target environment and exact files/tables, read/write/deploy category, expected effect, risk, backup/rollback, and verification.
- After acting, disclose what was actually done, outcomes and unresolved risks, and identify any GitHub branch/PR and audit/approval reference. Never claim that a notification or audit exists until tested.
- Documentation in this public repository is **not a technical permission boundary**. Configure restrictive agent sandbox/approval modes, provider access scopes, protected branches, and deployment/manual review gates independently.
- In NPDB itself, plan owner-only, privacy-preserving audit trails for login/logout/failure, viewing/search, downloads, writes, permission denials, bulk operations and privileged agent/infrastructure actions. Record actor identity, UTC event time, resource/action, outcome and approval reference; redact tokens, private values and signed URLs. Do not capture search contents or raw scientific records indiscriminately.
- The existing Supabase `audit_events` table and `record_audit_event` code are only a partial starting point, not comprehensive surveillance. Read-only checks on 2026-11-02 found write events only and a logging-history gap; no automated anomaly alerts have been demonstrated.
- Preserve an honest division of responsibilities: the owner decides; agents implement only the approved scope; provider-native logs and independent controls are needed for direct Supabase, GitHub, Streamlit and machine activity outside the app.
- Scope this phase to **draft documentation only**. Do not independently implement audit schema changes, enable agents/alerts, change permissions or deploy from this policy.

