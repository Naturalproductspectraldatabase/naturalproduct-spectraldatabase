# Natural Products Spectral Database Deployment

## Saat ini app masih localhost?

Ya. Selama kamu menjalankan Streamlit di laptop sendiri, alamat aktifnya tetap `http://localhost:8501`.
Itu adalah alamat development lokal, bukan alamat publik permanen.

## Setelah dibuat publik, pengguna akses lewat apa?

Pengguna tidak lagi memakai `localhost`.
Mereka akan membuka URL publik hasil deploy, misalnya:

- `https://npdb-tyas.streamlit.app`
- `https://npdb-tyas.onrender.com`
- domain kamu sendiri jika nanti ditambahkan

Selama deploy belum dilakukan, hanya perangkat yang bisa menjangkau laptop kamu yang bisa membuka app.

## Model yang dipakai di project ini

1. SQLite lokal menyimpan metadata, peak tables, dan link file.
2. Google Drive menyimpan preview image dan raw data besar.
3. Streamlit menampilkan preview image Drive bila link valid dan permission benar.
4. Raw file tetap dibuka atau diunduh dari Google Drive.

## Rekomendasi deploy kecil untuk sekitar 50 user

Pilihan paling sederhana:

1. Deploy app Streamlit ke host publik.
2. Simpan kredensial di `.streamlit/secrets.toml` atau secret manager platform.
3. Share URL publik hanya ke user yang kamu approve.

Pilihan platform:

1. Streamlit Community Cloud untuk prototipe publik ringan.
2. Render/Railway untuk kontrol lebih stabil.
3. VPS jika nanti ingin kontrol penuh dan domain sendiri.

## Command lokal

Jalankan dari root project:

```bash
streamlit run scripts/app.py
```

Kalau host butuh port dari environment:

```bash
streamlit run scripts/app.py --server.address 0.0.0.0 --server.port $PORT
```

## Backup lokal lintas perangkat

Karena `.streamlit/config.toml` di project ini memakai `address = "0.0.0.0"` dan `port = 8501`, app bisa dijadikan cadangan lokal untuk HP/PC lain di jaringan Wi-Fi yang sama.

Langkah singkat:

1. Jalankan app di laptop utama.
2. Cari IP lokal laptop, misalnya `192.168.1.8`.
3. Buka dari HP/PC lain:
   `http://192.168.1.8:8501`

Panduan detail ada di:

- `LOCAL_BACKUP_ACCESS.md`

## Setup secret

Copy isi contoh:

- `.streamlit/secrets.toml.example`

Menjadi:

- `.streamlit/secrets.toml`

Lalu pilih salah satu:

1. Satu login bersama dengan `NPDB_ACCESS_USERNAME` dan `NPDB_ACCESS_PASSWORD`
2. Banyak akun approved user dengan `NPDB_APPROVED_USERS`

## Catatan penting

1. Untuk raw data besar, pakai Google Drive link, bukan upload lokal.
2. Untuk preview spectra, link Google Drive harus bisa dilihat oleh user yang diberi akses.
3. Field `SMILES`, `InChI`, dan `InChIKey` sekarang menjadi fondasi pencarian struktur tahap berikutnya.
