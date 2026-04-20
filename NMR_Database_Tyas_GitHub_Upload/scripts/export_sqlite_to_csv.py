from pathlib import Path
import sqlite3

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_DIR / "database" / "nmr.db"
EXPORT_DIR = PROJECT_DIR / "data" / "exports" / "supabase_import"
TABLES = ["compounds", "proton_nmr", "carbon_nmr", "spectra_files"]


def main():
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        for table_name in TABLES:
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            output_path = EXPORT_DIR / f"{table_name}.csv"
            df.to_csv(output_path, index=False)
            print(f"exported {table_name}: {output_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
