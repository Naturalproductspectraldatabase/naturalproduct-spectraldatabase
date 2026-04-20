# Local Backup Access Guide

## Tujuan

Kalau hosting publik gratis bermasalah, kamu tetap bisa membuka database dari:

1. laptop/PC kamu sendiri
2. HP kamu
3. perangkat lain dalam Wi-Fi yang sama

## Kondisi yang harus dipenuhi

1. Laptop yang menyimpan project harus menyala.
2. App Streamlit harus sedang berjalan.
3. HP/PC lain harus berada pada jaringan Wi-Fi yang sama.
4. Firewall sistem harus mengizinkan koneksi ke port `8501`.

## Cara menjalankan app lokal

Di Terminal, jalankan:

```bash
streamlit run /Users/triandatyas/Desktop/NMR_Database_Tyas/scripts/app.py
```

Project ini sudah disiapkan dengan `.streamlit/config.toml` agar server mendengarkan pada:

- `0.0.0.0`
- port `8501`

Artinya app bisa diakses dari perangkat lain di jaringan lokal.

## Cara mengetahui alamat yang dibuka dari HP

Di Mac:

```bash
ipconfig getifaddr en0
```

Jika Wi-Fi aktif, hasilnya biasanya seperti:

```text
192.168.1.8
```

Maka di HP kamu buka:

```text
http://192.168.1.8:8501
```

## Jika `en0` tidak memberi hasil

Coba:

```bash
ifconfig | grep "inet "
```

Lalu cari IP lokal yang biasanya diawali:

1. `192.168.x.x`
2. `10.x.x.x`
3. `172.16.x.x` sampai `172.31.x.x`

## Cara backup data

Untuk membuat backup database SQLite dan ekspor CSV terbaru:

```bash
python3 /Users/triandatyas/Desktop/NMR_Database_Tyas/scripts/create_local_backup.py
```

Hasilnya masuk ke:

1. `database/backups/nmr_backup_YYYYMMDD_HHMMSS.db`
2. `database/backups/latest_csv/`

## Kapan sebaiknya backup

1. sebelum batch import besar
2. sebelum edit schema/database
3. sebelum deploy
4. setelah banyak submission baru masuk

## Rekomendasi strategi aman jangka panjang

Gunakan 3 lapis:

1. `Supabase` untuk metadata utama online
2. `Google Drive` untuk raw spectra besar
3. `SQLite lokal + backup folder` sebagai cadangan offline cepat

## Keterbatasan mode lokal

1. Bukan URL permanen global
2. Hanya nyaman untuk jaringan yang sama
3. Akan mati jika laptop mati atau app tidak berjalan

## Rekomendasi praktis

Anggap mode lokal ini sebagai `emergency backup access`, bukan jalur utama publik.
