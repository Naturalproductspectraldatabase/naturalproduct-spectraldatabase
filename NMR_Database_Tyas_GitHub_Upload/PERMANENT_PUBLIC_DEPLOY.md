# Permanent Public Deploy Guide

## Jawaban singkat dulu

Ya, saya bisa membantu sangat jauh:

1. menyiapkan project,
2. menyiapkan schema Supabase,
3. menyiapkan file ekspor dari SQLite,
4. menyiapkan format secret dan login,
5. menyiapkan urutan klik dan isi form.

Tetapi untuk membuat URL permanen sungguhan, kamu tetap perlu akun milikmu sendiri untuk:

1. GitHub
2. Streamlit Community Cloud
3. Supabase

Alasannya sederhana: URL permanen dan database cloud harus berada di akun kamu, bukan di sesi kerja sementara saya.

## Tentang URL yang kamu inginkan

`https://NaturalProduct_SpectralDatabase` tidak bisa dipakai apa adanya.

Alasannya:

1. hostname URL perlu domain yang valid, misalnya `.streamlit.app` atau `.com`
2. underscore `_` tidak dipakai untuk nama host web

Versi yang realistis dan mirip adalah:

- `https://naturalproduct-spectraldatabase.streamlit.app`

Kalau subdomain itu belum dipakai orang lain, kamu bisa memilihnya saat deploy di Streamlit Community Cloud.

## Arsitektur gratis yang paling aman untuk kamu

1. Frontend/app: Streamlit Community Cloud
2. Metadata database: Supabase Postgres
3. File besar dan spectra raw: Google Drive
4. Login awal kecil: access gate di app dengan pola `npdb_<nama>`

## Login yang saya siapkan

Format login:

1. Username: `npdb_<nama>`
2. Password: `OnnamideA13.`

Contoh:

1. `npdb_tyas`
2. `npdb_sensei`

Nama yang diizinkan akan dibaca dari:

- `.streamlit/secrets.toml`

## Langkah super detail

### Bagian A. Buat akun

1. Buat akun GitHub di [https://github.com](https://github.com)
2. Buat akun Streamlit Community Cloud di [https://share.streamlit.io](https://share.streamlit.io)
3. Buat akun Supabase di [https://supabase.com](https://supabase.com)

### Bagian B. Siapkan repo GitHub

1. Buka GitHub.
2. Klik `New repository`.
3. Nama repo yang disarankan: `naturalproduct-spectraldatabase`
4. Pilih `Public`
5. Klik `Create repository`

Setelah repo jadi, upload isi folder berikut ke repo:

- `Desktop/NMR_Database_Tyas/`

Yang jangan ikut diupload:

- `.streamlit/secrets.toml`
- backup database besar yang tidak perlu

### Bagian C. Siapkan Supabase

1. Login ke Supabase dashboard.
2. Klik `New project`.
3. Isi project name, password database, dan region yang dekat.
4. Setelah project jadi, buka `SQL Editor`.
5. Klik `New query`.
6. Copy isi file:

- `database/supabase_schema.sql`

7. Paste ke SQL Editor.
8. Klik `Run`

### Bagian D. Ekspor data SQLite lama

Di laptop, jalankan:

```bash
python3 /Users/triandatyas/Desktop/NMR_Database_Tyas/scripts/export_sqlite_to_csv.py
```

Hasilnya akan masuk ke:

- `data/exports/supabase_import/`

File yang akan muncul:

1. `compounds.csv`
2. `proton_nmr.csv`
3. `carbon_nmr.csv`
4. `spectra_files.csv`

### Bagian E. Import CSV ke Supabase

Untuk tiap tabel:

1. Buka `Table Editor`
2. Pilih tabel yang sesuai
3. Klik `Import data from CSV`
4. Upload file CSV yang sesuai

Urutan import:

1. `compounds.csv`
2. `proton_nmr.csv`
3. `carbon_nmr.csv`
4. `spectra_files.csv`

Urutan ini penting karena tabel lain bergantung pada `compound_id`.

### Bagian F. Ambil kredensial Supabase

Di Supabase:

1. buka `Project Settings`
2. buka `API`
3. copy:
   `Project URL`
4. copy:
   `anon public key`

Simpan nanti untuk Streamlit secrets.

### Bagian G. Deploy ke Streamlit Community Cloud

1. Login ke Streamlit Community Cloud
2. Klik `Create app`
3. Pilih repo GitHub kamu
4. Branch: `main`
5. Main file path:
   `scripts/app.py`
6. Pada `App URL`, isi:
   `naturalproduct-spectraldatabase`
   jika masih tersedia
7. Klik `Advanced settings`
8. Paste secrets
9. Klik `Deploy`

### Bagian H. Isi secrets di Streamlit Cloud

Format awal yang disarankan:

```toml
NPDB_APPROVED_PASSWORD = "OnnamideA13."
NPDB_APPROVED_NAMES = ["tyas", "sensei", "labmate1"]
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_ANON_KEY = "your-anon-key"
```

## Kenapa saya belum bisa menyelesaikan deploy permanen sendirian dari sini?

Karena sistem ini tidak punya akses otomatis ke:

1. akun GitHub kamu
2. akun Streamlit Cloud kamu
3. akun Supabase kamu
4. halaman dashboard web tempat tombol deploy/import diklik

Saya bisa menyiapkan semuanya dan memandu langkahnya dengan sangat detail, tetapi klik akhir tetap perlu dilakukan di akun kamu.
