"""Seed DATA UJI COBA (sintetis). Jalankan: python seed.py [--reset]"""
import sqlite3, json, os, sys, random
from datetime import datetime, timedelta, date
from werkzeug.security import generate_password_hash
import config, instrument as I

def connect(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    c = sqlite3.connect(path); c.row_factory = sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); return c

def migrate(c):
    c.executescript(open(os.path.join(config.BASE,"schema.sql"),encoding="utf8").read()); c.commit()

DEMO = {"admin":("admin@bakesah.test","Admin#Dev2026"),
        "midwife1":("bidan1@bakesah.test","Bidan#Dev2026"),
        "midwife2":("bidan2@bakesah.test","Bidan#Dev2026"),
        "patient":("ibu01@bakesah.test","Ibu#Dev2026")}   # ibu01..ibu10 (password sama)

def seed(c):
    if c.execute("SELECT COUNT(*) FROM users").fetchone()[0]: return False
    rnd = random.Random(2026); today = date.today(); now = datetime.now().replace(microsecond=0)
    ts = lambda d: d.isoformat(timespec="seconds")
    def user(email, pw, role, name):
        return c.execute("INSERT INTO users(email,password_hash,role,full_name,created_at) VALUES(?,?,?,?,?)",
            (email, generate_password_hash(pw), role, name, ts(now))).lastrowid
    user(*DEMO["admin"],"admin","[UJI COBA] Administrator Uji")
    mids = []
    for n,k in enumerate(("midwife1","midwife2"),1):
        u = user(*DEMO[k],"midwife",f"[UJI COBA] Bidan Uji {n}"); mids.append(u)
        c.execute("INSERT INTO midwife_profiles(user_id,facility,str_number_test) VALUES(?,?,?)",(u,"Fasilitas Uji Coba",f"STR-UJI-{n:03d}"))
    pats = []
    for n in range(1,11):
        u = user(f"ibu{n:02d}@bakesah.test", DEMO["patient"][1], "patient", f"[UJI COBA] Ibu Uji {n:02d}")
        reg = today - timedelta(days=rnd.randint(40,120))
        p = c.execute("INSERT INTO patient_profiles(user_id,midwife_user_id,birth_year,registered_at,village) VALUES(?,?,?,?,?)",
            (u, mids[(n-1)%2], rnd.randint(1988,2005), reg.isoformat(), "Wilayah Uji Coba")).lastrowid
        lmp = today - timedelta(weeks=rnd.randint(8,36))
        c.execute("INSERT INTO pregnancy_records(patient_id,lmp_date,edd_date,gravida,para) VALUES(?,?,?,?,?)",
            (p, lmp.isoformat(), (lmp+timedelta(days=280)).isoformat(), rnd.randint(1,4), rnd.randint(0,3)))
        pats.append((p, mids[(n-1)%2], reg))
    cats = I.CATEGORIES[1:]
    for idx,(p,m,reg) in enumerate(pats):
        for k in range(rnd.randint(1,3)):
            when = datetime.combine(min(today, reg + timedelta(days=rnd.randint(0,(today-reg).days))), datetime.min.time()) + timedelta(hours=rnd.randint(8,16))
            ans = {i: rnd.choice("abcd") for i in I.IDS}
            ans["e10"] = rnd.choice("bcdd")
            if idx == 3 and k == 0: ans["e10"] = "a"      # satu kasus keselamatan sintetis
            flag = int(ans["e10"] == "a")
            s = c.execute("INSERT INTO screening_records(patient_id,instrument,visit_type,answers_json,safety_flag,screened_at) VALUES(?,?,?,?,?,?)",
                (p,"EPDS Kemenkes 2026",I.VISITS[min(k,2)],json.dumps(ans),flag,ts(when))).lastrowid
            if rnd.random() < 0.8 or flag:
                cat = I.CATEGORIES[3] if flag else rnd.choice(cats)
                c.execute("INSERT INTO screening_results(screening_id,category,patient_note,internal_note,assessed_by,assessed_at) VALUES(?,?,?,?,?,?)",
                    (s,cat,"Terima kasih sudah mengisi. Silakan berdiskusi dengan bidan pada kunjungan berikutnya." if cat!=cats[0] else "Tetap jaga istirahat dan terus terhubung dengan keluarga.",
                     "[UJI COBA] catatan internal bidan — tidak untuk pasien.",m,ts(when+timedelta(days=1))))
                if cat != cats[0]:
                    c.execute("INSERT INTO follow_ups(patient_id,midwife_user_id,screening_id,action,due_date,status,created_at) VALUES(?,?,?,?,?,?,?)",
                        (p,m,s,"Evaluasi lanjutan dan pendampingan" if flag else "Pantau kondisi pada kunjungan berikutnya",
                         (when.date()+timedelta(days=rnd.randint(3,14))).isoformat(), rnd.choice(I.FU_STATUS), ts(when+timedelta(days=1))))
        for k in range(rnd.randint(0,3)):
            d = today - timedelta(days=rnd.randint(1,60))
            c.execute("INSERT INTO counseling_sessions(patient_id,midwife_user_id,session_date,session_type,patient_summary,internal_note,created_at) VALUES(?,?,?,?,?,?,?)",
                (p,m,d.isoformat(),rnd.choice(I.SESSION_TYPES),"Membahas rutinitas tidur dan dukungan keluarga. (data uji coba)","[UJI COBA] catatan internal bidan.",ts(now)))
    for t,b,tp in [
        ("Mengenali perubahan perasaan selama hamil","Perubahan suasana hati saat hamil adalah hal yang umum. Bila perasaan sedih atau cemas berlangsung lama, bicarakan dengan bidan.","Dasar"),
        ("Tidur yang cukup untuk ibu hamil","Atur rutinitas malam yang tenang dan minta dukungan pendamping untuk berbagi tugas rumah.","Rutinitas"),
        ("Relaksasi napas sederhana","Tarik napas perlahan melalui hidung, hembuskan perlahan melalui mulut selama beberapa menit.","Relaksasi"),
        ("Kapan perlu bantuan segera","Bila ada pikiran menyakiti diri, segera minta pendamping ke IGD terdekat atau hubungi 119/112.","Keselamatan"),
        ("Dukungan pendamping dan keluarga","Ceritakan perasaan Bunda kepada orang yang dipercaya dan libatkan pendamping saat kunjungan.","Dukungan"),
        ("Mengenal skrining EPDS","EPDS adalah pertanyaan tentang perasaan 7 hari terakhir. Penilaian hasil dilakukan oleh Bidan, Dokter, atau Psikolog Klinis.","Skrining")]:
        c.execute("INSERT INTO educational_materials(title,body,topic) VALUES(?,?,?)",(t,b,tp))
    for u in [r[0] for r in c.execute("SELECT id FROM users WHERE role='midwife'")]:
        c.execute("INSERT INTO notifications(user_id,message,created_at) VALUES(?,?,?)",(u,"[UJI COBA] Ada skrining pasien yang menunggu penilaian.",ts(now)))
    c.execute("INSERT INTO audit_logs(user_id,role,action,target,detail,created_at) VALUES(NULL,'system','seed','database','Data uji coba sintetis dibuat',?)",(ts(now),))
    c.commit(); return True

if __name__ == "__main__":
    cfg = config.load()
    if cfg.ENV == "production": sys.exit("Seed uji coba tidak boleh dijalankan di produksi.")
    if "--reset" in sys.argv and os.path.exists(cfg.DB_PATH): os.remove(cfg.DB_PATH)
    c = connect(cfg.DB_PATH); migrate(c)
    print("Seed dibuat" if seed(c) else "Database sudah berisi data (pakai --reset untuk mengulang)")
