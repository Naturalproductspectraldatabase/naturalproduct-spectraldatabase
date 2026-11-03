"""Scientific disclosure tests using only synthetic potency and NMR metadata.

Does not access production, credentials, research records, assets or the network.
"""
import ast
from pathlib import Path
import unittest

import pandas as pd


APP = Path(__file__).resolve().parents[1] / "scripts" / "app.py"
SOURCE = APP.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def function(name, dependencies=None):
    matches = [node for node in TREE.body
               if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(matches) != 1:
        raise AssertionError(name)
    node = matches[0]
    node.decorator_list = []
    ns = dict(dependencies or {})
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(APP), "exec"), ns)
    return ns[name]


class ScientificDisclosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.disclose = staticmethod(function("disclose_potency_unit_status", {"pd": pd}))
        cls.export = staticmethod(function(
            "export_bioactivity_results", {"pd": pd, "disclose_potency_unit_status": cls.disclose}
        ))

    def test_missing_unit_is_flagged_without_guessing_or_modifying(self):
        raw = pd.DataFrame([
            {"Value": 12.0, "Unit": None},
            {"Value": 5.0, "Unit": "mM"},
            {"Value": 7.5, "Unit": ""},
            {"Value": None, "Unit": ""},
        ])
        snapshot = raw.copy(deep=True)
        flagged = self.disclose(raw)
        pd.testing.assert_frame_equal(snapshot, raw)
        self.assertEqual(flagged["Unit"].tolist()[:3], [None, "mM", ""])
        self.assertIn("Not recorded", flagged["Unit Status"].iloc[0])
        self.assertIn("dimensionless", flagged["Unit Status"].iloc[2])
        self.assertEqual(flagged["Unit Status"].iloc[1], "Recorded")
        self.assertEqual(flagged["Unit Status"].iloc[3], "No potency value")

    def test_export_has_unit_status_and_keeps_units_case_sensitive(self):
        raw = pd.DataFrame([
            {"id": 1, "potency_type": "IC50", "potency_value": 12.5, "potency_unit": ""},
            {"id": 2, "potency_type": "IC50", "potency_value": 1.0, "potency_unit": "mM"},
            {"id": 3, "potency_type": "pIC50", "potency_value": 7.0, "potency_unit": ""},
        ])
        out = self.export(raw)
        self.assertIn("Unit Status", out.columns)
        self.assertEqual(out["Unit"].tolist(), ["", "mM", ""])
        self.assertIn("Not recorded", out["Unit Status"].iloc[2])
        self.assertEqual(out["Unit Status"].iloc[1], "Recorded")

    def test_nmr_coverage_is_denominator_based_not_database_wide(self):
        self.assertIn("Registered NMR peak-list coverage", SOURCE)
        self.assertIn("n_h:,}/{n_total:,}", SOURCE)
        self.assertIn("n_c:,}/{n_total:,}", SOURCE)
        self.assertIn("different solvents or instruments", SOURCE)

    def test_nmr_score_is_not_presented_as_confidence(self):
        self.assertIn("uncalibrated heuristic ranking", SOURCE)
        self.assertNotIn('"Score (%)": round(item["score"], 2)', SOURCE)
        self.assertIn('"Heuristic NMR Rank (0–100)"', SOURCE)
        self.assertIn('f"Heuristic rank:', SOURCE)
        self.assertIn("not calibrated confidence", SOURCE)


if __name__ == "__main__":
    unittest.main()
