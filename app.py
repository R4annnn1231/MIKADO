from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector

app = Flask(__name__)
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
# HELPER: AUTO-GENERATE NO KMS 6 DIGIT BERURUTAN
# ==========================================
def generate_no_kms(cursor):
    cursor.execute("SELECT no_register_kms FROM anak ORDER BY no_register_kms DESC LIMIT 1")
    last_kms = cursor.fetchone()
    
    if last_kms and last_kms.get('no_register_kms'):
        try:
            digits = ''.join(filter(str.isdigit, last_kms['no_register_kms']))
            last_number = int(digits) if digits else 0
            next_number = last_number + 1
        except:
            next_number = 1
    else:
        next_number = 1
        
    return f"{next_number:06d}"

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
        
        bb_lahir = request.form.get('bb_lahir') or 0
        pb_lahir = request.form.get('pb_lahir') or 0

        if not username or not password or not nik_anak:
            flash('Gagal mendaftar: Pastikan form terisi semua!', 'danger')
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

        # Otomatis generate No KMS 6 digit berurutan
        no_kms = generate_no_kms(cursor)
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
            flash(f'Pendaftaran berhasil! No. KMS otomatis: {no_kms}', 'success')
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
    
    statistik = {
        'total_anak': 0,
        'stunting': 0,
        'gizi_kurang_buruk': 0
    }
    
    if session['role'] == 'ortu':
        cursor.execute("SELECT * FROM anak WHERE username_ortu = %s", (session['username'],))
        sapaan = "Orang Tua"
        anak_data = cursor.fetchall()
        statistik['total_anak'] = len(anak_data)
    else:
        cursor.execute("SELECT * FROM anak")
        sapaan = "Admin"
        anak_data = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*) as total FROM anak")
        res_total = cursor.fetchone()
        statistik['total_anak'] = res_total['total'] if res_total else 0
        
        cursor.execute("SELECT COUNT(*) as total FROM status_gizi WHERE tb_u LIKE '%Stunting%' OR tb_u LIKE '%Sangat Pendek%'")
        res_stunting = cursor.fetchone()
        statistik['stunting'] = res_stunting['total'] if res_stunting else 0
        
        cursor.execute("SELECT COUNT(*) as total FROM status_gizi WHERE bb_u LIKE '%Gizi Kurang%' OR bb_u LIKE '%Gizi Buruk%'")
        res_gizi = cursor.fetchone()
        statistik['gizi_kurang_buruk'] = res_gizi['total'] if res_gizi else 0
        
    conn.close()
    return render_template('index.html', anak_data=anak_data, sapaan=sapaan, role=session['role'], username=session['username'], statistik=statistik)

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

@app.route('/identitas', methods=['GET', 'POST'])
def identitas():
    if 'role' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Tambah Anak Manual oleh Admin via Modal Identitas
    if request.method == 'POST' and session['role'] == 'admin':
        nik_anak = request.form.get('nik_anak')
        nama_anak = request.form.get('nama_anak')
        tanggal_lahir = request.form.get('tanggal_lahir')
        jenis_kelamin = request.form.get('jenis_kelamin')
        nama_ortu = request.form.get('nama_ortu')
        alamat_lengkap = request.form.get('alamat_lengkap')
        posyandu = request.form.get('posyandu_terdaftar')
        bb_lahir = request.form.get('bb_lahir') or 0
        pb_lahir = request.form.get('pb_lahir') or 0

        cursor.execute("SELECT * FROM anak WHERE nik_anak = %s", (nik_anak,))
        if cursor.fetchone():
            flash('Gagal: NIK Anak sudah terdaftar di sistem!', 'danger')
            conn.close()
            return redirect(url_for('identitas'))

        no_kms = generate_no_kms(cursor)

        try:
            cursor.execute("""
                INSERT INTO anak (nik_anak, nama_lengkap, tanggal_lahir, jenis_kelamin, 
                                  nama_ortu, username_ortu, alamat_lengkap, posyandu_terdaftar, 
                                  no_register_kms, bb_lahir, pb_lahir) 
                VALUES (%s, %s, %s, %s, %s, 'admin_manual', %s, %s, %s, %s, %s)
            """, (nik_anak, nama_anak, tanggal_lahir, jenis_kelamin, nama_ortu, 
                  alamat_lengkap, posyandu, no_kms, float(bb_lahir), float(pb_lahir)))
            conn.commit()
            flash(f'Anak berhasil ditambahkan! No. KMS otomatis: {no_kms}', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Gagal menambah data: {str(e)}', 'danger')
        finally:
            conn.close()
        return redirect(url_for('identitas'))

    cari = request.args.get('cari')
    if session['role'] == 'ortu':
        cursor.execute("SELECT * FROM anak WHERE username_ortu = %s", (session['username'],))
        data_anak = cursor.fetchall()
        daftar_anak = data_anak
    else:
        if cari:
            cursor.execute("SELECT * FROM anak WHERE nik_anak = %s OR no_register_kms = %s", (cari, cari))
            data_anak = cursor.fetchall()
        else:
            data_anak = []
        daftar_anak = []

    conn.close()
    return render_template('ui_identitas.html', data_anak=data_anak, daftar_anak=daftar_anak, role=session['role'])


@app.route('/pengukuran', methods=['GET', 'POST'])
def pengukuran():
    if 'role' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    grafik_nik = request.args.get('grafik_nik')
    if grafik_nik:
        if session['role'] == 'ortu':
            cursor.execute("SELECT usia_bulan, berat_badan, tinggi_badan FROM pengukuran WHERE nik_anak=%s AND nik_anak IN (SELECT nik_anak FROM anak WHERE username_ortu=%s) ORDER BY usia_bulan ASC", (grafik_nik, session['username']))
        else:
            cursor.execute("SELECT usia_bulan, berat_badan, tinggi_badan FROM pengukuran WHERE nik_anak=%s ORDER BY usia_bulan ASC", (grafik_nik,))
        data_grafik = cursor.fetchall()
        conn.close()
        return jsonify(data_grafik)

    if request.method == 'POST' and session['role'] == 'admin':
        nik_input = request.form['nik_anak']
        cursor.execute("SELECT nik_anak, jenis_kelamin FROM anak WHERE nik_anak = %s OR no_register_kms = %s", (nik_input, nik_input))
        anak_info = cursor.fetchone()
        
        if not anak_info:
            flash('Gagal: NIK atau No. KMS anak tidak ditemukan di database!', 'danger')
            return redirect(url_for('pengukuran'))
            
        nik_anak = anak_info['nik_anak']
        jk = anak_info['jenis_kelamin']
        tgl_ukur = request.form['tanggal_pengukuran']
        usia = float(request.form['usia_bulan'])
        bb = float(request.form['berat_badan'])
        tb = float(request.form['tinggi_badan'])
        lingkar = request.form.get('lingkar_kepala', 0)
        lila = request.form.get('lila', 0)
        
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
        flash('Data pengukuran berhasil ditambahkan!', 'success')
        return redirect(url_for('pengukuran'))

    cari = request.args.get('cari')
    if session['role'] == 'ortu':
        cursor.execute("""
            SELECT p.*, a.nama_lengkap, s.kategori_status 
            FROM pengukuran p 
            JOIN anak a ON p.nik_anak = a.nik_anak 
            LEFT JOIN status_gizi s ON p.id_pengukuran = s.id_pengukuran
            WHERE a.username_ortu = %s ORDER BY p.tanggal_pengukuran DESC
        """, (session['username'],))
        data_pengukuran = cursor.fetchall()
        cursor.execute("SELECT nik_anak, nama_lengkap FROM anak WHERE username_ortu = %s", (session['username'],))
        daftar_anak = cursor.fetchall()
    else:
        if cari:
            cursor.execute("""
                SELECT p.*, a.nama_lengkap, s.kategori_status 
                FROM pengukuran p 
                JOIN anak a ON p.nik_anak = a.nik_anak 
                LEFT JOIN status_gizi s ON p.id_pengukuran = s.id_pengukuran
                WHERE a.nik_anak = %s OR a.no_register_kms = %s 
                ORDER BY p.tanggal_pengukuran DESC
            """, (cari, cari))
            data_pengukuran = cursor.fetchall()
        else:
            data_pengukuran = []
        daftar_anak = []

    conn.close()
    return render_template('ui_pengukuran.html', data_pengukuran=data_pengukuran, daftar_anak=daftar_anak, role=session['role'])


@app.route('/gizi')
def gizi():
    if 'role' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cari = request.args.get('cari')
    
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
        data_gizi = cursor.fetchall()
        cursor.execute("SELECT nik_anak, nama_lengkap FROM anak WHERE username_ortu = %s", (session['username'],))
        daftar_anak = cursor.fetchall()
    else:
        if cari:
            query = """
                SELECT a.nama_lengkap, p.usia_bulan, s.bb_u, s.tb_u, s.bb_tb, s.imt_u, s.kategori_status 
                FROM status_gizi s
                JOIN pengukuran p ON s.id_pengukuran = p.id_pengukuran
                JOIN anak a ON p.nik_anak = a.nik_anak
                WHERE a.nik_anak = %s OR a.no_register_kms = %s
                ORDER BY p.tanggal_pengukuran DESC
            """
            cursor.execute(query, (cari, cari))
            data_gizi = cursor.fetchall()
        else:
            data_gizi = []
        daftar_anak = []

    cursor.execute("SELECT * FROM rekomendasi_gizi")
    semua_resep = cursor.fetchall()

    for item in data_gizi:
        bb_u = item.get('bb_u') or ''
        usia = float(item.get('usia_bulan') or 0)

        if 'Kurang' in bb_u or 'Buruk' in bb_u:
            target_status = 'Gizi Kurang'
        elif 'Lebih' in bb_u or 'Obesitas' in bb_u:
            target_status = 'Risiko Gizi Lebih'
        else:
            target_status = 'Normal'

        rekomendasi_terpilih = []
        for resep in semua_resep:
            if resep['kategori_status'] == target_status and resep['usia_min_bulan'] <= usia <= resep['usia_max_bulan']:
                rekomendasi_terpilih.append(resep)

        item['rekomendasi'] = rekomendasi_terpilih

    conn.close()
    return render_template('ui_gizi.html', data_gizi=data_gizi, daftar_anak=daftar_anak, role=session['role'])


@app.route('/riwayat', methods=['GET', 'POST'])
def riwayat():
    if 'role' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST' and session['role'] == 'admin':
        nik_input = request.form.get('nik_anak')
        cursor.execute("SELECT nik_anak FROM anak WHERE nik_anak = %s OR no_register_kms = %s", (nik_input, nik_input))
        anak_info = cursor.fetchone()
        
        if not anak_info:
            flash('Gagal: NIK atau No. KMS anak tidak ditemukan.', 'danger')
            return redirect(url_for('riwayat'))
            
        nik = anak_info['nik_anak']
        asi = request.form.get('asi_eksklusif', '-')
        vit_a = request.form.get('vitamin_a', '-')
        alergi = request.form.get('catatan_penyakit', '-')
        
        list_imunisasi = request.form.getlist('imunisasi')
        imunisasi = ", ".join(list_imunisasi) if list_imunisasi else "Belum ada"
        
        mpasi = '-'
        rawat = '-'
        
        try:
            cursor.execute("""
                INSERT INTO riwayat_kesehatan (nik_anak, riwayat_imunisasi, asi_eksklusif, vitamin_a, riwayat_mpasi, riwayat_penyakit_alergi, riwayat_rawat_inap) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (nik, imunisasi, asi, vit_a, mpasi, alergi, rawat))
            conn.commit()
            flash('Data Riwayat Kesehatan berhasil ditambahkan!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Gagal menambahkan data: {str(e)}', 'danger')
            
        return redirect(url_for('riwayat'))
    
    cari = request.args.get('cari')
    if session['role'] == 'ortu':
        cursor.execute("""
            SELECT r.*, 
                   r.riwayat_imunisasi AS imunisasi, 
                   r.riwayat_penyakit_alergi AS catatan_penyakit,
                   CURRENT_DATE() AS tanggal_catat,
                   a.nama_lengkap 
            FROM riwayat_kesehatan r 
            JOIN anak a ON r.nik_anak = a.nik_anak
            WHERE a.username_ortu = %s
        """, (session['username'],))
        data_riwayat = cursor.fetchall()
        cursor.execute("SELECT nik_anak, nama_lengkap FROM anak WHERE username_ortu = %s", (session['username'],))
        daftar_anak = cursor.fetchall()
    else:
        if cari:
            cursor.execute("""
                SELECT r.*, 
                       r.riwayat_imunisasi AS imunisasi, 
                       r.riwayat_penyakit_alergi AS catatan_penyakit,
                       CURRENT_DATE() AS tanggal_catat,
                       a.nama_lengkap 
                FROM riwayat_kesehatan r 
                JOIN anak a ON r.nik_anak = a.nik_anak
                WHERE a.nik_anak = %s OR a.no_register_kms = %s
            """, (cari, cari))
            data_riwayat = cursor.fetchall()
        else:
            data_riwayat = []
        daftar_anak = []
        
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
            nik_input = request.form['nik_anak']
            cursor.execute("SELECT nik_anak FROM anak WHERE nik_anak = %s OR no_register_kms = %s", (nik_input, nik_input))
            anak_info = cursor.fetchone()
            
            if not anak_info:
                flash("Gagal: NIK atau No. KMS tidak ditemukan.", "danger")
                return redirect(url_for('perkembangan'))
                
            nik = anak_info['nik_anak']
            tugas_list = request.form.getlist('tugas[]') 
            
            cursor.execute("DELETE FROM pencapaian_perkembangan WHERE nik_anak = %s", (nik,))
            for kode in tugas_list:
                cursor.execute("INSERT INTO pencapaian_perkembangan (nik_anak, kode_tugas) VALUES (%s, %s)", (nik, kode))
            conn.commit()
            flash('Capaian perkembangan berhasil diperbarui!', 'success')
            return redirect(url_for('perkembangan', cari_anak=nik))

        cari_input = request.args.get('cari_anak', '')
        checked_tasks = []
        nik_filter = ''
        anak_terpilih = None
        
        if cari_input:
            cursor.execute("SELECT nik_anak, nama_lengkap, no_register_kms FROM anak WHERE nik_anak = %s OR no_register_kms = %s", (cari_input, cari_input))
            anak_terpilih = cursor.fetchone()
            
            if anak_terpilih:
                nik_filter = anak_terpilih['nik_anak']
                cursor.execute("SELECT kode_tugas FROM pencapaian_perkembangan WHERE nik_anak = %s", (nik_filter,))
                for row in cursor.fetchall():
                    checked_tasks.append(row['kode_tugas'])
            else:
                flash("Data anak dengan NIK atau No. KMS tersebut tidak ditemukan.", "danger")
                
        if session['role'] == 'ortu':
            cursor.execute("SELECT nik_anak, nama_lengkap FROM anak WHERE username_ortu = %s", (session['username'],))
            daftar_anak = cursor.fetchall()
        else:
            daftar_anak = []
            
    except Exception as e:
        flash(f"Gagal memuat data dari database: {str(e)}", "danger")
        daftar_anak = []
        checked_tasks = []
        nik_filter = ''
        anak_terpilih = None
    finally:
        conn.close()
    
    return render_template('ui_perkembangan.html', 
                           daftar_anak=daftar_anak, role=session['role'], 
                           nik_terpilih=nik_filter, anak_terpilih=anak_terpilih,
                           checked_tasks=checked_tasks, all_tugas=ALL_TUGAS)

# ==========================================
# 5. FASE 4: API INTEGRASI PUSKESMAS / DINKES
# ==========================================
@app.route('/api/v1/anak/<nik>/rekam_medis', methods=['GET'])
def api_rekam_medis_anak(nik):
    api_key = request.headers.get('X-API-KEY')
    if api_key != 'mikado_dinkes_secure_2024':
        return jsonify({'status': 'error', 'message': 'Akses Ditolak: API Key tidak valid!'}), 401
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT nik_anak, nama_lengkap, tanggal_lahir, jenis_kelamin, posyandu_terdaftar FROM anak WHERE nik_anak = %s", (nik,))
    anak = cursor.fetchone()
    
    if not anak:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Data anak tidak ditemukan'}), 404
        
    cursor.execute("""
        SELECT p.tanggal_pengukuran, p.usia_bulan, p.berat_badan, p.tinggi_badan, 
               s.bb_u, s.tb_u, s.kategori_status
        FROM pengukuran p
        LEFT JOIN status_gizi s ON p.id_pengukuran = s.id_pengukuran
        WHERE p.nik_anak = %s 
        ORDER BY p.tanggal_pengukuran ASC
    """, (nik,))
    riwayat_pertumbuhan = cursor.fetchall()
    
    cursor.execute("SELECT riwayat_imunisasi, riwayat_penyakit_alergi, asi_eksklusif FROM riwayat_kesehatan WHERE nik_anak = %s ORDER BY id_riwayat DESC LIMIT 1", (nik,))
    riwayat_kesehatan = cursor.fetchone()
    
    conn.close()
    
    return jsonify({
        'status': 'success',
        'sumber_data': 'Aplikasi MIKAdO',
        'data': {
            'identitas_pasien': anak,
            'kesehatan_terakhir': riwayat_kesehatan,
            'grafik_pertumbuhan': riwayat_pertumbuhan
        }
    })

if __name__ == '__main__':
    app.run(debug=True, ssl_context='adhoc')
