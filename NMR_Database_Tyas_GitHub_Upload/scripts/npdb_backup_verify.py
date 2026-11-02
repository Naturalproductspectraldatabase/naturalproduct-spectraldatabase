"""Verify a *private* NPDB backup against a locally prepared manifest.

Does NOT access NPDB production, create a backup, or prove PostgreSQL restore.
Run in a trusted offline environment. Never commit real manifests or backups.

Layout:
  backup-root/
    database/schema.sql
    database/data.sql
    storage/structures/<object path>
    storage/spectra/<object path>
  private-manifest.json  # may be outside backup-root

Manifest structure:
{
 "version": 1,
 "database_files": [{"path": "schema.sql", "size": 123, "sha256": "..."}],
 "storage_buckets": [
   {"name": "structures", "expected_objects": 1,
    "objects": [{"path": "a.png", "size": 321, "sha256": "..."}]}
 ]
}
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys

_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_ALLOWED_BUCKET = re.compile(r"^[A-Za-z0-9_-]+$")


def _verify_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError("path must be a nonempty, POSIX-style relative path")
    path = PurePosixPath(relative)
    if path.is_absolute() or any(part in (".", "..") for part in path.parts):
        raise ValueError("path traversal or absolute path rejected")
    # Resolve on the local machine; reject symlink escape and all symlinks,
    # so archived objects cannot be swapped out by linked files.
    current = root
    for segment in path.parts:
        current = current / segment
        if current.is_symlink():
            raise ValueError("symlink in backup path")
    resolved = current.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("backup path escapes trusted root")
    return resolved


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_inventory(manifest_path: Path):
    with manifest_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("unsupported manifest schema version")
    db = data.get("database_files")
    buckets = data.get("storage_buckets")
    if not isinstance(db, list) or not db:
        raise ValueError("database_files must list all logical export parts")
    if not isinstance(buckets, list) or not buckets:
        raise ValueError("storage_buckets must list all in-scope buckets")
    return db, buckets


def _checked_entry(entry: dict):
    if not isinstance(entry, dict):
        raise ValueError("manifest file entry must be an object")
    path = entry.get("path")
    size = entry.get("size")
    digest = entry.get("sha256")
    if not isinstance(path, str) or not path:
        raise ValueError("manifest file path missing")
    if type(size) is not int or size <= 0:
        raise ValueError("manifest file size must be positive integer")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise ValueError("manifest file checksum must be SHA-256")
    return path, size, digest.lower()


def verify_backup(root: Path, manifest_path: Path, required_buckets=("structures", "spectra")):
    """Return a summary. Raise ValueError on mismatch or incomplete inventory.

    Verifies local file bytes and complete declared inventory. Does NOT know
    whether an exported DB has consistent tables, or whether source inventory
    was complete; always perform a separate restoration test.
    """
    root = root.resolve()
    if not root.is_dir():
        raise ValueError("backup root directory does not exist")
    database, buckets = _read_inventory(manifest_path)

    seen = set()
    total_bytes = 0
    result = {"database_files": 0, "storage_objects": {}, "verified_bytes": 0}

    def verify_entry(base: Path, item):
        nonlocal total_bytes
        filename, expected_size, digest = _checked_entry(item)
        candidate = _verify_path(base, filename)
        if candidate in seen:
            raise ValueError("duplicate path in manifest")
        seen.add(candidate)
        if not candidate.is_file():
            raise ValueError("manifest refers to a missing or non-file object")
        size = candidate.stat().st_size
        if size != expected_size:
            raise ValueError("size mismatch")
        if _file_hash(candidate) != digest:
            raise ValueError("SHA-256 mismatch")
        total_bytes += size

    database_root = root / "database"
    for item in database:
        verify_entry(database_root, item)
    result["database_files"] = len(database)

    if len({str(_checked_entry(e)[0]) for e in database}) != len(database):
        raise ValueError("duplicate database names")
    # Assert no extra unrecorded files; data must not vanish silently.
    for folder in (database_root,):
        if not folder.is_dir():
            raise ValueError("declared backup folder is absent")
        for current, dirs, files in os.walk(folder, followlinks=False):
            for name in dirs + files:
                candidate = Path(current, name)
                if candidate.is_symlink():
                    raise ValueError("untracked symbolic link")
                if candidate.is_file() and candidate.resolve() not in seen:
                    raise ValueError("untracked backup file")

    seen_buckets = set()
    for b in buckets:
        if not isinstance(b, dict):
            raise ValueError("bucket entry must be an object")
        name = b.get("name")
        expected = b.get("expected_objects")
        objects = b.get("objects")
        if not isinstance(name, str) or not _ALLOWED_BUCKET.fullmatch(name):
            raise ValueError("invalid bucket name")
        if name in seen_buckets:
            raise ValueError("duplicate bucket")
        seen_buckets.add(name)
        if type(expected) is not int or expected < 0 or not isinstance(objects, list):
            raise ValueError("expected_objects must be nonnegative and objects a list")
        if len(objects) != expected:
            raise ValueError("object count differs from manifest expectation")
        bucket_root = root / "storage" / name
        if not bucket_root.is_dir():
            raise ValueError("declared bucket backup folder is missing")
        count = 0
        for item in objects:
            verify_entry(bucket_root, item)
            count += 1
        for current, dirs, files in os.walk(bucket_root, followlinks=False):
            for item in dirs + files:
                candidate = Path(current, item)
                if candidate.is_symlink():
                    raise ValueError("untracked symbolic link in bucket")
                if candidate.is_file() and candidate.resolve() not in seen:
                    raise ValueError("untracked Storage object")
        result["storage_objects"][name] = count

    missing = set(required_buckets) - seen_buckets
    if missing:
        raise ValueError("required buckets missing from manifest")
    storage_root = root / "storage"
    if not storage_root.is_dir():
        raise ValueError("Storage backup directory is missing")
    for child in storage_root.iterdir():
        if child.is_symlink() or child.name not in seen_buckets:
            raise ValueError("untracked storage bucket or symbolic link")
    result["verified_bytes"] = total_bytes
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check checksum and inventory of an OFFLINE NPDB backup")
    parser.add_argument("backup_root", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--require-bucket", action="append", default=None)
    args = parser.parse_args(argv)
    required = tuple(args.require_bucket) if args.require_bucket is not None else ("structures", "spectra")
    try:
        summary = verify_backup(args.backup_root, args.manifest, required)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        # Intentionally omit full paths, secrets and filenames from output.
        print(f"BACKUP CHECK FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print("BACKUP FILE INTEGRITY CHECK PASSED (not a database restore test)")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
