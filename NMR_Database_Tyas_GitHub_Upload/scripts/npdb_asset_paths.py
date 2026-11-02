"""Bounded local scientific-asset reads; never use returned paths for later opens.

Trusted configuration supplies project/root paths; record metadata supplies only
source. Remote references are deliberately not handled here. Linux dirfd walking
with O_NOFOLLOW closes validation/open symlink races. Unsupported systems fail
closed. Asset directories must not be writable by untrusted OS users.
"""
import os
from pathlib import Path, PureWindowsPath
import stat


class AssetAccessError(ValueError):
    """Public error deliberately contains neither source paths nor OS details."""


def _deny():
    raise AssetAccessError("Local asset is unavailable or not permitted.") from None


def _candidate(source, project, roots):
    if not isinstance(source, (str, Path)):
        _deny()
    text = str(source)
    # Do not decode/normalize ambiguous record values into another filename.
    if (not text or text != text.strip() or any(ord(c) < 32 for c in text)
            or "\\" in text or ":" in text or "%" in text
            or PureWindowsPath(text).drive):
        _deny()
    value = Path(text)
    if any(p in ("..",) or p.startswith(".") for p in value.parts if p != "/"):
        _deny()
    project = Path(project).absolute()
    candidate = value if value.is_absolute() else project / value
    for root in roots:
        root = Path(root).absolute()
        try:
            relative = candidate.relative_to(root)
        except ValueError:
            continue
        if relative.parts:
            return root, relative
    _deny()


def read_local_asset(source, *, project, roots, max_bytes, allowed_suffixes):
    """Read a regular, single-link asset under explicit trusted roots.

    Allow contained absolute legacy paths and project-relative asset paths.
    Reject ALL symlinks (including within roots), hardlinks, hidden components,
    remote/encoded references, devices, FIFOs and oversized data. The caller
    must select suffixes for its context and validate media bytes before inline
    rendering; a suffix is not proof of MIME type or scientific identity.
    No metadata is rewritten, no cache is used, and no filesystem is mutated.
    """
    if type(max_bytes) is not int or max_bytes < 1 or not allowed_suffixes:
        _deny()
    if not hasattr(os, "O_NOFOLLOW") or os.open not in os.supports_dir_fd:
        _deny()
    descriptors = []
    try:
        root, relative = _candidate(source, project, roots)
        if relative.suffix.lower() not in {s.lower() for s in allowed_suffixes}:
            _deny()
        # Walk from filesystem root as well: a replaced configured root must
        # not redirect reads outside containment. Every directory is pinned.
        fd = os.open(root.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(fd)
        for part in root.parts[1:] + relative.parts[:-1]:
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            descriptors.append(fd)
        fd = os.open(relative.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        descriptors.append(fd)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > max_bytes:
            _deny()
        chunks, size = [], 0
        while True:
            chunk = os.read(fd, min(65536, max_bytes + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > max_bytes:
                _deny()
        after = os.fstat(fd)
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            _deny()
        return b"".join(chunks)
    except (OSError, ValueError, TypeError):
        _deny()
    finally:
        for fd in reversed(descriptors):
            os.close(fd)
