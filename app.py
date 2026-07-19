import os, json, datetime, traceback, base64
import gspread
from flask import Flask, render_template, request, jsonify, redirect
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24).hex())
SHEET_ID = "1tz1uFlQi4KkIkqqnModjMj21qcvvxGf0KcuavD9U9bA"

def gc():
    b64 = os.environ.get("GAUTH_B64")
    info = json.loads(base64.b64decode(b64.strip()).decode())
    creds = Credentials.from_authorized_user_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else: raise RuntimeError("Credentials invalid")
    return gspread.authorize(creds)

def sheet(name):
    return gc().open_by_key(SHEET_ID).worksheet(name)

def ensure_jurnal():
    try: return sheet("Jurnal")
    except:
        sh = gc().open_by_key(SHEET_ID)
        ws = sh.add_worksheet("Jurnal", 1000, 9)
        ws.update("A1:I1", [["ID","Tanggal","Referensi","Sumber","Keterangan","Debit","Kredit","Kategori","Catatan"]])
        ws.format("A1:I1", {"textFormat": {"bold": True}})
        return ws

def next_row(ws, start=4):
    vals = ws.col_values(1)
    for i, v in enumerate(vals[start-1:], start=start):
        if not v.strip(): return i
    return len(vals) + 1

def next_nota(ws, prefix):
    vals = ws.col_values(3)
    n = 0
    for v in vals:
        if v.startswith(prefix) and v[1:].isdigit():
            n = max(n, int(v[1:]))
    return prefix + str(n + 1)

def hitung_total(tipe, j1, j2, harga):
    try: j1 = float(j1 or 0)
    except: j1 = 0
    try: j2 = float(j2 or 0)
    except: j2 = 0
    try: h = int(harga or 0)
    except: h = 0
    return int(j1 * j2 * h) if tipe == "M2" else int(j1 * h)

def jurnal(tgl, ref, sumber, ket, debit=0, kredit=0, kategori="Order"):
    ws = ensure_jurnal()
    row = next_row(ws, 2)
    ws.update(f"A{row}:I{row}", [[str(row-1), tgl, ref, sumber, ket, str(debit), str(kredit), kategori, ""]],
              value_input_option="USER_ENTERED")
    return row

def parse_int(v):
    try: return int(v.replace(".","").replace(",",""))
    except: return 0

# ─── Routes ────────────────────────────────────────

@app.route("/")
def index(): return redirect("/pos")

@app.route("/pos")
def pos():
    ws = sheet("Pricelist")
    pl = []
    for r in ws.get_all_values()[3:]:
        if r[0] and r[0].strip().isdigit():
            pl.append({"id":r[0],"nama":r[1],"tipe":r[4] if len(r)>4 and r[4] in ("KG","PCS","M2") else "KG","harga":r[3] if len(r)>3 else "0"})
    return render_template("pos.html", pricelist=pl)

@app.route("/dashboard")
def dash(): return render_template("dashboard.html")

@app.route("/uang")
def uang(): return render_template("uang.html")

@app.route("/cari")
def cari(): return render_template("cari.html")

@app.route("/laporan")
def laporan(): return render_template("laporan.html")

@app.route("/export/pdf")
def export_pdf():
    return render_template("export.html")

# ─── API ───────────────────────────────────────────

@app.route("/api/order", methods=["POST"])
def add_order():
    d = request.get_json()
    ws = sheet("Orderan")
    row = next_row(ws)
    tipe = d.get("tipe","KG")
    j1 = d.get("jumlah","0"); j2 = d.get("jumlah2","")
    harga = d.get("harga","0")
    total = hitung_total(tipe, j1, j2, harga)
    tgl = d.get("tgl_masuk", datetime.date.today().strftime("%d %b %Y"))
    tgl_selesai = d.get("tgl_selesai","")
    pref = d.get("nota_prefix","A")
    nota = next_nota(ws, pref)
    sumber = "Outlet" if pref == "A" else "R.Laundry"
    bayar = d.get("bayar","Cash")
    bayar_waktu = d.get("bayar_waktu","Langsung")

    ws.update(f"A{row}:Q{row}", [[str(row-3), tgl, nota, d.get("pelanggan",""), d.get("no_hp",""),
        d.get("layanan",""), j1, j2, harga, str(total), "Proses", bayar, "",
        tgl_selesai, d.get("non_kilo",""), bayar_waktu, tipe]],
        value_input_option="USER_ENTERED")

    # Auto jurnal — entry pendapatan
    ket = f"{d.get('pelanggan','')} - {d.get('layanan','')} ({nota})"
    if bayar_waktu == "Ambil":
        jurnal(tgl, nota, sumber, ket, debit=total, kredit=0, kategori="Piutang")
    else:
        jurnal(tgl, nota, sumber, ket, debit=total, kredit=0, kategori="Order")

    return jsonify({"ok":True,"nota":nota,"total":total,"sumber":sumber})

@app.route("/api/order/<int:row>", methods=["PUT","DELETE"])
def edit_order(row):
    ws = sheet("Orderan")
    if request.method == "DELETE":
        ws.update(f"A{row}:Q{row}", [[""]*17], value_input_option="USER_ENTERED")
        return jsonify({"ok":True})
    d = request.get_json()
    tipe = d.get("tipe","KG"); j1 = d.get("jumlah","0"); j2 = d.get("jumlah2","")
    harga = d.get("harga","0"); total = hitung_total(tipe, j1, j2, harga)
    ws.update(f"A{row}:Q{row}", [[str(row-3), d.get("tgl_masuk",""), d.get("nota",""),
        d.get("pelanggan",""), d.get("no_hp",""), d.get("layanan",""),
        j1, j2, harga, str(total), d.get("status","Proses"), d.get("bayar","Cash"), "",
        d.get("tgl_selesai",""), d.get("non_kilo",""), d.get("bayar_waktu","Langsung"), tipe]],
        value_input_option="USER_ENTERED")
    return jsonify({"ok":True,"total":total})

@app.route("/api/jurnal", methods=["POST","GET"])
def api_jurnal():
    if request.method == "POST":
        d = request.get_json()
        tgl = datetime.date.today().strftime("%d %b %Y")
        sumber = d.get("sumber","Umum")
        ket = d.get("keterangan","")
        debit = d.get("debit","0")
        kredit = d.get("kredit","0")
        kategori = d.get("kategori","Lain")
        ref = d.get("ref",f"#{datetime.date.today().strftime('%d%m%y')}")
        jurnal(tgl, ref, sumber, ket, debit, kredit, kategori)
        return jsonify({"ok":True})

    # GET: ambil data jurnal + hitung saldo
    ws = ensure_jurnal()
    vals = ws.get_all_values()[1:]
    sumber = request.args.get("sumber","")
    entries = []
    for r in vals:
        if not r[0] or not r[0].strip().isdigit(): continue
        if sumber and r[3] != sumber: continue
        entries.append({
            "id":r[0],"tgl":r[1],"ref":r[2],"sumber":r[3],"ket":r[4],
            "debit":parse_int(r[5]),"kredit":parse_int(r[6]),"kategori":r[7],"catatan":r[8]
        })
    def saldo_sumber(s):
        return sum(e["debit"] for e in entries if e["sumber"]==s) - sum(e["kredit"] for e in entries if e["sumber"]==s)
    return jsonify({
        "entries": entries,
        "saldo": {"Outlet":saldo_sumber("Outlet"),"R.Laundry":saldo_sumber("R.Laundry"),"Umum":saldo_sumber("Umum")},
        "total": sum(e["debit"] for e in entries) - sum(e["kredit"] for e in entries)
    })

@app.route("/api/ringkasan")
def api_ringkasan():
    ows = sheet("Orderan")
    orders = [r for r in ows.get_all_values()[3:] if r[0] and r[0].strip().isdigit()]
    today = datetime.date.today()
    now_str = today.strftime("%d %b %Y")
    orders_today = [r for r in orders if now_str in r[1]]
    pendapatan_hari = sum(parse_int(r[9]) for r in orders_today)
    order_aktif = sum(1 for r in orders if r[10] and r[10].strip()=="Proses")
    total_revenue = sum(parse_int(r[9]) for r in orders)

    jws = ensure_jurnal()
    jvals = [r for r in jws.get_all_values()[1:] if r[0] and r[0].strip().isdigit()]
    saldo_outlet = sum(parse_int(r[5]) for r in jvals if r[3]=="Outlet") - sum(parse_int(r[6]) for r in jvals if r[3]=="Outlet")
    saldo_rl = sum(parse_int(r[5]) for r in jvals if r[3]=="R.Laundry") - sum(parse_int(r[6]) for r in jvals if r[3]=="R.Laundry")
    saldo_umum = sum(parse_int(r[5]) for r in jvals if r[3]=="Umum") - sum(parse_int(r[6]) for r in jvals if r[3]=="Umum")

    import datetime as dt
    monday = today - dt.timedelta(days=today.weekday())
    month_map = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"Mei":5,"Jun":6,"Jul":7,"Agu":8,"Sep":9,"Okt":10,"Nov":11,"Des":12}
    week_orders = []
    for r in orders:
        try:
            parts = r[1].split()
            if len(parts)==3:
                d = dt.date(int(parts[2]), month_map.get(parts[1],1), int(parts[0]))
                if monday <= d <= today:
                    week_orders.append(r)
        except: pass
    pendapatan_minggu = sum(parse_int(r[9]) for r in week_orders)

    return jsonify({
        "pendapatan_hari": pendapatan_hari,"order_aktif": order_aktif,"order_hari": len(orders_today),
        "total_revenue": total_revenue,"pendapatan_minggu": pendapatan_minggu,
        "saldo_outlet": saldo_outlet,"saldo_rl": saldo_rl,"saldo_umum": saldo_umum
    })

@app.route("/data/<jenis>")
def data_jenis(jenis):
    ws = sheet({"orderan":"Orderan","buku":"Buku Besar"}.get(jenis, jenis))
    vals = ws.get_all_values()[3:]
    return jsonify([r for r in vals if r[0] and r[0].strip().isdigit()])

@app.route("/data/pelanggan")
def data_pelanggan():
    vals = sheet("Orderan").get_all_values()[3:]
    orders = [r for r in vals if r[0] and r[0].strip().isdigit()]
    p = {}
    for r in reversed(orders):
        name = r[3].strip() if r[3] else ""
        if not name: continue
        if name not in p:
            p[name] = {"nama":name,"hp":r[4] if len(r)>4 else "","total_order":0,"total_berat":0.0,"total_bayar":0,"orders":[]}
        x = p[name]; x["total_order"] += 1
        try: x["total_berat"] += float(r[6] or 0)
        except: pass
        try: x["total_bayar"] += int(r[9] or 0)
        except: pass
        if r[4] and not x["hp"]: x["hp"] = r[4]
        x["orders"].append({
            "id":r[0],"tgl":r[1],"nota":r[2],"layanan":r[5],
            "jumlah":r[6] if len(r)>6 else "","jumlah2":r[7] if len(r)>7 else "",
            "harga":r[8] if len(r)>8 else "","total":r[9] if len(r)>9 else "",
            "status":r[10] if len(r)>10 else "","bayar":r[11] if len(r)>11 else "",
            "tgl_selesai":r[13] if len(r)>13 else "","non_kilo":r[14] if len(r)>14 else "",
            "bayar_waktu":r[15] if len(r)>15 else "","tipe":r[16] if len(r)>16 else "KG"
        })
    return jsonify(sorted(p.values(), key=lambda x: x["total_bayar"], reverse=True))

@app.route("/setup/jurnal", methods=["POST"])
def setup_jurnal():
    ws = ensure_jurnal()
    orders = sheet("Orderan").get_all_values()[3:]
    jurnal_existing = ws.get_all_values()[1:]
    existing_refs = set(r[2] for r in jurnal_existing if len(r)>2)
    count = 0
    for r in orders:
        if r[0] and r[0].strip().isdigit() and r[2] not in existing_refs:
            nota = r[2]
            pref = nota[0] if nota else "A"
            sumber = "Outlet" if pref=="A" else "R.Laundry"
            total = parse_int(r[9]) if len(r)>9 else 0
            if total > 0:
                ket = f"{r[3]} - {r[5]} ({nota})" if len(r)>5 else nota
                jurnal(r[1] or datetime.date.today().strftime("%d %b %Y"), nota, sumber, ket, debit=total, kategori="Order")
                count += 1
    return jsonify({"ok":True,"backfilled":count})

@app.route("/health")
def health():
    try:
        gc()
        return jsonify({"status":"ok"})
    except: return jsonify({"status":"error"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)