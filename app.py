from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector

app = Flask(__name__)
# Secret key digunakan untuk mengamankan sesi (session)
app.secret_key = 'mikado_rahasia_aman_123'

# ==========================================
# 1. KONEKSI DATABASE (TiDB Cloud)
# ==========================================
def get_db_connection():
    return mysql.connector.connect(
        host="gateway01.ap-southeast-1.prod.aws.tidbcloud.com",
        port=4000,
        user="23YJq4NcMhgnK5h.root",
        password="yu4v6RGpScB6UVoT",
        database="Mikado",
        ssl_verify_cert=True,
        ssl_verify_identity=True
    )

# ==========================================
# 2. SISTEM AUTENTIKASI & REGISTRASI
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
            # Verifikasi password
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
        # Data Akun (Tabel users)
        username = request.form['username']
        password = request.form['password']
        
        # Data Anak (Tabel anak)
        nik_anak = request.form['nik_anak']
        nama_anak = request.form['nama_anak']
        tanggal_lahir = request.form['tanggal_lahir']
        jenis_kelamin = request.form['jenis_kelamin']
        nama_ortu = request.form['nama_ortu']
        alamat_lengkap = request.form['alamat_lengkap']
        posyandu = request.form['posyandu_terdaftar']
        no_kms = request.form['no_register_kms']
        bb_lahir = request.form['bb_lahir']
        pb_lahir = request.form['pb_lahir']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Cek apakah username atau NIK sudah terdaftar
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            flash('Username sudah digunakan! Silakan pilih yang lain.', 'danger')
            conn.close()
            return redirect(url_for('register'))
            
        cursor.execute("SELECT * FROM anak WHERE nik_anak = %s", (nik_anak,))
        if cursor.fetchone():
            flash('NIK Anak sudah terdaftar di sistem!', 'danger')
            conn.close()
            return redirect(url_for('register'))

        # Enkripsi password
        hashed_password = generate_password_hash(password)
        
        try:
            # 1. Simpan ke tabel users
            cursor.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, 'ortu')", (username, hashed_password))
            
            # 2. Simpan ke tabel anak
            cursor.execute("""
                INSERT INTO anak (nik_anak, nama_lengkap, tanggal_lahir, jenis_kelamin, 
                                  nama_ortu, username_ortu, alamat_lengkap, posyandu_terdaftar, 
                                  no_register_kms, bb_lahir, pb_lahir) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (nik_anak, nama_anak, tanggal_lahir, jenis_kelamin, nama_ortu, username, 
                  alamat_lengkap, posyandu, no_kms, bb_lahir, pb_lahir))
            
            conn.commit()
            flash('Pendaftaran berhasil! Silakan login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            conn.rollback()
            flash(f'Terjadi kesalahan database: {str(e)}', 'danger')
        finally:
            conn.close()
            
    return render_template('register.html')

# ==========================================
# 3. MANAJEMEN HALAMAN UTAMA & PROFIL
# ==========================================
@app.route('/')
def index():
    if 'role' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if session['role'] == 'ortu':
        cursor.execute("SELECT * FROM anak WHERE username_ortu = %s", (session['username'],))
        sapaan = "Orang Tua"
    else:
        cursor.execute("SELECT * FROM anak")
        sapaan = "Admin"
        
    anak_data = cursor.fetchall()
    conn.close()
    
    return render_template('index.html', anak_data=anak_data, sapaan=sapaan, role=session['role'], username=session['username'])

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

@app.route('/edit_anak/<nik>', methods=['GET', 'POST'])
def edit_anak(nik):
    if 'role' not in session:
        return redirect(url_for('login'))
        
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

# ==========================================
# 4. RUTE 5 MENU UTAMA MIKAdO
# ==========================================

@app.route('/identitas')
def identitas():
    if 'role' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if session['role'] == 'ortu':
        cursor.execute("SELECT * FROM anak WHERE username_ortu = %s", (session['username'],))
    else:
        cursor.execute("SELECT * FROM anak")
        
    data_anak = cursor.fetchall()
    conn.close()
    return render_template('ui_identitas.html', data_anak=data_anak)


@app.route('/pengukuran', methods=['GET', 'POST'])
def pengukuran():
    if 'role' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. Endpoint AJAX untuk merespons permintaan Grafik KMS Antropometri
    grafik_nik = request.args.get('grafik_nik')
    if grafik_nik:
        if session['role'] == 'ortu':
            cursor.execute("SELECT usia_bulan, berat_badan FROM pengukuran WHERE nik_anak=%s AND nik_anak IN (SELECT nik_anak FROM anak WHERE username_ortu=%s) ORDER BY usia_bulan ASC", (grafik_nik, session['username']))
        else:
            cursor.execute("SELECT usia_bulan, berat_badan FROM pengukuran WHERE nik_anak=%s ORDER BY usia_bulan ASC", (grafik_nik,))
        
        data_grafik = cursor.fetchall()
        conn.close()
        return jsonify(data_grafik)

    # 2. Tangkap Data Input Baru (Mode Admin) & Hitung Gizi Otomatis
    if request.method == 'POST' and session['role'] == 'admin':
        nik_anak = request.form['nik_anak']
        tgl_ukur = request.form['tanggal_pengukuran']
        usia = float(request.form['usia_bulan'])
        bb = float(request.form['berat_badan'])
        tb = float(request.form['tinggi_badan'])
        lingkar = request.form.get('lingkar_kepala', 0)
        lila = request.form.get('lila', 0)
        
        # Simpan ke tabel pengukuran
        cursor.execute("""
            INSERT INTO pengukuran (nik_anak, tanggal_pengukuran, usia_bulan, berat_badan, tinggi_badan, lingkar_kepala, lila) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (nik_anak, tgl_ukur, usia, bb, tb, lingkar, lila))
        
        id_pengukuran = cursor.lastrowid # Ambil ID yang baru saja masuk
        
        # LOGIKA PERHITUNGAN STATUS GIZI (IMT)
        tb_m = tb / 100.0 # Ubah cm ke meter
        if tb_m > 0:
            imt = round(bb / (tb_m * tb_m), 1)
        else:
            imt = 0
            
        # Penentuan Kategori IMT/U Standar Dasar
        if imt < 13.5:
            imt_u_status = 'Gizi Buruk'
        elif 13.5 <= imt < 14.5:
            imt_u_status = 'Gizi Kurang'
        elif 14.5 <= imt <= 18.5:
            imt_u_status = 'Normal'
        elif 18.5 < imt <= 19.5:
            imt_u_status = 'Beresiko Lebih'
        else:
            imt_u_status = 'Obesitas'
            
        # Placeholder untuk status lain (Bisa Anda kembangkan nanti jika ada rumus spesifik Z-Score)
        kategori_status = imt_u_status
            
        cursor.execute("""
            INSERT INTO status_gizi (id_pengukuran, bb_u, tb_u, bb_tb, imt_u, kategori_status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (id_pengukuran, "Sesuai Umur", "Normal", "Normal", imt_u_status, kategori_status))
        
        conn.commit()
        flash('Data Pengukuran berhasil ditambahkan & Status Gizi diperbarui!', 'success')
        return redirect(url_for('pengukuran'))

    # 3. Render Tabel Data Pengukuran
    if session['role'] == 'ortu':
        cursor.execute("""
            SELECT p.*, a.nama_lengkap 
            FROM pengukuran p 
            JOIN anak a ON p.nik_anak = a.nik_anak 
            WHERE a.username_ortu = %s
            ORDER BY p.tanggal_pengukuran DESC
        """, (session['username'],))
    else:
        cursor.execute("""
            SELECT p.*, a.nama_lengkap 
            FROM pengukuran p 
            JOIN anak a ON p.nik_anak = a.nik_anak
            ORDER BY p.tanggal_pengukuran DESC
        """)
        
    data_pengukuran = cursor.fetchall()
    
    # Tarik daftar anak untuk dropdown form
    cursor.execute("SELECT nik_anak, nama_lengkap FROM anak")
    daftar_anak = cursor.fetchall()
    
    conn.close()
    
    return render_template('ui_pengukuran.html', data_pengukuran=data_pengukuran, daftar_anak=daftar_anak, role=session['role'])
    # 2. Render Tabel Data Pengukuran
    if session['role'] == 'ortu':
        cursor.execute("""
            SELECT p.*, a.nama_lengkap 
            FROM pengukuran p 
            JOIN anak a ON p.nik_anak = a.nik_anak 
            WHERE a.username_ortu = %s
        """, (session['username'],))
    else:
        cursor.execute("""
            SELECT p.*, a.nama_lengkap 
            FROM pengukuran p 
            JOIN anak a ON p.nik_anak = a.nik_anak
        """)
        
    data_pengukuran = cursor.fetchall()
    conn.close()
    
    # Anda perlu memastikan ui_pengukuran.html memiliki struktur form input & script Chart.js
    return render_template('ui_pengukuran.html', data_pengukuran=data_pengukuran)


@app.route('/gizi')
def gizi():
    if 'role' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if session['role'] == 'ortu':
        query = """
            SELECT a.nama_lengkap, p.usia_bulan, s.bb_u, s.tb_u, s.bb_tb, s.imt_u, s.kategori_status 
            FROM status_gizi s
            JOIN pengukuran p ON s.id_pengukuran = p.id_pengukuran
            JOIN anak a ON p.nik_anak = a.nik_anak
            WHERE a.username_ortu = %s
            ORDER BY p.tanggal_pengukuran DESC
        """
        cursor.execute(query, (session['username'],))
    else:
        query = """
            SELECT a.nama_lengkap, p.usia_bulan, s.bb_u, s.tb_u, s.bb_tb, s.imt_u, s.kategori_status 
            FROM status_gizi s
            JOIN pengukuran p ON s.id_pengukuran = p.id_pengukuran
            JOIN anak a ON p.nik_anak = a.nik_anak
            ORDER BY p.tanggal_pengukuran DESC
        """
        cursor.execute(query)
        
    data_gizi = cursor.fetchall()
    conn.close()
    return render_template('ui_gizi.html', data_gizi=data_gizi)


@app.route('/riwayat')
def riwayat():
    if 'role' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if session['role'] == 'ortu':
        cursor.execute("""
            SELECT r.*, a.nama_lengkap 
            FROM riwayat_kesehatan r 
            JOIN anak a ON r.nik_anak = a.nik_anak
            WHERE a.username_ortu = %s
        """, (session['username'],))
    else:
        cursor.execute("""
            SELECT r.*, a.nama_lengkap 
            FROM riwayat_kesehatan r 
            JOIN anak a ON r.nik_anak = a.nik_anak
        """)
        
    data_riwayat = cursor.fetchall()
    conn.close()
    return render_template('ui_riwayat.html', data_riwayat=data_riwayat)


@app.route('/perkembangan')
def perkembangan():
    if 'role' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if session['role'] == 'ortu':
        cursor.execute("""
            SELECT p.*, a.nama_lengkap 
            FROM pencapaian_perkembangan p 
            JOIN anak a ON p.nik_anak = a.nik_anak
            WHERE a.username_ortu = %s
        """, (session['username'],))
    else:
        cursor.execute("""
            SELECT p.*, a.nama_lengkap 
            FROM pencapaian_perkembangan p 
            JOIN anak a ON p.nik_anak = a.nik_anak
        """)
        
    data_perkembangan = cursor.fetchall()
    conn.close()
    return render_template('ui_perkembangan.html', data_perkembangan=data_perkembangan)

# Menjalankan Server
if __name__ == '__main__':
    app.run(debug=True, ssl_context='adhoc')
