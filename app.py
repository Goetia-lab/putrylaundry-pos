import os, json, datetime, traceback, base64
import gspread
from flask import Flask, render_template, request, jsonify, redirect
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

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
        else:
            raise RuntimeError("Credentials invalid")
    return gspread.authorize(creds)

def sheet(name):
    return gc().open_by_key(SHEET_ID).worksheet(name)

def next_row(ws):
    vals = ws.col_values(1)
    for i, v in enumerate(vals[3:], start=4):
        if not v.strip(): return i
    return len(vals) + 1

def next_nota(ws, prefix):
    """Cari nomor nota terakhir untuk prefix A/B, return prefix+nomor_selanjutnya."""
    vals = ws.col_values(3)
    max_n = 0
    for v in vals:
        if v.startswith(prefix) and v[1:].isdigit():
            n = int(v[1:])
            if n > max_n: max_n = n
    return prefix + str(max_n + 1)

# ─── Routes ────────────────────────────────────────

@app.route("/")
def index():
    return redirect("/pos")

@app.route("/pos")
def pos():
    ws = sheet("Pricelist")
    pricelist = [r for r in ws.get_all_values()[3:] if r[0].strip().isdigit()]
    return render_template("pos.html", pricelist=pricelist)

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/uang")
def uang():
    return render_template("uang.html")

@app.route("/cari")
def cari():
    return render_template("cari.html")

# ─── API ───────────────────────────────────────────

@app.route("/api/order", methods=["POST"])
def add_order():
    data = request.get_json()
    ws = sheet("Orderan")
    row = next_row(ws)
    layanan = data.get("layanan", "")
    harga = data.get("harga", "0")
    berat = data.get("berat", "0")
    total = int(berat or 0) * int(harga or 0)
    tgl = data.get("tgl_masuk", datetime.date.today().strftime("%d %b %Y"))
    tgl_selesai = data.get("tgl_selesai", "")
    nota_prefix = data.get("nota_prefix", "A")
    nota = data.get("nota") or next_nota(ws, nota_prefix)
    status = "Proses"
    bayar = data.get("bayar", "Cash")
    bayar_waktu = data.get("bayar_waktu", "Langsung")
    ws.update(f"A{row}:O{row}", [[
        str(row-3), tgl, nota,
        data.get("pelanggan",""), data.get("no_hp",""),
        layanan, berat, harga, str(total),
        status, bayar, "",
        tgl_selesai, data.get("non_kilo",""), bayar_waktu
    ]], value_input_option="USER_ENTERED")
    return jsonify({"ok": True, "row": row, "total": total, "nota": nota})

@app.route("/api/order/<int:row>", methods=["PUT", "DELETE"])
def edit_order(row):
    ws = sheet("Orderan")
    if request.method == "DELETE":
        ws.update(f"A{row}:O{row}", [[""]*15], value_input_option="USER_ENTERED")
        return jsonify({"ok": True})
    data = request.get_json()
    total = int(data.get("berat",0)) * int(data.get("harga",0))
    ws.update(f"A{row}:O{row}", [[
        str(row-3), data.get("tgl_masuk",""), data.get("nota",""),
        data.get("pelanggan",""), data.get("no_hp",""),
        data.get("layanan",""), data.get("berat","0"), data.get("harga","0"),
        str(total), data.get("status","Proses"), data.get("bayar","Cash"), "",
        data.get("tgl_selesai",""), data.get("non_kilo",""), data.get("bayar_waktu","Langsung")
    ]], value_input_option="USER_ENTERED")
    return jsonify({"ok": True, "total": total})

@app.route("/api/uang", methods=["POST"])
def add_uang():
    data = request.get_json()
    ws = sheet("Buku Besar")
    row = next_row(ws)
    debit = str(data.get("debit","")).replace(".","").replace(",","")
    kredit = str(data.get("kredit","")).replace(".","").replace(",","")
    tgl = datetime.date.today().strftime("%d %b %Y")
    ws.update(f"A{row}:F{row}", [[
        str(row-3), tgl, data.get("keterangan",""),
        debit or "", kredit or "", ""
    ]], value_input_option="USER_ENTERED")
    return jsonify({"ok": True, "row": row})

@app.route("/data/<jenis>")
def data_jenis(jenis):
    ws = sheet({"orderan":"Orderan","buku":"Buku Besar","kas":"Kas Outlet"}.get(jenis, jenis))
    vals = ws.get_all_values()[3:]
    return jsonify([r for r in vals if r[0].strip().isdigit()])

@app.route("/data/pelanggan")
def data_pelanggan():
    vals = sheet("Orderan").get_all_values()[3:]
    orders = [r for r in vals if r[0].strip().isdigit()]
    p = {}
    for r in reversed(orders):
        name = r[3].strip()
        if not name: continue
        if name not in p:
            p[name] = {"nama":name, "hp":r[4], "total_order":0, "total_berat":0.0, "total_bayar":0, "orders":[]}
        x = p[name]; x["total_order"] += 1
        x["total_berat"] += float(r[6] or 0)
        x["total_bayar"] += int(r[8] or 0)
        if r[4] and not x["hp"]: x["hp"] = r[4]
        x["orders"].append({"id":r[0],"tgl":r[1],"nota":r[2],"layanan":r[5],"berat":r[6],"harga":r[7],"total":r[8],"status":r[9],"bayar":r[10],"tgl_selesai":r[12] if len(r)>12 else "","non_kilo":r[13] if len(r)>13 else "","bayar_waktu":r[14] if len(r)>14 else ""})
    return jsonify(sorted(p.values(), key=lambda x: x["total_bayar"], reverse=True))

@app.route("/health")
def health():
    try:
        gc()
        return jsonify({"status":"ok"})
    except: return jsonify({"status":"error"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)