PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN('patient','midwife','admin')), full_name TEXT NOT NULL,
 is_active INTEGER NOT NULL DEFAULT 1, is_test_data INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS midwife_profiles(
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
 facility TEXT, str_number_test TEXT);
CREATE TABLE IF NOT EXISTS patient_profiles(
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
 midwife_user_id INTEGER REFERENCES users(id), birth_year INTEGER, registered_at TEXT NOT NULL, village TEXT);
CREATE TABLE IF NOT EXISTS pregnancy_records(
 id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL REFERENCES patient_profiles(id) ON DELETE CASCADE,
 lmp_date TEXT, edd_date TEXT, gravida INTEGER, para INTEGER, status TEXT NOT NULL DEFAULT 'Hamil');
CREATE TABLE IF NOT EXISTS screening_records(
 id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL REFERENCES patient_profiles(id) ON DELETE CASCADE,
 instrument TEXT NOT NULL, visit_type TEXT NOT NULL, answers_json TEXT NOT NULL,
 safety_flag INTEGER NOT NULL DEFAULT 0, screened_at TEXT NOT NULL);
-- Fase 1: aplikasi TIDAK menghitung skor. Kategori diisi oleh tenaga kesehatan.
CREATE TABLE IF NOT EXISTS screening_results(
 id INTEGER PRIMARY KEY, screening_id INTEGER NOT NULL UNIQUE REFERENCES screening_records(id) ON DELETE CASCADE,
 category TEXT NOT NULL, patient_note TEXT, internal_note TEXT,
 assessed_by INTEGER NOT NULL REFERENCES users(id), assessed_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS counseling_sessions(
 id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL REFERENCES patient_profiles(id) ON DELETE CASCADE,
 midwife_user_id INTEGER NOT NULL REFERENCES users(id), session_date TEXT NOT NULL, session_type TEXT NOT NULL,
 patient_summary TEXT, internal_note TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS follow_ups(
 id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL REFERENCES patient_profiles(id) ON DELETE CASCADE,
 midwife_user_id INTEGER NOT NULL REFERENCES users(id), screening_id INTEGER REFERENCES screening_records(id),
 action TEXT NOT NULL, due_date TEXT, status TEXT NOT NULL DEFAULT 'Direncanakan', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS educational_materials(
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL, topic TEXT);
CREATE TABLE IF NOT EXISTS notifications(
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 message TEXT NOT NULL, is_read INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_logs(
 id INTEGER PRIMARY KEY, user_id INTEGER, role TEXT, action TEXT NOT NULL, target TEXT, detail TEXT,
 ip TEXT, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_scr_patient ON screening_records(patient_id, screened_at);
CREATE INDEX IF NOT EXISTS ix_pat_midwife ON patient_profiles(midwife_user_id);
CREATE INDEX IF NOT EXISTS ix_cs_patient ON counseling_sessions(patient_id, session_date);
CREATE INDEX IF NOT EXISTS ix_fu_patient ON follow_ups(patient_id);
