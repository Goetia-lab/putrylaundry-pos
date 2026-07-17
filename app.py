import os, json, datetime, traceback, base64, gspread
from flask import Flask, render_template, request, jsonify, redirect
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24).hex())

SHEET_ID = "1tz1uFlQi4KkIkqqnModjMj21qcvvxGf0KcuavD9U9bA"
GAUTH_JSON_KEY = "GAUTH_JSON"
GAUTH_B64_KEY  = "GAUTH_B64"
...[truncated]