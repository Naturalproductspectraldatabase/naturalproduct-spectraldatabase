"""Offline C15 regression tests for NPDB New Submission (dummy data only).

Run from a full repository checkout:
python -m unittest discover -s NMR_Database_Tyas_GitHub_Upload/tests -p 'test_wizard_draft.py' -v

Requires only Python stdlib; no Streamlit, Supabase, credentials or network.
"""
import ast
import importlib.util
from pathlib import Path
import unittest

PROJECT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT / "scripts" / "npdb_wizard_draft.py"
APP_PATH = PROJECT / "scripts" / "app.py"
spec = importlib.util.spec_from_file_location("npdb_wizard_draft_test", MODULE_PATH)
draft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(draft)


class WizardPersistenceTests(unittest.TestCase):
    def test_all_four_steps_have_distinct_keys(self):
        seen = set()
        for step in (1, 2, 3, 4):
            fields = set(draft.WIZARD_STEP_FIELDS[step])
            self.assertTrue(fields)
            self.assertFalse(fields & seen, f"overlapping widget keys at step {step}")
            seen |= fields
        self.assertIn("wizard_source_organism", seen)
        self.assertIn("wizard_sample_code", seen)
        self.assertIn("wizard_ftir_data", seen)
        self.assertIn("wizard_hrms_data", seen)
        self.assertIn("wizard_doi", seen)

    def test_step_two_inputs_survive_streamlit_widget_cleanup(self):
        state = {
            "wizard_source_organism": "TEST SPONGE",
            "wizard_sample_code": "DEMO-123",
            "wizard_collection_location": "DEMO LOCALITY",
            "wizard_gps_coordinates": "DEMO-COORD",
            "wizard_depth_m": "17",
            "wizard_note": "DEMO FIELD NOTES",
        }
        draft.persist_visible_wizard_step(state, 2)
        for key in draft.WIZARD_STEP_FIELDS[2]:
            state.pop(key, None)  # Streamlit removed inactive widgets
        # Current step 3 must not overwrite step 2's good data.
        state["wizard_uv_data"] = "DEMO UV"
        draft.persist_visible_wizard_step(state, 3)
        for key, expected in {
            "wizard_source_organism": "TEST SPONGE",
            "wizard_sample_code": "DEMO-123",
            "wizard_collection_location": "DEMO LOCALITY",
            "wizard_gps_coordinates": "DEMO-COORD",
            "wizard_depth_m": "17",
            "wizard_note": "DEMO FIELD NOTES",
        }.items():
            self.assertEqual(draft.draft_value(state, key), expected)

    def test_step_three_spectroscopy_survives_navigation_to_review(self):
        state = {key: f"DEMO:{key}" for key in draft.WIZARD_STEP_FIELDS[3]
                 if key not in draft.UPLOAD_KEYS}
        draft.persist_visible_wizard_step(state, 3)
        for key in draft.WIZARD_STEP_FIELDS[3]:
            state.pop(key, None)
        state["wizard_journal_name"] = "JOURNAL DEMO"
        draft.persist_visible_wizard_step(state, 4)
        for key in (
            "wizard_uv_data", "wizard_ftir_data", "wizard_cd_data",
            "wizard_optical_rotation", "wizard_melting_point",
            "wizard_crystallization_method", "wizard_ccdc_number", "wizard_hrms_data",
        ):
            self.assertEqual(draft.draft_value(state, key), f"DEMO:{key}")
        self.assertEqual(draft.draft_value(state, "wizard_journal_name"), "JOURNAL DEMO")

    def test_all_four_steps_survive_multiple_back_and_forward_transitions(self):
        state = {}
        fixtures = {
            1: {"wizard_trivial_name": "TEST STRUCTURE"},
            2: {"wizard_source_organism": "DEMO SOURCE", "wizard_sample_code": "S-001"},
            3: {"wizard_uv_data": "UV demo", "wizard_hrms_data": "HRMS demo"},
            4: {"wizard_doi": "10.0000/dummy"},
        }
        for step, values in fixtures.items():
            state.update(values)
            draft.persist_visible_wizard_step(state, step)
            for key in draft.WIZARD_STEP_FIELDS[step]:
                state.pop(key, None)
        # Returning to step 2 and changing one field should preserve everything else.
        state["wizard_sample_code"] = "S-002"
        draft.persist_visible_wizard_step(state, 2)
        self.assertEqual(draft.draft_value(state, "wizard_sample_code"), "S-002")
        for step, values in fixtures.items():
            for key, val in values.items():
                if key == "wizard_sample_code":
                    continue
                self.assertEqual(draft.draft_value(state, key), val)

    def test_hidden_cleared_keys_cannot_override_saved_draft(self):
        state = {
            "_draft_wizard_sample_code": "DEMO-ORIGINAL",
            "wizard_sample_code": "",  # stale hidden widget
            "wizard_uv_data": "UV DEMO",
        }
        draft.persist_visible_wizard_step(state, 3)
        self.assertEqual(draft.draft_value(state, "wizard_sample_code"), "DEMO-ORIGINAL")

    def test_visible_field_can_intentionally_be_cleared(self):
        state = {
            "_draft_wizard_sample_code": "DEMO-ORIGINAL",
            "wizard_sample_code": "",
        }
        draft.persist_visible_wizard_step(state, 2)
        self.assertEqual(draft.draft_value(state, "wizard_sample_code"), "")

    def test_uploads_remain_in_memory_after_widget_disappears(self):
        dummy_file = object()
        state = {
            "wizard_structure_upload": dummy_file,
            "wizard_submission_spectra_uploads": [object(), object()],
        }
        draft.persist_visible_wizard_step(state, 3)
        state.pop("wizard_structure_upload")
        state.pop("wizard_submission_spectra_uploads")
        self.assertIs(draft.draft_value(state, "wizard_structure_upload"), dummy_file)
        self.assertEqual(len(draft.draft_value(state, "wizard_submission_spectra_uploads")), 2)

    def test_transient_empty_file_uploader_does_not_erase_saved_upload(self):
        dummy_file = object()
        state = {
            "_draft_wizard_structure_upload": dummy_file,
            "wizard_structure_upload": None,
        }
        draft.persist_visible_wizard_step(state, 3)
        self.assertIs(draft.draft_value(state, "wizard_structure_upload"), dummy_file)

    def test_explicit_reset_clears_only_wizard_fields_and_drafts(self):
        state = {
            "another_user_setting": "KEEP",
            "_draft_wizard_sample_code": "DEMO",
            "wizard_sample_code": "DEMO",
            "_draft_wizard_uv_data": "DEMO UV",
        }
        draft.reset_wizard_drafts(state)
        self.assertEqual(state["another_user_setting"], "KEEP")
        self.assertEqual(state["compound_wizard_step"], 1)
        self.assertNotIn("_draft_wizard_sample_code", state)
        self.assertNotIn("_draft_wizard_uv_data", state)

    def test_invalid_step_is_rejected(self):
        with self.assertRaises(ValueError):
            draft.persist_visible_wizard_step({}, 0)
        with self.assertRaises(ValueError):
            draft.persist_visible_wizard_step({}, 5)

    def test_application_calls_step_scoped_saves_not_rerun_wide_copy(self):
        source = APP_PATH.read_text(encoding="utf-8")
        self.assertIn("from npdb_wizard_draft import persist_visible_wizard_step", source)
        self.assertEqual(source.count("persist_wizard_inputs(wizard_step)"), 3)
        marker = 'elif compound_page == "New Submission":'
        region = source[source.index(marker):source.index(marker)+3000]
        self.assertNotIn("        persist_wizard_inputs()", region)

    def test_final_review_exposes_origin_and_spectroscopic_metadata(self):
        source = APP_PATH.read_text(encoding="utf-8")
        self.assertIn("Review all Origin and Spectral Data before saving", source)
        for key in ("wizard_sample_code", "wizard_ftir_data", "wizard_hrms_data"):
            self.assertIn(key, source)

    def test_hydration_only_runs_for_current_visible_step(self):
        source = APP_PATH.read_text(encoding="utf-8")
        marker = 'elif compound_page == "New Submission":'
        region = source[source.index(marker):source.index(marker) + 2400]
        self.assertIn("for key in WIZARD_STEP_FIELDS[wizard_step]:", region)
        self.assertNotIn("for key in [", region)
        self.assertLess(region.index('wizard_step = int('), region.index("hydrate_wizard_widget(key)"))

    def test_hydrate_skips_read_only_file_uploader_widget_keys(self):
        app_source = APP_PATH.read_text(encoding="utf-8")
        tree = ast.parse(app_source, filename=str(APP_PATH))
        node = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == "hydrate_wizard_widget")
        class UploadSafeState(dict):
            def __setitem__(self, key, value):
                if key in draft.UPLOAD_KEYS:
                    raise AssertionError("cannot assign directly to Streamlit uploader widget")
                super().__setitem__(key, value)
        class FakeSt:
            session_state = UploadSafeState({
                "_draft_wizard_structure_upload": object(),
                "_draft_wizard_submission_spectra_uploads": [object()],
            })
        ns = {"st": FakeSt()}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(APP_PATH), "exec"), ns)
        hydrate = ns["hydrate_wizard_widget"]
        for key in draft.UPLOAD_KEYS:
            hydrate(key)
            self.assertNotIn(key, FakeSt.session_state)
            self.assertIn(f"_draft_{key}", FakeSt.session_state)

    def test_app_source_is_syntactically_valid_without_importing_app(self):
        ast.parse(APP_PATH.read_text(encoding="utf-8"), filename=str(APP_PATH))


if __name__ == "__main__":
    unittest.main()
