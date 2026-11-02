"""Nonproduction source/AST regression checks for Home layout and donut.

Run on a local full checkout:
python -m unittest discover -s NMR_Database_Tyas_GitHub_Upload/tests -p 'test_home_visual_rhythm.py' -v

No app startup, network, Streamlit, Supabase or file writes.
"""
from pathlib import Path
import ast
import unittest


APP_PATH = Path(__file__).resolve().parents[1] / "scripts" / "app.py"


class HomeVisualRhythmTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = APP_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source, filename=str(APP_PATH))

    def test_plotly_pie_is_not_pulled_out(self):
        funcs = [
            f for f in self.tree.body
            if isinstance(f, ast.FunctionDef) and f.name == "render_dashboard_pie_chart"
        ]
        self.assertEqual(len(funcs), 1)
        calls = [
            call for call in ast.walk(funcs[0])
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "update_traces"
        ]
        self.assertTrue(any(
            any(k.arg == "pull" and isinstance(k.value, ast.Constant)
                and k.value.value == 0 for k in call.keywords)
            for call in calls
        ))
        self.assertNotIn("pull=[0.025]", self.source)

    def test_search_button_keeps_original_behavior(self):
        self.assertIn(
            'st.button("Start Searching ->", key="dashboard_start_search"',
            self.source,
        )
        self.assertIn('navigate_internal("Search & Match")', self.source)
        self.assertIn('with st.container(key="dashboard_search_action"):', self.source)

    def test_spacing_only_targets_home_sections(self):
        for required in (
            ".dashboard-home-section-gap",
            ".st-key-dashboard_search_action",
            ".st-key-dashboard_workspace_cta",
            ".dashboard-workspace-card .dashboard-workspace-title",
        ):
            self.assertIn(required, self.source)
        self.assertIn("aria-hidden=\\"true\\"", self.source)

    def test_mobile_css_has_separate_spacing(self):
        self.assertIn("@media (max-width: 900px)", self.source)
        self.assertIn("padding-top: 0.4rem;", self.source)

    def test_app_parses_without_importing_cloud_services(self):
        self.assertIsNotNone(self.tree)


if __name__ == "__main__":
    unittest.main()
