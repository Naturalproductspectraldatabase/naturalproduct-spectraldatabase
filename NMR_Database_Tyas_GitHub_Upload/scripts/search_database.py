import sqlite3
import os

# Menentukan lokasi folder project
folder_script = os.path.dirname(os.path.abspath(__file__))
folder_project = os.path.dirname(folder_script)

# Menentukan lokasi database
folder_database = os.path.join(folder_project, "database")
path_database = os.path.join(folder_database, "nmr.db")


def tampilkan_metadata(compound):
    print("=" * 90)
    print(f"ID Senyawa           : {compound[0]}")
    print(f"Nama trivial         : {compound[1]}")
    print(f"Nama IUPAC           : {compound[2]}")
    print(f"Rumus molekul        : {compound[3]}")
    print(f"Kelas senyawa        : {compound[4]}")
    print(f"Subkelas senyawa     : {compound[5]}")
    print(f"Sumber material      : {compound[6]}")
    print(f"Sample code          : {compound[7]}")
    print(f"Lokasi koleksi       : {compound[8]}")
    print(f"GPS                  : {compound[9]}")
    print(f"Depth (m)            : {compound[10]}")
    print(f"UV                   : {compound[11]}")
    print(f"FTIR                 : {compound[12]}")
    print(f"Optical rotation     : {compound[13]}")
    print(f"Titik leleh          : {compound[14]}")
    print(f"Metode kristalisasi  : {compound[15]}")
    print(f"Path struktur        : {compound[16]}")
    print(f"Nama jurnal          : {compound[17]}")
    print(f"Tahun publikasi      : {compound[18]}")
    print(f"Volume               : {compound[19]}")
    print(f"Pages                : {compound[20]}")
    print(f"DOI                  : {compound[21]}")
    print(f"Sumber data          : {compound[22]}")
    print(f"Catatan              : {compound[23]}")
    print("-" * 90)


def tampilkan_proton_nmr(cursor, compound_id):
    cursor.execute("""
        SELECT delta_ppm, multiplicity, j_value, proton_count, assignment, solvent, instrument_mhz
        FROM proton_nmr
        WHERE compound_id = ?
        ORDER BY delta_ppm DESC
    """, (compound_id,))
    proton_data = cursor.fetchall()

    print("1H NMR:")
    if proton_data:
        for row in proton_data:
            delta_ppm, multiplicity, j_value, proton_count, assignment, solvent, instrument_mhz = row

            if j_value is None or str(j_value).strip() == "":
                j_text = "-"
            else:
                j_text = j_value

            print(
                f"  δH {delta_ppm} | {multiplicity} | J = {j_text} | "
                f"{proton_count} | {assignment} | {solvent} | {instrument_mhz} MHz"
            )
    else:
        print("  Tidak ada data 1H.")
    print("-" * 90)


def tampilkan_carbon_nmr(cursor, compound_id):
    cursor.execute("""
        SELECT delta_ppm, carbon_type, assignment, solvent, instrument_mhz
        FROM carbon_nmr
        WHERE compound_id = ?
        ORDER BY delta_ppm DESC
    """, (compound_id,))
    carbon_data = cursor.fetchall()

    print("13C NMR:")
    if carbon_data:
        for row in carbon_data:
            delta_ppm, carbon_type, assignment, solvent, instrument_mhz = row
            print(
                f"  δC {delta_ppm} | {carbon_type} | {assignment} | "
                f"{solvent} | {instrument_mhz} MHz"
            )
    else:
        print("  Tidak ada data 13C.")
    print("=" * 90)
    print()


def cari_senyawa():
    try:
        conn = sqlite3.connect(path_database)
        cursor = conn.cursor()

        print("\n=== Pencarian Database NMR ===")
        keyword = input("Masukkan nama senyawa / keyword: ").strip()

        cursor.execute("""
            SELECT id, trivial_name, iupac_name, molecular_formula,
                   compound_class, compound_subclass,
                   source_material, sample_code, collection_location,
                   gps_coordinates, depth_m, uv_data, ftir_data,
                   optical_rotation, melting_point, crystallization_method,
                   structure_image_path, journal_name, publication_year,
                   volume, pages, doi, data_source, note
            FROM compounds
            WHERE trivial_name LIKE ?
               OR iupac_name LIKE ?
               OR sample_code LIKE ?
               OR source_material LIKE ?
               OR collection_location LIKE ?
               OR compound_class LIKE ?
               OR compound_subclass LIKE ?
               OR journal_name LIKE ?
               OR doi LIKE ?
        """, (
            f"%{keyword}%",
            f"%{keyword}%",
            f"%{keyword}%",
            f"%{keyword}%",
            f"%{keyword}%",
            f"%{keyword}%",
            f"%{keyword}%",
            f"%{keyword}%",
            f"%{keyword}%"
        ))

        compounds = cursor.fetchall()

        if not compounds:
            print("\nTidak ada senyawa yang ditemukan.")
            conn.close()
            return

        print(f"\nDitemukan {len(compounds)} senyawa.\n")

        for compound in compounds:
            compound_id = compound[0]
            tampilkan_metadata(compound)
            tampilkan_proton_nmr(cursor, compound_id)
            tampilkan_carbon_nmr(cursor, compound_id)

        conn.close()

    except Exception as e:
        print(f"Terjadi error saat mencari data: {e}")


if __name__ == "__main__":
    cari_senyawa()