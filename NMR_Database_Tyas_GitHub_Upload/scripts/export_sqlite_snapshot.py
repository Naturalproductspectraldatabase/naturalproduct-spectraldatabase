import sqlite3
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_DIR / "database" / "nmr.db"
EXPORT_DIR = PROJECT_DIR / "data" / "exports" / "supabase_snapshot"

TABLES = [
    "compounds",
    "proton_nmr",
    "carbon_nmr",
    "spectra_files",
    "bioactivity_records",
]


def main():
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        for table in TABLES:
            df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
            out = EXPORT_DIR / f"{table}.csv"
            df.to_csv(out, index=False)
            print(f"exported {table}: {out}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
