"""Synthetic-only tests for the offline NPDB database+Storage backup verifier."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from npdb_backup_verify import verify_backup, main


class BackupIntegrityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="npdb-backup-synthetic-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "backup"
        self.root.mkdir()
        self.manifest_path = Path(tmp.name) / "private-manifest.json"
        self.db_schema = self.create("database/schema.sql", b"-- SYNTHETIC schema export\nCREATE TABLE compounds (id int);\n")
        self.db_data = self.create("database/data.sql", b"COPY compounds (id) FROM stdin;\n42\n\\.\n")
        self.structure = self.create("storage/structures/example/test.png", b"FAKE-PNG-SYNTHETIC-ONLY")
        self.spectrum = self.create("storage/spectra/example/spectrum.txt", b"1H NMR FAKE DATA 1.20 3.45")
        self.manifest = {
            "version": 1,
            "database_files": [
                self.entry("schema.sql", self.db_schema),
                self.entry("data.sql", self.db_data),
            ],
            "storage_buckets": [
                {"name": "structures", "expected_objects": 1,
                 "objects": [self.entry("example/test.png", self.structure)]},
                {"name": "spectra", "expected_objects": 1,
                 "objects": [self.entry("example/spectrum.txt", self.spectrum)]},
            ]
        }
        self.save()

    def create(self, filename, content):
        path = self.root / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    @staticmethod
    def entry(filename, path):
        data = path.read_bytes()
        return {"path": filename, "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest()}

    def save(self):
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def verify(self):
        self.save()
        return verify_backup(self.root, self.manifest_path)

    def test_valid_database_and_storage_inventory(self):
        result = self.verify()
        self.assertEqual(result["database_files"], 2)
        self.assertEqual(result["storage_objects"], {"structures": 1, "spectra": 1})
        self.assertGreater(result["verified_bytes"], 0)

    def test_cli_reports_success_without_printing_manifest_paths(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            status = main([str(self.root), str(self.manifest_path)])
        self.assertEqual(status, 0)
        self.assertIn("not a database restore test", stdout.getvalue())
        self.assertNotIn(str(self.root), stdout.getvalue())

    def test_modified_spectra_bytes_fail(self):
        self.spectrum.write_bytes(b"1H NMR FAKE DATA 1.20 3.46")
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            self.verify()

    def test_truncated_sql_dump_fails(self):
        self.db_data.write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "size mismatch"):
            self.verify()

    def test_absent_storage_object_fails(self):
        self.structure.unlink()
        with self.assertRaisesRegex(ValueError, "missing or non-file"):
            self.verify()

    def test_absent_storage_bucket_fails(self):
        self.manifest["storage_buckets"] = self.manifest["storage_buckets"][:1]
        with self.assertRaisesRegex(ValueError, "required buckets missing"):
            self.verify()

    def test_wrong_source_inventory_count_fails(self):
        self.manifest["storage_buckets"][0]["expected_objects"] = 2
        with self.assertRaisesRegex(ValueError, "object count differs"):
            self.verify()

    def test_untracked_extra_spectrum_fails(self):
        self.create("storage/spectra/example/hidden.bin", b"EXTRA")
        with self.assertRaisesRegex(ValueError, "untracked Storage object"):
            self.verify()

    def test_untracked_extra_sql_fails(self):
        self.create("database/secret-dump.sql", b"UNTRACKED")
        with self.assertRaisesRegex(ValueError, "untracked backup file"):
            self.verify()

    def test_duplicate_entries_fail(self):
        self.manifest["database_files"].append(self.manifest["database_files"][0].copy())
        with self.assertRaisesRegex(ValueError, "duplicate path"):
            self.verify()

    def test_path_traversal_fails(self):
        self.manifest["database_files"][0]["path"] = "../schema.sql"
        with self.assertRaisesRegex(ValueError, "traversal"):
            self.verify()

    def test_absolute_path_fails(self):
        self.manifest["database_files"][0]["path"] = str(self.db_schema)
        with self.assertRaisesRegex(ValueError, "traversal"):
            self.verify()

    def test_symlink_object_fails(self):
        target = self.create("storage/structures/example/real.png", b"REAL")
        self.structure.unlink()
        try:
            self.structure.symlink_to(target)
        except OSError:
            self.skipTest("filesystem does not allow symlinks")
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.verify()

    def test_invalid_negative_or_boolean_size_fails(self):
        for size in (-1, True, 0):
            self.manifest["database_files"][0]["size"] = size
            with self.subTest(size=size), self.assertRaisesRegex(ValueError, "positive integer"):
                self.verify()
        self.manifest["database_files"][0] = self.entry("schema.sql", self.db_schema)

    def test_invalid_checksum_fails(self):
        self.manifest["database_files"][0]["sha256"] = "12345"
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.verify()

    def test_no_real_data_or_network_modules_required(self):
        source = (SCRIPTS / "npdb_backup_verify.py").read_text(encoding="utf-8")
        self.assertNotIn("supabase_client", source)
        self.assertNotIn("requests.get(", source)
        self.assertNotIn("urllib.request", source)


if __name__ == "__main__":
    unittest.main()
