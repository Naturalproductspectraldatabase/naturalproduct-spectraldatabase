"""Synthetic-only NPDB Storage restore rehearsal, no network or production data."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
import sys

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from npdb_backup_manifest import create_private_manifest, write_private_manifest
from npdb_storage_local_restore import restore_storage_locally


class StorageLocalRehearsalTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="npdb-synthetic-storage-restore-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.backup = self.root / "private-backup"
        self.backup.mkdir()
        self.manifest_path = self.root / "PRIVATE-MANIFEST.json"
        self.restored = self.root / "new-restore"
        self.add_file("database/schema.sql", b"-- fake schema for CI\n")
        self.add_file("database/data.sql", b"-- fake COPY data for CI\n")
        self.add_file("storage/structures/synthetic/A.png", b"FAKE 2D STRUCTURE IMAGE")
        self.add_file("storage/spectra/demo/B.dx", b"FAKE 1H NMR JCAMP")
        info = create_private_manifest(self.backup, {"structures": 1, "spectra": 1})
        write_private_manifest(self.manifest_path, info, self.backup)

    def add_file(self, path, data):
        dest = self.backup / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    def test_restored_binary_bytes_and_hierarchies_match(self):
        result = restore_storage_locally(self.backup, self.manifest_path, self.restored)
        self.assertEqual(result["buckets"], {"spectra": 1, "structures": 1})
        self.assertEqual(result["restored_objects"], 2)
        for path in ("structures/synthetic/A.png", "spectra/demo/B.dx"):
            original = (self.backup / "storage" / path).read_bytes()
            copy = (self.restored / "storage" / path).read_bytes()
            self.assertEqual(hashlib.sha256(original).digest(), hashlib.sha256(copy).digest())
            self.assertEqual(original, copy)
        self.assertFalse((self.restored / "database").exists(), "PostgreSQL restore is separate")

    def test_corrupt_source_fails_before_creating_restore_directory(self):
        (self.backup / "storage/spectra/demo/B.dx").write_bytes(b"CORRUPT")
        with self.assertRaisesRegex(ValueError, "mismatch"):
            restore_storage_locally(self.backup, self.manifest_path, self.restored)
        self.assertFalse(self.restored.exists())

    def test_missing_source_fails_before_copy(self):
        (self.backup / "storage/structures/synthetic/A.png").unlink()
        with self.assertRaisesRegex(ValueError, "missing"):
            restore_storage_locally(self.backup, self.manifest_path, self.restored)
        self.assertFalse(self.restored.exists())

    def test_existing_restore_target_is_not_overwritten(self):
        self.restored.mkdir()
        (self.restored / "private.txt").write_text("KEEP")
        with self.assertRaisesRegex(ValueError, "already exists"):
            restore_storage_locally(self.backup, self.manifest_path, self.restored)
        self.assertEqual((self.restored / "private.txt").read_text(), "KEEP")

    def test_cannot_copy_into_backup_source_or_git_tree(self):
        with self.assertRaisesRegex(ValueError, "overlaps backup source"):
            restore_storage_locally(self.backup, self.manifest_path,
                                    self.backup / "inside")
        repo = self.root / "repository"
        (repo / ".git").mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "Git repository"):
            restore_storage_locally(self.backup, self.manifest_path,
                                    repo / "restore")

    def test_traversal_in_manifest_never_creates_destination(self):
        data = json.loads(self.manifest_path.read_text())
        data["storage_buckets"][0]["objects"][0]["path"] = "../../outside.txt"
        self.manifest_path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "traversal"):
            restore_storage_locally(self.backup, self.manifest_path, self.restored)
        self.assertFalse(self.restored.exists())

    def test_no_cloud_network_or_private_secrets_in_source(self):
        source = (SCRIPTS / "npdb_storage_local_restore.py").read_text()
        self.assertNotIn("supabase.create_client", source)
        self.assertNotIn("requests.", source)
        self.assertNotIn("urllib.request", source)

    @unittest.skipUnless(os.name == "posix", "Unix permission test")
    def test_restored_files_are_private(self):
        restore_storage_locally(self.backup, self.manifest_path, self.restored)
        path = self.restored / "storage/structures/synthetic/A.png"
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
