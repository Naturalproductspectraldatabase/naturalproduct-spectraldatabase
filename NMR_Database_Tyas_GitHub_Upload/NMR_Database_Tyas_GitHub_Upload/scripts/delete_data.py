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


def konfirmasi_hapus():
    jawab = input("Yakin ingin menghapus? Ketik 'yes' untuk konfirmasi: ").strip().lower()
    return jawab == "yes"


def hapus_compound(cursor):
    compound_id = input_integer("Masukkan ID senyawa yang ingin dihapus: ")

    cursor.execute("""
        SELECT id, trivial_name, sample_code
        FROM compounds
        WHERE id = ?
    """, (compound_id,))
    result = cursor.fetchone()

    if not result:
        print("\nID senyawa tidak ditemukan.")
        return False

    print("\nData senyawa yang akan dihapus:")
    print(f"ID Senyawa     : {result[0]}")
    print(f"Nama trivial   : {result[1]}")
    print(f"Sample code    : {result[2]}")
    print("\nPERINGATAN: Semua data 1H, 13C, dan file spektra terkait juga akan terhapus.")

    if not konfirmasi_hapus():
        print("\nPenghapusan dibatalkan.")
        return False

    cursor.execute("DELETE FROM compounds WHERE id = ?", (compound_id,))
    print("\nBerhasil! Data senyawa telah dihapus.")
    return True


def hapus_proton(cursor):
    peak_id = input_integer("Masukkan ID peak proton yang ingin dihapus: ")

    cursor.execute("""
        SELECT id, compound_id, delta_ppm, multiplicity, assignment
        FROM proton_nmr
        WHERE id = ?
    """, (peak_id,))
    result = cursor.fetchone()

    if not result:
        print("\nID peak proton tidak ditemukan.")
        return False

    print("\nData peak proton yang akan dihapus:")
    print(f"ID peak        : {result[0]}")
    print(f"compound_id    : {result[1]}")
    print(f"delta_ppm      : {result[2]}")
    print(f"multiplicity   : {result[3]}")
    print(f"assignment     : {result[4]}")

    if not konfirmasi_hapus():
        print("\nPenghapusan dibatalkan.")
        return False

    cursor.execute("DELETE FROM proton_nmr WHERE id = ?", (peak_id,))
    print("\nBerhasil! Data peak proton telah dihapus.")
    return True


def hapus_carbon(cursor):
    peak_id = input_integer("Masukkan ID peak carbon yang ingin dihapus: ")

    cursor.execute("""
        SELECT id, compound_id, delta_ppm, carbon_type, assignment
        FROM carbon_nmr
        WHERE id = ?
    """, (peak_id,))
    result = cursor.fetchone()

    if not result:
        print("\nID peak carbon tidak ditemukan.")
        return False

    print("\nData peak carbon yang akan dihapus:")
    print(f"ID peak        : {result[0]}")
    print(f"compound_id    : {result[1]}")
    print(f"delta_ppm      : {result[2]}")
    print(f"carbon_type    : {result[3]}")
    print(f"assignment     : {result[4]}")

    if not konfirmasi_hapus():
        print("\nPenghapusan dibatalkan.")
        return False

    cursor.execute("DELETE FROM carbon_nmr WHERE id = ?", (peak_id,))
    print("\nBerhasil! Data peak carbon telah dihapus.")
    return True


def hapus_spectrum_file(cursor):
    file_id = input_integer("Masukkan ID file spektra yang ingin dihapus: ")

    cursor.execute("""
        SELECT id, compound_id, spectrum_type, file_path
        FROM spectra_files
        WHERE id = ?
    """, (file_id,))
    result = cursor.fetchone()

    if not result:
        print("\nID file spektra tidak ditemukan.")
        return False

    print("\nData file spektra yang akan dihapus:")
    print(f"ID file        : {result[0]}")
    print(f"compound_id    : {result[1]}")
    print(f"spectrum_type  : {result[2]}")
    print(f"file_path      : {result[3]}")

    if not konfirmasi_hapus():
        print("\nPenghapusan dibatalkan.")
        return False

    cursor.execute("DELETE FROM spectra_files WHERE id = ?", (file_id,))
    print("\nBerhasil! Data file spektra telah dihapus.")
    return True


def delete_data():
    try:
        conn = sqlite3.connect(path_database)
        cursor = conn.cursor()

        print("\n=== Hapus Data ===")
        print("1. Hapus data senyawa")
        print("2. Hapus data peak proton NMR")
        print("3. Hapus data peak carbon NMR")
        print("4. Hapus data file spektra")

        pilihan = input("Pilih jenis data yang ingin dihapus (1-4): ").strip()

        berhasil = False

        if pilihan == "1":
            berhasil = hapus_compound(cursor)
        elif pilihan == "2":
            berhasil = hapus_proton(cursor)
        elif pilihan == "3":
            berhasil = hapus_carbon(cursor)
        elif pilihan == "4":
            berhasil = hapus_spectrum_file(cursor)
        else:
            print("\nPilihan tidak valid.")

        if berhasil:
            conn.commit()

        conn.close()

    except Exception as e:
        print(f"Terjadi error saat menghapus data: {e}")


if __name__ == "__main__":
    delete_data()