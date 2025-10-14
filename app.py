from flask import Flask, render_template, request, redirect, send_file, Response
import sqlite3
import pandas as pd
from functools import wraps

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('ncc_members.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT, last_name TEXT, birth_month TEXT, birth_day TEXT, birth_year TEXT,
        address TEXT, phone TEXT, email TEXT, family_members TEXT,
        communication TEXT, volunteer_interests TEXT, comments TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/thank-you')
def thank_you():
    return render_template('thank_you.html')

@app.route('/admin')
def admin():
    return render_template('admin_dashboard.html')

@app.route('/submit', methods=['POST'])
def submit():
    try:
        data = request.form
        interests = request.form.getlist('volunteer_interests')
        conn = sqlite3.connect('ncc_members.db')
        c = conn.cursor()
        c.execute('''INSERT INTO members (
            first_name, last_name, birth_month, birth_day, birth_year,
            address, phone, email, family_members, communication, volunteer_interests, comments
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
            data.get('first_name', ''),
            data.get('last_name', ''),
            data.get('birth_month', ''),
            data.get('birth_day', ''),
            data.get('birth_year', ''),
            data.get('address', ''),
            data.get('phone', ''),
            data.get('email', ''),
            data.get('family_members', ''),
            data.get('communication', ''),
            ', '.join(request.form.getlist('volunteer_interests')),
            data.get('comments', '')
        ))
        conn.commit()
        conn.close()
        return redirect('/thank-you')
    except Exception as e:
        return f"Something went wrong: {e}", 500

def check_auth(username, password):
    return username == 'Nc_adm127in' and password == '2Uh0tOO7&'

def authenticate():
    return Response(
        'Access Denied: Authentication Required.', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

@app.route('/export')
@requires_auth
def export():
    conn = sqlite3.connect('ncc_members.db')
    df = pd.read_sql_query("SELECT * FROM members", conn)
    file_path = "ncc_members_export.xlsx"
    df.to_excel(file_path, index=False)
    conn.close()
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
