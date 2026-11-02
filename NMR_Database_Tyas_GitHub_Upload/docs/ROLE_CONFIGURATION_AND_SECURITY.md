# NPDB role configuration: explicit server-approved editors

**Development candidate only:** This describes the `is_owner_editor` guard in PR for the QA candidate. It does not create users, change the live Streamlit secrets or grant access itself.

The owner `npdb_tyas` is the existing owner account. To enable the planned mentor/editor account `npdb_tjomori`, the Streamlit administrator must configure a **distinct, strong password hash** in the server-only `NPDB_APPROVED_USERS` setting. Each account must have its own hash; do not copy or share the owner's credentials.

Example **shape only**, with non-functional placeholders (NEVER commit real hashes):

```toml
# Configure in Streamlit Community Cloud Secrets; do not commit secrets.toml.
NPDB_APPROVED_USERS = [
  { username = "npdb_tyas", role = "owner", password_hash = "<owner-pbkdf2-hash-placeholder>" },
  { username = "npdb_tjomori", role = "editor", password_hash = "<mentor-pbkdf2-hash-placeholder>" },
  { username = "npdb_viewer", role = "viewer", password_hash = "<viewer-pbkdf2-hash-placeholder>" }
]
```

The app performs login validation against the approved records; permission checks must also match the configured role, not merely session state. Anonymous/approved_names accounts, revoked accounts and mismatched session roles cannot edit. The existing legacy `NPDB_ACCESS_USERNAME` owner path remains supported when that configured username matches the known owner.

**Not yet enforced:** Separation between curator-editor and owner-administrator privileges is limited in the current single-page app. `is_owner_editor` historically gates some technical path diagnostics. Owner-only management, approvals, account administration and destructive operation roles should be separated in follow-up security reviews. No autonomous creation of the mentor account is intended; official account setup requires administrator action and secure password handling.

**Test requirements:** authenticated owner, configured editor, viewer, unauthorized username, forged role, deleted editor and legacy owner; then a real browser test on isolated staging before deploying. The test suite uses entirely synthetic identities, not real account hashes.
