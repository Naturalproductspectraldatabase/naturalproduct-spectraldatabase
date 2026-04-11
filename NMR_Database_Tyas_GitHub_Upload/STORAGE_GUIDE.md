# Storage and Naming Guide

## Tujuan

Panduan ini menjaga file lokal, Google Drive, dan database tetap sinkron, rapi, mudah dicari, dan tidak duplikasi.

## Struktur folder lokal di Desktop

Project root:

```text
Desktop/NMR_Database_Tyas/
├── .streamlit/
├── database/
│   ├── nmr.db
│   └── backups/
├── data/
│   ├── branding/
│   ├── docs/
│   ├── exports/
│   ├── spectra/
│   ├── structures/
│   ├── submissions/
│   │   ├── inbox/
│   │   ├── reviewed/
│   │   └── approved/
│   └── templates/
└── scripts/
```

## Fungsi tiap folder lokal

- `database/nmr.db`: database utama.
- `database/backups/`: backup sebelum edit besar, import besar, atau deployment.
- `data/structures/`: gambar struktur ringan untuk preview.
- `data/spectra/`: preview spectra ringan, bukan raw file besar.
- `data/templates/`: template CSV dari aplikasi.
- `data/submissions/inbox/`: bahan baru dari mahasiswa, labmate, atau paper yang belum dicek.
- `data/submissions/reviewed/`: bahan yang sudah diperiksa tetapi belum final.
- `data/submissions/approved/`: bahan final yang sudah cocok dengan record database.
- `data/exports/`: hasil ekspor CSV/report untuk dibagikan.
- `data/docs/`: SOP, checklist, atau catatan kurasi.

## Struktur Google Drive yang disarankan

```text
Google Drive/
└── NPDB_Tyas/
    ├── NPDB_Public_Previews/
    ├── NPDB_Raw_Data/
    │   └── <compound_id_or_name>/
    │       ├── 1H/
    │       ├── 13C/
    │       ├── JCAMP_DX/
    │       └── MNova/
    └── NPDB_Submission_Source/
        └── <year>/
            └── <submitter_or_paper>/
```

## Aturan penyimpanan

1. SQLite hanya menyimpan metadata, peak, dan link.
2. Raw data besar disimpan di Google Drive.
3. Preview image boleh lokal atau Google Drive.
4. Satu dataset hanya punya satu file kanonik aktif.
5. Jika ada revisi file, update link file lama atau ganti file lama, jangan buat salinan acak tanpa penanda versi.

## Aturan penamaan file

Gunakan format yang konsisten:

1. Structure preview: `NPDB_<compound_id>_<trivial_name>_structure.png`
2. Spectra preview: `NPDB_<compound_id>_<trivial_name>_<spectrum_type>_preview.png`
3. Raw 1H: `NPDB_<compound_id>_<trivial_name>_1H_raw.<ext>`
4. Raw 13C: `NPDB_<compound_id>_<trivial_name>_13C_raw.<ext>`
5. JCAMP-DX: `NPDB_<compound_id>_<trivial_name>_jcamp.dx`
6. MNova: `NPDB_<compound_id>_<trivial_name>_mnova.mnova`

## Aturan submit

Minimal metadata yang harus ada sebelum record dipublikasikan:

1. Trivial name
2. Molecular formula
3. Compound class
4. Source material
5. Minimal satu dari `SMILES`, `InChI`, atau `InChIKey`
6. Minimal satu spectra preview atau raw-data link

## Anti-duplikasi

Sebelum menambah file atau record:

1. Cari dulu berdasarkan trivial name, sample code, DOI, dan InChIKey.
2. Jika file baru hanya versi lebih rapi dari file lama, ganti file lama.
3. Jika memang versi baru berbeda, tambahkan catatan versi secara eksplisit.
4. Jangan simpan file yang sama di laptop dan Google Drive kecuali memang perlu untuk preview lokal.

## Workflow terbaik

1. File masuk ke `data/submissions/inbox/` atau `NPDB_Submission_Source/`.
2. Kurator cek metadata dan file.
3. File final dipindah ke lokasi kanonik.
4. Link Google Drive atau path preview dimasukkan ke database.
5. Setelah publish, backup database ke `database/backups/`.
