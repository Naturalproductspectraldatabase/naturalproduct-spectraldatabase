# NPDB integration verification — 3 November 2026 JST

## Outcome

Release remains blocked. This candidate combines #13 (cache/concurrent edits and
submission persistence), #12 (fail-closed login), #4 (curated PNG integrity),
#7 (carbon gallery/pagination), and #9 (Home spacing). #5 and #8 remain separate
prototypes; they are not production authorization or durable notification systems.

Main baseline inspected: `58620eb2a4671173c9e5e1428e0d22adac919c6a`.
All remote branches were fetched. PRs #3–#9, #12 and #13 were open; #10 and #11
were merged. PR #12's GitHub workflow run 41477821372 succeeded. No other
branch's CI result is inherited as proof that this combined candidate passed CI.

## Verification performed

- Public repository cloned locally successfully; ordinary authenticated Git push
  was unavailable, so connector-backed Git object publication is used.
- Core #13: 27 local unit tests passed.
- Combined candidate before new tests: 58 local unit tests passed; all scripts
  passed Python compilation.
- Five full-script Streamlit AppTest cases passed with an empty temporary local
  database, synthetic credentials, cleared environment, and blocked urllib HTTP:
  missing configuration; stale authenticated session with missing configuration;
  configured form; rejected invalid password; accepted valid viewer login.
- Streamlit 1.66.1 and Python 3.12 used locally. These are tested versions, not
  verified production runtime versions. The added CI job installs pinned UI test
  dependencies and repeats the five full-script tests.
- Live production browser rendered the login gate. No authenticated browsing,
  mobile/zoom/accessibility, or scientific search validation is claimed.
- Streamlit Community Cloud dashboard rendered signed out. Deployed branch,
  secrets configuration, logs and staging-app availability remain unverified.

## Read-only database findings

- Supabase project `npdb` / `aquiutmhghrcqwzdwbjq`: ACTIVE_HEALTHY, Postgres 17.
- Exact counts: compounds 4,063; proton peaks 1,288; carbon peaks 1,266;
  spectrum-file references 105. Compact table inventory row estimates showed zero
  and must not be used as exact counts.
- Security advisor returned no lints. This does not establish application-level
  authorization safety. Inspected policies rely on server service-role access;
  owner/editor/viewer enforcement needs explicit application testing.
- All four storage buckets inspected are private. Duplicate service-role storage
  policies exist; do not change them without a reviewed migration/rollback plan.
- Backup bucket: 20 objects; newest object's creation timestamp is
  2026-05-11 15:39:07 UTC. This proves neither current backup coverage nor absence
  of newer backups elsewhere. No object contents were downloaded or restored.
- Spectra bucket: 161 objects; structures bucket: 4,076 objects. Differences from
  file-reference counts do not establish orphaned objects or justify deletion.

## Required next gates

1. Authenticate the owner dashboard securely; inspect branch/path/runtime, logs,
   deployment revision, available staging app and secret *presence* without
   exposing values. Do not paste credentials into issues or chat.
2. Establish fresh database plus storage backup coverage and rehearse restoration
   in an isolated environment. A bucket inventory is not a backup validation.
3. Provision or identify separate staging database/storage and disposable test
   identities. Confirm any incremental hosting/database cost before incurring it.
4. Test owner/editor/viewer boundaries, submit/readback for every wizard field,
   edit conflicts and failed uploads, image failures, gallery navigation, search,
   exports and recovery in staging. Inspect low-level write guards as well as UI.
5. Verify browser layouts at mobile/laptop/desktop widths and 80/100/125% zoom;
   benchmark representative data volumes without copying confidential data into CI.
6. Review complete release diff, passing candidate CI, rollback rehearsal and
   backup freshness before any main merge or deployment. App rollback uses the
   recorded pre-release main revision; schema/data changes need separate tested
   restoration procedures. This candidate contains no schema migration.

Existing scientific architecture, metadata, provenance, rights, stable-ID,
documentation and external-pilot requirements in NPDB_RELEASE_READINESS_20261103.md
remain open. No claim of complete scientific or public-release readiness is made.

Authorization for production-changing actions expires after 3 November 2026 JST.
No production rows, schema, storage objects, credentials or deployment were changed
by this verification session.
