"""Putry Laundry POS — Flask App"""
import os, json, datetime, gspread
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "putry-laundry-pos-key-2026")

# ── Google Sheets Connection ──
SHEET_ID = "1tz1uFlQi4KkIkqqnModjMj21qcvvxGf0KcuavD9U9bA"

def get_gc():
    """Connect to Google Sheets using OAuth credentials"""
    if os.environ.get("GAUTH_JSON"):
        # Production: from Render env var
        info = json.loads(os.environ["GAUTH_JSON"])
    else:
        # Local dev: from token file
        tok_path = os.path.expanduser("~/AppData/Local/hermes/google_token.json")
        if not os.path.exists(tok_path):
            tok_path = os.path.expanduser("~/Downloads/gsheets_token.json")
        with open(tok_path) as f:
            info = json.load(f)
    
    creds = Credentials.from_authorized_user_info(info, scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])
    
    # Auto-refresh if expired
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    
    return gspread.authorize(creds)

def sh():
    gc = get_gc()
    return gc.open_by_key(SHEET_ID)

# ── Helpers ──
def next_row(ws):
    """Find the next empty row in a sheet (col A = 'No')"""
    vals = ws.col_values(1)
    for i, v in enumerate(vals[3:], start=4):  # skip title + headers
        if not v.strip():
            return i
    return len(vals) + 1

# ── Routes ──
@app.route("/")
def index():
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():
    ws = sh().worksheet("Dashboard")
    values = ws.get_all_values()
    return render_template("dashboard.html", values=values)

@app.route("/pos")
def pos():
    ws = sh().worksheet("Pricelist")
    pricelist = ws.get_all_values()[3:]  # skip header rows
    pricelist = [r for r in pricelist if r[0].strip() and r[0].isdigit()]
    return render_template("pos.html", pricelist=pricelist)

@app.route("/kas")
def kas():
    return render_template("kas.html")

@app.route("/buku")
def buku():
    return render_template("buku.html")

@app.route("/api/order", methods=["POST"])
def add_order():
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

@app.route("/api/kas", methods=["POST"])
def add_kas():
    data = request.get_json()
    sheet_name = data.get("sheet", "Kas Outlet")
    ws = sh().worksheet(sheet_name)
    row = next_row(ws)
    
    debit = data.get("debit", "").replace(".","").replace(",","")
    kredit = data.get("kredit", "").replace(".","").replace(",","")
    
    ws.update(f"A{row}:E{row}", [[
        str(row - 3),
        data.get("tanggal", datetime.date.today().strftime("%d %b %Y")),
        data.get("keterangan", ""),
        debit if debit else "",
        kredit if kredit else ""
    ]], value_input_option="USER_ENTERED")
    
    return jsonify({"ok": True, "row": row})

@app.route("/api/bukubesar", methods=["POST"])
def add_bukubesar():
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

@app.route("/data/orderan")
def data_orderan():
    ws = sh().worksheet("Orderan")
    values = ws.get_all_values()[3:]
    values = [r for r in values if r[0].strip().isdigit()]
    return jsonify(values)

@app.route("/data/bukubesar")
def data_bukubesar():
    ws = sh().worksheet("Buku Besar")
    values = ws.get_all_values()[3:]
    values = [r for r in values if r[0].strip().isdigit()]
    return jsonify(values)

@app.route("/data/kas/<sheet>")
def data_kas(sheet):
    ws = sh().worksheet(sheet)
    values = ws.get_all_values()[3:]
    values = [r for r in values if r[0].strip().isdigit()]
    return jsonify(values)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
