"""NPDB structure-image integrity tests, isolated from network and production data.

Run on a complete local checkout:
  python -m unittest discover -s NMR_Database_Tyas_GitHub_Upload/tests -p 'test_structure_image_integrity.py' -v

The tests compile only selected functions from the real app.py AST with dummy
Pillow images and mocked services. They never import the live Streamlit app,
contact Supabase, use credentials or mutate database records.
"""
import ast
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageOps


APP = Path(__file__).resolve().parents[1] / "scripts" / "app.py"


def isolated(name, namespace):
    tree = ast.parse(APP.read_text(encoding="utf-8"), filename=str(APP))
    nodes = [x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == name]
    if not nodes:
        raise AssertionError(f"Function {name} not found in app.py")
    exec(compile(ast.Module(body=[nodes[-1]], type_ignores=[]), str(APP), "exec"), namespace)
    return namespace[name]


def img_png_bytes(img):
    data = io.BytesIO()
    img.save(data, format="PNG")
    return data.getvalue()


def no_smiles_fallback(*args, **kwargs):
    raise AssertionError("A curated/uploaded PNG must NOT be replaced with SMILES")


class FakeSt:
    def __init__(self):
        self.images = []
        self.warnings = []
        self.captions = []
        self.infos = []

    def cache_data(self, *a, **k):
        return lambda f: f

    def image(self, img, **kwargs):
        self.images.append(img)

    def warning(self, msg):
        self.warnings.append(str(msg))

    def caption(self, msg):
        self.captions.append(str(msg))

    def info(self, msg):
        self.infos.append(str(msg))


class DummyUrlOpener:
    def __init__(self, png):
        self.png = png
        self.requested_urls = []

    def urlopen(self, url, timeout=8, context=None):
        self.requested_urls.append(url)
        return io.BytesIO(self.png)


class StructureImageIntegrityTests(unittest.TestCase):
    def ns_images(self):
        ns = {
            "Image": Image,
            "ImageOps": ImageOps,
            "STRUCTURE_DETAIL_IMAGE_SIZE": (300, 240),
            "STRUCTURE_THUMBNAIL_IMAGE_SIZE": (160, 140),
            "STRUCTURE_RENDERER_VERSION": "test-only",
            "EXTERNAL_ASSET_CACHE_TTL_SECONDS": 30,
            "STRUCTURE_MIN_CRISP_ASSET_EDGE": 700,
            "io": io,
            "st": FakeSt(),
            "standardized_structure_from_smiles": no_smiles_fallback,
            "pil_image_to_png_bytes": img_png_bytes,
        }
        isolated("normalize_structure_image", ns)
        return ns

    def test_curated_small_local_png_is_not_overridden_by_smiles(self):
        ns = self.ns_images()
        loader = isolated("load_standardized_structure_image", ns)
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "curated.png"
            # Solid colors survive resampling deterministically.
            im = Image.new("RGB", (120, 60), (20, 50, 80))
            im.save(p)
            actual = loader(p, size=(300, 240), fallback_smiles="INCORRECT_DUMMY_SMILES")
            self.assertEqual(actual.size, (300, 240))
            self.assertEqual(actual.mode, "RGB")
            self.assertEqual(actual.getpixel((150, 120)), (20, 50, 80))

    def test_curated_small_remote_png_is_not_overridden_by_smiles(self):
        ns = self.ns_images()
        opener = DummyUrlOpener(img_png_bytes(Image.new("RGB", (70, 70), (65, 140, 10))))
        import types
        ns["urllib"] = types.SimpleNamespace(request=opener)
        ns["display_asset_url"] = lambda text: "https://test.invalid/test.png"
        ns["_supabase_ssl_context"] = lambda: None
        loader = isolated("load_external_structure_png_bytes", ns)
        data = loader(
            "storage://structures/curated_structures/compound_1/test.png",
            size=(200, 200),
            fallback_smiles="INCORRECT_DUMMY_SMILES",
        )
        with Image.open(io.BytesIO(data)) as result:
            self.assertEqual(result.size, (200, 200))
            self.assertEqual(result.getpixel((100, 100)), (65, 140, 10))
        self.assertEqual(opener.requested_urls, ["https://test.invalid/test.png"])

    def test_transparent_png_is_composited_on_opaque_white(self):
        ns = self.ns_images()
        normalize = ns["normalize_structure_image"]
        transparent = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        for px in range(40, 61):
            for py in range(40, 61):
                transparent.putpixel((px, py), (0, 0, 0, 255))
        normalized = normalize(transparent, size=(200, 200))
        self.assertEqual(normalized.mode, "RGB")
        self.assertEqual(normalized.getpixel((0, 0)), (255, 255, 255))
        self.assertEqual(normalized.getpixel((100, 100)), (0, 0, 0))

    def test_broken_curated_reference_warns_without_smiles_substitution(self):
        ns = self.ns_images()
        ns.update({
            "maybe_blank": lambda x: str(x or "").strip(),
            "first_structure_identifier": lambda *a: "INCORRECT_DUMMY_SMILES",
            "load_standardized_structure_source": lambda *a, **k: None,
            "is_external_url": lambda x: False,
            "is_supabase_storage_reference": lambda x: True,
            "is_generated_structure_reference": lambda x: False,
            "structure_smiles_png_bytes": no_smiles_fallback,
            "structure_smiles_image_url": no_smiles_fallback,
        })
        render = isolated("render_compound_structure_from_row", ns)
        render({
            "structure_image_path": "storage://structures/curated_structures/compound_1/reference.png",
            "smiles": "INCORRECT_DUMMY_SMILES",
        })
        self.assertFalse(ns["st"].images)
        self.assertEqual(len(ns["st"].warnings), 1)
        self.assertIn("not replaced", ns["st"].warnings[0])

    def test_generated_image_displays_unverified_source_label(self):
        ns = self.ns_images()
        ns.update({
            "maybe_blank": lambda x: str(x or "").strip(),
            "first_structure_identifier": lambda *a: "CCO",
            "load_standardized_structure_source": lambda *a, **k: Image.new("RGB", (90, 90), "white"),
            "is_generated_structure_reference": lambda x: "generated/" in x,
        })
        render = isolated("render_compound_structure_from_row", ns)
        render({"structure_image_path": "storage://structures/generated/dummy.png", "smiles": "CCO"})
        self.assertEqual(len(ns["st"].images), 1)
        self.assertTrue(any("unverified" in x for x in ns["st"].captions))

    def test_missing_image_path_marks_computed_depiction_unverified(self):
        ns = self.ns_images()
        ns.update({
            "maybe_blank": lambda x: str(x or "").strip(),
            "first_structure_identifier": lambda *a: "CCO",
            "structure_smiles_png_bytes": lambda *a, **k: b"pretend_png",
        })
        render = isolated("render_compound_structure_from_row", ns)
        render({"structure_image_path": "", "smiles": "CCO"})
        self.assertEqual(len(ns["st"].images), 1)
        self.assertTrue(any("unverified" in x for x in ns["st"].captions))

    def test_compound_detail_never_silently_falls_back_for_missing_registered_image(self):
        tree = ast.parse(APP.read_text(encoding="utf-8"))
        fn = next(n for n in reversed(tree.body) if isinstance(n, ast.FunctionDef) and n.name == "show_compound_detail")
        block = ast.get_source_segment(APP.read_text(encoding="utf-8"), fn)
        self.assertIn("Registered structure image could not be displayed", block)
        self.assertIn("is_generated_structure_reference(structure_path)", block)

    def test_low_res_png_substitution_logic_removed_from_image_loaders(self):
        tree = ast.parse(APP.read_text(encoding="utf-8"))
        for name in ("load_standardized_structure_image", "load_external_structure_png_bytes"):
            fn = next(n for n in reversed(tree.body) if isinstance(n, ast.FunctionDef) and n.name == name)
            refs = [node for node in ast.walk(fn) if isinstance(node, ast.Name)]
            self.assertNotIn("STRUCTURE_MIN_CRISP_ASSET_EDGE", [n.id for n in refs])


if __name__ == "__main__":
    unittest.main()
