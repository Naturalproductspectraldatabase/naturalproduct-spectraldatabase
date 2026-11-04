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


def validate_asset_content(data, suffix):
    """Check renderable media and text; opaque scientific formats download only.

    This is a file-format guard, not verification of chemical/scientific content.
    Archives are never extracted. Text datasets are not rendered as HTML.
    """
    import io
    import warnings
    suffix = suffix.lower()
    if not data:
        _deny()
    image_formats = {'.png': 'PNG', '.jpg': 'JPEG', '.jpeg': 'JPEG',
                     '.webp': 'WEBP', '.gif': 'GIF', '.tif': 'TIFF', '.tiff': 'TIFF'}
    try:
        if suffix in image_formats:
            from PIL import Image
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as image:
                    if image.format != image_formats[suffix] or image.width * image.height > 40_000_000:
                        _deny()
                    image.verify()
        elif suffix == '.pdf':
            if not data.startswith(b'%PDF-'):
                _deny()
        elif suffix == '.zip':
            if not data.startswith((b'PK\x03\x04', b'PK\x05\x06')):
                _deny()
        elif suffix in {'.jdx', '.dx', '.jcamp', '.csv', '.tsv', '.txt'}:
            if b'\x00' in data:
                _deny()
            # Preserve legacy scientific encodings without modifying bytes.
        elif suffix not in {'.mnova', '.fid'}:
            _deny()
    except Exception:
        _deny()


def write_local_asset(data, *, root, filename):
    """Exclusively create an asset through a pinned, symlink-free directory."""
    if not isinstance(data, bytes) or not filename or Path(filename).name != filename or filename.startswith('.'):
        _deny()
    root = Path(root).absolute()
    descriptors = []
    created = None
    try:
        fd = os.open(root.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(fd)
        for part in root.parts[1:]:
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            descriptors.append(fd)
        directory_fd = fd
        for counter in range(1000):
            name = filename if not counter else f'{Path(filename).stem}_{counter}{Path(filename).suffix}'
            try:
                output = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o600, dir_fd=directory_fd)
                created = name
                break
            except FileExistsError:
                continue
        else:
            _deny()
        with os.fdopen(output, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        return root / name
    except (OSError, ValueError, TypeError):
        if created is not None:
            try:
                os.unlink(created, dir_fd=directory_fd)
            except OSError:
                pass
        _deny()
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def validate_https_asset_url(url, *, allowed_hosts=None):
    """Validate a browser URL, or an exact trusted-host server fetch URL."""
    import ipaddress
    from urllib.parse import urlsplit
    try:
        if not isinstance(url, str) or any(ord(c) < 33 for c in url) or '\\' in url:
            _deny()
        parsed = urlsplit(url)
        host = parsed.hostname
        if (parsed.scheme != 'https' or not host or parsed.username is not None
                or parsed.password is not None or parsed.port not in (None, 443)
                or host == 'localhost' or host.endswith(('.localhost', '.local'))):
            _deny()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            _deny()
        if allowed_hosts is not None and host.lower() not in {h.lower() for h in allowed_hosts if h}:
            _deny()
        return url
    except (TypeError, ValueError):
        _deny()


def read_https_asset(url, *, allowed_hosts, max_bytes):
    """Bounded TLS read with no proxy and trusted-host checks on every redirect.

    Hosts come only from server configuration and a fixed public-service list.
    Arbitrary record URLs may remain browser links; they cannot become server
    requests. No authentication headers/cookies are attached to this fetch.
    """
    import urllib.request
    if type(max_bytes) is not int or max_bytes < 1:
        _deny()
    validate_https_asset_url(url, allowed_hosts=allowed_hosts)

    class TrustedRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            validate_https_asset_url(newurl, allowed_hosts=allowed_hosts)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), TrustedRedirect())
        with opener.open(url, timeout=15) as response:
            validate_https_asset_url(response.geturl(), allowed_hosts=allowed_hosts)
            data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                _deny()
            return data
    except Exception:
        _deny()
