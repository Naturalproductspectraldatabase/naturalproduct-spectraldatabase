"""Synthetic WAL backup regression: never touches NPDB data or production."""
from pathlib import Path
import sqlite3
import tempfile
import unittest
from contextlib import closing
import ast
import sys

APP = Path(__file__).resolve().parents[1] / "scripts" / "app.py"
sys.path.insert(0, str(APP.parent))
from npdb_sqlite_snapshot import verified_sqlite_snapshot_bytes, SQLiteSnapshotError


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.db = Path(self.t.name) / "fake.db"

    def test_committed_wal_is_preserved(self):
        with closing(sqlite3.connect(self.db)) as writer:
            self.assertEqual(writer.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
            writer.execute("PRAGMA wal_autocheckpoint=0")
            writer.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, data TEXT)")
            writer.commit()
            writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            writer.execute("INSERT INTO sample VALUES (1, 'synthetic')")
            writer.commit()
            raw = self.db.read_bytes()
            payload = verified_sqlite_snapshot_bytes(self.db)
            self.assertEqual(self.db.read_bytes(), raw)
            self.assertNotEqual(raw, payload)
            with closing(sqlite3.connect(":memory:")) as restored:
                restored.deserialize(payload)
                self.assertEqual(restored.execute("SELECT data FROM sample").fetchone(), ("synthetic",))
                self.assertEqual(restored.execute("PRAGMA integrity_check").fetchone(), ("ok",))

    def test_plain_database_restore(self):
        with closing(sqlite3.connect(self.db)) as con:
            con.execute("CREATE TABLE t (x INTEGER)")
            con.execute("INSERT INTO t VALUES (7)")
            con.commit()
        payload = verified_sqlite_snapshot_bytes(self.db)
        with closing(sqlite3.connect(":memory:")) as restored:
            restored.deserialize(payload)
            self.assertEqual(restored.execute("SELECT x FROM t").fetchone()[0], 7)

    def test_missing_source_denied(self):
        with self.assertRaises(SQLiteSnapshotError):
            verified_sqlite_snapshot_bytes(self.db)

    def test_symlink_denied(self):
        with closing(sqlite3.connect(self.db)) as con:
            con.execute("CREATE TABLE t (x INTEGER)")
            con.commit()
        link = Path(self.t.name) / "link.db"
        link.symlink_to(self.db)
        with self.assertRaises(SQLiteSnapshotError):
            verified_sqlite_snapshot_bytes(link)

    def test_invalid_bytes_denied(self):
        self.db.write_bytes(b"not sqlite")
        with self.assertRaises(SQLiteSnapshotError):
            verified_sqlite_snapshot_bytes(self.db)

    def test_size_limit_denied(self):
        with closing(sqlite3.connect(self.db)) as con:
            con.execute("CREATE TABLE t (x INTEGER)")
            con.commit()
        with self.assertRaises(SQLiteSnapshotError):
            verified_sqlite_snapshot_bytes(self.db, max_bytes=100)
        with self.assertRaises(SQLiteSnapshotError):
            verified_sqlite_snapshot_bytes(self.db, max_bytes=0)


    def test_real_app_backup_boundary_checks_owner_and_reads_wal(self):
        # Extract the actual production function, without importing Streamlit
        # or touching credentials, services or private NPDB data.
        tree = ast.parse(APP.read_text(encoding="utf-8"), filename=str(APP))
        function = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "get_backup_bytes"][-1]
        seen = []
        def require(action):
            seen.append(action)
            if self.role != "owner":
                raise PermissionError("Denied by synthetic role gate")
        with closing(sqlite3.connect(self.db)) as writer:
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute("PRAGMA wal_autocheckpoint=0")
            writer.execute("CREATE TABLE sample (v INTEGER)")
            writer.commit()
            writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            writer.execute("INSERT INTO sample VALUES (42)")
            writer.commit()
            namespace = {"DB_PATH": self.db, "require_backend_permission": require,
                         "verified_sqlite_snapshot_bytes": verified_sqlite_snapshot_bytes}
            exec(compile(ast.Module(body=[function], type_ignores=[]), str(APP), "exec"), namespace)
            self.role = "viewer"
            with self.assertRaises(PermissionError):
                namespace["get_backup_bytes"]()
            self.role = "owner"
            snapshot = namespace["get_backup_bytes"]()
            self.assertEqual(seen, ["admin", "admin"])
            with closing(sqlite3.connect(":memory:")) as restored:
                restored.deserialize(snapshot)
                self.assertEqual(restored.execute("SELECT v FROM sample").fetchone(), (42,))
                self.assertEqual(restored.execute("PRAGMA integrity_check").fetchone(), ("ok",))


if __name__ == "__main__":
    unittest.main()
