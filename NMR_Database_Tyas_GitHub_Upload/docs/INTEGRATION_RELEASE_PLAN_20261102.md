# NPDB integration, validation and release gates — 2026-11-02

**Current policy:** all listed PRs are drafts and none may be merged/deployed without fresh, action-specific approval from the NPDB owner. Supabase production metadata, Storage, accounts, RLS and live notifications must not be modified for the purposes of testing. Screenshots at reduced browser zoom do NOT establish a responsive-layout defect.

## 1. Current branches and dependencies

| Draft PR | Purpose | Touches app.py? | Gate |
| --- | --- | --- | --- |
| #2 | Agent governance, approval/security rules | No | Owner review; documentation only |
| #3 | C1/C2 cloud-cache source key and revision-checked compound editing | Yes | Full compiler, regression tests, concurrency UI |
| #4 | Curated PNG priority, no silent fallback to wrong SMILES | Yes | Image rendering + signed-URL/CPU tests |
| #5 | Owner Quality Center, curator task mock UI | Yes | Identity/permission tests, dummy UI |
| #6 | **C15 critical** wizard per-step draft persistence | Yes | Real Streamlit multi-step test with dummy record, readback |
| #7 | Shared ¹H/¹³C gallery with controls top & bottom | Yes | 10/20/40 page UI/navigation tests |
| #8 | Offline SQLite in-memory demo owner approval/audit/outbox | No | Role, expiry, replay, tamper, transactional tests |

**All branches were based on the same \`main\` commit**. Five (#3/#4/#5/#6/#7) independently alter a single 14k-line app.py. There is material overlap, so **never blindly merge all PRs**, or claim that a pass on an individual branch validates the integrated result.

## 2. Recommended validation order

1. **C15 (#6)**: compile app and helper, run the 13 local tests, exercise wizard steps 1→2→3→4→2→3→4, attach dummy PNG/spectrum, inspect final review, save to disposable SQLite/staging, reopen exact dummy row and confirm every input persisted. Also test intentional clearing and empty optional fields. Do not use production to create a test record.
2. **C1/C2 (#3)**: run the 14 regression tests and simulate snapshot→cloud recovery, two browser sessions racing on one dummy compound, row-version conflict and column probe failure. Verify no old value or missing curation_status gets written; cloud recovery invalidates all relevant caches.
3. **Curated image rendering (#4)**: verify PNG takes precedence over SMILES, background is opaque white, protected image loss yields a visible warning and not a wrong generated depiction, and generated images are clearly labeled. Inspect whether repeated preview requests stress memory.
4. **Owner and curator demo (#5)**: run 25 tests; viewer must not see owner notices or curator tasks even by direct URL; owner must not be bypassed by passing only username/only role. Demo approval cannot execute action.
5. **Spectrum galleries (#7)**: run 15 tests; 13C gallery should start with five registered file records while 1H has 100 files (as of read-only count); verify same pagination UI at top and bottom, 40/page, search resets, mobile and browser scroll behavior.
6. **Staging approval backend (#8)**: run 16 tests; verify requester identity, explicit owner decision, immutable proposal, expiration, replay, optimistic-lock, audit, pending outbox, rollback. This is SQLite RAM-only, NOT a production authentication implementation.
7. **Full integrated rehearsal**: after owner permits an integration branch, cherry-pick/reconcile these changes one at a time, run every test after each step, and then full Streamlit browser tests in disposable staging using a separately authorized test identity.

### Required reviewer commands

\`\`\`bash
python -m py_compile NMR_Database_Tyas_GitHub_Upload/scripts/app.py
python -m py_compile NMR_Database_Tyas_GitHub_Upload/scripts/npdb_wizard_draft.py
python -m py_compile NMR_Database_Tyas_GitHub_Upload/scripts/npdb_gallery_pagination.py
python -m py_compile NMR_Database_Tyas_GitHub_Upload/scripts/npdb_quality_center.py
python -m py_compile NMR_Database_Tyas_GitHub_Upload/scripts/npdb_approval_demo_store.py
python -m unittest discover -s NMR_Database_Tyas_GitHub_Upload/tests -p 'test_*.py' -v
\`\`\`

The existing repository may have extra tests, duplicate code and package dependencies. Resolve each failure before selecting a release candidate. Do **not** add auto-running workflows, paid CI, cron, email services, or scheduled monitoring without owner consent.

## 3. Production read-only baseline

As of 2026-11-02, SQL SELECT checks:

- **4,063** compounds; **59** unique compounds with ¹H peaks; **59** with ¹³C peaks; **59** have both.
- **100** registered ¹H spectra files (89 unique compounds) and **5** ¹³C spectra files (5 compounds); count of peak rows is *not* count of compounds with spectra.
- **2,981** compounds have blank source_category; **976** carry compound_class \`Marine Natural Product\`, which is origin rather than a chemical class.
- C15 broad screening with *all selected origin/spectroscopy fields empty* found just **one** record (ID 4024). This is not a reliable prevalence estimate or proof of previous data loss. Do not automatically edit or infer missing fields.
- Structure review flagged formula-to-InChI inconsistency in a small number of records; see separate prior structure audit. These flags require human verification against source PNG/publication.
- Provider logs and email alerts are **not** established as complete, automatic or reliable by any current draft.

## 4. Remaining high-priority independent defects

- Login fail-open when secrets are absent, in-memory lockout reset on reload and shared-password modes (Claude security audit). Fix/test separately before public editor rollout.
- ¹H matching rank depends on query input order; add a reference dataset and order-invariant matcher before making quality claims.
- Low-contrast UI inputs; stage a conventional dark Streamlit theme and verify WCAG 4.5:1 normal-text contrast.
- Download Full Record may expose GPS; review record-level location visibility and downloadable packages.
- Viewer role should not receive technical storage paths or owner-only details.
- Improve data model for source organism vs substrate/host, chemical class system, references, NMR dataset/provenance; avoid mass correcting compounds automatically.
- Backup recovery test and trusted provenance for approved curated ChemDraw-export PNGs (not native .cdx files).
- Scale: paginated PostgreSQL queries rather than fetching all rows, bounded cache sizes/TTLs, compressed previews, realistic staging RAM measurement.

## 5. Release checklist and owner approvals

| Gate | Required evidence | Allowed now? |
| --- | --- | --- |
| Read-only production verification | Aggregate SQL SELECT and redacted report | Yes |
| Nonproduction code edits/isolated dummy tests | Draft branch/PR; no live accounts/files | Yes |
| Install or execute new GitHub Actions automation | Cost, scope, credentials and owner consent | **Separate approval** |
| Create staging Supabase resources or migrations | Exact SQL, private RLS, backup and owner consent | **Separate approval** |
| Configure live editor account, user roles or permissions | Reviewed RBAC and owner consent | **Separate approval** |
| Real email/webhook/notification delivery | Provider, address, costs, privacy and consent | **Separate approval** |
| Merge any draft PR into main | Full tested integrated diff and owner consent | **Separate approval** |
| Deploy Streamlit/Supabase production | Rollback plan, backup, monitoring and owner consent | **Separate approval** |
| Correct scientific structures, NMR or metadata | Verified source, before/after diff and explicit approval | **Separate approval** |

**Do not promise universal agent monitoring or enforceability by documentation alone.** A real owner approval interface requires backend-enforced scoped authorization, audit trail and per-provider notification configuration.
