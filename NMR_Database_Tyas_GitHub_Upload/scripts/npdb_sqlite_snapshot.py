"""Consistent offline SQLite backup bytes for an owner-only local NPDB export.

SQLite's online backup API reads committed WAL contents that Path.read_bytes()
misses. This module does NOT back up Supabase PostgreSQL or Storage. The caller
must enforce owner authorization and handle returned bytes as private data.
"""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile

DEFAULT_MAX_SNAPSHOT_BYTES = 256 * 1024 * 1024


class SQLiteSnapshotError(RuntimeError):
    """Export refused/invalid (no user-supplied path or data in error text)."""


def verified_sqlite_snapshot_bytes(db_path, *, max_bytes=DEFAULT_MAX_SNAPSHOT_BYTES):
    """Create an integrity-checked, standalone SQLite database from a WAL snapshot.

    Uses an exclusively owned temporary directory, SQLite's backup API, and a
    rollback-journal checkpoint on the *temporary copy*, never on the source.
    The temp copy is removed after readback; no application or Supabase writes.
    No network, secrets, or research content are printed.
    """
    if type(max_bytes) is not int or max_bytes <= 0:
        raise SQLiteSnapshotError("Invalid SQLite backup size limit.")
    source_path = Path(db_path)
    if source_path.is_symlink() or not source_path.is_file():
        raise SQLiteSnapshotError("Local SQLite source is not available.")
    try:
        with tempfile.TemporaryDirectory(prefix="npdb-sqlite-snapshot-") as td:
            output = Path(td) / "snapshot.db"
            output.touch(mode=0o600, exist_ok=False)
            with closing(sqlite3.connect(source_path.absolute().as_uri() + "?mode=ro", uri=True, timeout=10)) as source:
                source.execute("PRAGMA query_only = ON")
                with closing(sqlite3.connect(output)) as target:
                    source.backup(target, pages=128, sleep=0.05)
                    # A standalone SQLite export must not depend on -wal/-shm.
                    mode = target.execute("PRAGMA journal_mode=DELETE").fetchone()
                    if mode != ("delete",):
                        raise SQLiteSnapshotError("Could not finalize standalone SQLite snapshot.")
                    if target.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                        raise SQLiteSnapshotError("SQLite snapshot failed integrity verification.")
            if output.stat().st_size > max_bytes:
                raise SQLiteSnapshotError("SQLite snapshot exceeds the configured size limit.")
            return output.read_bytes()
    except SQLiteSnapshotError:
        raise
    except (sqlite3.Error, OSError, ValueError) as exc:
        raise SQLiteSnapshotError("SQLite snapshot could not be created safely.") from exc
