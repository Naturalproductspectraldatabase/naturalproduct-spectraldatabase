import sqlite3
import os

# Menentukan lokasi folder project
folder_script = os.path.dirname(os.path.abspath(__file__))
folder_project = os.path.dirname(folder_script)

# Menentukan lokasi database
folder_database = os.path.join(folder_project, "database")
path_database = os.path.join(folder_database, "nmr.db")


def parse_peak_input(text):
    """
    Mengubah input seperti:
    149.7, 135.7, 129.6, 114.5
    menjadi list float.
    """
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


def cari_kemiripan_13c():
    try:
        conn = sqlite3.connect(path_database)
        cursor = conn.cursor()

        print("\n=== Pencarian Berdasarkan 13C NMR ===")
        print("Masukkan daftar peak 13C dipisah koma.")
        print("Contoh: 149.7, 135.7, 129.6, 114.5, 61.5")

        peak_input = input("\nDaftar peak 13C: ").strip()
        query_peaks = parse_peak_input(peak_input)

        if not query_peaks:
            print("\nTidak ada peak valid yang dimasukkan.")
            conn.close()
            return

        tolerance_input = input("Toleransi ppm [default 0.5]: ").strip()
        if tolerance_input == "":
            tolerance = 0.5
        else:
            try:
                tolerance = float(tolerance_input)
            except ValueError:
                print("Input toleransi tidak valid. Dipakai default 0.5 ppm.")
                tolerance = 0.5

        # Ambil semua senyawa
        cursor.execute("""
            SELECT id, trivial_name, sample_code, molecular_formula, source_material
            FROM compounds
        """)
        compounds = cursor.fetchall()

        hasil = []

        for compound in compounds:
            compound_id, trivial_name, sample_code, molecular_formula, source_material = compound

            # Ambil semua peak 13C senyawa ini
            cursor.execute("""
                SELECT delta_ppm
                FROM carbon_nmr
                WHERE compound_id = ?
            """, (compound_id,))
            db_peaks = [row[0] for row in cursor.fetchall()]

            if not db_peaks:
                continue

            matched_query_peaks = []
            matched_db_peaks = set()

            # Cek tiap peak query terhadap peak database
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

            match_count = len(matched_query_peaks)
            total_query = len(query_peaks)
            score = (match_count / total_query) * 100 if total_query > 0 else 0

            hasil.append({
                "compound_id": compound_id,
                "trivial_name": trivial_name,
                "sample_code": sample_code,
                "molecular_formula": molecular_formula,
                "source_material": source_material,
                "match_count": match_count,
                "total_query": total_query,
                "score": score,
                "matched_peaks": matched_query_peaks,
                "db_peak_count": len(db_peaks)
            })

        # Urutkan hasil: skor tertinggi dulu, lalu match_count terbesar
        hasil.sort(key=lambda x: (x["score"], x["match_count"]), reverse=True)

        if not hasil:
            print("\nTidak ada data 13C di database.")
            conn.close()
            return

        print("\n=== HASIL PENCARIAN 13C ===\n")

        for i, item in enumerate(hasil[:10], start=1):
            print("=" * 80)
            print(f"Ranking              : {i}")
            print(f"ID Senyawa           : {item['compound_id']}")
            print(f"Nama trivial         : {item['trivial_name']}")
            print(f"Sample code          : {item['sample_code']}")
            print(f"Rumus molekul        : {item['molecular_formula']}")
            print(f"Sumber material      : {item['source_material']}")
            print(f"Jumlah peak query    : {item['total_query']}")
            print(f"Jumlah peak 13C DB   : {item['db_peak_count']}")
            print(f"Peak cocok           : {item['match_count']}/{item['total_query']}")
            print(f"Skor kecocokan       : {item['score']:.1f}%")

            if item["matched_peaks"]:
                print("Matched peaks:")
                for q, dbp, diff in item["matched_peaks"]:
                    print(f"  query {q}  <->  db {dbp}   (selisih {diff:.3f})")
            else:
                print("Matched peaks: tidak ada")

            print("=" * 80)
            print()

        conn.close()

    except Exception as e:
        print(f"Terjadi error saat pencarian 13C: {e}")


if __name__ == "__main__":
    cari_kemiripan_13c()