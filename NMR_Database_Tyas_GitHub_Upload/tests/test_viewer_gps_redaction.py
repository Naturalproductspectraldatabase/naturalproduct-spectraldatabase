"""No real GPS data: role-based redaction on actual production function AST.

The test compiles only small un-decorated functions from app.py; never imports
Streamlit application, secrets, network, production DB or research records.
"""
import ast
from pathlib import Path
import unittest
from authorization_fixture import bind_authorization

import pandas as pd

APP = Path(__file__).resolve().parents[1] / "scripts" / "app.py"
SOURCE = ast.parse(APP.read_text(encoding="utf-8"), filename=str(APP))


def compile_function(name, ns):
    funcs = [n for n in SOURCE.body if isinstance(n, ast.FunctionDef) and n.name == name]
    if not funcs:
        raise AssertionError("Application function missing: " + name)
    fn = funcs[-1]
    # Preserve actual outer authorization and projection on public wrappers.
    fn.decorator_list = [d for d in fn.decorator_list if isinstance(d,ast.Name) and d.id == "authorized_read"]
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(APP), "exec"), ns)
    return ns[name]


class PreciseGpsRoleTests(unittest.TestCase):
    def setUp(self):
        self.role = "viewer"
        self.source = pd.DataFrame([
            {"id": 1, "gps_coordinates": "SYNTHETIC-SECRET-COORDS", "trivial_name": "Synthetic compound"}
        ])
        self.ns = bind_authorization(role="viewer")
        self.ns.update({
            "current_backend_role": lambda: self.role,
            "SOURCE_NORMALIZATION_CACHE_VERSION": "test-only",
            "get_db_signature": lambda: "test-signature",
            "pd": pd,
        })
        compile_function("display_precise_gps", self.ns)
        compile_function("redact_private_gps_for_current_user", self.ns)

    def test_fail_closed_and_privileged_visibility(self):
        render = self.ns["display_precise_gps"]
        for role in ("", "revoked", "unknown"):
            self.role=role
            with self.assertRaises(PermissionError):render("SYNTHETIC-SECRET-COORDS")
        for role in ("viewer", "approved-viewer", "editor"):
            self.role = role
            self.assertEqual(render("SYNTHETIC-SECRET-COORDS"), "")
        for role in ("owner", "owner_editor", "admin"):
            self.role = role
            self.assertEqual(render("SYNTHETIC-SECRET-COORDS"), "SYNTHETIC-SECRET-COORDS")

    def test_copy_does_not_modify_cached_source_across_sessions(self):
        guard = self.ns["redact_private_gps_for_current_user"]
        self.role = "owner"
        self.assertEqual(guard(self.source).loc[0, "gps_coordinates"], "SYNTHETIC-SECRET-COORDS")
        self.role = "viewer"
        self.assertIsNone(guard(self.source).loc[0, "gps_coordinates"])
        self.assertEqual(self.source.loc[0, "gps_coordinates"], "SYNTHETIC-SECRET-COORDS")
        self.role = "owner"
        self.assertEqual(guard(self.source).loc[0, "gps_coordinates"], "SYNTHETIC-SECRET-COORDS")

    def test_compound_cached_wrappers_are_masked(self):
        for public, private in (
            ("load_all_compounds", "_load_all_compounds_cached"),
            ("load_dashboard_compounds", "_load_dashboard_compounds_cached"),
            ("load_search_compounds", "_load_search_compounds_cached"),
            ("load_compound_row", "_load_compound_row_cached"),
        ):
            with self.subTest(public=public):
                ns = dict(self.ns)
                ns[private] = lambda *args, **kw: self.source
                wrapped = compile_function(public, ns)
                self.role = "viewer"
                masked = wrapped(1) if public == "load_compound_row" else wrapped()
                self.assertIsNone(masked.loc[0, "gps_coordinates"])
                self.role = "editor"
                visible = wrapped(1) if public == "load_compound_row" else wrapped()
                self.assertIsNone(visible.loc[0, "gps_coordinates"])

    def test_specimen_cached_wrappers_are_masked(self):
        for public, private in (
            ("load_all_specimens", "_load_all_specimens_cached"),
            ("load_specimen_row", "_load_specimen_row_cached"),
        ):
            with self.subTest(public=public):
                ns = dict(self.ns)
                ns[private] = lambda *args, **kw: self.source
                wrapped = compile_function(public, ns)
                self.role = "viewer"
                masked = wrapped(1) if public == "load_specimen_row" else wrapped()
                self.assertIsNone(masked.loc[0, "gps_coordinates"])
                self.role = "owner"
                visible = wrapped(1) if public == "load_specimen_row" else wrapped()
                self.assertEqual(visible.loc[0, "gps_coordinates"], "SYNTHETIC-SECRET-COORDS")

    def test_csv_export_never_leaks_gps_for_viewer(self):
        export = compile_function("export_name_results", dict(self.ns))
        self.role = "viewer"
        csv = export(self.source)
        self.assertIn("GPS Coordinates", csv.columns)
        self.assertIsNone(csv.loc[0, "GPS Coordinates"])
        self.role = "owner"
        self.assertEqual(export(self.source).loc[0, "GPS Coordinates"], "SYNTHETIC-SECRET-COORDS")

    def test_all_known_detail_and_export_paths_call_role_guard(self):
        for name in (
            "build_compound_summary_text",
            "_important_metadata_dataframe",
            "show_compound_detail",
            "show_specimen_library_pages",
        ):
            with self.subTest(name=name):
                fn = [n for n in SOURCE.body if isinstance(n, ast.FunctionDef) and n.name == name][-1]
                guards = [n for n in ast.walk(fn)
                          if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                          and n.func.id == "display_precise_gps"]
                self.assertTrue(guards, "No precise GPS guard in " + name)


if __name__ == "__main__":
    unittest.main()
