import sqlite3
import os

# Menentukan lokasi folder project
folder_script = os.path.dirname(os.path.abspath(__file__))
folder_project = os.path.dirname(folder_script)

# Menentukan lokasi database
folder_database = os.path.join(folder_project, "database")
path_database = os.path.join(folder_database, "nmr.db")


ALLOWED_FIELDS = [
    "compound_id",
    "delta_ppm",
    "multiplicity",
    "j_value",
    "proton_count",
    "assignment",
    "solvent",
    "instrument_mhz",
    "note"
]


def input_integer(prompt_text):
    while True:
        value = input(prompt_text).strip()
        try:
            return int(value)
        except ValueError:
            print("Input harus berupa angka bulat. Contoh: 1")


def tampilkan_field():
    print("\nField yang bisa diupdate:")
    for i, field in enumerate(ALLOWED_FIELDS, start=1):
        print(f"{i}. {field}")


def update_proton_nmr():
    try:
        conn = sqlite3.connect(path_database)
        cursor = conn.cursor()

        print("\n=== Update Data Proton NMR ===")

        peak_id = input_integer("Masukkan ID peak proton     : ")

        cursor.execute("""
            SELECT id, compound_id, delta_ppm, multiplicity, j_value,
                   proton_count, assignment, solvent, instrument_mhz, note
            FROM proton_nmr
            WHERE id = ?
        """, (peak_id,))
        result = cursor.fetchone()

        if not result:
            print("\nID peak proton tidak ditemukan.")
            conn.close()
            return

        print("\nPeak ditemukan:")
        print(f"ID peak              : {result[0]}")
        print(f"compound_id          : {result[1]}")
        print(f"delta_ppm            : {result[2]}")
        print(f"multiplicity         : {result[3]}")
        print(f"j_value              : {result[4]}")
        print(f"proton_count         : {result[5]}")
        print(f"assignment           : {result[6]}")
        print(f"solvent              : {result[7]}")
        print(f"instrument_mhz       : {result[8]}")
        print(f"note                 : {result[9]}")

        tampilkan_field()

        pilihan = input("\nPilih nomor field yang ingin diupdate: ").strip()

        try:
            pilihan_index = int(pilihan) - 1
            if pilihan_index < 0 or pilihan_index >= len(ALLOWED_FIELDS):
                print("Pilihan field tidak valid.")
                conn.close()
                return
        except ValueError:
            print("Pilihan harus berupa angka.")
            conn.close()
            return

        field_name = ALLOWED_FIELDS[pilihan_index]

        cursor.execute(f"""
            SELECT {field_name}
            FROM proton_nmr
            WHERE id = ?
        """, (peak_id,))
        old_value = cursor.fetchone()[0]

        print(f"\nField yang dipilih : {field_name}")
        print(f"Nilai lama         : {old_value}")

        new_value = input("Nilai baru         : ").strip()

        if field_name in ["compound_id"]:
            try:
                parsed_value = int(new_value)
            except ValueError:
                print("Nilai harus berupa angka bulat.")
                conn.close()
                return
        elif field_name in ["delta_ppm"]:
            try:
                parsed_value = float(new_value)
            except ValueError:
                print("Nilai harus berupa angka.")
                conn.close()
                return
        else:
            parsed_value = new_value

        cursor.execute(f"""
            UPDATE proton_nmr
            SET {field_name} = ?
            WHERE id = ?
        """, (parsed_value, peak_id))

        conn.commit()

        print("\nBerhasil! Data proton NMR telah diperbarui.")

        cursor.execute(f"""
            SELECT {field_name}
            FROM proton_nmr
            WHERE id = ?
        """, (peak_id,))
        updated_value = cursor.fetchone()[0]

        print(f"Nilai baru tersimpan: {updated_value}")

        conn.close()

    except Exception as e:
        print(f"Terjadi error saat update data proton NMR: {e}")


if __name__ == "__main__":
    update_proton_nmr()