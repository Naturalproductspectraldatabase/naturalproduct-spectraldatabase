import sqlite3
import os

# Menentukan lokasi folder project
folder_script = os.path.dirname(os.path.abspath(__file__))
folder_project = os.path.dirname(folder_script)

# Menentukan lokasi database
folder_database = os.path.join(folder_project, "database")
path_database = os.path.join(folder_database, "nmr.db")


def parse_peak_input(text):
    peaks = []
    for item in text.split(","):
        item = item.strip()
        if item == "":
            continue
        try:
            peaks.append(float(item))
        except ValueError:
            print(f"Warning: '{item}' bukan angka valid dan akan diabaikan.")
    return peaks


def cari_match(query_peaks, db_peaks, tolerance):
    matched_query_peaks = []
    matched_db_peaks = set()

    for q in query_peaks:
        best_match = None
        best_diff = None
        best_index = None

        for i, db_peak in enumerate(db_peaks):
            if i in matched_db_peaks:
                continue

            diff = abs(q - db_peak)
            if diff <= tolerance:
                if best_diff is None or diff < best_diff:
                    best_diff = diff
                    best_match = db_peak
                    best_index = i

        if best_match is not None:
            matched_query_peaks.append((q, best_match, best_diff))
            matched_db_peaks.add(best_index)

    return matched_query_peaks


def search_combined_nmr():
    try:
        conn = sqlite3.connect(path_database)
        cursor = conn.cursor()

        print("\n=== Pencarian Gabungan 1H + 13C NMR ===")
        print("Masukkan daftar peak 1H dan 13C dipisah koma.")
        print("Contoh 1H : 4.93, 4.83, 4.67, 2.23, 1.72")
        print("Contoh 13C: 149.7, 135.7, 129.6, 114.5, 61.5")

        proton_input = input("\nDaftar peak 1H   : ").strip()
        carbon_input = input("Daftar peak 13C  : ").strip()

        query_protons = parse_peak_input(proton_input)
        query_carbons = parse_peak_input(carbon_input)

        if not query_protons and not query_carbons:
            print("\nTidak ada peak valid yang dimasukkan.")
            conn.close()
            return

        proton_tol_input = input("Toleransi 1H [default 0.05]: ").strip()
        if proton_tol_input == "":
            proton_tolerance = 0.05
        else:
            try:
                proton_tolerance = float(proton_tol_input)
            except ValueError:
                print("Input toleransi 1H tidak valid. Dipakai default 0.05 ppm.")
                proton_tolerance = 0.05

        carbon_tol_input = input("Toleransi 13C [default 0.5]: ").strip()
        if carbon_tol_input == "":
            carbon_tolerance = 0.5
        else:
            try:
                carbon_tolerance = float(carbon_tol_input)
            except ValueError:
                print("Input toleransi 13C tidak valid. Dipakai default 0.5 ppm.")
                carbon_tolerance = 0.5

        cursor.execute("""
            SELECT id, trivial_name, sample_code, molecular_formula, source_material
            FROM compounds
        """)
        compounds = cursor.fetchall()

        hasil = []

        for compound in compounds:
            compound_id, trivial_name, sample_code, molecular_formula, source_material = compound

            # Ambil peak 1H
            cursor.execute("""
                SELECT delta_ppm
                FROM proton_nmr
                WHERE compound_id = ?
            """, (compound_id,))
            db_protons = [row[0] for row in cursor.fetchall()]

            # Ambil peak 13C
            cursor.execute("""
                SELECT delta_ppm
                FROM carbon_nmr
                WHERE compound_id = ?
            """, (compound_id,))
            db_carbons = [row[0] for row in cursor.fetchall()]

            proton_matches = []
            carbon_matches = []

            proton_score = 0.0
            carbon_score = 0.0

            if query_protons:
                proton_matches = cari_match(query_protons, db_protons, proton_tolerance)
                proton_score = (len(proton_matches) / len(query_protons)) * 100

            if query_carbons:
                carbon_matches = cari_match(query_carbons, db_carbons, carbon_tolerance)
                carbon_score = (len(carbon_matches) / len(query_carbons)) * 100

            # Skor total
            if query_protons and query_carbons:
                total_score = (proton_score * 0.5) + (carbon_score * 0.5)
            elif query_protons:
                total_score = proton_score
            else:
                total_score = carbon_score

            hasil.append({
                "compound_id": compound_id,
                "trivial_name": trivial_name,
                "sample_code": sample_code,
                "molecular_formula": molecular_formula,
                "source_material": source_material,
                "proton_match_count": len(proton_matches),
                "carbon_match_count": len(carbon_matches),
                "proton_total_query": len(query_protons),
                "carbon_total_query": len(query_carbons),
                "proton_score": proton_score,
                "carbon_score": carbon_score,
                "total_score": total_score,
                "proton_matches": proton_matches,
                "carbon_matches": carbon_matches,
                "db_proton_count": len(db_protons),
                "db_carbon_count": len(db_carbons)
            })

        hasil.sort(key=lambda x: x["total_score"], reverse=True)

        print("\n=== HASIL PENCARIAN GABUNGAN ===\n")

        for i, item in enumerate(hasil[:10], start=1):
            print("=" * 90)
            print(f"Ranking              : {i}")
            print(f"ID Senyawa           : {item['compound_id']}")
            print(f"Nama trivial         : {item['trivial_name']}")
            print(f"Sample code          : {item['sample_code']}")
            print(f"Rumus molekul        : {item['molecular_formula']}")
            print(f"Sumber material      : {item['source_material']}")
            print(f"Jumlah peak 1H DB    : {item['db_proton_count']}")
            print(f"Jumlah peak 13C DB   : {item['db_carbon_count']}")
            print(f"1H cocok             : {item['proton_match_count']}/{item['proton_total_query']}  ({item['proton_score']:.1f}%)")
            print(f"13C cocok            : {item['carbon_match_count']}/{item['carbon_total_query']}  ({item['carbon_score']:.1f}%)")
            print(f"Skor total           : {item['total_score']:.1f}%")

            if item["proton_matches"]:
                print("\nMatched 1H peaks:")
                for q, dbp, diff in item["proton_matches"]:
                    print(f"  query {q}  <->  db {dbp}   (selisih {diff:.3f})")

            if item["carbon_matches"]:
                print("\nMatched 13C peaks:")
                for q, dbp, diff in item["carbon_matches"]:
                    print(f"  query {q}  <->  db {dbp}   (selisih {diff:.3f})")

            print("=" * 90)
            print()

        conn.close()

    except Exception as e:
        print(f"Terjadi error saat pencarian gabungan NMR: {e}")


if __name__ == "__main__":
    search_combined_nmr()