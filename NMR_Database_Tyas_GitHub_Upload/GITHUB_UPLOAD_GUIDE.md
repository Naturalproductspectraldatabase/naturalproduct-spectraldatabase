# GitHub Upload Guide

## Kenapa muncul error 25MB

GitHub web upload menolak file tunggal yang terlalu besar.

Di project ini, penyebab utamanya adalah beberapa file gambar lama yang ukurannya sangat besar, misalnya:

1. `data/branding/header.png`
2. `data/branding/header1.png`
3. `data/branding/header_main.png`
4. beberapa file structure PNG yang sangat besar

## Yang perlu kamu upload ke GitHub

Upload project ini, tetapi ikuti aturan berikut:

1. file kode di `scripts/`
2. file konfigurasi `.streamlit/config.toml`
3. file panduan `.md`, `.html`, `.txt`
4. database schema Supabase
5. file spectra preview kecil
6. file structure image yang sudah diperkecil

## Yang tidak perlu kamu upload

Jangan upload:

1. `.streamlit/secrets.toml`
2. `data/branding/header.png`
3. `data/branding/header1.png`
4. `data/branding/header_main.png`
5. `data/structures/Luquilloamide A.1.png`
6. backup file lama dan file cadangan script

## Kenapa aman tidak mengupload file branding besar

App ini sudah memakai prioritas file web yang ringan:

1. `logo_header_web.png`
2. `header1_web.png`
3. `header_main_web.png`

Jadi file branding besar lama bukan file utama untuk deploy.

## Cara paling mudah upload ke GitHub

Kalau upload via web GitHub:

1. buka repo GitHub kamu
2. pilih `Add file`
3. pilih `Upload files`
4. drag folder project yang sudah dirapikan

Kalau GitHub tetap menolak banyak file sekaligus, upload bertahap:

1. upload semua file di root project
2. upload folder `scripts/`
3. upload folder `database/` tanpa backup besar
4. upload folder `data/` yang sudah dirapikan

## Pilihan yang lebih stabil

Lebih aman pakai GitHub Desktop dibanding upload web browser, karena:

1. lebih tahan untuk banyak file
2. lebih mudah melihat file mana yang ikut
3. lebih mudah update project berikutnya
