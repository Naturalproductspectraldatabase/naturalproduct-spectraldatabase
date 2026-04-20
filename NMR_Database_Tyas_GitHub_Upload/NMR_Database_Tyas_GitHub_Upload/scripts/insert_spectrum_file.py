import sqlite3
import os

# Menentukan lokasi folder project
folder_script = os.path.dirname(os.path.abspath(__file__))
folder_project = os.path.dirname(folder_script)

# Menentukan lokasi database
folder_database = os.path.join(folder_project, "database")
path_database = os.path.join(folder_database, "nmr.db")


def input_integer(prompt_text):
    while True:
        value = input(prompt_text).strip()
        try:
            return int(value)
        except ValueError:
            print("Input harus berupa angka bulat. Contoh: 1")


def tambah_spectrum_file():
    try:
        conn = sqlite3.connect(path_database)
        cursor = conn.cursor()

        print("\n=== Input Data File Spektra ===")
        print("Contoh spectrum_type: 1H, 13C, FTIR, UV, Polarimeter, HMBC, HSQC, COSY, NOESY")

        while True:
            compound_id = input_integer("ID senyawa                  : ")
            spectrum_type = input("Jenis spektra               : ").strip()
            file_path = input("Path file spektra           : ").strip()
            note = input("Catatan tambahan            : ").strip()

            cursor.execute("""
                INSERT INTO spectra_files (
                    compound_id,
                    spectrum_type,
                    file_path,
                    note
                )
                VALUES (?, ?, ?, ?)
            """, (
                compound_id,
                spectrum_type,
                file_path,
                note
            ))

            conn.commit()
            file_id = cursor.lastrowid

            print("\nBerhasil! File spektra telah disimpan.")
            print(f"ID file baru: {file_id}")

            lanjut = input("\nTambah file spektra lagi? (y/n): ").strip().lower()
            if lanjut != "y":
                break

            print("\n--- Input file spektra berikutnya ---")

        conn.close()
        print("\nSelesai input data file spektra.")

    except Exception as e:
        print(f"Terjadi error saat menambahkan file spektra: {e}")


if __name__ == "__main__":
    tambah_spectrum_file()