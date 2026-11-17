# BAKESAH Digital — Portal Multi-Role (Fase 1, DATA UJI COBA)

Pendamping edukasi & administratif kesehatan mental ibu hamil. **Fase 1: tanpa skor** (menghindari SaMD).
Aplikasi hanya *mencatat* jawaban EPDS (Buku Saku Kemenkes 2026). **Kategori hasil diisi oleh Bidan**, bukan dihitung aplikasi.

## Menjalankan
```bash
pip install -r requirements.txt
python seed.py --reset      # opsional: buat ulang database uji coba
python app.py               # http://127.0.0.1:5000
python test_e2e.py          # uji otomatis (hak akses, penyimpanan, Excel, audit)
```
Database development: `instance/bakesah_dev.sqlite3` (SQLite, dibuat + di-seed otomatis saat pertama jalan).
Produksi: `BAKESAH_ENV=production BAKESAH_SECRET_KEY=... BAKESAH_DB_PATH=...` (seed dinonaktifkan; akun demo disembunyikan; cookie Secure).
Untuk PostgreSQL/Supabase: skema di `schema.sql` portabel (ganti `AUTOINCREMENT`-style `INTEGER PRIMARY KEY` → `SERIAL`, `ON CONFLICT` sudah kompatibel); lapisan akses ada di `app.py` (`db()`, `q()`).

## Akun demo (khusus development — semua DATA UJI COBA)
| Peran | Email | Kata sandi |
|---|---|---|
| Administrator | admin@bakesah.test | Admin#Dev2026 |
| Bidan 1 / 2 | bidan1@bakesah.test / bidan2@bakesah.test | Bidan#Dev2026 |
| Ibu hamil 01–10 | ibu01@bakesah.test … ibu10@bakesah.test | Ibu#Dev2026 |
Ibu ganjil → Bidan 1, ibu genap → Bidan 2.

## Tabel (11)
users, patient_profiles, midwife_profiles, pregnancy_records, screening_records, screening_results, counseling_sessions, follow_ups, educational_materials, notifications, audit_logs.

## Hak akses (divalidasi di server, bukan hanya UI)
- **Pasien**: hanya data sendiri; tidak pernah menerima catatan internal bidan.
- **Bidan**: hanya pasien yang ditugaskan; menilai skrining, mencatat pendampingan/tindak lanjut; unduh Excel cakupannya.
- **Admin**: kelola akun & penugasan, statistik agregat, log aktivitas, ekspor agregat/individual. **Tidak** melihat jawaban butir maupun catatan internal (minimisasi data).
- Sesi cookie HttpOnly+SameSite, header `X-Requested-With` untuk request pengubah data, pembatasan percobaan login, hash kata sandi (werkzeug), CSP.

## Jalur keselamatan
Pilih opsi **a** pada Pertanyaan 10 → alur berhenti, dialog darurat (IGD / 119 / 112) tampil. Rekaman parsial tersimpan dengan *penanda keselamatan* dan bidan menerima notifikasi prioritas. Ini penanda berbasis aturan Buku Saku, bukan skor.

## Excel (.xlsx)
Pasien: PROFIL, RIWAYAT SKRINING, PENDAMPINGAN. Bidan: RINGKASAN, DATA PASIEN, DATA SKRINING, DATA PENDAMPINGAN, REKAPITULASI. Admin: format bidan versi agregat (tanpa nama) + ekspor individual per pasien.
Header berwarna, freeze header, filter tabel, lebar kolom otomatis, nama file otomatis (peran + periode + waktu). Data kosong → pesan "belum tersedia" (HTTP 404). Setiap ekspor tercatat di audit log.

## Catatan klinis & regulasi
Seluruh data adalah **data uji coba sintetis**. Hasil skrining bukan diagnosis. Instrumen & kategori belum divalidasi klinis oleh pihak berwenang; tinjau kembali sebelum dipakai pada pasien nyata.
