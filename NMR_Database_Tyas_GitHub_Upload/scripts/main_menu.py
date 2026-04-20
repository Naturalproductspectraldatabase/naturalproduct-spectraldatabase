import os


def jalankan_script(nama_file):
    folder_script = os.path.dirname(os.path.abspath(__file__))
    path_script = os.path.join(folder_script, nama_file)
    os.system(f'/usr/local/bin/python3 "{path_script}"')


def tampilkan_menu():
    while True:
        print("\n" + "=" * 82)
        print("                       NMR DATABASE TYAS - MAIN MENU")
        print("=" * 82)
        print("1. Tambah data senyawa baru")
        print("2. Tambah data 1H NMR")
        print("3. Tambah data 13C NMR")
        print("4. Tambah file spektra")
        print("5. Cari data senyawa (nama / keyword)")
        print("6. Cari kemiripan berdasarkan 13C NMR")
        print("7. Cari kemiripan berdasarkan 1H NMR")
        print("8. Cari kemiripan gabungan 1H + 13C")
        print("9. Update data senyawa")
        print("10. Update data proton NMR")
        print("11. Update data carbon NMR")
        print("12. Update data file spektra")
        print("13. Hapus data")
        print("14. Keluar")
        print("=" * 82)

        pilihan = input("Pilih menu (1-14): ").strip()

        if pilihan == "1":
            jalankan_script("insert_compound.py")
        elif pilihan == "2":
            jalankan_script("insert_proton_nmr.py")
        elif pilihan == "3":
            jalankan_script("insert_carbon_nmr.py")
        elif pilihan == "4":
            jalankan_script("insert_spectrum_file.py")
        elif pilihan == "5":
            jalankan_script("search_database.py")
        elif pilihan == "6":
            jalankan_script("search_by_carbon.py")
        elif pilihan == "7":
            jalankan_script("search_by_proton.py")
        elif pilihan == "8":
            jalankan_script("search_combined_nmr.py")
        elif pilihan == "9":
            jalankan_script("update_compound.py")
        elif pilihan == "10":
            jalankan_script("update_proton_nmr.py")
        elif pilihan == "11":
            jalankan_script("update_carbon_nmr.py")
        elif pilihan == "12":
            jalankan_script("update_spectrum_file.py")
        elif pilihan == "13":
            jalankan_script("delete_data.py")
        elif pilihan == "14":
            print("\nKeluar dari program. Sampai jumpa.")
            break
        else:
            print("\nPilihan tidak valid. Silakan pilih angka 1-14.")


if __name__ == "__main__":
    tampilkan_menu()