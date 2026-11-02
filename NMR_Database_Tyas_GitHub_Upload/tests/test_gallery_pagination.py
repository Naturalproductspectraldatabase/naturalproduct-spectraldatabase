"""Offline unit tests for shared 1H/13C gallery pagination (no app startup).

Run on a complete checkout:
python -m unittest discover -s NMR_Database_Tyas_GitHub_Upload/tests -p 'test_gallery_pagination.py' -v
"""
import ast
import importlib.util
from pathlib import Path
import re
import unittest


PROJECT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT / "scripts" / "npdb_gallery_pagination.py"
APP_PATH = PROJECT / "scripts" / "app.py"
spec = importlib.util.spec_from_file_location("npdb_gallery_pagination_test", MODULE_PATH)
pages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pages)


def isolated_app_function(name, namespace):
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"), filename=str(APP_PATH))
    candidates = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    if not candidates:
        raise AssertionError(f"Function {name} does not exist")
    exec(compile(ast.Module(body=[candidates[-1]], type_ignores=[]), str(APP_PATH), "exec"), namespace)
    return namespace[name]


class SharedGalleryPaginationTests(unittest.TestCase):
    def test_paginate_ten_twenty_and_forty(self):
        for size in (10, 20, 40):
            start, end, count = pages.pagination_window(101, size, 1)
            self.assertEqual((start, end), (0, size))
            self.assertEqual(count, (101 + size - 1) // size)

    def test_last_page_includes_remaining_records(self):
        self.assertEqual(pages.pagination_window(83, 40, 3), (80, 83, 3))

    def test_no_more_pages_for_zero_records(self):
        self.assertEqual(pages.pagination_window(0, 10, 8), (0, 0, 1))

    def test_invalid_page_and_page_size_are_safe(self):
        self.assertEqual(pages.bounded_page(-10, 5), 1)
        self.assertEqual(pages.bounded_page(100, 5), 5)
        self.assertEqual(pages.bounded_page("not a page", 5), 1)
        self.assertEqual(pages.bounded_page(None, 5), 1)
        with self.assertRaises(ValueError):
            pages.pagination_window(50, 0, 1)

    def test_top_and_bottom_are_synchronized(self):
        state = {}
        self.assertEqual(pages.set_gallery_page(state, "one_h_gallery", 3, 8), 3)
        self.assertEqual(state["one_h_gallery_page"], 3)
        self.assertEqual(state["one_h_gallery_top_jump"], 3)
        self.assertEqual(state["one_h_gallery_bottom_jump"], 3)

    def test_next_clicked_at_last_page_is_clamped(self):
        state = {}
        self.assertEqual(pages.set_gallery_page(state, "one_h_gallery", 15, 9), 9)
        self.assertEqual(state["one_h_gallery_bottom_jump"], 9)

    def test_search_change_resets_page_to_one(self):
        state = {}
        pages.apply_gallery_criteria(state, prefix="one_h_gallery", search_text="", page_size=10, total_pages=9)
        pages.set_gallery_page(state, "one_h_gallery", 7, 9)
        actual = pages.apply_gallery_criteria(
            state, prefix="one_h_gallery", search_text="sponge", page_size=10,
            total_pages=8,
        )
        self.assertEqual(actual, 1)
        self.assertEqual(state["one_h_gallery_bottom_jump"], 1)

    def test_change_in_page_size_resets_page(self):
        state = {}
        pages.apply_gallery_criteria(state, prefix="one_h_gallery", search_text="", page_size=10, total_pages=9)
        pages.set_gallery_page(state, "one_h_gallery", 6, 9)
        self.assertEqual(
            pages.apply_gallery_criteria(state, prefix="one_h_gallery", search_text="", page_size=40, total_pages=3),
            1,
        )

    def test_current_page_clamps_when_fewer_results_return(self):
        state = {}
        pages.apply_gallery_criteria(state, prefix="thirteen_c_gallery", search_text="", page_size=10, total_pages=8)
        pages.set_gallery_page(state, "thirteen_c_gallery", 7, 8)
        actual = pages.apply_gallery_criteria(
            state, prefix="thirteen_c_gallery", search_text="", page_size=10, total_pages=2,
        )
        self.assertEqual(actual, 2)

    def test_h_and_c_pages_have_independent_state(self):
        state = {}
        pages.set_gallery_page(state, "one_h_gallery", 5, 9)
        pages.set_gallery_page(state, "thirteen_c_gallery", 2, 3)
        self.assertEqual(state["one_h_gallery_page"], 5)
        self.assertEqual(state["thirteen_c_gallery_page"], 2)

    def test_two_dimensional_spectra_not_mislabeled_as_carbon_1d(self):
        ns = {"maybe_blank": lambda x: str(x or "").strip(), "re": re}
        check = isolated_app_function("is_carbon_spectrum_label", ns)
        for value in ("13C", "carbon", "13C NMR", "C-13"):
            self.assertTrue(check(value), value)
        for value in ("1H", "1H HSQC", "13C HSQC", "13C HMBC", "COSY", None):
            self.assertFalse(check(value), value)

    def test_both_gallery_routes_are_registered(self):
        text = APP_PATH.read_text(encoding="utf-8")
        for label in ('"1H Spectra Gallery"', '"13C Spectra Gallery"'):
            self.assertIn(label, text)
        self.assertIn('elif main_section == "13C Spectra Gallery":', text)
        self.assertIn('show_carbon_spectra_gallery()', text)

    def test_shared_renderer_wires_top_and_bottom_controls(self):
        source = APP_PATH.read_text(encoding="utf-8")
        self.assertIn('_render_spectra_gallery_pagination(prefix, pages, "top")', source)
        self.assertIn('_render_spectra_gallery_pagination(prefix, pages, "bottom")', source)
        self.assertIn("[↑ Back to gallery top]", source)
        self.assertIn('on_click=_set_spectra_gallery_page', source)
        self.assertIn('on_change=_jump_spectra_gallery_page', source)

    def test_gallery_page_renders_only_current_slice(self):
        source = APP_PATH.read_text(encoding="utf-8")
        self.assertIn("current_page = gallery_df.iloc[start:end]", source)
        self.assertIn("for _, row in current_page.iterrows():", source)

    def test_app_and_helpers_parse_without_importing_live_services(self):
        ast.parse(APP_PATH.read_text(encoding="utf-8"), filename=str(APP_PATH))
        ast.parse(MODULE_PATH.read_text(encoding="utf-8"), filename=str(MODULE_PATH))


if __name__ == "__main__":
    unittest.main()
