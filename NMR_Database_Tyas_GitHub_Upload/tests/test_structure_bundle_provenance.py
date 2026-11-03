"""Synthetic scientific-integrity checks for compound ZIP structure provenance.

Uses extracted app functions and disposable DataFrames. No network, credentials,
private research records, production Storage or database access.
"""
import ast
import datetime
import hashlib
import io
import json
from pathlib import Path
import unittest
import zipfile

import pandas as pd


APP = Path(__file__).resolve().parents[1] / "scripts" / "app.py"
SOURCE = APP.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def extract_function(name, dependencies):
    matches = [
        node for node in TREE.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one app function: {name}")
    function = matches[0]
    function.decorator_list = []
    namespace = dict(dependencies)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(APP), "exec"), namespace)
    return namespace[name]


class StructureBundleProvenanceTests(unittest.TestCase):
    @staticmethod
    def source_stub(read_asset, render_smiles):
        dependencies = {
            "maybe_blank": lambda text: str(text or "").strip(),
            "_asset_bytes_from_source": read_asset,
            "structure_smiles_png_bytes": render_smiles,
            "STRUCTURE_DOWNLOAD_IMAGE_SIZE": (400, 400),
            "structure_smiles_image_url": lambda _: "https://example.invalid/synthetic",
        }
        return extract_function("_compound_structure_asset", dependencies)

    def test_registered_unavailable_image_never_substitutes_smiles_drawing(self):
        source = self.source_stub(
            lambda path, kind="attachment": (b"", ""),
            lambda *args, **kwargs: b"SYNTHETIC_UNVERIFIED_STRUCTURE",
        )
        actual = source({
            "structure_image_path": "storage://structures/private-missing.png",
            "smiles": "CCO",
        })
        self.assertEqual(actual, (b"", ""), "A registered depiction must not be replaced silently")

    def test_registered_available_image_preserves_exact_bytes(self):
        expected = b"SYNTHETIC_REGISTERED_IMAGE_BYTES"
        source = self.source_stub(
            lambda path, kind="attachment": (expected, ".png"),
            lambda *args, **kwargs: self.fail("Should not render SMILES"),
        )
        self.assertEqual(source({
            "structure_image_path": "storage://structures/synthetic.png",
            "smiles": "CCO",
        }), (expected, ".png"))

    def test_missing_registered_reference_does_not_generate_structure(self):
        source = self.source_stub(
            lambda *args, **kwargs: self.fail("Should not read nonexistent reference"),
            lambda *args, **kwargs: self.fail("Should not synthesize unregistered drawing"),
        )
        self.assertEqual(source({"structure_image_path": "", "smiles": "CCO"}), (b"", ""))

    @staticmethod
    def build_bundle(*, path, structure_bytes):
        safe_metadata = lambda row: pd.DataFrame([{"Field": "Compound", "Value": "synthetic"}])
        def columns(frame, expected):
            return frame.reindex(columns=expected).copy()
        env = {
            "pd": pd,
            "io": io,
            "zipfile": zipfile,
            "json": json,
            "hashlib": hashlib,
            "datetime": datetime.datetime,
            "UTC": datetime.timezone.utc,
            "_archive_safe_name": lambda *args, **kwargs: "synthetic_compound",
            "clean_text": lambda value: str(value) if value is not None else "",
            "maybe_blank": lambda value: str(value or "").strip(),
            "_important_metadata_dataframe": safe_metadata,
            "_important_bioactivity_dataframe": lambda frame: frame.copy(),
            "_select_existing_columns": columns,
            "build_compound_summary_text": lambda *args: b"SYNTHETIC RECORD ONLY",
            "_dataframes_to_record_workbook": lambda _: b"SYNTHETIC WORKBOOK ONLY",
            "_compound_structure_asset": lambda _: (structure_bytes, ".png" if structure_bytes else ""),
        }
        bundle = extract_function("build_compound_record_bundle", env)
        compound = pd.DataFrame([{
            "id": 101, "trivial_name": "synthetic", "structure_image_path": path,
        }])
        empty = pd.DataFrame()
        archive_bytes, _ = bundle(compound, empty, empty, empty, empty)
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as z:
            manifest = json.loads(z.read("manifest.json"))
            assets = [n for n in z.namelist() if n.startswith("structure/")]
            return manifest, assets, [z.read(n) for n in assets]

    def test_registered_unavailable_provenance_is_explicit_in_manifest(self):
        manifest, filenames, _ = self.build_bundle(
            path="storage://structures/synthetic-unavailable.png", structure_bytes=b"",
        )
        self.assertEqual(manifest["structure_asset_status"], "registered_unavailable")
        self.assertEqual(filenames, [])
        self.assertIn("not substituted", manifest["structure_policy"].lower())

    def test_registered_original_checksum_and_manifest(self):
        asset = b"SYNTHETIC_REGISTERED_IMAGE_BYTES"
        manifest, filenames, contents = self.build_bundle(
            path="storage://structures/synthetic.png", structure_bytes=asset,
        )
        self.assertEqual(manifest["structure_asset_status"], "embedded_registered")
        self.assertEqual(manifest["structure_asset_sha256"], hashlib.sha256(asset).hexdigest())
        self.assertEqual(len(filenames), 1)
        self.assertEqual(contents[0], asset)

    def test_unregistered_image_status_is_explicit(self):
        manifest, filenames, _ = self.build_bundle(path="", structure_bytes=b"")
        self.assertEqual(manifest["structure_asset_status"], "not_registered")
        self.assertEqual(filenames, [])


if __name__ == "__main__":
    unittest.main()
