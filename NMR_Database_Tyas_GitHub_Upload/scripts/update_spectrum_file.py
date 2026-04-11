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
    "spectrum_type",
    "file_path",
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


def update_spectrum_file():
    try:
        conn = sqlite3.connect(path_database)
        cursor = conn.cursor()

        print("\n=== Update Data File Spektra ===")

        file_id = input_integer("Masukkan ID file spektra    : ")

        cursor.execute("""
            SELECT id, compound_id, spectrum_type, file_path, note
            FROM spectra_files
            WHERE id = ?
        """, (file_id,))
        result = cursor.fetchone()

        if not result:
            print("\nID file spektra tidak ditemukan.")
            conn.close()
            return

        print("\nFile spektra ditemukan:")
        print(f"ID file              : {result[0]}")
        print(f"compound_id          : {result[1]}")
        print(f"spectrum_type        : {result[2]}")
        print(f"file_path            : {result[3]}")
        print(f"note                 : {result[4]}")

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
            FROM spectra_files
            WHERE id = ?
        """, (file_id,))
        old_value = cursor.fetchone()[0]

        print(f"\nField yang dipilih : {field_name}")
        print(f"Nilai lama         : {old_value}")

        new_value = input("Nilai baru         : ").strip()

        if field_name == "compound_id":
            try:
                parsed_value = int(new_value)
            except ValueError:
                print("compound_id harus berupa angka bulat.")
                conn.close()
                return
        else:
            parsed_value = new_value

        cursor.execute(f"""
            UPDATE spectra_files
            SET {field_name} = ?
            WHERE id = ?
        """, (parsed_value, file_id))

        conn.commit()

        print("\nBerhasil! Data file spektra telah diperbarui.")

        cursor.execute(f"""
            SELECT {field_name}
            FROM spectra_files
            WHERE id = ?
        """, (file_id,))
        updated_value = cursor.fetchone()[0]

        print(f"Nilai baru tersimpan: {updated_value}")

        conn.close()

    except Exception as e:
        print(f"Terjadi error saat update data file spektra: {e}")


if __name__ == "__main__":
    update_spectrum_file()