"""Full-script login checks in a disposable, empty local database.

Install Streamlit to enable these tests. No bundled research data, production
credentials, or network requests are used.
"""
import base64
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec("streamlit"), "Streamlit not installed")
class StreamlitLoginIntegrationTests(unittest.TestCase):
    def setUp(self):
        from streamlit.testing.v1 import AppTest

        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        scripts = root / "scripts"
        scripts.mkdir()
        (root / "database").mkdir()
        (root / "data").mkdir()
        source = Path(__file__).resolve().parents[1] / "scripts"
        for file in source.glob("*.py"):
            shutil.copy2(file, scripts / file.name)
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.network = patch("urllib.request.urlopen", side_effect=AssertionError("Network forbidden in isolated QA"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.app = AppTest.from_file(str(scripts / "app.py"), default_timeout=30)

    def configure_login(self):
        digest = hashlib.pbkdf2_hmac("sha256", b"synthetic-test-password", b"qa-salt", 10000)
        encoded = base64.urlsafe_b64encode(digest).decode().rstrip("=")
        self.app.secrets["NPDB_ACCESS_USERNAME"] = "synthetic_viewer"
        self.app.secrets["NPDB_ACCESS_PASSWORD_HASH"] = f"pbkdf2_sha256$10000$qa-salt${encoded}"
        self.app.secrets["NPDB_READ_BACKEND"] = "local"

    def test_missing_configuration_stops_before_data_ui(self):
        self.app.run()
        self.assertEqual(len(self.app.exception), 0)
        self.assertTrue(any("login is not configured" in error.value for error in self.app.error))
        self.assertEqual(len(self.app.text_input), 0)

    def test_stale_authenticated_session_cannot_bypass_missing_configuration(self):
        self.app.session_state["npdb_authenticated"] = True
        self.app.run()
        self.assertEqual(len(self.app.exception), 0)
        self.assertTrue(any("login is not configured" in error.value for error in self.app.error))

    def test_invalid_password_keeps_login_gate(self):
        self.configure_login()
        self.app.run()
        self.app.text_input[0].input("synthetic_viewer")
        self.app.text_input[1].input("incorrect")
        self.app.button[0].click().run()
        self.assertEqual(len(self.app.exception), 0)
        self.assertFalse(self.app.session_state.get("npdb_authenticated", False))

    def test_configured_login_form_renders_without_data_access(self):
        self.configure_login()
        self.app.run()
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual([field.label for field in self.app.text_input], ["Username", "Password"])

    def test_valid_viewer_login_opens_empty_local_workspace(self):
        self.configure_login()
        self.app.run()
        self.app.text_input[0].input("synthetic_viewer")
        self.app.text_input[1].input("synthetic-test-password")
        self.app.button[0].click().run()
        self.assertEqual(len(self.app.exception), 0)
        self.assertTrue(self.app.session_state["npdb_authenticated"])
        self.assertEqual(self.app.session_state["npdb_username"], "synthetic_viewer")


    def configure_multi_role_login(self):
        def hash_password(password, salt):
            digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 10000)
            encoded = base64.urlsafe_b64encode(digest).decode().rstrip("=")
            return f"pbkdf2_sha256$10000${salt}${encoded}"

        self.app.secrets["NPDB_APPROVED_USERS"] = [
            {"username": "npdb_tyas", "role": "owner", "password_hash": hash_password("test-owner-only", "qa-owner")},
            {"username": "npdb_tjomori", "role": "editor", "password_hash": hash_password("test-mentor-only", "qa-mentor")},
            {"username": "npdb_viewer", "role": "viewer", "password_hash": hash_password("test-viewer-only", "qa-viewer")},
        ]
        self.app.secrets["NPDB_READ_BACKEND"] = "local"

    def test_explicitly_approved_mentor_editor_login_is_not_owner_login(self):
        self.configure_multi_role_login()
        self.app.run()
        self.app.text_input[0].input("npdb_tjomori")
        self.app.text_input[1].input("test-mentor-only")
        self.app.button[0].click().run()
        self.assertEqual(len(self.app.exception), 0)
        self.assertTrue(self.app.session_state["npdb_authenticated"])
        self.assertEqual(self.app.session_state["npdb_auth_mode"], "approved_users")
        self.assertEqual(self.app.session_state["npdb_role"], "editor")
        self.assertEqual(self.app.session_state["npdb_username"], "npdb_tjomori")

    def test_explicit_viewer_login_stays_read_only(self):
        self.configure_multi_role_login()
        self.app.run()
        self.app.text_input[0].input("npdb_viewer")
        self.app.text_input[1].input("test-viewer-only")
        self.app.button[0].click().run()
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual(self.app.session_state["npdb_role"], "viewer")


if __name__ == "__main__":
    unittest.main()
