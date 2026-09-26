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
            if check_password_hash(user['password'], password) or user['password'] == password:
                session['role'] = user['role']
                session['username'] = user['username']
                
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
        username = request.form.get('username')
        password = request.form.get('password')
        
        nik_anak = request.form.get('nik_anak')
        nama_anak = request.form.get('nama_anak')
        tanggal_lahir = request.form.get('tanggal_lahir')
        jenis_kelamin = request.form.get('jenis_kelamin')
        nama_ortu = request.form.get('nama_ortu')
        alamat_lengkap = request.form.get('alamat_lengkap')
        posyandu = request.form.get('posyandu_terdaftar')
        no_kms = request.form.get('no_register_kms')
        
        bb_lahir = request.form.get('bb_lahir') or 0
        pb_lahir = request.form.get('pb_lahir') or 0

        if not username or not password or not nik_anak:
            flash('Gagal mendaftar: Pastikan form HTML sudah versi terbaru dan terisi semua!', 'danger')
            return redirect(url_for('register'))

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
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

        hashed_password = generate_password_hash(password)
        
        try:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, 'ortu')", (username, hashed_password))
            
            cursor.execute("""
                INSERT INTO anak (nik_anak, nama_lengkap, tanggal_lahir, jenis_kelamin, 
                                  nama_ortu, username_ortu, alamat_lengkap, posyandu_terdaftar, 
                                  no_register_kms, bb_lahir, pb_lahir) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (nik_anak, nama_anak, tanggal_lahir, jenis_kelamin, nama_ortu, username, 
                  alamat_lengkap, posyandu, no_kms, float(bb_lahir), float(pb_lahir)))
            
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
    
    # 1. Endpoint AJAX untuk Grafik KMS
    grafik_nik = request.args.get('grafik_nik')
    if grafik_nik:
        if session['role'] == 'ortu':
            cursor.execute("SELECT usia_bulan, berat_badan, tinggi_badan FROM pengukuran WHERE nik_anak=%s AND nik_anak IN (SELECT nik_anak FROM anak WHERE username_ortu=%s) ORDER BY usia_bulan ASC", (grafik_nik, session['username']))
        else:
            cursor.execute("SELECT usia_bulan, berat_badan, tinggi_badan FROM pengukuran WHERE nik_anak=%s ORDER BY usia_bulan ASC", (grafik_nik,))
        
        data_grafik = cursor.fetchall()
        conn.close()
        return jsonify(data_grafik)

    # 2. Tangkap Input & Kalkulasi Z-SCORE WHO + Deteksi Tren
    if request.method == 'POST' and session['role'] == 'admin':
        nik_anak = request.form['nik_anak']
        tgl_ukur = request.form['tanggal_pengukuran']
        usia = float(request.form['usia_bulan'])
        bb = float(request.form['berat_badan'])
        tb = float(request.form['tinggi_badan'])
        lingkar = request.form.get('lingkar_kepala', 0)
        lila = request.form.get('lila', 0)
        
        cursor.execute("SELECT jenis_kelamin FROM anak WHERE nik_anak = %s", (nik_anak,))
        anak_info = cursor.fetchone()
        jk = anak_info['jenis_kelamin'] if anak_info else 'L'
        
        # DETEKSI TREN "T" (Tidak Naik) ATAU "N" (Naik)
        cursor.execute("SELECT berat_badan FROM pengukuran WHERE nik_anak = %s ORDER BY usia_bulan DESC LIMIT 1", (nik_anak,))
        data_lama = cursor.fetchone()
        
        tren_status = "Data Awal"
        if data_lama:
            bb_lama = float(data_lama['berat_badan'])
            if bb <= bb_lama:
                tren_status = "T (Tidak Naik/Turun) ⚠️"
            else:
                tren_status = "N (Naik) ✅"
        
        cursor.execute("""
            INSERT INTO pengukuran (nik_anak, tanggal_pengukuran, usia_bulan, berat_badan, tinggi_badan, lingkar_kepala, lila) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (nik_anak, tgl_ukur, usia, bb, tb, lingkar, lila))
        
        id_pengukuran = cursor.lastrowid
        
        if jk == 'L':
            bb_normal_bawah = (usia * 0.2) + 3.0  
            bb_normal_atas = (usia * 0.25) + 4.5  
            tb_normal_bawah = (usia * 0.8) + 48.0 
        else:
            bb_normal_bawah = (usia * 0.18) + 2.8 
            bb_normal_atas = (usia * 0.23) + 4.2 
            tb_normal_bawah = (usia * 0.75) + 47.0 
            
        if bb < bb_normal_bawah:
            bb_u_status = 'Gizi Kurang'
            if bb < bb_normal_bawah - 1.5: bb_u_status = 'Gizi Buruk'
        elif bb > bb_normal_atas:
            bb_u_status = 'Risiko Lebih'
        else:
            bb_u_status = 'Berat Normal'
            
        if tb < tb_normal_bawah:
            tb_u_status = 'Stunting (Pendek)'
            if tb < tb_normal_bawah - 3: tb_u_status = 'Sangat Pendek'
        else:
            tb_u_status = 'Tinggi Normal'
            
        kategori_status = f"{bb_u_status} | {tb_u_status} | Tren: {tren_status}"
            
        cursor.execute("""
            INSERT INTO status_gizi (id_pengukuran, bb_u, tb_u, bb_tb, imt_u, kategori_status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (id_pengukuran, bb_u_status, tb_u_status, "TBA", "Tidak Dipakai", kategori_status))
        
        conn.commit()
        flash('Data berhasil ditambahkan dengan perhitungan Z-Score standar dan deteksi tren!', 'success')
        return redirect(url_for('pengukuran'))

    # 3. Render Tabel Data (dengan status gizi digabung)
    if session['role'] == 'ortu':
        cursor.execute("""
            SELECT p.*, a.nama_lengkap, s.kategori_status 
            FROM pengukuran p 
            JOIN anak a ON p.nik_anak = a.nik_anak 
            LEFT JOIN status_gizi s ON p.id_pengukuran = s.id_pengukuran
            WHERE a.username_ortu = %s ORDER BY p.tanggal_pengukuran DESC
        """, (session['username'],))
    else:
        cursor.execute("""
            SELECT p.*, a.nama_lengkap, s.kategori_status 
            FROM pengukuran p 
            JOIN anak a ON p.nik_anak = a.nik_anak 
            LEFT JOIN status_gizi s ON p.id_pengukuran = s.id_pengukuran
            ORDER BY p.tanggal_pengukuran DESC
        """)
        
    data_pengukuran = cursor.fetchall()
    cursor.execute("SELECT nik_anak, nama_lengkap FROM anak")
    daftar_anak = cursor.fetchall()
    conn.close()
    
    return render_template('ui_pengukuran.html', data_pengukuran=data_pengukuran, daftar_anak=daftar_anak, role=session['role'])


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


@app.route('/riwayat', methods=['GET', 'POST'])
def riwayat():
    if 'role' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST' and session['role'] == 'admin':
        nik = request.form['nik_anak']
        imunisasi = request.form['riwayat_imunisasi']
        asi = request.form['asi_eksklusif']
        vit_a = request.form['vitamin_a']
        mpasi = request.form['riwayat_mpasi']
        alergi = request.form['riwayat_penyakit_alergi']
        rawat = request.form['riwayat_rawat_inap']
        
        cursor.execute("""
            INSERT INTO riwayat_kesehatan (nik_anak, riwayat_imunisasi, asi_eksklusif, vitamin_a, riwayat_mpasi, riwayat_penyakit_alergi, riwayat_rawat_inap) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (nik, imunisasi, asi, vit_a, mpasi, alergi, rawat))
        conn.commit()
        flash('Data Riwayat Kesehatan berhasil ditambahkan!', 'success')
        return redirect(url_for('riwayat'))
    
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
    cursor.execute("SELECT nik_anak, nama_lengkap FROM anak")
    daftar_anak = cursor.fetchall()
    conn.close()
    return render_template('ui_riwayat.html', data_riwayat=data_riwayat, daftar_anak=daftar_anak, role=session['role'])


@app.route('/perkembangan', methods=['GET', 'POST'])
def perkembangan():
    if 'role' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    ALL_TUGAS = {
        'Usia 0 - 6 Bulan': [['KP1', 'Mata melirik ke kanan dan ke kiri'], ['TS2', 'Membalas senyum pada orang lain'], ['GK3', 'Menegakkan kepala saat ditengkurapkan'], ['GK4', 'Miring sendiri / Tengkurap mandiri'], ['KA5', 'Mengeluarkan 3 suara berbeda (mengoceh)']],
        'Usia 6 - 12 Bulan': [['GH6', 'Meraih dan memegang benda di hadapannya'], ['GK7', 'Duduk sendiri tanpa dibantu'], ['GH8', 'Membuka tutup mainan/kotak'], ['TS9', 'Aktif bermain "Ciluk-ba"'], ['GH10', 'Mengambil benda dengan ibu jari dan telunjuk']],
        'Usia 1 - 2 Tahun': [['GK12', 'Berjalan sendiri tanpa berpegangan'], ['MD14', 'Minum dari gelas sendiri tanpa tumpah'], ['KA16', 'Menyebut 2 kata berbeda dengan benar']],
        'Usia 2 - 3 Tahun': [['GK24', 'Berlari tanpa sering jatuh'], ['GH26', 'Mencoret-coret dengan alat tulis'], ['KA28', 'Merangkai kalimat tanya atau sangkal'], ['MD31', 'Membuka baju dan melepas celana sendiri']],
        'Usia 3 - 4 Tahun': [['GK34', 'Berdiri dengan satu kaki tanpa berpegangan'], ['GH36', 'Menggambar garis lurus atau lingkaran'], ['KC38', 'Mengenal dan menyebutkan minimal 1 warna'], ['TS40', 'Mulai bermain bersama teman sebaya']],
        'Usia 4 - 5 Tahun': [['GK42', 'Melompat dengan satu kaki'], ['GH45', 'Menggambar orang dengan minimal 3 bagian tubuh'], ['KA47', 'Menceritakan kejadian sehari-hari dengan lancar'], ['MD50', 'Mencuci dan mengeringkan tangan sendiri']]
    }
    
    try:
        if request.method == 'POST' and session['role'] == 'admin':
            nik = request.form['nik_anak']
            tugas_list = request.form.getlist('tugas[]') 
            
            cursor.execute("DELETE FROM pencapaian_perkembangan WHERE nik_anak = %s", (nik,))
            for kode in tugas_list:
                cursor.execute("INSERT INTO pencapaian_perkembangan (nik_anak, kode_tugas) VALUES (%s, %s)", (nik, kode))
            conn.commit()
            flash('Capaian perkembangan berhasil diperbarui!', 'success')
            return redirect(url_for('perkembangan', nik=nik))

        nik_filter = request.args.get('nik', '')
        checked_tasks = []
        if nik_filter:
            cursor.execute("SELECT kode_tugas FROM pencapaian_perkembangan WHERE nik_anak = %s", (nik_filter,))
            for row in cursor.fetchall():
                checked_tasks.append(row['kode_tugas'])
                
        if session['role'] == 'ortu':
            cursor.execute("SELECT nik_anak, nama_lengkap FROM anak WHERE username_ortu = %s", (session['username'],))
        else:
            cursor.execute("SELECT nik_anak, nama_lengkap FROM anak")
            
        daftar_anak = cursor.fetchall()
        
    except Exception as e:
        flash(f"Gagal memuat data dari database: {str(e)}", "danger")
        daftar_anak = []
        checked_tasks = []
        nik_filter = ''
    finally:
        conn.close()
    
    return render_template('ui_perkembangan.html', 
                           daftar_anak=daftar_anak, role=session['role'], 
                           nik_terpilih=nik_filter, checked_tasks=checked_tasks,
                           all_tugas=ALL_TUGAS)

if __name__ == '__main__':
    app.run(debug=True, ssl_context='adhoc')
