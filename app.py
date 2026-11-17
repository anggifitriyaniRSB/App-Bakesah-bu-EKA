"""BAKESAH Digital — backend API (Flask + SQLite dev). Otorisasi SELALU divalidasi di server."""
import io, json, os, re, sqlite3, time
from datetime import datetime, date, timedelta
from functools import wraps
from flask import Flask, g, jsonify, request, session, send_file, send_from_directory, abort
from werkzeug.security import check_password_hash, generate_password_hash
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import config, instrument as I, seed as S

cfg = config.load()
app = Flask(__name__, static_folder=None)
app.config.update(SECRET_KEY=cfg.SECRET_KEY, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=cfg.COOKIE_SECURE, PERMANENT_SESSION_LIFETIME=timedelta(hours=2), MAX_CONTENT_LENGTH=64*1024)
STATIC = os.path.join(config.BASE, "static")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
FAILS = {}   # rate-limit login sederhana (per email+ip)

# ---------- db ----------
def db():
    if "db" not in g: g.db = S.connect(cfg.DB_PATH)
    return g.db
@app.teardown_appcontext
def _close(_):
    d = g.pop("db", None)
    if d: d.close()
def now(): return datetime.now().isoformat(timespec="seconds")
def q(sql, a=()): return db().execute(sql, a).fetchall()
def q1(sql, a=()): return db().execute(sql, a).fetchone()
def audit(action, target=None, detail=None, uid=None, role=None):
    u = session.get("uid") if uid is None else uid
    db().execute("INSERT INTO audit_logs(user_id,role,action,target,detail,ip,created_at) VALUES(?,?,?,?,?,?,?)",
                 (u, role or session.get("role"), action, target, detail, request.remote_addr, now())); db().commit()

# ---------- auth ----------
def current():
    uid = session.get("uid")
    if not uid: return None
    u = q1("SELECT id,email,role,full_name,is_active FROM users WHERE id=?", (uid,))
    if not u or not u["is_active"]: session.clear(); return None
    return u
def need(*roles):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            u = current()
            if not u: return jsonify(error="Silakan masuk terlebih dahulu."), 401
            if u["role"] not in roles:
                audit("akses_ditolak", request.path); return jsonify(error="Tidak memiliki hak akses."), 403
            g.user = u; return f(*a, **k)
        return w
    return deco
@app.before_request
def csrf_guard():   # SameSite + header kustom untuk request pengubah data
    if request.method in ("POST","PUT","PATCH","DELETE") and request.headers.get("X-Requested-With") != "bakesah":
        return jsonify(error="Permintaan tidak valid."), 400
@app.after_request
def sec(r):
    r.headers.update({"X-Content-Type-Options":"nosniff","X-Frame-Options":"DENY","Referrer-Policy":"no-referrer",
        "Content-Security-Policy":"default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; script-src 'self' 'unsafe-inline'"+(" https://cdnjs.cloudflare.com" if request.path=="/edukasi" else "")+"; frame-ancestors 'none'"})
    if request.path.startswith("/api/"): r.headers["Cache-Control"] = "no-store"
    return r

def clean(v, n=500): return (v or "").strip()[:n] if isinstance(v, str) or v is None else ""
def vdate(v):
    try: return date.fromisoformat(v).isoformat()
    except Exception: return None

@app.get("/api/config")
def api_config(): return jsonify(env=cfg.ENV, demo=cfg.SHOW_DEMO_ACCOUNTS, instrument=I.public(), categories=I.CATEGORIES,
    fu_status=I.FU_STATUS, session_types=I.SESSION_TYPES)

@app.post("/api/login")
def login():
    d = request.get_json(silent=True) or {}; email = clean(d.get("email"),120).lower(); pw = d.get("password") or ""
    key = (email, request.remote_addr); f = FAILS.get(key, (0, 0))
    if f[0] >= 5 and time.time() - f[1] < 300:
        return jsonify(error="Terlalu banyak percobaan. Coba lagi dalam beberapa menit."), 429
    u = q1("SELECT * FROM users WHERE email=?", (email,))
    if not u or not u["is_active"] or not check_password_hash(u["password_hash"], pw):
        FAILS[key] = (f[0]+1, time.time()); audit("login_gagal", email, uid=0, role="-")
        return jsonify(error="Email atau kata sandi tidak sesuai."), 401
    FAILS.pop(key, None); session.clear(); session.permanent = True
    session.update(uid=u["id"], role=u["role"]); audit("login", email)
    return jsonify(user=dict(id=u["id"], role=u["role"], name=u["full_name"]))
@app.post("/api/logout")
def logout():
    if session.get("uid"): audit("logout")
    session.clear(); return jsonify(ok=True)
@app.get("/api/me")
def me():
    u = current()
    if not u: return jsonify(user=None)
    n = q1("SELECT COUNT(*) c FROM notifications WHERE user_id=? AND is_read=0", (u["id"],))["c"]
    return jsonify(user=dict(id=u["id"], role=u["role"], name=u["full_name"]), unread=n)
@app.get("/api/notifications")
@need("patient","midwife","admin")
def notifs():
    rows = [dict(r) for r in q("SELECT id,message,is_read,created_at FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 20", (g.user["id"],))]
    db().execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (g.user["id"],)); db().commit()
    return jsonify(items=rows)
def notify(uid, msg):
    db().execute("INSERT INTO notifications(user_id,message,created_at) VALUES(?,?,?)", (uid, msg, now()))

# ---------- helpers cakupan ----------
def my_patient(user_id): return q1("SELECT * FROM patient_profiles WHERE user_id=?", (user_id,))
def scoped_patient(pid):
    """Pasien dalam cakupan pengguna saat ini (bidan: yang ditugaskan; admin: semua)."""
    p = q1("""SELECT pp.*,u.full_name,u.email FROM patient_profiles pp JOIN users u ON u.id=pp.user_id WHERE pp.id=?""", (pid,))
    if not p: return None
    if g.user["role"] == "midwife" and p["midwife_user_id"] != g.user["id"]: return None
    return p
def pcode(pid): return "P-%04d" % pid
def age(by): return date.today().year - by if by else None
def ga_weeks(lmp):
    try: return (date.today() - date.fromisoformat(lmp)).days // 7
    except Exception: return None
def result_row(r, internal=False):
    d = dict(id=r["id"], date=r["screened_at"], instrument=r["instrument"], visit=r["visit_type"], safety=bool(r["safety_flag"]),
             category=r["category"] or I.CATEGORIES[0], note=r["patient_note"] or "")
    if internal: d.update(internal_note=r["internal_note"] or "", assessed_at=r["assessed_at"])
    return d
SCR_SQL = """SELECT sr.*,res.category,res.patient_note,res.internal_note,res.assessed_at FROM screening_records sr
             LEFT JOIN screening_results res ON res.screening_id=sr.id"""

# ---------- pasien ----------
@app.get("/api/patient/dashboard")
@need("patient")
def pat_dash():
    p = my_patient(g.user["id"]); pid = p["id"]
    preg = q1("SELECT * FROM pregnancy_records WHERE patient_id=? ORDER BY id DESC", (pid,))
    mid = q1("SELECT full_name FROM users WHERE id=?", (p["midwife_user_id"],)) if p["midwife_user_id"] else None
    scr = [result_row(r) for r in q(SCR_SQL+" WHERE sr.patient_id=? ORDER BY sr.screened_at DESC", (pid,))]
    ses = [dict(date=r["session_date"], type=r["session_type"], summary=r["patient_summary"] or "") for r in
           q("SELECT * FROM counseling_sessions WHERE patient_id=? ORDER BY session_date DESC", (pid,))]
    fu = [dict(action=r["action"], due=r["due_date"], status=r["status"]) for r in
          q("SELECT * FROM follow_ups WHERE patient_id=? ORDER BY id DESC", (pid,))]
    mats = [dict(r) for r in q("SELECT id,title,body,topic FROM educational_materials ORDER BY id")]
    return jsonify(profile=dict(name=g.user["full_name"], email=g.user["email"], age=age(p["birth_year"]), registered=p["registered_at"], midwife=mid["full_name"] if mid else None),
        pregnancy=dict(ga_weeks=ga_weeks(preg["lmp_date"]), edd=preg["edd_date"], gravida=preg["gravida"], para=preg["para"], status=preg["status"]) if preg else None,
        screenings=scr, sessions=ses, followups=fu, materials=mats)
@app.post("/api/patient/screenings")
@need("patient")
def pat_screen():
    d = request.get_json(silent=True) or {}; ans = d.get("answers"); visit = d.get("visit")
    if visit not in I.VISITS or not isinstance(ans, dict): return jsonify(error="Data skrining tidak valid."), 400
    if any(k not in I.IDS or v not in list(I.LETTERS) for k, v in ans.items()): return jsonify(error="Jawaban tidak valid."), 400
    safety = ans.get(I.SAFETY_ITEM) == I.SAFETY_OPTION
    if not safety and set(ans) != set(I.IDS): return jsonify(error="Mohon jawab semua pertanyaan."), 400
    p = my_patient(g.user["id"])
    sid = db().execute("INSERT INTO screening_records(patient_id,instrument,visit_type,answers_json,safety_flag,screened_at) VALUES(?,?,?,?,?,?)",
        (p["id"], "EPDS Kemenkes 2026", visit, json.dumps(ans), int(safety), now())).lastrowid
    if p["midwife_user_id"]:
        notify(p["midwife_user_id"], ("[PRIORITAS] " if safety else "")+f"Skrining baru dari {pcode(p['id'])} menunggu penilaian.")
    db().commit(); audit("skrining_dibuat", f"screening:{sid}", "safety_stop" if safety else "lengkap")
    return jsonify(id=sid, safety=safety, safety_text=I.SAFETY_TEXT if safety else None)
@app.get("/api/patient/export.xlsx")
@need("patient")
def pat_export():
    p = my_patient(g.user["id"]); pid = p["id"]
    preg = q1("SELECT * FROM pregnancy_records WHERE patient_id=? ORDER BY id DESC", (pid,))
    scr = q(SCR_SQL+" WHERE sr.patient_id=? ORDER BY sr.screened_at", (pid,))
    ses = q("SELECT * FROM counseling_sessions WHERE patient_id=? ORDER BY session_date", (pid,))
    fu = q("SELECT * FROM follow_ups WHERE patient_id=?", (pid,))
    if not scr and not ses: audit("ekspor_kosong","pasien"); return jsonify(error="Data laporan belum tersedia."), 404
    wb = Workbook(); wb.remove(wb.active)
    sheet(wb,"PROFIL",["Kolom","Isi"],[["Nama",g.user["full_name"]],["Email",g.user["email"]],["Usia",age(p["birth_year"]) or ""],
        ["Tanggal registrasi",p["registered_at"]],["Usia kehamilan (minggu)",ga_weeks(preg["lmp_date"]) if preg else ""],
        ["Perkiraan persalinan",preg["edd_date"] if preg else ""],["Status kehamilan",preg["status"] if preg else ""]])
    sheet(wb,"RIWAYAT SKRINING",["Tanggal skrining","Jenis skrining","Kunjungan","Hasil / kategori (penilaian tenaga kesehatan)","Catatan untuk Bunda"],
        [[r["screened_at"],r["instrument"],r["visit_type"],r["category"] or I.CATEGORIES[0],r["patient_note"] or ""] for r in scr])
    fmap = {}
    for f in fu: fmap.setdefault(f["midwife_user_id"], []).append(f["status"])
    sheet(wb,"PENDAMPINGAN",["Tanggal pendampingan","Jenis pendampingan","Ringkasan","Status tindak lanjut"],
        [[r["session_date"],r["session_type"],r["patient_summary"] or "",", ".join(sorted(set(fmap.get(r["midwife_user_id"],[])))) or "-"] for r in ses])
    audit("ekspor_xlsx", "pasien", f"pid={pid}")
    return xlsx(wb, "Pasien", None, None)

# ---------- bidan / admin: data bercakupan ----------
def period_args():
    frm = vdate(request.args.get("from")) or (date.today()-timedelta(days=90)).isoformat()
    to = vdate(request.args.get("to")) or date.today().isoformat()
    st = request.args.get("status"); st = st if st in I.FU_STATUS else None
    grp = request.args.get("group"); grp = grp if grp in ("day","week","month") else "week"
    return frm, to, st, grp
def collect(frm, to, st):
    mid = g.user["id"] if g.user["role"] == "midwife" else None
    where, a = ("WHERE pp.midwife_user_id=?", [mid]) if mid else ("WHERE 1=1", [])
    pats = q(f"""SELECT pp.*,u.full_name,u.email,(SELECT u2.full_name FROM users u2 WHERE u2.id=pp.midwife_user_id) mname
                 FROM patient_profiles pp JOIN users u ON u.id=pp.user_id {where} ORDER BY pp.id""", a)
    if st:
        ok = {r["patient_id"] for r in q("SELECT patient_id FROM follow_ups WHERE status=? AND date(created_at) BETWEEN ? AND ?", (st, frm, to))}
        pats = [p for p in pats if p["id"] in ok]
    ids = [p["id"] for p in pats]; ph = ",".join("?"*len(ids)) or "NULL"
    scr = q(SCR_SQL+f" WHERE sr.patient_id IN ({ph}) AND date(sr.screened_at) BETWEEN ? AND ? ORDER BY sr.screened_at", ids+[frm,to])
    ses = q(f"SELECT * FROM counseling_sessions WHERE patient_id IN ({ph}) AND session_date BETWEEN ? AND ? ORDER BY session_date", ids+[frm,to])
    fus = q(f"SELECT * FROM follow_ups WHERE patient_id IN ({ph}) AND date(created_at) BETWEEN ? AND ?"+(" AND status=?" if st else "")+" ORDER BY id", ids+[frm,to]+([st] if st else []))
    return pats, scr, ses, fus
def bucket(ds, grp):
    d = date.fromisoformat(ds[:10])
    if grp == "day": return d.isoformat()
    if grp == "month": return d.strftime("%Y-%m")
    return (d - timedelta(days=d.weekday())).isoformat()
def summarize(pats, scr, ses, fus, grp):
    cat = {c: 0 for c in I.CATEGORIES}
    for r in scr: cat[r["category"] or I.CATEGORIES[0]] += 1
    fs = {s: 0 for s in I.FU_STATUS}
    for f in fus: fs[f["status"]] += 1
    series = {}
    for r in scr:
        b = series.setdefault(bucket(r["screened_at"], grp), {"screenings": 0, "sessions": 0}); b["screenings"] += 1
    for r in ses:
        b = series.setdefault(bucket(r["session_date"], grp), {"screenings": 0, "sessions": 0}); b["sessions"] += 1
    need_fu = len({f["patient_id"] for f in fus if f["status"] != "Selesai"})
    return dict(patients=len(pats), screenings=len(scr), sessions=len(ses), categories=cat, followups=fs, need_followup=need_fu,
                series=[dict(period=k, **v) for k, v in sorted(series.items())])

@app.get("/api/staff/dashboard")
@need("midwife","admin")
def staff_dash():
    frm, to, st, grp = period_args(); pats, scr, ses, fus = collect(frm, to, st)
    last = {}
    for r in scr: last[r["patient_id"]] = r["category"] or I.CATEGORIES[0]
    pl = [dict(id=p["id"], code=pcode(p["id"]), name=p["full_name"] if g.user["role"]=="midwife" else None, age=age(p["birth_year"]),
               ga_weeks=(lambda r: ga_weeks(r["lmp_date"]) if r else None)(q1("SELECT lmp_date FROM pregnancy_records WHERE patient_id=? ORDER BY id DESC",(p["id"],))),
               midwife=p["mname"], last_category=last.get(p["id"], "-"),
               pending=sum(1 for f in fus if f["patient_id"]==p["id"] and f["status"]!="Selesai")) for p in pats]
    return jsonify(range=dict(frm=frm, to=to, status=st, group=grp), summary=summarize(pats, scr, ses, fus, grp), patients=pl)

@app.get("/api/midwife/patients/<int:pid>")
@need("midwife")
def mw_patient(pid):
    p = scoped_patient(pid)
    if not p: audit("akses_ditolak", f"patient:{pid}"); return jsonify(error="Pasien tidak ditemukan dalam cakupan Bunda."), 404
    audit("lihat_pasien", f"patient:{pid}")
    preg = q1("SELECT * FROM pregnancy_records WHERE patient_id=? ORDER BY id DESC", (pid,))
    scr = []
    for r in q(SCR_SQL+" WHERE sr.patient_id=? ORDER BY sr.screened_at DESC", (pid,)):
        d = result_row(r, True); d["answers"] = [dict(q=t, a=(lambda L: f"{L}. {I.answer_text(i,L)}")(json.loads(r["answers_json"]).get(i)) if json.loads(r["answers_json"]).get(i) else "— (tidak dijawab)") for i,t,_ in I.ITEMS]; scr.append(d)
    return jsonify(patient=dict(id=pid, code=pcode(pid), name=p["full_name"], age=age(p["birth_year"]), registered=p["registered_at"],
                   ga_weeks=ga_weeks(preg["lmp_date"]) if preg else None, edd=preg["edd_date"] if preg else None),
        screenings=scr,
        sessions=[dict(r) for r in q("SELECT id,session_date,session_type,patient_summary,internal_note FROM counseling_sessions WHERE patient_id=? ORDER BY session_date DESC", (pid,))],
        followups=[dict(r) for r in q("SELECT id,action,due_date,status,screening_id FROM follow_ups WHERE patient_id=? ORDER BY id DESC", (pid,))])
@app.post("/api/midwife/screenings/<int:sid>/assess")
@need("midwife")
def mw_assess(sid):
    s = q1("SELECT * FROM screening_records WHERE id=?", (sid,))
    if not s or not scoped_patient(s["patient_id"]): audit("akses_ditolak", f"screening:{sid}"); return jsonify(error="Tidak ditemukan."), 404
    d = request.get_json(silent=True) or {}
    if d.get("category") not in I.CATEGORIES[1:]: return jsonify(error="Kategori tidak valid."), 400
    db().execute("""INSERT INTO screening_results(screening_id,category,patient_note,internal_note,assessed_by,assessed_at) VALUES(?,?,?,?,?,?)
        ON CONFLICT(screening_id) DO UPDATE SET category=excluded.category,patient_note=excluded.patient_note,internal_note=excluded.internal_note,assessed_by=excluded.assessed_by,assessed_at=excluded.assessed_at""",
        (sid, d["category"], clean(d.get("patient_note")), clean(d.get("internal_note")), g.user["id"], now()))
    pu = q1("SELECT user_id FROM patient_profiles WHERE id=?", (s["patient_id"],))["user_id"]
    notify(pu, "Hasil skrining Bunda sudah dinilai oleh tenaga kesehatan."); db().commit()
    audit("penilaian_skrining", f"screening:{sid}", d["category"]); return jsonify(ok=True)
@app.post("/api/midwife/sessions")
@need("midwife")
def mw_session():
    d = request.get_json(silent=True) or {}; p = scoped_patient(d.get("patient_id") if isinstance(d.get("patient_id"), int) else -1)
    if not p: return jsonify(error="Pasien di luar cakupan."), 404
    if d.get("type") not in I.SESSION_TYPES or not vdate(d.get("date")): return jsonify(error="Tanggal/jenis tidak valid."), 400
    i = db().execute("INSERT INTO counseling_sessions(patient_id,midwife_user_id,session_date,session_type,patient_summary,internal_note,created_at) VALUES(?,?,?,?,?,?,?)",
        (p["id"], g.user["id"], vdate(d["date"]), d["type"], clean(d.get("summary")), clean(d.get("internal_note")), now())).lastrowid
    db().commit(); audit("pendampingan_dicatat", f"session:{i}"); return jsonify(id=i)
@app.post("/api/midwife/followups")
@need("midwife")
def mw_fu():
    d = request.get_json(silent=True) or {}; p = scoped_patient(d.get("patient_id") if isinstance(d.get("patient_id"), int) else -1)
    if not p or not clean(d.get("action")): return jsonify(error="Data tidak valid."), 400
    due = vdate(d.get("due")) if d.get("due") else None
    i = db().execute("INSERT INTO follow_ups(patient_id,midwife_user_id,action,due_date,status,created_at) VALUES(?,?,?,?,?,?)",
        (p["id"], g.user["id"], clean(d["action"],300), due, "Direncanakan", now())).lastrowid
    db().commit(); audit("tindak_lanjut_dibuat", f"followup:{i}"); return jsonify(id=i)
@app.patch("/api/midwife/followups/<int:fid>")
@need("midwife")
def mw_fu_upd(fid):
    f = q1("SELECT * FROM follow_ups WHERE id=?", (fid,)); d = request.get_json(silent=True) or {}
    if not f or not scoped_patient(f["patient_id"]) or d.get("status") not in I.FU_STATUS: return jsonify(error="Tidak ditemukan."), 404
    db().execute("UPDATE follow_ups SET status=? WHERE id=?", (d["status"], fid)); db().commit()
    audit("tindak_lanjut_diubah", f"followup:{fid}", d["status"]); return jsonify(ok=True)

# ---------- Excel ----------
HF = Font(bold=True, color="FFFFFF"); HFILL = PatternFill("solid", fgColor="602B75"); THIN = Side(style="thin", color="E7DFEC")
def sheet(wb, title, headers, rows):
    ws = wb.create_sheet(title); ws.append(headers)
    for r in rows: ws.append(list(r))
    for c in ws[1]: c.font = HF; c.fill = HFILL; c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for row in ws.iter_rows(min_row=2):
        for c in row: c.alignment = Alignment(vertical="top", wrap_text=True); c.border = Border(bottom=THIN)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{max(len(rows),1)+1}"
    for i, h in enumerate(headers, 1):
        w = max([len(str(h))] + [len(str(r[i-1])) for r in rows if i-1 < len(r)]) + 3
        ws.column_dimensions[get_column_letter(i)].width = min(max(w, 12), 60)
    return ws
def xlsx(wb, who, frm, to):
    b = io.BytesIO(); wb.save(b); b.seek(0)
    per = f"_{frm}_sd_{to}" if frm else ""
    name = f"BAKESAH_Laporan_{who}{per}_{datetime.now():%Y%m%d-%H%M%S}.xlsx"
    return send_file(b, as_attachment=True, download_name=name, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
@app.get("/api/staff/export.xlsx")
@need("midwife","admin")
def staff_export():
    frm, to, st, grp = period_args(); pats, scr, ses, fus = collect(frm, to, st); mw = g.user["role"] == "midwife"
    if not scr and not ses:
        audit("ekspor_kosong", g.user["role"], f"{frm}..{to}"); return jsonify(error="Data belum tersedia untuk periode/filter ini."), 404
    sm = summarize(pats, scr, ses, fus, grp); wb = Workbook(); wb.remove(wb.active)
    rows = [["Periode laporan", f"{frm} s.d. {to}"], ["Filter status tindak lanjut", st or "Semua"], ["Total pasien", sm["patients"]],
            ["Total skrining", sm["screenings"]], ["Total pendampingan", sm["sessions"]]]
    rows += [[f"Kategori: {k}", v] for k, v in sm["categories"].items()] + [[f"Tindak lanjut: {k}", v] for k, v in sm["followups"].items()]
    sheet(wb, "RINGKASAN", ["Keterangan", "Nilai"], rows)
    pid_cat = {}
    sheet(wb, "DATA PASIEN", ["ID pasien"]+(["Nama (data uji coba)"] if mw else [])+["Usia","Usia kehamilan (minggu)","Bidan penanggung jawab","Status pendampingan"],
        [[pcode(p["id"])]+([p["full_name"]] if mw else [])+[age(p["birth_year"]) or "",
         (lambda r: ga_weeks(r["lmp_date"]) if r else "")(q1("SELECT lmp_date FROM pregnancy_records WHERE patient_id=? ORDER BY id DESC",(p["id"],))),
         p["mname"] or "-", "Didampingi" if any(s["patient_id"]==p["id"] for s in ses) else "Belum ada sesi pada periode"] for p in pats])
    sheet(wb, "DATA SKRINING", ["ID skrining","ID pasien","Tanggal skrining","Jenis skrining","Kunjungan","Hasil / kategori (penilaian tenaga kesehatan)","Penanda keselamatan"],
        [[f"S-{r['id']:05d}",pcode(r["patient_id"]),r["screened_at"],r["instrument"],r["visit_type"],r["category"] or I.CATEGORIES[0],"Ya" if r["safety_flag"] else "Tidak"] for r in scr])
    ses_fu = {}
    for f in fus: ses_fu.setdefault(f["patient_id"], set()).add(f["status"])
    sheet(wb, "DATA PENDAMPINGAN", ["ID pendampingan","ID pasien","Tanggal pendampingan","Jenis pendampingan","Status tindak lanjut"],
        [[f"C-{r['id']:05d}",pcode(r["patient_id"]),r["session_date"],r["session_type"],", ".join(sorted(ses_fu.get(r["patient_id"],[]))) or "-"] for r in ses])
    rec = [[k,"Skrining",v["screenings"]] for k,v in [(x["period"],x) for x in sm["series"]]] + [[k,"Pendampingan",v["sessions"]] for k,v in [(x["period"],x) for x in sm["series"]]]
    rec += [["Distribusi kategori", k, v] for k, v in sm["categories"].items()] + [["Rekap tindak lanjut", k, v] for k, v in sm["followups"].items()]
    sheet(wb, "REKAPITULASI", ["Periode / kelompok", "Jenis", "Jumlah"], rec)
    audit("ekspor_xlsx", g.user["role"], f"{frm}..{to} status={st or '-'}")
    return xlsx(wb, "Bidan" if mw else "Admin", frm, to)

# ---------- admin ----------
@app.get("/api/admin/users")
@need("admin")
def adm_users():
    rows = [dict(r) for r in q("""SELECT u.id,u.email,u.role,u.full_name,u.is_active,u.is_test_data,pp.id pid,pp.midwife_user_id mid
        FROM users u LEFT JOIN patient_profiles pp ON pp.user_id=u.id ORDER BY u.role,u.id""")]
    return jsonify(users=rows, midwives=[dict(id=r["id"], name=r["full_name"]) for r in q("SELECT id,full_name FROM users WHERE role='midwife' AND is_active=1")])
@app.post("/api/admin/users")
@need("admin")
def adm_create():
    d = request.get_json(silent=True) or {}; email = clean(d.get("email"),120).lower(); name = clean(d.get("name"),100)
    if d.get("role") not in ("patient","midwife") or not EMAIL_RE.match(email) or len(name) < 3 or len(d.get("password") or "") < 10:
        return jsonify(error="Data tidak valid (kata sandi minimal 10 karakter)."), 400
    if q1("SELECT 1 FROM users WHERE email=?", (email,)): return jsonify(error="Email sudah terdaftar."), 409
    uid = db().execute("INSERT INTO users(email,password_hash,role,full_name,created_at) VALUES(?,?,?,?,?)",
        (email, generate_password_hash(d["password"]), d["role"], name, now())).lastrowid
    if d["role"] == "patient":
        db().execute("INSERT INTO patient_profiles(user_id,registered_at) VALUES(?,?)", (uid, date.today().isoformat()))
        db().execute("INSERT INTO pregnancy_records(patient_id) VALUES((SELECT id FROM patient_profiles WHERE user_id=?))", (uid,))
    else: db().execute("INSERT INTO midwife_profiles(user_id) VALUES(?)", (uid,))
    db().commit(); audit("pengguna_dibuat", f"user:{uid}", d["role"]); return jsonify(id=uid)
@app.patch("/api/admin/users/<int:uid>")
@need("admin")
def adm_toggle(uid):
    u = q1("SELECT * FROM users WHERE id=?", (uid,)); d = request.get_json(silent=True) or {}
    if not u or u["id"] == g.user["id"] or u["role"] == "admin": return jsonify(error="Tidak dapat diubah."), 400
    db().execute("UPDATE users SET is_active=? WHERE id=?", (1 if d.get("active") else 0, uid)); db().commit()
    audit("pengguna_diubah", f"user:{uid}", f"active={bool(d.get('active'))}"); return jsonify(ok=True)
@app.post("/api/admin/assign")
@need("admin")
def adm_assign():
    d = request.get_json(silent=True) or {}
    p = q1("SELECT id FROM patient_profiles WHERE id=?", (d.get("patient_id") if isinstance(d.get("patient_id"),int) else -1,))
    m = q1("SELECT id FROM users WHERE id=? AND role='midwife' AND is_active=1", (d.get("midwife_id") if isinstance(d.get("midwife_id"),int) else -1,))
    if not p or not m: return jsonify(error="Pasien/bidan tidak valid."), 400
    db().execute("UPDATE patient_profiles SET midwife_user_id=? WHERE id=?", (m["id"], p["id"])); db().commit()
    audit("penugasan", f"patient:{p['id']}", f"midwife:{m['id']}"); return jsonify(ok=True)
@app.get("/api/admin/audit")
@need("admin")
def adm_audit():
    return jsonify(items=[dict(r) for r in q("""SELECT a.id,a.created_at,a.role,a.action,a.target,a.detail,u.email FROM audit_logs a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 200""")])
@app.get("/api/admin/export-patient/<int:pid>.xlsx")
@need("admin")
def adm_patient_export(pid):
    p = scoped_patient(pid)
    if not p: return jsonify(error="Pasien tidak ditemukan."), 404
    scr = q(SCR_SQL+" WHERE sr.patient_id=? ORDER BY sr.screened_at", (pid,)); ses = q("SELECT * FROM counseling_sessions WHERE patient_id=? ORDER BY session_date", (pid,))
    if not scr and not ses: return jsonify(error="Data laporan belum tersedia."), 404
    wb = Workbook(); wb.remove(wb.active)   # tanpa jawaban butir & tanpa catatan internal
    sheet(wb,"RIWAYAT SKRINING",["ID pasien","Tanggal","Kunjungan","Kategori (penilaian tenaga kesehatan)"],[[pcode(pid),r["screened_at"],r["visit_type"],r["category"] or I.CATEGORIES[0]] for r in scr])
    sheet(wb,"PENDAMPINGAN",["ID pasien","Tanggal","Jenis"],[[pcode(pid),r["session_date"],r["session_type"]] for r in ses])
    audit("ekspor_xlsx","admin-individual",f"pid={pid}"); return xlsx(wb, f"Individual_{pcode(pid)}", None, None)

# ---------- static ----------
@app.get("/")
def index(): return send_from_directory(STATIC, "index.html")
@app.get("/static/<path:f>")
def static_files(f):
    if f not in ("logo-full.jpg","logo-mark.jpg"): abort(404)
    return send_from_directory(STATIC, f)
@app.get("/edukasi")
def edukasi(): return send_from_directory(STATIC, "edukasi.html")
@app.get("/healthz")
def health(): return jsonify(ok=True, env=cfg.ENV)

def init():
    c = S.connect(cfg.DB_PATH); S.migrate(c)
    if cfg.ENV != "production": S.seed(c)
    c.close()
init()
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False)
