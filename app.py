import os, json, datetime, traceback, gspread
from flask import Flask, render_template, request, jsonify, redirect
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "putry-laundry-pos-key-2026")

SHEET_ID = "1tz1uFlQi4KkIkqqnModjMj21qcvvxGf0KcuavD9U9bA"

# Show errors on page for debugging
app.config["PROPAGATE_EXCEPTIONS"] = False

def get_gc():
    if os.environ.get("GAUTH_JSON"):
        info = json.loads(os.environ["GAUTH_JSON"])
    else:
        tok_path = os.path.expanduser("~/AppData/Local/hermes/google_token.json")
        if not os.path.exists(tok_path):
            tok_path = os.path.expanduser("~/Downloads/gsheets_token.json")
        with open(tok_path) as f:
            info = json.load(f)
    creds = Credentials.from_authorized_user_info(info)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return gspread.authorize(creds)

def sh():
    return get_gc().open_by_key(SHEET_ID)

def next_row(ws):
    vals = ws.col_values(1)
    for i, v in enumerate(vals[3:], start=4):
        if not v.strip():
            return i
    return len(vals) + 1

@app.route("/")
def index():
    return redirect("/dashboard")

@app.route("/dashboard")
def dashboard():
    try:
        ws = sh().worksheet("Dashboard")
        values = ws.get_all_values()
        return render_template("dashboard.html", values=values)
    except Exception as e:
        return f"<h3>Dashboard Error</h3><pre>{traceback.format_exc()}</pre>", 500

@app.route("/pos")
def pos():
    try:
        ws = sh().worksheet("Pricelist")
        pricelist = ws.get_all_values()[3:]
        pricelist = [r for r in pricelist if r[0].strip() and r[0].isdigit()]
        return render_template("pos.html", pricelist=pricelist)
    except Exception as e:
        return f"<h3>POS Error</h3><pre>{traceback.format_exc()}</pre>", 500

@app.route("/kas")
def kas():
    return render_template("kas.html")

@app.route("/buku")
def buku():
    return render_template("buku.html")

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
            total,
            data.get("status", "Proses"),
            data.get("bayar", "Cash"),
            data.get("catatan", "")
        ]], value_input_option="USER_ENTERED")
        return jsonify({"ok": True, "row": row, "total": total})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "traceback": traceback.format_exc()}), 500

@app.route("/api/kas", methods=["POST"])
def add_kas():
    try:
        data = request.get_json()
        sheet_name = data.get("sheet", "Kas Outlet")
        ws = sh().worksheet(sheet_name)
        row = next_row(ws)
        debit = str(data.get("debit", "")).replace(".","").replace(",","")
        kredit = str(data.get("kredit", "")).replace(".","").replace(",","")
        ws.update(f"A{row}:E{row}", [[
            str(row - 3),
            data.get("tanggal", datetime.date.today().strftime("%d %b %Y")),
            data.get("keterangan", ""),
            debit if debit else "",
            kredit if kredit else ""
        ]], value_input_option="USER_ENTERED")
        return jsonify({"ok": True, "row": row})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "traceback": traceback.format_exc()}), 500

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
            debit if debit else "",
            kredit if kredit else "",
            ""
        ]], value_input_option="USER_ENTERED")
        return jsonify({"ok": True, "row": row})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/data/orderan")
def data_orderan():
    try:
        ws = sh().worksheet("Orderan")
        values = ws.get_all_values()[3:]
        values = [r for r in values if r[0].strip().isdigit()]
        return jsonify(values)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/data/bukubesar")
def data_bukubesar():
    try:
        ws = sh().worksheet("Buku Besar")
        values = ws.get_all_values()[3:]
        values = [r for r in values if r[0].strip().isdigit()]
        return jsonify(values)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/data/kas/<sheet>")
def data_kas(sheet):
    try:
        ws = sh().worksheet(sheet)
        values = ws.get_all_values()[3:]
        values = [r for r in values if r[0].strip().isdigit()]
        return jsonify(values)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
