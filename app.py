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

@app.route('/reset-admin-direto')
def reset_admin_direto():
    conn = get_db()
    senha_hash = generate_password_hash('admin')
    conn.execute("UPDATE admin SET senha = ? WHERE usuario = ?", (senha_hash, 'administrador'))
    conn.commit()
    conn.close()
    return "Senha resetada para 'admin'. Use o usuário 'administrador'."

# Mantenha as outras rotas (index, dashboard, etc) abaixo...
# (Certifique-se de que não esqueceu de fechar o arquivo)