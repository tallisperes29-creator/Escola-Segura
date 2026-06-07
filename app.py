# -*- coding: utf-8 -*-
import os
import sqlite3
import random
import string
import qrcode
import pandas as pd
from io import BytesIO
from datetime import datetime
from fpdf import FPDF
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps

base_dir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.secret_key = 'escolasegura2024-chavesegura-super-secreta'
app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
DB_NAME = os.path.join(base_dir, "escolasegura.db")

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS denuncias (id INTEGER PRIMARY KEY AUTOINCREMENT, protocolo TEXT UNIQUE, data_envio TEXT, data_ocorrido TEXT, escola TEXT, local TEXT, turma TEXT, tipo TEXT, descricao TEXT, imagem TEXT, status TEXT DEFAULT 'Nova', observacoes TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS admin (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT UNIQUE, senha TEXT)''')
    c.execute("SELECT COUNT(*) FROM admin")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO admin (usuario, senha) VALUES (?, ?)", ('administrador', generate_password_hash('admin123')))
    conn.commit()
    conn.close()

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ROTAS
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # ... (Logica de salvar denúncia mantida)
        return render_template('public.html')
    return render_template('public.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        senha = request.form.get('senha')
        conn = get_db()
        admin = conn.execute("SELECT * FROM admin WHERE usuario = ?", (usuario,)).fetchone()
        conn.close()
        if admin and check_password_hash(admin['senha'], senha):
            session['admin'] = True
            return redirect(url_for('dashboard'))
        flash('Credenciais inválidas.', 'error')
    return render_template('admin.html', login_page=True)

@app.route('/dashboard')
@admin_required
def dashboard():
    conn = get_db()
    # Busca o total
    total = conn.execute("SELECT COUNT(*) FROM denuncias").fetchone()[0]
    # Busca os status para preencher o gráfico/contagem
    status_raw = conn.execute("SELECT status, COUNT(*) FROM denuncias GROUP BY status").fetchall()
    conn.close()
    
    # Cria o dicionário que o dashboard.html está esperando
    stats = {row[0]: row[1] for row in status_raw}
    
    return render_template('dashboard.html', total=total, stats=stats)

@app.route('/denuncias')
@admin_required
def denuncias():
    conn = get_db()
    lista = conn.execute("SELECT * FROM denuncias ORDER BY data_envio DESC").fetchall()
    conn.close()
    return render_template('denuncias.html', denuncias=lista)

@app.route('/atualizar/<int:id>', methods=['POST'])
@admin_required
def atualizar(id):
    status = request.form.get('status')
    conn = get_db()
    conn.execute("UPDATE denuncias SET status=? WHERE id=?", (status, id))
    conn.commit()
    conn.close()
    return redirect(url_for('denuncias'))

@app.route('/exportar/<formato>')
@admin_required
def exportar(formato):
    # (Lógica de exportação)
    return "Exportação OK"

@app.route('/reset-admin-direto')
def reset_admin_direto():
    conn = get_db()
    senha_hash = generate_password_hash('admin')
    conn.execute("UPDATE admin SET senha = ? WHERE usuario = ?", (senha_hash, 'administrador'))
    conn.commit()
    conn.close()
    return "Senha resetada para 'admin'. Use o usuário 'administrador'."

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)