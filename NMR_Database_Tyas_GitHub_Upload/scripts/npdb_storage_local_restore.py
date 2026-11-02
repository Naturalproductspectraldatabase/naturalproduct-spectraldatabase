"""Restore PRIVATE NPDB Storage backup bytes to a *new local directory*.

No Supabase APIs, uploads, cloud writes, production credentials or URL access.
Requires an existing verified private backup manifest and creates a separate
local copy for readback validation. This is NOT a Supabase Storage restore.
Do not commit restored files or manifests. Use only on a trusted computer.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from npdb_backup_verify import (
    _checked_entry,
    _file_hash,
    _read_inventory,
    _verify_path,
    verify_backup,
)


def _is_inside_git_worktree(path: Path) -> bool:
    return any((p / ".git").exists() for p in (path, *path.parents))


def restore_storage_locally(backup_root: Path, manifest_path: Path, restored_root: Path):
    """Verify input; atomically copy all Storage objects; independently hash output.

    The original database files are NOT copied here: their PostgreSQL restore
    must be handled separately. The target must be new and private.
    """
    source = backup_root.resolve(strict=True)
    dest = restored_root.expanduser().absolute()
    if dest.exists() or dest.is_symlink():
        raise ValueError("local restore target already exists")
    if not dest.parent.is_dir() or dest.parent.is_symlink():
        raise ValueError("local restore parent must exist and not be a symlink")
    if dest.is_relative_to(source) or source.is_relative_to(dest):
        raise ValueError("local restore target overlaps backup source")
    if _is_inside_git_worktree(dest.parent):
        raise ValueError("local restore target cannot be inside a Git repository")

    # Fail closed before writing even one byte if the source is inconsistent.
    verify_backup(source, manifest_path)
    _, buckets = _read_inventory(manifest_path)
    result = {"buckets": {}, "restored_objects": 0, "restored_bytes": 0}

    with tempfile.TemporaryDirectory(prefix=".npdb-storage-restore-", dir=dest.parent) as workdir:
        staging = Path(workdir)
        for bucket in buckets:
            name = bucket["name"]
            source_bucket = source / "storage" / name
            target_bucket = staging / "storage" / name
            target_bucket.mkdir(parents=True, exist_ok=False)
            count = 0
            for item in bucket["objects"]:
                relative, expected_size, expected_sha = _checked_entry(item)
                original = _verify_path(source_bucket, relative)
                candidate = _verify_path(target_bucket, relative)
                candidate.parent.mkdir(parents=True, exist_ok=True)
                # Mode is private by default, not derived from public source flags.
                with original.open("rb") as input_file, candidate.open("xb") as output_file:
                    os.chmod(candidate, 0o600)
                    shutil.copyfileobj(input_file, output_file, length=1024 * 1024)
                if candidate.stat().st_size != expected_size or _file_hash(candidate) != expected_sha:
                    raise ValueError("restored object does not match private manifest")
                count += 1
                result["restored_bytes"] += expected_size
                result["restored_objects"] += 1
            result["buckets"][name] = count
        if dest.exists() or dest.is_symlink():
            raise ValueError("local restore target appeared during operation")
        # The temporary directory resides beside the final target, so this is
        # an atomic local filesystem rename rather than a partial copy.
        os.rename(staging, dest)

    return result


def main(argv=None):
    p = argparse.ArgumentParser(description="Local-only NPDB Storage copy + checksum readback")
    p.add_argument("backup_root", type=Path)
    p.add_argument("private_manifest", type=Path)
    p.add_argument("new_local_restore_directory", type=Path)
    args = p.parse_args(argv)
    try:
        summary = restore_storage_locally(
            args.backup_root, args.private_manifest, args.new_local_restore_directory
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        # Never echo private object names, paths, hashes or exception details.
        print(f"LOCAL STORAGE REHEARSAL FAILED: {type(exc).__name__}", file=sys.stderr)
        return 1
    print("LOCAL STORAGE COPY + HASH READBACK PASSED; NOT A LIVE STORAGE RESTORE.")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
