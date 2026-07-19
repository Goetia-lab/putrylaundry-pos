import os, json, datetime, traceback, base64
import gspread
from flask import Flask, render_template, request, jsonify, redirect
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24).hex())

SHEET_ID = "1tz1uFlQi4KkIkqqnModjMj21qcvvxGf0KcuavD9U9bA"

def get_gauth_info():
    """Get Google auth from GAUTH_B64 env var (base64-encoded JSON)."""
    b64 = os.environ.get("GAUTH_B64")
    if not b64:
        raise ValueError("GAUTH_B64 env var not set")
    try:
        return json.loads(base64.b64decode(b64.strip()).decode("utf-8"))
    except Exception as e:
        raise ValueError(f"Invalid GAUTH_B64: {e}")

def get_gc():
    info = get_gauth_info()
    scopes = info.get("scopes", ["https://www.googleapis.com/auth/spreadsheets"])
    creds = Credentials.from_authorized_user_info(info, scopes=scopes)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as e:
                raise RuntimeError(f"Token expired permanently: {e}")
        else:
            raise RuntimeError("Credentials invalid and can't refresh")
    return gspread.authorize(creds)

def sh():
    return get_gc().open_by_key(SHEET_ID)

def next_row(ws):
    vals = ws.col_values(1)
    for i, v in enumerate(vals[3:], start=4):
        if not v.strip():
            return i
    return len(vals) + 1

# ─── Routes ────────────────────────────────────────

@app.route("/")
def index():
    return redirect("/dashboard")

@app.route("/debug")
def debug():
    try:
        info = get_gauth_info()
        gc = get_gc()
        ws = gc.open_by_key(SHEET_ID).worksheet("Dashboard")
        vals = ws.get_all_values()
        return f"<h3>✅ OK</h3><p>Rows: {len(vals)}</p><pre>{json.dumps(vals[:3], indent=2)}</pre>"""
    except Exception as e:
        return f"<h3>❌ Error</h3><pre>{traceback.format_exc()}</pre>", 500

@app.route("/dashboard")
def dashboard():
    try:
        values = sh().worksheet("Dashboard").get_all_values()
        return render_template("dashboard.html", values=values)
    except Exception as e:
        return f"<h3>Dashboard Error</h3><pre>{traceback.format_exc()}</pre>", 500

@app.route("/pos")
def pos():
    try:
        ws = sh().worksheet("Pricelist")
        pricelist = ws.get_all_values()[3:]
        pricelist = [r for r in pricelist if r[0].strip().isdigit()]
        return render_template("pos.html", pricelist=pricelist)
    except Exception as e:
        return f"<h3>POS Error</h3><pre>{traceback.format_exc()}</pre>", 500

@app.route("/kas")
def kas():
    return render_template("kas.html")

@app.route("/buku")
def buku():
    return render_template("buku.html")

# ─── API ────────────────────────────────────────

@app.route("/api/order", methods=["POST"])
def add_order():
    try:
        data = request.get_json()
        ws = sh().worksheet("Orderan")
        row = next_row(ws)
        total = int(data.get("berat", 0)) * int(data.get("harga", 0))
        ws.update(f"A{row}:L{row}", [[
            str(row - 3),
            data.get("tanggal", datetime.date.today().strftime("%d %b %Y")),
            data.get("nota", ""),
            data.get("pelanggan", ""),
            data.get("no_hp", ""),
            data.get("layanan", ""),
            data.get("berat", "0"),
            data.get("harga", "0"),
            str(total),
            data.get("status", "Proses"),
            data.get("bayar", "Cash"),
            data.get("catatan", "")
        ]], value_input_option="USER_ENTERED")
        return jsonify({"ok": True, "row": row, "total": total})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/kas", methods=["POST"])
def add_kas():
    try:
        data = request.get_json()
        ws = sh().worksheet(data.get("sheet", "Kas Outlet"))
        row = next_row(ws)
        debit = str(data.get("debit", "")).replace(".","").replace(",","")
        kredit = str(data.get("kredit", "")).replace(".","").replace(",","")
        ws.update(f"A{row}:E{row}", [[
            str(row - 3),
            data.get("tanggal", datetime.date.today().strftime("%d %b %Y")),
            data.get("keterangan", ""),
            debit or "",
            kredit or ""
        ]], value_input_option="USER_ENTERED")
        return jsonify({"ok": True, "row": row})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/bukubesar", methods=["POST"])
def add_bukubesar():
    try:
        data = request.get_json()
        ws = sh().worksheet("Buku Besar")
        row = next_row(ws)
        debit = str(data.get("debit", "")).replace(".","").replace(",","")
        kredit = str(data.get("kredit", "")).replace(".","").replace(",","")
        ws.update(f"A{row}:F{row}", [[
            str(row - 3),
            data.get("tanggal", datetime.date.today().strftime("%d %b %Y")),
            data.get("transaksi", ""),
            debit or "",
            kredit or "",
            ""
        ]], value_input_option="USER_ENTERED")
        return jsonify({"ok": True, "row": row})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/data/orderan")
def data_orderan():
    try:
        values = sh().worksheet("Orderan").get_all_values()[3:]
        return jsonify([r for r in values if r[0].strip().isdigit()])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/data/bukubesar")
def data_bukubesar():
    try:
        values = sh().worksheet("Buku Besar").get_all_values()[3:]
        return jsonify([r for r in values if r[0].strip().isdigit()])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/data/kas/<sheet>")
def data_kas(sheet):
    try:
        values = sh().worksheet(sheet).get_all_values()[3:]
        return jsonify([r for r in values if r[0].strip().isdigit()])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/health")
def health():
    try:
        get_gc()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
