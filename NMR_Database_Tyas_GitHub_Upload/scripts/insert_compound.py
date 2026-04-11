import sqlite3
import os

# Menentukan lokasi folder project
folder_script = os.path.dirname(os.path.abspath(__file__))
folder_project = os.path.dirname(folder_script)

# Menentukan lokasi database
folder_database = os.path.join(folder_project, "database")
path_database = os.path.join(folder_database, "nmr.db")


def tambah_compound():
    try:
        conn = sqlite3.connect(path_database)
        cursor = conn.cursor()

        print("\n=== Input Data Senyawa Baru ===")

        trivial_name = input("Nama trivial                : ").strip()
        iupac_name = input("Nama IUPAC                  : ").strip()
        molecular_formula = input("Rumus molekul               : ").strip()
        source_material = input("Sumber material             : ").strip()
        sample_code = input("Sample code                 : ").strip()
        collection_location = input("Lokasi koleksi              : ").strip()
        gps_coordinates = input("GPS coordinates             : ").strip()
        depth_m_input = input("Depth (m)                   : ").strip()
        uv_data = input("Data UV                     : ").strip()
        ftir_data = input("Data FTIR                   : ").strip()
        optical_rotation = input("Optical rotation            : ").strip()
        melting_point = input("Titik leleh                 : ").strip()
        crystallization_method = input("Metode kristalisasi         : ").strip()
        structure_image_path = input("Path gambar struktur        : ").strip()
        note = input("Catatan tambahan            : ").strip()

        # Mengubah depth menjadi angka jika diisi
        if depth_m_input == "":
            depth_m = None
        else:
            depth_m = float(depth_m_input)

        cursor.execute("""
            INSERT INTO compounds (
                trivial_name,
                iupac_name,
                molecular_formula,
                source_material,
                sample_code,
                collection_location,
                gps_coordinates,
                depth_m,
                uv_data,
                ftir_data,
                optical_rotation,
                melting_point,
                crystallization_method,
                structure_image_path,
                note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trivial_name,
            iupac_name,
            molecular_formula,
            source_material,
            sample_code,
            collection_location,
            gps_coordinates,
            depth_m,
            uv_data,
            ftir_data,
            optical_rotation,
            melting_point,
            crystallization_method,
            structure_image_path,
            note
        ))

        conn.commit()
        compound_id = cursor.lastrowid
        conn.close()

        print("\nBerhasil! Data senyawa telah disimpan.")
        print(f"ID senyawa baru: {compound_id}")

    except Exception as e:
        print(f"Terjadi error saat menambahkan senyawa: {e}")


if __name__ == "__main__":
    tambah_compound()