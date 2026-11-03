"""Synthetic, read-only frontend image-resolution guards.

No NPDB images, private files, production database, network or credentials.
"""
import ast
import base64
import io
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
    matches = [node for node in TREE.body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(matches) != 1:
        raise AssertionError(f"Expected exactly one {name} function")
    fn = matches[0]
    fn.decorator_list = []
    namespace = {
        "Path": Path, "Image": Image, "ImageOps": ImageOps, "io": io,
        "base64": base64, "mimetypes": mimetypes,
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(APP), "exec"), namespace)
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


if __name__ == "__main__":
    unittest.main()
