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

# Configuração para PyInstaller (caminhos absolutos)
base_dir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.secret_key = 'escolasegura2024-chavesegura-super-secreta'
app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16MB Max
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
DB_NAME = os.path.join(base_dir, "escolasegura.db")

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ============ BANCO DE DADOS ============
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS denuncias (
        id INTEGER PRIMARY KEY AUTOINCREMENT, protocolo TEXT UNIQUE, data_envio TEXT,
        data_ocorrido TEXT, escola TEXT, local TEXT, turma TEXT, tipo TEXT,
        descricao TEXT, imagem TEXT, status TEXT DEFAULT 'Nova', observacoes TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT UNIQUE, senha TEXT)''')
    
    # Criar admin padrão se não existir
    c.execute("SELECT COUNT(*) FROM admin")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO admin (usuario, senha) VALUES (?, ?)", 
                  ('administrador', generate_password_hash('admin123')))
    conn.commit()
    conn.close()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ============ ROTAS PÚBLICAS ============
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            escola = request.form.get('escola')
            local = request.form.get('local')
            tipo = request.form.get('tipo')
            descricao = request.form.get('descricao')
            
            if not all([escola, local, tipo, descricao]):
                flash('Preencha os campos obrigatórios!', 'error')
                return redirect(url_for('index'))
                
            imagem = ''
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    imagem = filename
            
            protocolo = f"ES-{datetime.now().strftime('%Y%m%d')}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"
            
            conn = get_db()
            conn.execute('''INSERT INTO denuncias (protocolo, data_envio, data_ocorrido, escola, local, turma, tipo, descricao, imagem) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                         (protocolo, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), request.form.get('data_ocorrido'),
                          escola, local, request.form.get('turma'), tipo, descricao, imagem))
            conn.commit()
            conn.close()
            
            return render_template('public.html', protocolo=protocolo)
        except Exception as e:
            flash(f'Erro ao salvar: {str(e)}', 'error')
    
    return render_template('public.html')

@app.route('/qrcode')
def gerar_qr():
    img = qrcode.make(request.host_url)
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

# ============ ROTAS ADMIN ============
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

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

def admin_required(f):
    def wrap(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

@app.route('/dashboard')
@admin_required
def dashboard():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM denuncias").fetchone()[0]
    status_raw = conn.execute("SELECT status, COUNT(*) FROM denuncias GROUP BY status").fetchall()
    tipos_raw = conn.execute("SELECT tipo, COUNT(*) FROM denuncias GROUP BY tipo").fetchall()
    conn.close()
    
    stats = {row[0]: row[1] for row in status_raw}
    tipos = {row[0]: row[1] for row in tipos_raw}
    
    return render_template('dashboard.html', total=total, stats=stats, tipos=tipos)

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
    obs = request.form.get('observacoes')
    conn = get_db()
    if obs:
        conn.execute("UPDATE denuncias SET status=?, observacoes=COALESCE(observacoes||'\n', '') || ? WHERE id=?", (status, f"[{datetime.now().strftime('%d/%m/%Y')}] {obs}", id))
    else:
        conn.execute("UPDATE denuncias SET status=? WHERE id=?", (status, id))
    conn.commit()
    conn.close()
    flash('Status atualizado com sucesso!', 'success')
    return redirect(url_for('denuncias'))

@app.route('/exportar/<formato>')
@admin_required
def exportar(formato):
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT protocolo, data_envio, tipo, local, status FROM denuncias", conn)
    conn.close()
    
    if formato == 'excel':
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Denúncias')
        output.seek(0)
        return send_file(output, download_name="relatorio_escolasegura.xlsx", as_attachment=True)
    
    elif formato == 'pdf':
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Relatório de Denúncias - EscolaSegura", ln=True, align='C')
        for i, row in df.iterrows():
            pdf.cell(200, 10, txt=f"{row['protocolo']} | {row['tipo']} | {row['status']}", ln=True)
        pdf_output = os.path.join(base_dir, 'relatorio.pdf')
        pdf.output(pdf_output)
        return send_file(pdf_output, as_attachment=True)

@app.route('/verificar-sessao')
def verificar_sessao():
    return f"Sessão atual: {session.get('admin')}"

@app.route('/reset-admin-direto')
def reset_admin_direto():
    from werkzeug.security import generate_password_hash
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Reseta para a senha 'admin'
    senha_hash = generate_password_hash('admin')
    cursor.execute("UPDATE admin SET senha = ? WHERE usuario = ?", (senha_hash, 'admin'))
    conn.commit()
    conn.close()
    return "Senha resetada com sucesso para 'admin'!"

if __name__ == '__main__':
    try:
        init_db()
        app.run(debug=True, port=5000)
    except Exception as e:
        print("------------------------------------------")
        print("ERRO ENCONTRADO, O SISTEMA NÃO PODE INICIAR:")
        print(e)
        print("------------------------------------------")
        input("Pressione ENTER para fechar esta janela...")