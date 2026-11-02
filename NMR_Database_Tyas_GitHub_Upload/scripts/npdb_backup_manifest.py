"""Create a PRIVATE SHA-256 manifest from a completed LOCAL NPDB backup.

This is a file inventory helper, not an exporter or restore test. Supply
independently observed Supabase bucket object counts using --bucket.
The generated private manifest must stay outside any Git repository.

Run on a trusted offline computer after completing SQL + Storage exports.
"""
import argparse
import json
import os
from pathlib import Path
import sys

from npdb_backup_verify import _file_hash, verify_backup


def _files_in(root: Path):
    if not root.is_dir() or root.is_symlink():
        raise ValueError("backup source folder missing or symbolic link")
    entries = []
    for current, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            if Path(current, name).is_symlink():
                raise ValueError("symbolic links forbidden inside backup")
        for name in files:
            path = Path(current, name)
            if not path.is_file() or path.stat().st_size <= 0:
                raise ValueError("backup contains invalid or zero-byte file")
            entries.append({
                "path": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": _file_hash(path),
            })
    return sorted(entries, key=lambda value: value["path"])


def create_private_manifest(root: Path, bucket_counts: dict,
                            required_database=("schema.sql", "data.sql")) -> dict:
    root = root.resolve()
    if not root.is_dir() or not bucket_counts:
        raise ValueError("backup directory or bucket counts unavailable")
    if not {"structures", "spectra"}.issubset(bucket_counts):
        raise ValueError("both structures and spectra buckets are mandatory")
    if any(type(count) is not int or count < 0 for count in bucket_counts.values()):
        raise ValueError("source bucket counts must be nonnegative integers")

    db = _files_in(root / "database")
    names = {e["path"] for e in db}
    missing = set(required_database) - names
    if missing:
        raise ValueError("a required logical export file was not found")

    storage = root / "storage"
    if not storage.is_dir() or storage.is_symlink():
        raise ValueError("Storage backup directory missing or symbolic link")
    discovered = {x.name for x in storage.iterdir() if x.is_dir() and not x.is_symlink()}
    if discovered != set(bucket_counts):
        raise ValueError("Storage bucket directories differ from source inventory")

    buckets = []
    for name, count in sorted(bucket_counts.items()):
        if not name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in name):
            raise ValueError("invalid bucket name")
        objects = _files_in(storage / name)
        if len(objects) != count:
            raise ValueError("downloaded object count differs from source inventory")
        buckets.append({"name": name, "expected_objects": count, "objects": objects})
    return {"version": 1, "database_files": db, "storage_buckets": buckets}


def _inside_git_tree(path: Path) -> bool:
    return any((parent / ".git").exists() for parent in (path, *path.parents))


def write_private_manifest(output: Path, data: dict, backup_root: Path):
    output = output.expanduser().absolute()
    if output.is_relative_to(backup_root.resolve()) or _inside_git_tree(output.parent):
        raise ValueError("private manifest must be stored outside backup root and Git working trees")
    if not output.parent.is_dir():
        raise ValueError("private manifest parent directory does not exist")
    # Exclusive creation; never overwrite an earlier manifest accidentally.
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    fd = os.open(output, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except BaseException:
        output.unlink(missing_ok=True)
        raise


def main(argv=None):
    cli = argparse.ArgumentParser(description="Build private, offline NPDB backup manifest")
    cli.add_argument("backup_root", type=Path)
    cli.add_argument("output_manifest", type=Path)
    cli.add_argument("--bucket", action="append", required=True, metavar="BUCKET=EXPECTED_COUNT")
    cli.add_argument("--require-db", action="append", default=None, metavar="FILE")
    args = cli.parse_args(argv)
    counts = {}
    try:
        for item in args.bucket:
            name, sep, raw_count = item.partition("=")
            if not sep or name in counts:
                raise ValueError("invalid or duplicate --bucket")
            counts[name] = int(raw_count)
        required = tuple(args.require_db) if args.require_db is not None else ("schema.sql", "data.sql")
        manifest = create_private_manifest(args.backup_root, counts, required)
        write_private_manifest(args.output_manifest, manifest, args.backup_root)
        verify_backup(args.backup_root, args.output_manifest)
    except (OSError, ValueError) as exc:
        # Do not leak filenames from private backups into terminal history/logs.
        print(f"PRIVATE BACKUP MANIFEST FAILED ({type(exc).__name__})", file=sys.stderr)
        return 1
    print("PRIVATE MANIFEST WRITTEN AND LOCAL FILE HASHES VERIFIED")
    print("This does not prove source completeness or restore success.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
