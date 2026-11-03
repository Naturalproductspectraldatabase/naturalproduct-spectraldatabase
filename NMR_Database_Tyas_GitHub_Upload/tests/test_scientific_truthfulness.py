"""Synthetic scientific truthfulness regressions for NPDB's draft release.

No network, database connections, authentic science records or local research files.
"""
import ast
from pathlib import Path
import re
import unittest

import pandas as pd

APP = Path(__file__).resolve().parents[1] / "scripts" / "app.py"
SOURCE = APP.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def function(name, names=None):
    defs = [x for x in TREE.body if isinstance(x, ast.FunctionDef) and x.name == name]
    if len(defs) != 1:
        raise AssertionError(f"One definition expected: {name}")
    fn = defs[0]
    fn.decorator_list = []
    env = dict(names or {})
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(APP), "exec"), env)
    return env[name]


class ScientificTruthfulnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.normalize = staticmethod(function(
            "normalize_curation_status",
            {"maybe_blank": lambda x: str(x or "").strip(),
             "CURATION_STATUS_OPTIONS": ("imported", "reviewed", "curated")},
        ))
        cls.infer = staticmethod(function(
            "infer_curation_status",
            {"maybe_blank": lambda x: str(x or "").strip(),
             "normalize_curation_status": cls.normalize},
        ))
        cls.active = staticmethod(function("is_explicit_positive_outcome", {"re": re}))

    def test_blank_or_unknown_curation_status_never_becomes_curated(self):
        for value in ("", None, "unknown", "not-reviewed", "pending"):
            with self.subTest(value=value):
                self.assertEqual(self.normalize(value), "imported")

    def test_explicit_curated_and_reviewed_statuses_are_preserved(self):
        self.assertEqual(self.normalize("curated"), "curated")
        self.assertEqual(self.normalize(" reviewed "), "reviewed")

    def test_missing_curation_evidence_is_not_inferred_as_curated(self):
        self.assertEqual(self.infer({"note": "", "data_source": ""}), "imported")
        self.assertEqual(self.infer({"data_source": "Experimental"}), "imported")
        self.assertEqual(self.infer({"curation_status": "curated"}), "curated")

    def test_inactive_and_negated_outcomes_do_not_count(self):
        for label in ("inactive", "Inactive (IC50 >100 uM)", "not active",
                      "not potent", "non-active", "negative", "strongly inactive",
                      "not active but potent", "moderate", "selective", ""):
            with self.subTest(label=label):
                self.assertFalse(self.active(label))

    def test_explicit_positive_outcome_categories(self):
        for label in ("active", "POTENT", "Strong", "strongly active", "highly potent"):
            with self.subTest(label=label):
                self.assertTrue(self.active(label))
        self.assertFalse(self.active("activity not reported"))

    def test_metadata_presence_not_labelled_verified(self):
        self.assertNotIn("% Verified", SOURCE)
        self.assertIn("Core Metadata Coverage", SOURCE)
        self.assertIn("% with name, class &amp; source", SOURCE)

    def test_nmr_entry_forms_never_prefill_conditions(self):
        forbidden = [
            'st.text_input("Solvent", value="CDCl3")',
            'st.text_input("Solvent", value="CDCl3", key="add13c_solvent")',
            'st.text_input("Instrument (MHz)", value="500")',
            'st.text_input("Instrument (MHz)", value="125")',
        ]
        for phrase in forbidden:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, SOURCE)

    def test_default_source_is_not_claimed_experimental(self):
        self.assertNotIn('value="Experimental")', SOURCE)
        self.assertNotIn('compound_row["data_source"] = compound_row["data_source"] or "Experimental"', SOURCE)

    def test_no_curated_fallback_in_writer_paths(self):
        self.assertNotIn('normalize_curation_status(curation_status, default="curated")', SOURCE)
        self.assertNotIn('get_wizard_value("wizard_curation_status", "curated")', SOURCE)

    def test_core_metadata_presence_does_not_require_structure_or_nmr(self):
        health = function("calculate_workspace_health", {"pd": pd, "enrich_compounds_dataframe": lambda frame: frame})
        raw = pd.DataFrame({
            "trivial_name": ["A", "B", "C"],
            "compound_class": ["alkaloid"] * 3,
            "source_category": ["sponge"] * 3,
            "source_organism": [""] * 3,
            "source_material": [""] * 3,
            "smiles": [""] * 3, "inchi": [""] * 3, "inchikey": [""] * 3,
            "doi": [""] * 3, "journal_name": [""] * 3,
        })
        output = health(raw)
        self.assertEqual(output["submission_ready"], 3)
        self.assertEqual(output["structure_ready"], 0)
        self.assertEqual(output["reference_ready"], 0)


if __name__ == "__main__":
    unittest.main()
