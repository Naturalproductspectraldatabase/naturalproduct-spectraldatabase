"""Least-privilege role authorization regression tests (no real secrets)."""
import ast
from pathlib import Path
import unittest

APP = Path(__file__).resolve().parents[1] / "scripts" / "app.py"


class Session:
    def __init__(self, **kwargs):
        self.session_state = kwargs


def build_checker(state=None, users=None, owner_username="npdb_tyas"):
    source = APP.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(APP))
    func = next(node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "is_owner_editor")
    st = Session(**(state or {}))
    normalized = lambda x: "".join(c for c in str(x or "").lower() if c.isalnum())
    ns = {
        "st": st,
        "load_approved_users": lambda: list(users or []),
        "normalize_login_slug": normalized,
        "get_secret_setting": lambda *keys: owner_username,
        "OWNER_EDITOR_USERNAME": "npdb_tyas",
        "OWNER_EDITOR_ROLES": {"owner", "owner_editor", "admin", "editor"},
    }
    exec(compile(ast.Module(body=[func],type_ignores=[]),str(APP),"exec"),ns)
    return ns["is_owner_editor"]


class AuthorizedEditorTests(unittest.TestCase):
    def state(self, name, role, mode="approved_users", authenticated=True):
        return {
            "npdb_authenticated": authenticated,
            "npdb_username": name,
            "npdb_role": role,
            "npdb_auth_mode": mode,
        }

    def users(self):
        # Disposable authorization fixtures; real hashes belong in secrets only.
        return [
            {"username": "npdb_tyas", "role": "owner"},
            {"username": "npdb_tjomori", "role": "editor"},
            {"username": "npdb_viewer", "role": "viewer"},
        ]

    def test_owner_authenticated_in_server_approved_users(self):
        self.assertTrue(build_checker(self.state("npdb_tyas", "owner"), self.users())())

    def test_mentor_is_editor_only_when_explicitly_approved(self):
        self.assertTrue(build_checker(self.state("npdb_tjomori", "editor"), self.users())())

    def test_viewer_cannot_edit(self):
        self.assertFalse(build_checker(self.state("npdb_viewer", "viewer"), self.users())())

    def test_approved_viewer_cannot_self_promote_role_in_session(self):
        self.assertFalse(build_checker(self.state("npdb_viewer", "editor"), self.users())())

    def test_removed_editor_loses_access_even_with_stale_session_role(self):
        self.assertFalse(build_checker(self.state("npdb_tjomori", "editor"),
                                       [{"username":"npdb_tyas","role":"owner"}])())

    def test_missing_server_configuration_does_not_grant_editor_rights(self):
        self.assertFalse(build_checker(self.state("npdb_tjomori", "editor"), [])())

    def test_approved_names_share_password_mode_never_grants_edit(self):
        self.assertFalse(build_checker(self.state("npdb_tjomori", "editor", mode="approved_names"),
                                       self.users())())

    def test_stale_session_without_authentication_does_not_grant_edit(self):
        self.assertFalse(build_checker(self.state("npdb_tjomori", "editor", authenticated=False),
                                       self.users())())

    def test_legacy_single_user_owner_still_has_edit(self):
        self.assertTrue(build_checker(self.state("npdb_tyas", "viewer", mode="single_user"),
                                      [],owner_username="npdb_tyas")())

    def test_legacy_single_user_other_username_does_not_edit(self):
        self.assertFalse(build_checker(self.state("npdb_tjomori", "editor", mode="single_user"),
                                       [],owner_username="npdb_tjomori")())

    def test_server_config_role_case_normalization(self):
        self.assertTrue(build_checker(self.state("NPDB_TJOMORI","editor"),
                                      [{"username":"npdb_tjomori","role":"Editor"}])())


if __name__ == "__main__":
    unittest.main()
