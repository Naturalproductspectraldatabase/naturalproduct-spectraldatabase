"""Read only CSV HEADER metadata from small official NP-MRD ZIP downloads.

No NPDB/Supabase access, credentials, bulk data imports or raw-record logs.
Source: https://np-mrd.org/downloads (download files may change over time).
"""
import argparse
import csv
from collections import Counter
import io
import json
from pathlib import PurePosixPath
import ssl
import urllib.request
from urllib.parse import urlparse
import zipfile

SOURCE_URLS = {
    "experimental_assignments": "https://np-mrd.org/system/downloads/current/assignment_tables.zip",
    "unassigned_peak_lists": "https://np-mrd.org/system/downloads/current/peak_lists.zip",
}

MAX_ZIP_BYTES = 2_000_000
MAX_UNCOMPRESSED_BYTES = 250_000_000
MAX_MEMBERS = 40_000
MAX_FIELDS = 100


def zip_schema_report(payload: bytes) -> dict:
    """Returns structural metadata only. Never returns raw record rows."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as exc:
        raise ValueError("downloaded content is not a ZIP archive") from exc

    with archive:
        infos = [x for x in archive.infolist() if not x.is_dir()]
        if len(infos) > MAX_MEMBERS:
            raise ValueError("ZIP has too many files")
        if sum(x.file_size for x in infos) > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("ZIP exceeds safe decompressed size")
        formats = Counter()
        csv_headers = []
        text_field_labels = Counter()
        for info in infos:
            suffix = PurePosixPath(info.filename).suffix.lower() or "(none)"
            formats[suffix] += 1
            if suffix == ".txt" and len(text_field_labels) < 80:
                # TXT archive members are data records. Inspect keys only;
                # NEVER print raw shifts, filenames, data rows, or compounds.
                import re
                with archive.open(info) as txt:
                    for _ in range(20):
                        line = txt.readline(4096).decode("utf-8", errors="ignore")
                        if not line:
                            break
                        m = re.match(r"^([A-Za-z][A-Za-z _-]{1,48})\s*[:=]", line)
                        if m:
                            text_field_labels[m.group(1).strip()] += 1
            if suffix != ".csv":
                continue
            with archive.open(info) as raw:
                # The first line suffices to determine the CSV field names.
                line = raw.readline(65537)
                if len(line) > 65536:
                    raise ValueError("CSV header too long")
                try:
                    header = line.decode("utf-8-sig").strip("\r\n")
                except UnicodeDecodeError:
                    header = line.decode("latin-1").strip("\r\n")
                fields = next(csv.reader([header]), [])
                if len(fields) > MAX_FIELDS:
                    raise ValueError("unexpectedly many CSV columns")
                # Restrict to standard field names, to avoid accidental data in
                # logs from a malformed CSV whose first row is actual content.
                names = []
                for field in fields:
                    val = field.strip()
                    if len(val) > 90 or not val or not all(c.isalnum() or c in "_ -()./[]" for c in val):
                        raise ValueError("non-schema-looking CSV header; not printing it")
                    names.append(val)
                csv_headers.append(names)
        return {
            "files_total": len(infos),
            "file_extensions": dict(sorted(formats.items())),
            "csv_files": len(csv_headers),
            "txt_field_labels": dict(text_field_labels.most_common(40)),
            "unique_csv_headers": [
                list(v) for v in sorted({tuple(v) for v in csv_headers})
            ],
        }


def fetch_and_probe(url: str):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "np-mrd.org":
        raise ValueError("only the official secure NP-MRD host is permitted")
    request = urllib.request.Request(url, headers={"User-Agent": "NPDB-Schema-Review/1.0 (scientific QA; no bulk storage)"})
    with urllib.request.urlopen(request, timeout=45, context=ssl.create_default_context()) as reply:
        final = urlparse(reply.geturl())
        if final.scheme != "https" or final.hostname not in ("np-mrd.org", "www.np-mrd.org"):
            raise ValueError("unexpected external redirect")
        blob = reply.read(MAX_ZIP_BYTES + 1)
    if len(blob) > MAX_ZIP_BYTES:
        raise ValueError("source ZIP larger than permitted probe limit")
    return zip_schema_report(blob)


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--probe", action="store_true", help="perform two small official HTTPS downloads")
    args = cli.parse_args()
    if not args.probe:
        print("Use --probe on an isolated GitHub runner to inspect *headers*, not contents.")
        return
    for label, url in SOURCE_URLS.items():
        try:
            report = fetch_and_probe(url)
            print(json.dumps({"dataset": label, **report}, sort_keys=True))
        except Exception as exc:
            # No URL query, path, raw CSV line, or retrieved sample content in logs.
            known = {
                "ZIP has too many files",
                "ZIP exceeds safe decompressed size",
                "non-schema-looking CSV header; not printing it",
                "downloaded content is not a ZIP archive",
                "source ZIP larger than permitted probe limit",
            }
            message = str(exc) if isinstance(exc, ValueError) and str(exc) in known else type(exc).__name__
            print(json.dumps({"dataset": label, "status": "unable_to_inspect",
                              "safe_reason": message}, sort_keys=True))


if __name__ == "__main__":
    main()
