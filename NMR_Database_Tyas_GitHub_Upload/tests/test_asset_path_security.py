"""Synthetic-only local asset containment and race regressions."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from npdb_asset_paths import AssetAccessError, read_local_asset


class AssetPathSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.root = self.project / 'data' / 'spectra'
        self.root.mkdir(parents=True)
        self.asset = self.root / 'sample.jdx'
        self.asset.write_bytes(b'##TITLE=synthetic\n##END=')
        self.secret = self.project / 'private.jdx'
        self.secret.write_bytes(b'SYNTHETIC-PRIVATE-MARKER')

    def read(self, source, **kw):
        return read_local_asset(source, project=self.project, roots=[self.root],
                                max_bytes=kw.get('max_bytes', 4096), allowed_suffixes={'.jdx'})

    def denied(self, source):
        with self.assertRaises(AssetAccessError) as error:
            self.read(source)
        self.assertEqual(str(error.exception), 'Local asset is unavailable or not permitted.')

    def test_preserves_relative_and_absolute_scientific_bytes(self):
        for source in [self.asset, 'data/spectra/sample.jdx']:
            self.assertEqual(self.read(source), self.asset.read_bytes())

    def test_private_files_and_prefix_siblings_denied(self):
        sibling = self.project / 'data' / 'spectra-private'
        sibling.mkdir()
        (sibling / 'copy.jdx').write_bytes(self.secret.read_bytes())
        for source in [self.secret, 'private.jdx', sibling / 'copy.jdx']:
            self.denied(source)

    def test_traversal_absolute_windows_encoded_and_remote_denied(self):
        for source in ['data/spectra/../../private.jdx', '/etc/passwd',
                       'C:\\private.jdx', '\\\\host\\share\\x.jdx',
                       'data/spectra/%2e%2e/private.jdx', 'file:///private.jdx',
                       'https://test.invalid/x.jdx', 'storage://spectra/x.jdx',
                       'data/spectra/sample.jdx\x00', '', None]:
            with self.subTest(source=source):
                self.denied(source)

    def test_hidden_configuration_and_disallowed_suffix_denied(self):
        for name in ['.secrets.jdx', 'secrets.toml', 'nmr.db', 'app.py']:
            target = self.root / name
            target.write_bytes(b'SYNTHETIC-PRIVATE-MARKER')
            self.denied(target)

    def test_leaf_symlink_and_hardlink_denied(self):
        link = self.root / 'link.jdx'
        link.symlink_to(self.secret)
        self.denied(link)
        link.unlink()
        os.link(self.secret, link)
        self.denied(link)

    def test_directory_symlink_and_root_symlink_denied(self):
        link = self.root / 'escape'
        link.symlink_to(self.project, target_is_directory=True)
        self.denied(link / 'private.jdx')
        alias = self.project / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(AssetAccessError):
            read_local_asset(alias / 'sample.jdx', project=self.project, roots=[alias],
                             max_bytes=4096, allowed_suffixes={'.jdx'})

    def test_file_swap_to_symlink_at_open_denied(self):
        real_open = os.open
        def swap(path, flags, **kwargs):
            if path == 'sample.jdx':
                self.asset.unlink()
                self.asset.symlink_to(self.secret)
            return real_open(path, flags, **kwargs)
        # Preserve platform support declaration for the patched function.
        with patch('os.open', swap), patch('os.supports_dir_fd', {swap}):
            self.denied(self.asset)

    def test_fifo_directory_missing_and_size_limit_denied(self):
        fifo = self.root / 'pipe.jdx'
        os.mkfifo(fifo)
        folder = self.root / 'directory.jdx'
        folder.mkdir()
        for target in [fifo, folder, self.root / 'absent.jdx']:
            self.denied(target)
        with self.assertRaises(AssetAccessError):
            self.read(self.asset, max_bytes=1)
        self.assertEqual(self.read(self.asset, max_bytes=self.asset.stat().st_size), self.asset.read_bytes())

    def test_replacement_is_not_served_from_stale_cache(self):
        self.assertNotEqual(self.read(self.asset), b'updated')
        self.asset.write_bytes(b'updated')
        self.assertEqual(self.read(self.asset), b'updated')


if __name__ == '__main__':
    unittest.main()
