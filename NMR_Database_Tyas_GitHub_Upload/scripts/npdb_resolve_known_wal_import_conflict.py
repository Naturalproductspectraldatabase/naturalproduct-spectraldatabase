"""CI-only exact import-union resolver for #38 asset + #42 WAL local backup.

No network, no production, no generic conflict resolution. Abort on any other hunk.
"""
from pathlib import Path
import re

file = Path("NMR_Database_Tyas_GitHub_Upload/scripts/app.py")
text = file.read_text(encoding="utf-8")
pattern = re.compile(r"(?m)^<<<<<<< HEAD\n(.*?)^=======\n(.*?)^>>>>>>> [0-9a-f]+\n", re.S)
matches = list(pattern.finditer(text))
if len(matches) != 1:
    raise SystemExit("Unexpected WAL conflict count; manual review required.")
ours = matches[0].group(1).strip()
theirs = matches[0].group(2).strip()
asset = "from npdb_asset_paths import AssetAccessError, read_local_asset, validate_asset_content, write_local_asset, validate_https_asset_url, read_https_asset"
wal = "from npdb_sqlite_snapshot import verified_sqlite_snapshot_bytes"
if ours != asset or theirs != wal:
    raise SystemExit("Unexpected WAL conflict content; manual review required.")
new = text[:matches[0].start()] + asset + "\n" + wal + "\n" + text[matches[0].end():]
if "return verified_sqlite_snapshot_bytes(DB_PATH)" not in new:
    raise SystemExit("Integrated owner SQLite snapshot call missing.")
if "def read_scientific_asset(" not in new or "def redact_private_gps_for_current_user(" not in new:
    raise SystemExit("Asset or viewer privacy functionality missing.")
if any(tag in new for tag in ("<<<<<<< ", ">>>>>>> ", "\n=======\n")):
    raise SystemExit("Conflict markers remain.")
file.write_text(new, encoding="utf-8")
print("Resolved exact #38/#42 import overlap; both scientific asset and WAL safety retained.")
