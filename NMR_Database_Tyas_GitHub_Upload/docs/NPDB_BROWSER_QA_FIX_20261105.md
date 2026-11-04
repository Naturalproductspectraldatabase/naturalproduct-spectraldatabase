# Issue19 browser-defect follow-up (separate draft)

Base is the cumulative candidate branch from #57 plus indirect-reader tests.
This patch addresses owner-reported deployed-main observations, not a claim that
the candidate has passed actual browser acceptance.

Source category counts collapse whitespace/case using existing vocabulary, group
case-equivalent values and preserve original dataframe/record values. Compound
class cards/charts can use NPDB_COMPOUND_CLASS_DISPLAY_ALIASES, an explicit owner-
reviewed dictionary; there is no inferred singular/plural taxonomy conversion.
Without approval, Alkaloid and Alkaloids remain submitted terms, with a disclosure
explaining that mappings require owner review. That terminology decision remains
BLOCKED until approved; no scientific data is rewritten.

Forgot password is a native Streamlit button opening Access Guide through session
state, supporting keyboard activation rather than a link to a collapsed expander.
Guide wording reflects editor curation and owner-only administration. A validated
NPDB_ACCOUNT_RECOVERY_URL may be an owner-approved HTTPS page or mailto address.
No email/route is invented. If absent/invalid, the UI explicitly states that recovery
contact is not configured. Owner route approval remains BLOCKED, not silently treated
as fixed. Do not put credentials or private tokens into this URL. No live configuration
or secrets are changed by this patch.

Quick Browse actions in both search and Home include compound name plus unique ID
in the visible/accessibility label, preserving stable keys and navigation.

Evidence: pure helper UNIT tests cover grouping/input preservation, explicit alias
approval, route validation and unique labels. Full-script synthetic AppTest covers
collapsed-to-open recovery and configured-route rendering. AppTest is not an actual
Chrome/mobile screenreader test. Existing security, chemistry/data/privacy and real
synthetic SQLite/PostgreSQL integration regressions run at exact PR HEAD in CI.
No claim of measured contrast, browser focus, email delivery or recovery-account
workflow completion. Work must validate those on the exact reviewed candidate.

Owner was asked for approved recovery route/class aliases; until supplied, both
configuration-dependent outcomes remain explicit blockers. No source data, schema,
credentials, real backup/Drive files, production/main or deployment changed. Genuine
independent restore #24 stays BLOCKED. Independent review of both this patch and
the cumulative candidate is still required.

Rollback: close draft; after authorized integration revert its presentation/helper/
test/CI commits together with dependency review. No data/schema rollback. Remove
any future display configuration only through owner-approved configuration change;
this PR does not install configuration in production.
