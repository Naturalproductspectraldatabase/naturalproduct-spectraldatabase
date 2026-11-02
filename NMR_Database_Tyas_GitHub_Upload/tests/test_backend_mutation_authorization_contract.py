"""SECURITY CONTRACT (currently EXPECTED RED until backend auth is fixed).

This tests real final functions from NPDB app.py with synthetic user states and
FAKE Supabase REST transport. No Streamlit initialization, passwords, network,
database or production records. Failures are explicit release blockers.

Conservative expected capabilities:
  anonymous/viewer -> no insert/update/delete
  approved editor   -> insert and update, no destructive delete
  approved owner    -> insert, update and delete

IMPORTANT: A production authorization rule must validate server-side approved
identity, not just a session_state role. Independent role-identity tests are
located in test_role_authorization.py on the editor PR.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


APP = Path(__file__).resolve().parents[1] / "scripts" / "app.py"


def _compile_real_final_functions(names, bindings):
    tree = ast.parse(APP.read_text(encoding="utf-8"), filename=str(APP))
    for name in names:
        candidates = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        ]
        if not candidates:
            raise AssertionError(f"Required backend entry point missing: {name}")
        node = candidates[-1]
        node.decorator_list = []
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(APP), "exec"), bindings)
    return bindings


def _synthetic_backend(role, *, authenticated=True):
    calls = []
    # All network/DB operations are dummy functions. Any attempted write
    # is recorded, not sent to a real service.
    def request(method, route, **kwargs):
        calls.append((method, route))
        return [{"id": 12345, "updated_at": "2026-11-03T00:00:00Z"}]

    def insert_request(table, row):
        calls.append(("POST", table))
        return [{"id": 12345}]

    st = SimpleNamespace(session_state={
        "npdb_authenticated": authenticated,
        "npdb_username": "synthetic_owner" if role == "owner" else "synthetic_" + role,
        "npdb_role": role,
        "npdb_auth_mode": "approved_users",
    })
    ctx = {
        "st": st,
        "cloud_backend_is_configured": lambda: False,
        "use_supabase_backend": lambda: True,
        "use_supabase_write_backend": lambda: True,
        "use_local_read_backend": lambda: False,
        "_supabase_request": request,
        "_supabase_insert_request": insert_request,
        "record_audit_event": lambda *args, **kwargs: None,
        "invalidate_cached_views": lambda: None,
        "_json_ready": lambda x: x,
        "maybe_blank": lambda value: str(value or "").strip(),
        "is_duplicate_primary_key_error": lambda exc: False,
        "get_connection": lambda: (_ for _ in ()).throw(
            AssertionError("No SQLite writes permitted in synthetic cloud test")),
    }
    _compile_real_final_functions((
        "ensure_write_target_ready",
        "supabase_insert_row",
        "supabase_update_row",
        "supabase_delete_row",
        "delete_compound_record",
    ), ctx)
    return ctx, calls


class MutatingBackendAuthorizationContract(unittest.TestCase):
    def test_guest_and_viewer_cannot_insert_or_update(self):
        for role, authenticated in (
            ("viewer", True), ("viewer", False), ("editor", False),
        ):
            for action in ("insert", "update"):
                with self.subTest(role=role, authenticated=authenticated, action=action):
                    ctx, calls = _synthetic_backend(role, authenticated=authenticated)
                    with self.assertRaises((PermissionError, RuntimeError)):
                        if action == "insert":
                            ctx["supabase_insert_row"]("compounds", {"trivial_name": "SYNTHETIC"})
                        else:
                            ctx["supabase_update_row"]("compounds", 12345, {"note": "SYNTHETIC"})
                    self.assertEqual(calls, [], "Unauthorised actor reached fake write transport")

    def test_guest_viewer_and_editor_cannot_delete_through_app_entrypoint(self):
        for role, authenticated in (
            ("viewer", False), ("viewer", True), ("editor", True),
        ):
            with self.subTest(role=role, authenticated=authenticated):
                ctx, calls = _synthetic_backend(role, authenticated=authenticated)
                with self.assertRaises((PermissionError, RuntimeError)):
                    ctx["delete_compound_record"](12345)
                self.assertEqual(calls, [], "Delete reached fake REST via unprivileged role")

    def test_guest_viewer_and_editor_cannot_delete_via_direct_supabase_helper(self):
        for role, authenticated in (
            ("viewer", False), ("viewer", True), ("editor", True),
        ):
            with self.subTest(role=role, authenticated=authenticated):
                ctx, calls = _synthetic_backend(role, authenticated=authenticated)
                with self.assertRaises((PermissionError, RuntimeError)):
                    ctx["supabase_delete_row"]("compounds", 12345)
                self.assertEqual(calls, [], "Direct delete helper reached fake REST")

    def test_approved_editor_can_insert_and_update_but_not_delete(self):
        ctx, calls = _synthetic_backend("editor")
        ctx["supabase_insert_row"]("compounds", {"trivial_name": "SYNTHETIC"})
        ctx["supabase_update_row"]("compounds", 12345, {"note": "TEST"})
        self.assertEqual([x[0] for x in calls], ["POST", "PATCH"])
        with self.assertRaises((PermissionError, RuntimeError)):
            ctx["supabase_delete_row"]("compounds", 12345)
        self.assertEqual([x[0] for x in calls], ["POST", "PATCH"])

    def test_approved_owner_can_access_owner_actions(self):
        ctx, calls = _synthetic_backend("owner")
        ctx["supabase_insert_row"]("compounds", {"trivial_name": "SYNTHETIC"})
        ctx["supabase_update_row"]("compounds", 12345, {"note": "TEST"})
        ctx["supabase_delete_row"]("compounds", 12345)
        self.assertEqual([x[0] for x in calls], ["POST", "PATCH", "DELETE"])


if __name__ == "__main__":
    unittest.main()
