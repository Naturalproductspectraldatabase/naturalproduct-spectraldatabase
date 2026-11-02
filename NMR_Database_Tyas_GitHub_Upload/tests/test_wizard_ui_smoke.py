"""Streamlit snapshot-only end-to-end wizard navigation regression.

Run in an isolated CI runner with:
 NPDB_READ_BACKEND=snapshot
 NPDB_ACCESS_PASSWORD_HASH=synthetic_dummy_hash
No production Supabase secrets or database writes are required.
"""
from pathlib import Path
import unittest

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # Offline AST-only CI has no Streamlit; separate AppTest job runs this.
    AppTest = None

APP = Path(__file__).resolve().parents[1] / "scripts" / "app.py"


@unittest.skipUnless(AppTest is not None, "Streamlit AppTest runs in dedicated UI CI job")
class WizardUiRoundtripTests(unittest.TestCase):
    def test_origin_and_spectra_survive_back_and_continue(self):
        app = AppTest.from_file(str(APP), default_timeout=120)
        app.session_state["npdb_authenticated"] = True
        app.session_state["npdb_username"] = "npdb_tyas"
        app.session_state["npdb_role"] = "owner"
        app.session_state["nav_section"] = "Compound Workspace"
        app.session_state["compound_page"] = "New Submission"
        app.session_state["compound_wizard_step"] = 1

        def checked_run(label):
            app.run(timeout=120)
            self.assertFalse(app.exception, f"{label}: {[x.message for x in app.exception]}")

        checked_run("initial")
        app.text_input(key="wizard_trivial_name").set_value("SYNTHETIC-DO-NOT-SAVE")
        app.button(key="wizard_next_1").click()
        checked_run("step 2")
        self.assertEqual(app.session_state["compound_wizard_step"], 2)

        app.text_input(key="wizard_source_organism").set_value("DEMO-TEST ORGANISM")
        app.text_input(key="wizard_sample_code").set_value("DEMO-SAMPLE")
        app.button(key="wizard_next_2").click()
        checked_run("step 3")
        self.assertEqual(app.session_state["compound_wizard_step"], 3)

        app.text_input(key="wizard_uv_data").set_value("DEMO UV 210 nm")
        app.text_input(key="wizard_ftir_data").set_value("DEMO 1700 cm-1")
        app.text_area(key="wizard_hrms_data").set_value("DEMO m/z 500.000")
        app.button(key="wizard_next_3").click()
        checked_run("step 4")
        self.assertEqual(app.session_state["compound_wizard_step"], 4)

        expected = {
            "wizard_source_organism": "DEMO-TEST ORGANISM",
            "wizard_sample_code": "DEMO-SAMPLE",
            "wizard_uv_data": "DEMO UV 210 nm",
            "wizard_ftir_data": "DEMO 1700 cm-1",
            "wizard_hrms_data": "DEMO m/z 500.000",
        }
        for key, value in expected.items():
            self.assertEqual(app.session_state.get("_draft_"+key),value,key)

        app.button(key="wizard_back_4").click()
        checked_run("back to step 3")
        app.button(key="wizard_back_3").click()
        checked_run("back to step 2")
        self.assertEqual(app.session_state["compound_wizard_step"],2)
        app.button(key="wizard_next_2").click()
        checked_run("forward to step 3")
        self.assertEqual(app.session_state["compound_wizard_step"],3)
        for key,value in expected.items():
            self.assertEqual(app.session_state.get("_draft_"+key),value,key)


if __name__ == "__main__":
    unittest.main()
