"""Fail-closed authentication regression tests. Runs without secrets or network."""
import ast
import unittest
from authorization_fixture import bind_authorization
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "scripts" / "app.py"

class StopStreamlit(Exception):
    pass

class FakeSt:
    def __init__(self, authorized=False):
        self.session_state = {"npdb_authenticated": authorized}
        self.messages = []
    def error(self, msg):
        self.messages.append(str(msg))
    def stop(self):
        raise StopStreamlit()

def isolated_verify(namespace):
    tree = ast.parse(APP.read_text(encoding="utf-8"), filename=str(APP))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "verify_access_gate")
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(APP), "exec"), namespace)
    return namespace["verify_access_gate"]

class FailClosedLoginTests(unittest.TestCase):
    def test_missing_secrets_disallow_anonymous_access(self):
        st = FakeSt()
        verify = isolated_verify({"st":st, "is_access_gate_enabled":lambda:False})
        with self.assertRaises(StopStreamlit):
            verify()
        self.assertTrue(st.messages)
        self.assertIn("login is not configured", st.messages[0])

    def test_missing_secrets_also_block_stale_session_authenticated_flag(self):
        st = FakeSt(authorized=True)
        verify = isolated_verify({"st":st,"is_access_gate_enabled":lambda:False})
        with self.assertRaises(StopStreamlit):
            verify()

    def test_validly_configured_authenticated_session_continues(self):
        st = FakeSt(authorized=True)
        ns = bind_authorization()
        st.session_state.update(ns["st"].session_state)
        ns.update(st=st, is_access_gate_enabled=lambda: True)
        verify = isolated_verify(ns)
        self.assertIsNone(verify())
        self.assertEqual(st.messages, [])

if __name__ == "__main__":
    unittest.main()
