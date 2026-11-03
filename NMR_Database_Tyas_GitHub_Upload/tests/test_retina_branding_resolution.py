"""Synthetic, read-only frontend image-resolution guards.

No NPDB images, private files, production database, network or credentials.
"""
import ast
import base64
import io
import os
from pathlib import Path
import mimetypes
import re
import tempfile
import unittest

from PIL import Image, ImageOps


APP = Path(__file__).resolve().parents[1] / "scripts" / "app.py"
CODE = APP.read_text(encoding="utf-8")
TREE = ast.parse(CODE)


def app_function(name):
    # Rehydrate the cached encoder and public revision-aware wrapper together.
    names = (["_cached_optimized_image_data_uri", name]
             if name == "optimized_image_data_uri" else [name])
    functions = []
    for function_name in names:
        matches = [node for node in TREE.body
                   if isinstance(node, ast.FunctionDef) and node.name == function_name]
        if len(matches) != 1:
            raise AssertionError(f"Expected exactly one {function_name} function")
        matches[0].decorator_list = []
        functions.append(matches[0])
    namespace = {
        "Path": Path, "Image": Image, "ImageOps": ImageOps, "io": io,
        "base64": base64, "mimetypes": mimetypes,
    }
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(APP), "exec"), namespace)
    return namespace[name]


class RetinaBrandingTests(unittest.TestCase):
    def test_sidebar_export_image_has_retina_pixel_budget(self):
        css = re.search(r"\.sidebar-brand-logo\s*\{[^}]*?width:\s*(\d+)px", CODE, re.S)
        self.assertIsNotNone(css)
        displayed_css_width = int(css.group(1))
        render = next(n for n in TREE.body if isinstance(n, ast.FunctionDef)
                      and n.name == "render_sidebar_workspace_summary")
        choices = [kw.value.value for call in ast.walk(render)
                   if isinstance(call, ast.Call)
                   and isinstance(call.func, ast.Name)
                   and call.func.id == "image_to_data_uri"
                   for kw in call.keywords if kw.arg == "max_px"
                   and isinstance(kw.value, ast.Constant)]
        self.assertTrue(choices, "Sidebar image max_px constraint missing")
        self.assertGreaterEqual(max(choices), 2 * displayed_css_width)

    def test_synthetic_transparent_logo_preserves_retina_source_budget(self):
        optimized = app_function("optimized_image_data_uri")
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "synthetic-logo.png"
            Image.new("RGBA", (512, 512), (22, 111, 184, 128)).save(src)
            value = optimized(str(src), max_px=256)
            self.assertTrue(value.startswith("data:image/png;base64,"))
            with Image.open(io.BytesIO(base64.b64decode(value.split(",", 1)[1]))) as im:
                self.assertEqual(im.size, (256, 256))
                self.assertEqual(im.mode, "RGBA")

    def test_source_at_256px_not_upscaled(self):
        optimized = app_function("optimized_image_data_uri")
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "synthetic-small.png"
            Image.new("RGBA", (256, 256), (255, 0, 0, 220)).save(src)
            uri = optimized(str(src), max_px=256)
            with Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1]))) as im:
                self.assertEqual(im.size, (256, 256))


    def test_same_path_new_pixels_invalidate_cached_data_uri(self):
        """A live Streamlit worker must not serve stale branding after replacement."""
        optimized = app_function("optimized_image_data_uri")
        cache = {}
        original_helper = optimized.__globals__["_cached_optimized_image_data_uri"]

        def fake_cache(path, max_px, quality, mtime_ns, byte_size):
            key = (path, max_px, quality, mtime_ns, byte_size)
            if key not in cache:
                cache[key] = original_helper(path, max_px, quality, mtime_ns, byte_size)
            return cache[key]
        optimized.__globals__["_cached_optimized_image_data_uri"] = fake_cache

        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "synthetic-live.png"
            Image.new("RGBA", (128, 128), (255, 0, 0, 255)).save(src)
            first = optimized(str(src), max_px=256)
            cached = optimized(str(src), max_px=256)
            self.assertEqual(first, cached)
            self.assertEqual(len(cache), 1)

            Image.new("RGBA", (128, 128), (0, 0, 255, 255)).save(src)
            st = src.stat()
            os.utime(src, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))
            second = optimized(str(src), max_px=256)
            self.assertNotEqual(first, second)
            self.assertEqual(len(cache), 2)

    def test_removed_image_returns_empty_instead_of_stale_cache(self):
        optimized = app_function("optimized_image_data_uri")
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "synthetic-removed.png"
            Image.new("RGBA", (64, 64), (17, 23, 129, 255)).save(src)
            self.assertTrue(optimized(str(src)))
            src.unlink()
            self.assertEqual(optimized(str(src)), "")


    def test_image_data_uri_wrapper_does_not_hide_asset_revisions(self):
        """Outer path-only cache must not bypass the signature-aware encoder."""
        matches = [node for node in TREE.body if isinstance(node, ast.FunctionDef)
                   and node.name == "image_to_data_uri"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].decorator_list, [],
                         "image_to_data_uri must not cache solely by path")
        wrapper = app_function("image_to_data_uri")
        versions = iter(["data:image/png;base64,VERSION1", "data:image/png;base64,VERSION2"])
        wrapper.__globals__["optimized_image_data_uri"] = lambda path, max_px: next(versions)
        self.assertNotEqual(wrapper("synthetic/path.png"), wrapper("synthetic/path.png"))


if __name__ == "__main__":
    unittest.main()
