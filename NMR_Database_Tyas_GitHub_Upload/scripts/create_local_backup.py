from datetime import datetime
from pathlib import Path
import shutil
import sqlite3

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_DIR / "database" / "nmr.db"
BACKUP_DIR = PROJECT_DIR / "database" / "backups"
EXPORT_DIR = BACKUP_DIR / "latest_csv"
TABLES = ["compounds", "proton_nmr", "carbon_nmr", "spectra_files"]


def main():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_backup_path = BACKUP_DIR / f"nmr_backup_{timestamp}.db"
    shutil.copy2(DB_PATH, db_backup_path)
    print(f"database backup created: {db_backup_path}")

    conn = sqlite3.connect(DB_PATH)
    try:
        for table_name in TABLES:
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            csv_path = EXPORT_DIR / f"{table_name}.csv"
            df.to_csv(csv_path, index=False)
            print(f"csv export updated: {csv_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
