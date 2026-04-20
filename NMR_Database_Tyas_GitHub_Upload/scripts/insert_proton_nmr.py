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


def input_float(prompt_text):
    while True:
        value = input(prompt_text).strip()
        try:
            return float(value)
        except ValueError:
            print("Input harus berupa angka desimal / angka biasa. Contoh: 1.55")


def tambah_proton_nmr():
    try:
        conn = sqlite3.connect(path_database)
        cursor = conn.cursor()

        print("\n=== Input Data Peak 1H NMR ===")

        while True:
            compound_id = input_integer("ID senyawa                  : ")
            delta_ppm = input_float("Delta ppm                   : ")
            multiplicity = input("Multiplicity                : ").strip()
            j_value = input("J value                     : ").strip()
            proton_count = input("Jumlah proton               : ").strip()
            assignment = input("Assignment                  : ").strip()
            solvent = input("Solvent                     : ").strip()
            instrument_mhz = input("Frekuensi instrumen (MHz)   : ").strip()
            note = input("Catatan tambahan            : ").strip()

            cursor.execute("""
                INSERT INTO proton_nmr (
                    compound_id,
                    delta_ppm,
                    multiplicity,
                    j_value,
                    proton_count,
                    assignment,
                    solvent,
                    instrument_mhz,
                    note
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                compound_id,
                delta_ppm,
                multiplicity,
                j_value,
                proton_count,
                assignment,
                solvent,
                instrument_mhz,
                note
            ))

            conn.commit()
            peak_id = cursor.lastrowid

            print("\nBerhasil! Data peak 1H NMR telah disimpan.")
            print(f"ID peak baru: {peak_id}")

            lanjut = input("\nTambah peak 1H lagi? (y/n): ").strip().lower()
            if lanjut != "y":
                break

            print("\n--- Input peak berikutnya ---")

        conn.close()
        print("\nSelesai input data 1H NMR.")

    except Exception as e:
        print(f"Terjadi error saat menambahkan data 1H NMR: {e}")


if __name__ == "__main__":
    tambah_proton_nmr()