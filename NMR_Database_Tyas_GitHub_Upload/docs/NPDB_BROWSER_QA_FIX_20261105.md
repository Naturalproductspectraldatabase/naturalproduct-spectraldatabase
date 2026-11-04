# Issue19 browser-defect follow-up (separate draft)

Base is the cumulative candidate branch from #57 plus indirect-reader tests.
This patch addresses owner-reported deployed-main observations, not a claim that
the candidate has passed actual browser acceptance.

Owner approved only these mappings in chat on5 Nov: compound class Alkaloids ->
Alkaloid; source category Marine Alga -> Marine alga. Explicit defaults live in
npdb_browser_qa.py, with separate configurable NPDB_COMPOUND_CLASS_DISPLAY_ALIASES
and NPDB_SOURCE_CATEGORY_DISPLAY_ALIASES dictionaries. Empty dictionaries disable
mappings; conflicting case-equivalent mappings preserve the submitted term.
Capitalization and whitespace matching applies to display/filter/group/statistic
views only. No extra chemical/taxonomic synonyms are inferred. Dataframe tests
verify grouped counts, combined filters, unique options, no omissions/duplicates,
separate vocabularies and unchanged input records.

Forgot password opens both Access Guide and a native Account Recovery modal;
Streamlit supplies modal focus/keyboard containment, to be verified by Work in a
real browser. Instructions state: account recovery is managed by the NPDB
administrator through a previously established communication channel. The owner
explicitly approved NO public contact address/URL. NPDB_ACCOUNT_RECOVERY_URL stays
unset by default; no dead link, personal address, reset flow or account-existence
lookup is introduced. A future owner-approved HTTPS/mailto route can be configured.
No production configuration or secrets are changed.

Quick Browse actions in both search and Home include compound name plus unique ID
in the visible/accessibility label, preserving stable keys and navigation.

Evidence: pure helper UNIT tests cover grouping/input preservation, explicit alias
approval, route validation and unique labels. Full-script synthetic AppTest covers
collapsed-to-open recovery and configured-route rendering. AppTest is not an actual
Chrome/mobile screenreader test. Existing security, chemistry/data/privacy and real
synthetic SQLite/PostgreSQL integration regressions run at exact PR HEAD in CI.
No claim of measured contrast, browser focus, email delivery or recovery-account
workflow completion. Work must validate those on the exact reviewed candidate.

Owner supplied the limited mappings and explicitly requested no public recovery
route for now. Those choices are implemented; actual browser focus/assistive
technology and account-recovery operations remain unverified. No source data, schema,
credentials, real backup/Drive files, production/main or deployment changed. Genuine
independent restore #24 stays BLOCKED. Independent review of both this patch and
the cumulative candidate is still required.

Rollback: close draft; after authorized integration revert its presentation/helper/
test/CI commits together with dependency review. No data/schema rollback. Remove
any future display configuration only through owner-approved configuration change;
this PR does not install configuration in production.
