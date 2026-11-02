"""Actual app attachment boundaries; all files and record values are synthetic."""
import ast
import hashlib
import io
from pathlib import Path
import sys
import tempfile
import types
import unittest
import zipfile

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from npdb_asset_paths import AssetAccessError, read_local_asset, validate_asset_content
APP = Path(__file__).resolve().parents[1] / 'scripts/app.py'


def load(ns, *names):
    tree = ast.parse(APP.read_text())
    for name in names:
        node = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name][-1]
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(APP), 'exec'), ns)


def reader_namespace(project):
    ns = dict(Path=Path, PROJECT_DIR=project, STRUCTURES_DIR=project/'data/structures',
              SPECTRA_DIR=project/'data/spectra', SPECIMENS_DIR=project/'data/specimens',
              read_local_asset=read_local_asset, validate_asset_content=validate_asset_content,
              AssetAccessError=AssetAccessError, LOCAL_ASSET_MAX_BYTES=1024*1024,
              LOCAL_IMAGE_SUFFIXES={'.png', '.jpg', '.jpeg', '.webp', '.gif'},
              LOCAL_SPECTRUM_SUFFIXES={'.png', '.pdf', '.jdx', '.txt', '.zip'},
              maybe_blank=lambda v: str(v or '').strip(),
              is_external_url=lambda v: str(v).startswith('https://'),
              is_supabase_storage_reference=lambda v: str(v).startswith('storage://'),
              io=io, Image=Image, hashlib=hashlib, slugify_value=lambda v: v)
    load(ns, 'read_scientific_asset', 'local_asset_available', 'get_full_file_path',
         '_asset_bytes_from_source', '_compound_structure_asset', 'render_registered_file_preview',
         '_render_specimen_image')
    return ns


class AppAssetBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name).resolve()
        self.ns = reader_namespace(self.project)
        for name in ('structures', 'spectra', 'specimens'):
            (self.project/'data'/name).mkdir(parents=True)
        output = io.BytesIO()
        Image.new('RGB', (8, 8), 'white').save(output, format='PNG')
        self.png = output.getvalue()
        self.image = self.project/'data/structures/curated.png'
        self.image.write_bytes(self.png)
        self.secret = self.project/'private.png'
        self.secret.write_bytes(b'SYNTHETIC-SECRET-MARKER')
        self.outputs = []
        self.ns['st'] = types.SimpleNamespace(
            image=lambda data, **kw: self.outputs.append(data),
            warning=lambda msg: self.outputs.append(msg), info=lambda msg: self.outputs.append(msg),
            download_button=lambda **kw: self.outputs.append(kw['data']))

    def test_curated_bytes_absolute_and_relative_preserved(self):
        for path in (self.image, 'data/structures/curated.png'):
            self.assertEqual(self.ns['read_scientific_asset'](path, 'structure'), self.png)

    def test_negative_paths_never_reach_preview_or_export(self):
        link = self.project/'data/structures/link.png'
        link.symlink_to(self.secret)
        for source in (self.secret, '../private.png', 'data/structures/../../private.png',
                       link, self.project/'.streamlit/secrets.toml', '/etc/passwd'):
            with self.subTest(case=Path(source).name):
                self.assertEqual(self.ns['_asset_bytes_from_source'](str(source)), (b'', ''))
                self.ns['render_registered_file_preview'](str(source))
                self.assertNotIn(b'SYNTHETIC-SECRET-MARKER', self.outputs)
                self.assertFalse(any(str(self.project) in str(x) for x in self.outputs))

    def test_context_roots_prevent_cross_category_reads(self):
        with self.assertRaises(AssetAccessError):
            self.ns['read_scientific_asset'](self.image, 'spectrum')

    def test_preview_passes_approved_bytes_to_streamlit(self):
        self.ns['render_registered_file_preview'](str(self.image), kind='structure')
        self.assertEqual(self.outputs, [self.png])
        self.ns['_render_specimen_image'](str(self.secret))
        self.assertNotIn(b'SYNTHETIC-SECRET-MARKER', self.outputs)

    def test_pdf_download_and_local_replacement_are_fresh(self):
        p = self.project/'data/spectra/synthetic.pdf'
        p.write_bytes(b'%PDF-1.4\nsynthetic')
        self.ns['render_registered_file_preview'](str(p), kind='spectrum')
        self.assertEqual(self.outputs, [p.read_bytes()])
        p.write_bytes(b'%PDF-1.4\nchanged')
        self.assertEqual(self.ns['read_scientific_asset'](p), p.read_bytes())

    def test_forged_image_and_pdf_and_oversize_are_blocked(self):
        for filename in ('forged.png', 'forged.pdf'):
            p = self.project/'data/spectra'/filename
            p.write_bytes(b'SYNTHETIC-SECRET-MARKER')
            self.assertEqual(self.ns['_asset_bytes_from_source'](str(p)), (b'', ''))
        self.ns['LOCAL_ASSET_MAX_BYTES'] = 2
        self.assertEqual(self.ns['_asset_bytes_from_source'](str(self.image)), (b'', ''))

    def test_record_structure_asset_does_not_substitute_missing_curated_image(self):
        self.ns['structure_smiles_png_bytes'] = lambda *a, **k: self.fail('curated image substituted')
        self.assertEqual(self.ns['_compound_structure_asset'](
            {'structure_image_path': str(self.secret), 'smiles': 'CCO'}), (b'', ''))

    def test_full_record_zip_excludes_secret_bytes(self):
        import pandas as pd
        ns = self.ns
        ns.update(pd=pd, datetime=__import__('datetime').datetime, UTC=__import__('datetime').UTC,
                  zipfile=zipfile, json=__import__('json'), clean_text=lambda v: str(v or ''),
                  _archive_safe_name=lambda v, **kw: v,
                  _important_metadata_dataframe=lambda row: pd.DataFrame(),
                  _important_bioactivity_dataframe=lambda df: df,
                  build_compound_summary_text=lambda *a: b'synthetic',
                  _dataframes_to_record_workbook=lambda *a: b'synthetic')
        load(ns, '_select_existing_columns', 'build_compound_record_bundle')
        record = pd.DataFrame([dict(id=1, trivial_name='synthetic', structure_image_path=str(self.secret))])
        data, _ = ns['build_compound_record_bundle'](record, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertFalse(any(n.startswith('structure/') for n in archive.namelist()))
            self.assertFalse(any(b'SYNTHETIC-SECRET-MARKER' in archive.read(n) for n in archive.namelist()))

    def test_no_record_reader_opens_locator_paths(self):
        tree = ast.parse(APP.read_text())
        for name in ('load_standardized_structure_image', '_asset_bytes_from_source',
                     'render_spectra_section', 'render_registered_file_preview', '_render_specimen_image'):
            node = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name][-1]
            text = ast.get_source_segment(APP.read_text(), node)
            self.assertNotIn('.read_bytes()', text)
            self.assertNotIn('open(full_path', text)
            self.assertNotIn('st.image(str(full_path)', text)
