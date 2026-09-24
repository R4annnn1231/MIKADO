from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector

app = Flask(__name__)
# Secret key digunakan untuk mengamankan sesi (session)
app.secret_key = 'mikado_rahasia_aman_123'

# ==========================================
# 1. KONEKSI DATABASE (Pengganti koneksi.php)
# ==========================================
def get_db_connection():
    return mysql.connector.connect(
        host="sql207.infinityfree.com",
        user="if0_42422230",
        password="yH9vII3P54P8MGT",
        database="if0_42422230_db_pemantauan_anak"
    )

# ==========================================
# 2. SISTEM AUTENTIKASI
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'role' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        if user:
            # Menggunakan werkzeug untuk verifikasi hash, setara password_verify di PHP
            if check_password_hash(user['password'], password) or user['password'] == password:
                session['role'] = user['role']
                session['username'] = user['username']
                
                # Jika role adalah ortu, ambil NIK anak
                if user['role'] == 'ortu':
                    cursor.execute("SELECT nik_anak FROM anak WHERE username_ortu = %s", (username,))
                    anak = cursor.fetchone()
                    if anak:
                        session['nik_anak'] = anak['nik_anak']
                
                conn.close()
                return redirect(url_for('index'))
            else:
                flash('Password yang Anda masukkan salah!', 'danger')
        else:
            flash('Username tidak ditemukan di sistem!', 'danger')
        conn.close()
        
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'role' in session:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form['username']
        # Enkripsi password menggunakan hash Python
        password = generate_password_hash(request.form['password'])
        nik_anak = request.form['nik_anak']
        nama_anak = request.form['nama_anak']
        nama_ortu = request.form['nama_ortu']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            flash('Username sudah digunakan! Silakan pilih username lain.', 'danger')
        else:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, 'ortu')", (username, password))
            cursor.execute("INSERT IGNORE INTO anak (nik_anak, nama_lengkap, nama_ortu, username_ortu) VALUES (%s, %s, %s, %s)", (nik_anak, nama_anak, nama_ortu, username))
            conn.commit()
            flash('Pendaftaran berhasil! Silakan login.', 'success')
            return redirect(url_for('login'))
            
        conn.close()
        
    return render_template('register.html')

# ==========================================
# 3. MANAJEMEN HALAMAN UTAMA (DASHBOARD)
# ==========================================
@app.route('/')
def index():
    if 'role' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Logika Filter Role: Menggabungkan index.php dan index_ortu.php
    if session['role'] == 'ortu':
        cursor.execute("SELECT * FROM anak WHERE username_ortu = %s", (session['username'],))
        sapaan = "Orang Tua"
    else:
        cursor.execute("SELECT * FROM anak")
        sapaan = "Admin"
        
    anak_data = cursor.fetchall()
    conn.close()
    
    return render_template('index.html', anak_data=anak_data, sapaan=sapaan, role=session['role'], username=session['username'])

# ==========================================
# 4. MANAJEMEN PROFIL & DATA
# ==========================================
@app.route('/profil', methods=['GET', 'POST'])
def profil():
    if 'role' not in session:
        return redirect(url_for('login'))
        
    username_saat_ini = session['username']
    
    if request.method == 'POST':
        username_baru = request.form['username']
        password_lama = request.form['password_lama']
        password_baru = request.form['password_baru']
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT password FROM users WHERE username = %s", (username_saat_ini,))
        user = cursor.fetchone()
        
        if check_password_hash(user['password'], password_lama) or user['password'] == password_lama:
            if password_baru:
                hashed_pw = generate_password_hash(password_baru)
                cursor.execute("UPDATE users SET username=%s, password=%s WHERE username=%s", (username_baru, hashed_pw, username_saat_ini))
            else:
                cursor.execute("UPDATE users SET username=%s WHERE username=%s", (username_baru, username_saat_ini))
            
            conn.commit()
            session['username'] = username_baru
            flash('Profil berhasil diperbarui!', 'success')
        else:
            flash('Password lama salah! Profil tidak bisa diubah.', 'danger')
            
        conn.close()
        
    return render_template('profil.html', username=session['username'])

@app.route('/gizi')
def gizi():
    if 'role' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Query persis seperti ui_gizi.php
    query = """
        SELECT anak.nama_lengkap, pengukuran.usia_bulan, status_gizi.* 
        FROM status_gizi 
        JOIN pengukuran ON status_gizi.id_pengukuran = pengukuran.id_pengukuran 
        JOIN anak ON pengukuran.nik_anak = anak.nik_anak 
        ORDER BY pengukuran.tanggal_pengukuran DESC
    """
    cursor.execute(query)
    data_gizi = cursor.fetchall()
    conn.close()
    
    return render_template('ui_gizi.html', data_gizi=data_gizi)

@app.route('/edit_anak/<nik>', methods=['GET', 'POST'])
def edit_anak(nik):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        nama_lengkap = request.form['nama_lengkap']
        nama_ortu = request.form['nama_ortu']
        cursor.execute("UPDATE anak SET nama_lengkap=%s, nama_ortu=%s WHERE nik_anak=%s", (nama_lengkap, nama_ortu, nik))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
        
    cursor.execute("SELECT * FROM anak WHERE nik_anak = %s", (nik,))
    data = cursor.fetchone()
    conn.close()
    return render_template('edit_anak.html', data=data)

# Menjalankan Server
if __name__ == '__main__':
    app.run(debug=True, ssl_context='adhoc')