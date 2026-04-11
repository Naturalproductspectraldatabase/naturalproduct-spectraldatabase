import sqlite3
import os

# Menentukan lokasi folder project
folder_script = os.path.dirname(os.path.abspath(__file__))
folder_project = os.path.dirname(folder_script)

# Menentukan lokasi folder database dan file database
folder_database = os.path.join(folder_project, "database")
path_database = os.path.join(folder_database, "nmr.db")


def buat_database():
    try:
        # Pastikan folder database ada
        os.makedirs(folder_database, exist_ok=True)

        # Membuka koneksi ke database
        conn = sqlite3.connect(path_database)
        cursor = conn.cursor()

        # Aktifkan foreign key
        cursor.execute("PRAGMA foreign_keys = ON;")

        # =========================
        # 1. Tabel compounds
        # =========================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS compounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trivial_name TEXT,
                iupac_name TEXT,
                molecular_formula TEXT,
                source_material TEXT,
                sample_code TEXT,
                collection_location TEXT,
                gps_coordinates TEXT,
                depth_m REAL,
                uv_data TEXT,
                ftir_data TEXT,
                optical_rotation TEXT,
                melting_point TEXT,
                crystallization_method TEXT,
                structure_image_path TEXT,
                note TEXT
            )
        """)

        # =========================
        # 2. Tabel proton_nmr
        # =========================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS proton_nmr (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                compound_id INTEGER NOT NULL,
                delta_ppm REAL NOT NULL,
                multiplicity TEXT,
                j_value TEXT,
                proton_count TEXT,
                assignment TEXT,
                solvent TEXT,
                instrument_mhz TEXT,
                note TEXT,
                FOREIGN KEY (compound_id) REFERENCES compounds(id) ON DELETE CASCADE
            )
        """)

        # =========================
        # 3. Tabel carbon_nmr
        # =========================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS carbon_nmr (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                compound_id INTEGER NOT NULL,
                delta_ppm REAL NOT NULL,
                carbon_type TEXT,
                assignment TEXT,
                solvent TEXT,
                instrument_mhz TEXT,
                note TEXT,
                FOREIGN KEY (compound_id) REFERENCES compounds(id) ON DELETE CASCADE
            )
        """)

        # =========================
        # 4. Tabel spectra_files
        # =========================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS spectra_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                compound_id INTEGER NOT NULL,
                spectrum_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                note TEXT,
                FOREIGN KEY (compound_id) REFERENCES compounds(id) ON DELETE CASCADE
            )
        """)

        conn.commit()
        conn.close()

        print("Berhasil! Database dan semua tabel telah dibuat.")
        print(f"Lokasi database: {path_database}")

    except Exception as e:
        print(f"Gagal membuat database: {e}")


if __name__ == "__main__":
    buat_database()