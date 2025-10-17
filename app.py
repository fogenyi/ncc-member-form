from flask import Flask, render_template, request, redirect, send_file, Response
import sqlite3
import pandas as pd
from functools import wraps
import json
import os

app = Flask(__name__)

DB_PATH = "ncc_members.db"

# -----------------------------
# DB Utilities
# -----------------------------
def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    """
    Create the members table if it doesn't exist (with the latest schema).
    """
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT,
            last_name TEXT,
            birth_month TEXT,
            birth_day TEXT,
            birth_year TEXT,
            address TEXT,
            phone TEXT,
            email TEXT,                 -- <-- included in base schema
            family_members TEXT,        -- JSON string from dynamic UI
            communication TEXT,
            volunteer_interests TEXT,
            comments TEXT
        )
    """)
    conn.commit()
    conn.close()

def ensure_schema():
    """
    Ensure older DBs have the required columns (idempotent).
    """
    conn = get_conn()
    c = conn.cursor()
    c.execute("PRAGMA table_info(members)")
    cols = {row[1] for row in c.fetchall()}  # column names

    # Add missing columns if needed (safe even if new DB)
    if "email" not in cols:
        c.execute("ALTER TABLE members ADD COLUMN email TEXT")
    if "family_members" not in cols:
        c.execute("ALTER TABLE members ADD COLUMN family_members TEXT")
    if "communication" not in cols:
        c.execute("ALTER TABLE members ADD COLUMN communication TEXT")
    if "volunteer_interests" not in cols:
        c.execute("ALTER TABLE members ADD COLUMN volunteer_interests TEXT")
    if "comments" not in cols:
        c.execute("ALTER TABLE members ADD COLUMN comments TEXT")

    conn.commit()
    conn.close()

# Initialize DB on startup
init_db()
ensure_schema()

# -----------------------------
# Auth utilities (for exports)
# -----------------------------
def check_auth(username, password):
    # Keep your existing credentials
    return username == 'Nc_adm127in' and password == '2Uh0tOO7&'

def authenticate():
    return Response(
        'Access Denied: Authentication Required.', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# -----------------------------
# Routes (pages)
# -----------------------------
@app.route('/')
def index():
    # index.html includes dynamic family members (relationship + volunteer)
    return render_template('index.html')

@app.route('/thank-you')
def thank_you():
    return render_template('thank_you.html')

@app.route('/admin')
def admin():
    return render_template('admin_dashboard.html')

# -----------------------------
# Form submit
# -----------------------------
@app.route('/submit', methods=['POST'])
def submit():
    try:
        data = request.form

        # Volunteer interests for primary member (checkboxes)
        interests = request.form.getlist('volunteer_interests')
        volunteer_interests = ', '.join(interests)

        # Family members JSON (hidden input). Store as-is if valid JSON; else store empty list.
        fam_raw = data.get('family_members', '').strip()
        if fam_raw:
            try:
                parsed = json.loads(fam_raw)
                # Ensure it's a list; otherwise store empty list
                if not isinstance(parsed, list):
                    fam_raw = "[]"
                else:
                    # Optionally normalize nulls -> ""
                    for m in parsed:
                        if isinstance(m, dict):
                            for k, v in list(m.items()):
                                if v is None:
                                    m[k] = ""
                    fam_raw = json.dumps(parsed, ensure_ascii=False)
            except Exception:
                fam_raw = "[]"
        else:
            fam_raw = "[]"

        conn = get_conn()
        c = conn.cursor()
        c.execute('''INSERT INTO members (
            first_name, last_name, birth_month, birth_day, birth_year,
            address, phone, email, family_members, communication, volunteer_interests, comments
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
            data.get('first_name', '').strip(),
            data.get('last_name', '').strip(),
            data.get('birth_month', '').strip(),
            data.get('birth_day', '').strip(),
            data.get('birth_year', '').strip(),
            data.get('address', '').strip(),
            data.get('phone', '').strip(),
            data.get('email', '').strip(),          # <-- email included
            fam_raw,                                 # <-- JSON string
            data.get('communication', '').strip(),
            volunteer_interests,
            data.get('comments', '').strip()
        ))
        conn.commit()
        conn.close()
        return redirect('/thank-you')
    except Exception as e:
        return f"Something went wrong: {e}", 500

# -----------------------------
# Exports
# -----------------------------
@app.route('/export')
@requires_auth
def export_xlsx():
    """
    Export all members to an Excel file (raw JSON in family_members).
    """
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM members", conn)
    conn.close()

    file_path = "ncc_members_export.xlsx"
    df.to_excel(file_path, index=False)
    return send_file(file_path, as_attachment=True, download_name=file_path)

@app.route('/export_csv')
@requires_auth
def export_csv():
    """
    Export a CSV that expands family members into separate rows.
    - One 'primary' row per registrant (family columns empty)
    - One 'family' row per family member with their details
    """
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM members", conn)
    conn.close()

    rows = []
    for _, r in df.iterrows():
        base = {
            "member_id": r.get("id", ""),
            "member_first_name": r.get("first_name", ""),
            "member_last_name": r.get("last_name", ""),
            "member_birth_month": r.get("birth_month", ""),
            "member_birth_day": r.get("birth_day", ""),
            "member_birth_year": r.get("birth_year", ""),
            "member_address": r.get("address", ""),
            "member_phone": r.get("phone", ""),
            "member_email": r.get("email", ""),
            "member_communication": r.get("communication", ""),
            "member_volunteer_interests": r.get("volunteer_interests", ""),
            "member_comments": r.get("comments", "")
        }

        # Primary row
        rows.append({
            **base,
            "row_type": "primary",
            "family_name": "",
            "family_birth_month": "",
            "family_birth_day": "",
            "family_birth_year": "",
            "family_relationship": "",
            "family_volunteer": ""
        })

        # Family rows
        fam_raw = r.get("family_members", "") or ""
        try:
            fam_list = json.loads(fam_raw) if str(fam_raw).strip() else []
            if not isinstance(fam_list, list):
                fam_list = []
        except Exception:
            fam_list = []

        for fam in fam_list:
            fam = fam or {}
            rows.append({
                **base,
                "row_type": "family",
                "family_name": fam.get("name", ""),
                "family_birth_month": fam.get("birth_month", ""),
                "family_birth_day": fam.get("birth_day", ""),
                "family_birth_year": fam.get("birth_year", ""),
                "family_relationship": fam.get("relationship", ""),
                "family_volunteer": fam.get("volunteer", "")
            })

    out_df = pd.DataFrame(rows)
    file_path = "ncc_members_with_family.csv"
    out_df.to_csv(file_path, index=False, encoding="utf-8-sig")
    return send_file(file_path, as_attachment=True, download_name=file_path)

# -----------------------------
# App entry
# -----------------------------
if __name__ == '__main__':
    # Bind to all interfaces for Render; port 8000 matches your Procfile/cmd
    app.run(host='0.0.0.0', port=8000)
