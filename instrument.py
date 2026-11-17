"""EPDS Buku Saku Kemenkes 2026 — teks baku. TIDAK ada penskoran di Fase 1 (menghindari SaMD)."""
ITEMS = [
 ("e1","Saya dapat tertawa dan melihat segi kelucuan hal-hal tertentu:",["Seperti biasanya","Sekarang tidak terlalu sering","Sekarang agak jarang","Tidak sama sekali"]),
 ("e2","Saya menanti-nanti untuk melakukan sesuatu dengan penuh harapan:",["Hampir seperti biasanya","Agak berkurang dari biasanya","Jelas berkurang dari biasanya","Hampir tidak sama sekali"]),
 ("e3","Saya menyalahkan diri sendiri jika ada sesuatu yang tidak berjalan dengan baik:",["Ya, hampir selalu","Ya, kadang-kadang","Tidak terlalu sering","Tidak, tidak pernah"]),
 ("e4","Saya merasa cemas atau khawatir tanpa alasan:",["Tidak, tidak sama sekali","Hampir tidak pernah","Ya, kadang-kadang","Ya, amat sering"]),
 ("e5","Saya merasa takut atau panik tanpa alasan:",["Ya, sering sekali","Ya, kadang-kadang","Tidak, tidak terlalu","Tidak, tidak pernah sama sekali"]),
 ("e6","Banyak hal menjadi beban untuk saya:",["Ya, seringkali saya sama sekali tidak dapat mengatasinya","Ya, kadang saya tidak dapat mengatasi seperti biasanya","Tidak, biasanya saya dapat mengatasinya dengan baik","Tidak, saya dapat mengatasinya dengan baik seperti biasanya"]),
 ("e7","Saya merasa begitu sedih sampai sulit tidur:",["Ya, hampir selalu","Ya, kadang-kadang","Tidak, tidak sering","Tidak, tidak pernah"]),
 ("e8","Saya merasa sedih atau susah:",["Ya, hampir selalu","Ya, sering","Jarang","Tidak pernah"]),
 ("e9","Saya merasa sangat sedih sehingga saya menangis:",["Ya, hampir selalu","Ya, sering","Hanya sekali-kali","Tidak pernah"]),
 ("e10","Pikiran untuk mencelakai diri sendiri sering muncul:",["Ya, agak sering","Kadang-kadang","Hampir tidak pernah","Tidak pernah"]),
]
IDS = [i[0] for i in ITEMS]
LETTERS = "abcd"
SAFETY_ITEM, SAFETY_OPTION = "e10", "a"
VISITS = ["K1 (Kunjungan Pertama)", "K5 (Kunjungan Kelima)", "KF3 (Nifas Ketiga)"]
CATEGORIES = ["Belum dinilai","Tidak memerlukan tindak lanjut khusus","Perlu pemantauan","Perlu evaluasi lanjutan oleh tenaga kesehatan"]
FU_STATUS = ["Direncanakan","Berjalan","Selesai"]
SESSION_TYPES = ["Konseling tatap muka","Kunjungan rumah","Konsultasi daring","Pendampingan kelompok"]
SAFETY_TEXT = "Keselamatan Bunda adalah prioritas. Segera minta pendamping dan pergi ke IGD Rumah Sakit terdekat, atau hubungi layanan darurat 119/112."

def public():
    return {"items":[{"id":i,"text":t,"options":[{"key":LETTERS[n],"label":o} for n,o in enumerate(os_)]} for i,t,os_ in ITEMS],
            "visits":VISITS,"safety_item":SAFETY_ITEM,"safety_option":SAFETY_OPTION,"safety_text":SAFETY_TEXT}

def answer_text(item_id, letter):
    for i,t,os_ in ITEMS:
        if i==item_id and letter in LETTERS: return os_[LETTERS.index(letter)]
    return ""
