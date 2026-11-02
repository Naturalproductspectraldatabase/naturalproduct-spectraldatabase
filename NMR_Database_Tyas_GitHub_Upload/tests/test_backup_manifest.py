"""Offline manifest generation using only synthetic backup files."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from npdb_backup_manifest import create_private_manifest, write_private_manifest
from npdb_backup_verify import verify_backup


class OfflineManifestGenerationTests(unittest.TestCase):
    def setUp(self):
        context = tempfile.TemporaryDirectory(prefix="npdb-synthetic-manifest-")
        self.addCleanup(context.cleanup)
        self.root = Path(context.name) / "backup"
        self.root.mkdir()
        self.output = Path(context.name) / "PRIVATE-manifest.json"
        self.mk("database/schema.sql", b"CREATE TABLE synthetic (id INT);")
        self.mk("database/data.sql", b"INSERT INTO synthetic VALUES (42);")
        self.mk("storage/structures/2026/TEST.png", b"TEST-FAKE-IMAGE")
        self.mk("storage/spectra/2026/TEST.dx", b"TEST-FAKE-JCAMP")

    def mk(self, name, data):
        dst = self.root / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
        return dst

    @staticmethod
    def counts():
        return {"structures": 1, "spectra": 1}

    def test_generated_manifest_passes_independent_file_hash_verifier(self):
        data = create_private_manifest(self.root, self.counts())
        write_private_manifest(self.output, data, self.root)
        self.assertEqual(
            verify_backup(self.root, self.output)["storage_objects"],
            {"spectra": 1, "structures": 1},
        )
        self.assertEqual(json.loads(self.output.read_text())["database_files"][0]["path"], "data.sql")

    def test_missing_or_extra_storage_files_fails_count_gate(self):
        self.mk("storage/spectra/other.dx", b"UNEXPECTED")
        with self.assertRaisesRegex(ValueError, "downloaded object count"):
            create_private_manifest(self.root, self.counts())

    def test_required_db_dump_component_must_exist(self):
        (self.root / "database/data.sql").unlink()
        with self.assertRaisesRegex(ValueError, "required logical export"):
            create_private_manifest(self.root, self.counts())

    def test_missing_source_bucket_in_expected_counts_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "mandatory"):
            create_private_manifest(self.root, {"structures": 1})

    def test_missing_bucket_directory_not_silently_accepted(self):
        (self.root / "storage/spectra/2026/TEST.dx").unlink()
        (self.root / "storage/spectra/2026").rmdir()
        (self.root / "storage/spectra").rmdir()
        with self.assertRaisesRegex(ValueError, "directories differ"):
            create_private_manifest(self.root, self.counts())

    def test_manifest_does_not_overwrite_existing_private_copy(self):
        m = create_private_manifest(self.root, self.counts())
        write_private_manifest(self.output, m, self.root)
        with self.assertRaises(FileExistsError):
            write_private_manifest(self.output, m, self.root)

    def test_manifest_rejects_output_in_backup_or_git_tree(self):
        m = create_private_manifest(self.root, self.counts())
        with self.assertRaisesRegex(ValueError, "outside backup root"):
            write_private_manifest(self.root / "manifest.json", m, self.root)
        fake_repo = self.root.parent / "repo"
        fake_repo.mkdir()
        (fake_repo / ".git").mkdir()
        with self.assertRaisesRegex(ValueError, "outside backup root and Git"):
            write_private_manifest(fake_repo / "manifest.json", m, self.root)

    def test_empty_or_symlinked_storage_object_fails(self):
        path = self.root / "storage/structures/2026/TEST.png"
        path.write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "zero-byte"):
            create_private_manifest(self.root, self.counts())

    def test_private_manifest_file_permissions_on_posix(self):
        import os
        m = create_private_manifest(self.root, self.counts())
        write_private_manifest(self.output, m, self.root)
        if os.name == "posix":
            self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
