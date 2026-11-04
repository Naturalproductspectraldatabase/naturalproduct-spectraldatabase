# NMR result navigation correction

Base: #59 exact272d502d6812f62bbb20acd2cf3106b203c0ea1c, preserving #58/#57. app.py scoped ownership claimed through #17. No scientific matcher/parser, schema, records, images, taxonomy, theme, auth or export changes.

## Confirmed defect and correction

Full-script AppTest with actual app.py, empty disposable local SQLite and one synthetic compound99001 with carbon10/proton1 reproduced four failures BEFORE the patch: Open Record in13C,1H,combined mode and editor Update Metadata all leave selected_compound_id=None after clicking a result. Buttons are created only during the form-submit run, so the next rerun does not execute the inline click handler.

Use Streamlit on_click callbacks for those two result actions. Callback executes before the next full-script run, setting the existing selected id/navigation state. No persistent search-result cache introduced. Results are still submit-only; returning to search requires resubmission. This narrow fix does not implement the audit's separate preserve-results-on-back proposal.

## Evidence and limits

Tests copy all application Python helpers into a new TemporaryDirectory, clear environment, configure dummy local users, forbid urllib network, initialize only synthetic SQLite records, submit all3 NMR forms and click actual result buttons. They check record identity/navigation, editor destination, viewer disabled editing, fresh-session isolation and password-rotation denial of an already rendered action. They perform no mutation form submission and no access to original research files or databases. Existing backend authorization tests remain required: callback navigation itself grants no write capability.

Local exploratory Python3.14/Streamlit1.56/pandas3: before4 assertion failures; after initial3 methods pass (all3 search subcases, editor and revocation). Final local run:4 methods pass, including viewer/fresh-session isolation (19.185s). Supported pinned Python3.11/3.12,Streamlit1.66.1,RDKit CI is the integration gate. AppTest exercises real Streamlit callbacks/reruns but does not demonstrate browser keyboard focus, contrast, assistive technology, viewport layout or real production acceptance. Browser acceptance belongs to Work #19/#23.

Risks: callbacks may set navigation before top-level auth revalidation; revoked sessions still stop at login before reads, verified by saved-action test. No cross-user/global result cache or extra query work. Existing authorization gates remain unchanged. Curator approval is not needed for navigation; scientific ranking assumptions remain unchanged and unresolved science evidence is retained in separate #60.

Review/rollback: independently review narrow app.py diff and exact-SHA CI before adopting into cumulative candidate. Separate sibling to docs/test #61; do not merge either independently to main. Close unmerged draft or revert this commit only on candidate to roll back; original navigation defect will return. No data rollback. #24 actual production restore, #43 privacy decisions and release remain BLOCKED.
