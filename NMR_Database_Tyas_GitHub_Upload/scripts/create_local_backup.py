from datetime import datetime
import json
from pathlib import Path
import shutil
import sqlite3
import zipfile

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_DIR / "database" / "nmr.db"
BACKUP_DIR = PROJECT_DIR / "database" / "backups"
EXPORT_DIR = BACKUP_DIR / "latest_csv"
TABLES = ["compounds", "proton_nmr", "carbon_nmr", "spectra_files", "bioactivity_records"]


def main():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_backup_path = BACKUP_DIR / f"nmr_backup_{timestamp}.db"
    shutil.copy2(DB_PATH, db_backup_path)
    print(f"database backup created: {db_backup_path}")

    manifest = {
        "project": "npdb",
        "created_at_local": datetime.now().isoformat(timespec="seconds"),
        "database_backup": str(db_backup_path),
        "tables": {},
    }

    conn = sqlite3.connect(DB_PATH)
    try:
        for table_name in TABLES:
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            csv_path = EXPORT_DIR / f"{table_name}.csv"
            df.to_csv(csv_path, index=False)
            manifest["tables"][table_name] = {
                "rows": int(len(df)),
                "csv": str(csv_path),
            }
            print(f"csv export updated: {csv_path}")
    finally:
        conn.close()

    manifest_path = BACKUP_DIR / f"manifest_{timestamp}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    archive_path = BACKUP_DIR / f"npdb_local_snapshot_{timestamp}.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(db_backup_path, arcname=f"database/{db_backup_path.name}")
        archive.write(manifest_path, arcname="manifest.json")
        for table_name in TABLES:
            csv_path = EXPORT_DIR / f"{table_name}.csv"
            archive.write(csv_path, arcname=f"tables/{csv_path.name}")
    print(f"snapshot archive created: {archive_path}")


if __name__ == "__main__":
    main()
