import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
from fpdf import FPDF
import hashlib
import os
import random

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Rizki Cell ERP V12", layout="wide", page_icon="🚀")

# --- SESSION STATE INISIALISASI AWAL ---
if 'is_logged_in' not in st.session_state:
    st.session_state.update({'is_logged_in': False, 'user': None, 'role': None, 'cabang': None, 'shift_id': None})
if 'db_mode' not in st.session_state:
    st.session_state.db_mode = 'Real' # Default ke database asli
if 'cart' not in st.session_state:
    st.session_state.cart = [] # Inisialisasi Keranjang Belanja
if 'struk_ready' not in st.session_state:
    st.session_state.update({'struk_ready': False, 'struk_data': None, 'struk_filename': ""})

# Penentuan Database
DB_NAME = 'dummy_rizki_cell_v12.db' if st.session_state.db_mode == 'Dummy' else 'rizki_cell_v12.db'

# --- KEAMANAN & UTILITAS ---
def hash_pass(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Fungsi Log Audit & Notifikasi (Toast)
def log_and_notify(user, aksi, tabel, pesan_toast, data_lama="-", data_baru="-", icon="✅"):
    tgl = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_NAME) as conn_log:
        conn_log.execute("INSERT INTO audit_logs (tgl, user, aksi, tabel, data_lama, data_baru) VALUES (?,?,?,?,?,?)", 
                     (tgl, user, aksi, tabel, str(data_lama), str(data_baru)))
    st.toast(pesan_toast, icon=icon)

# --- DATABASE ENGINE (V12 SCHEMA) ---
def init_db(db_file):
    conn_db = sqlite3.connect(db_file, check_same_thread=False)
    cursor = conn_db.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS suppliers (id INTEGER PRIMARY KEY, nama TEXT, kontak TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, nama TEXT, kategori TEXT, hpp REAL, jual REAL, stok INTEGER, min_stok INTEGER, supplier_nama TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY, shift_id INTEGER, tgl TEXT, produk TEXT, qty INTEGER, total REAL, profit REAL, metode TEXT, cabang TEXT, is_ppob INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS shifts (id INTEGER PRIMARY KEY, user TEXT, cabang TEXT, waktu_buka TEXT, waktu_tutup TEXT, modal_awal REAL, total_tunai REAL, status TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS ppob_ledger (id INTEGER PRIMARY KEY, tgl TEXT, jenis TEXT, nominal REAL, saldo_akhir REAL, keterangan TEXT, user TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS cabang (id INTEGER PRIMARY KEY, nama TEXT UNIQUE, alamat TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT, cabang_nama TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS piutang (id INTEGER PRIMARY KEY, tgl TEXT, nama_pelanggan TEXT, nominal REAL, status TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY, tgl TEXT, user TEXT, aksi TEXT, tabel TEXT, data_lama TEXT, data_baru TEXT)''')
    
    cursor.execute("SELECT COUNT(*) FROM cabang")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO cabang (nama, alamat) VALUES (?,?)", ("Pusat", "Jl. Utama No. 1"))
        cursor.execute("INSERT INTO cabang (nama, alamat) VALUES (?,?)", ("Cabang 1", "Jl. Cabang No. 2"))
        
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password, role, cabang_nama) VALUES (?,?,?,?)", ("owner", hash_pass("master"), "Owner", "Pusat"))
        cursor.execute("INSERT INTO users (username, password, role, cabang_nama) VALUES (?,?,?,?)", ("admin1", hash_pass("admin"), "Admin", "Cabang 1"))
        cursor.execute("INSERT INTO suppliers (nama, kontak) VALUES (?,?)", ("Supplier Umum", "-"))
        cursor.execute("INSERT INTO ppob_ledger (tgl, jenis, nominal, saldo_akhir, keterangan, user) VALUES (?,?,?,?,?,?)", 
                       (datetime.now().strftime("%Y-%m-%d %H:%M"), "Sistem", 0, 0, "Inisialisasi Sistem", "system"))
    conn_db.commit()
    return conn_db

# --- GENERATOR DUMMY DATA SKALA BESAR (3 BULAN) ---
def generate_dummy_data_if_needed(db_file):
    conn_dummy = sqlite3.connect(db_file)
    cur = conn_dummy.cursor()
    cur.execute("SELECT COUNT(*) FROM sales")
    if cur.fetchone()[0] == 0:
        # 1. Variasi Produk yang Lebih Banyak
        dummy_products = [
            ("Voucher Telkomsel 10GB", "Paket Data", 25000, 28000, 500),
            ("Voucher Indosat 5GB", "Paket Data", 15000, 18000, 450),
            ("Voucher XL 15GB", "Paket Data", 35000, 40000, 300),
            ("Voucher Tri 30GB", "Paket Data", 55000, 62000, 200),
            ("Kabel Data Type-C Fast", "Aksesoris", 12000, 25000, 350),
            ("Kabel Data iPhone/Lightning", "Aksesoris", 15000, 30000, 300),
            ("Tempered Glass Layar", "Aksesoris", 8000, 25000, 800),
            ("Casing Silicon Polos", "Aksesoris", 10000, 25000, 400),
            ("Earphone Bluetooth TWS", "Aksesoris", 45000, 85000, 150),
            ("Charger Adapter 20W", "Aksesoris", 35000, 65000, 200)
        ]
        for p in dummy_products:
            cur.execute("INSERT INTO products (nama, kategori, hpp, jual, stok, min_stok, supplier_nama) VALUES (?,?,?,?,?,?,?)", 
                        (p[0], p[1], p[2], p[3], p[4], 10, "Supplier Umum"))
        
        # 2. Inisialisasi Saldo PPOB Awal untuk Dummy
        cur.execute("INSERT INTO ppob_ledger (tgl, jenis, nominal, saldo_akhir, keterangan, user) VALUES (?,?,?,?,?,?)", 
                    (datetime.now().strftime("%Y-%m-%d %H:%M"), "Top-Up Dummy", 5000000, 5000000, "Modal PPOB Awal", "owner"))
        
        # 3. Generate Transaksi Harian (90 Hari Terakhir)
        start_date = datetime.now() - timedelta(days=90)
        saldo_ppob_berjalan = 5000000
        
        for i in range(90):
            current_date = start_date + timedelta(days=i)
            # Acak jam buka shift
            waktu_buka = current_date.replace(hour=random.randint(7, 9), minute=random.randint(0, 59))
            waktu_tutup = current_date.replace(hour=random.randint(21, 23), minute=random.randint(0, 59))
            
            cur.execute("INSERT INTO shifts (user, cabang, waktu_buka, waktu_tutup, modal_awal, status) VALUES (?,?,?,?,?,?)", 
                        ("owner", "Pusat", waktu_buka.strftime("%Y-%m-%d %H:%M"), waktu_tutup.strftime("%Y-%m-%d %H:%M"), 200000, "CLOSED"))
            shift_id = cur.lastrowid
            
            # Buat 20 hingga 40 Transaksi per hari
            for _ in range(random.randint(20, 40)):
                trx_time = waktu_buka + timedelta(minutes=random.randint(10, 800))
                tgl_str = trx_time.strftime("%Y-%m-%d %H:%M")
                
                # Peluang 30% transaksi PPOB, 70% Fisik
                if random.random() < 0.3:
                    # Dummy PPOB
                    jenis_ppob = random.choice(["Pulsa Reguler", "Token PLN", "Topup Dana/Ovo"])
                    modal_ppob = random.choice([10000, 20000, 50000])
                    jual_ppob = modal_ppob + 2000
                    
                    cur.execute("INSERT INTO sales (shift_id, tgl, produk, qty, total, profit, metode, cabang, is_ppob) VALUES (?,?,?,?,?,?,?,?,?)",
                                (shift_id, tgl_str, f"{jenis_ppob} {modal_ppob}", 1, jual_ppob, 2000, random.choice(["Tunai", "QRIS"]), "Pusat", 1))
                    
                    saldo_ppob_berjalan -= modal_ppob
                    cur.execute("INSERT INTO ppob_ledger (tgl, jenis, nominal, saldo_akhir, keterangan, user) VALUES (?,?,?,?,?,?)",
                                (tgl_str, "Transaksi", modal_ppob, saldo_ppob_berjalan, "Trx Dummy", "owner"))
                else:
                    # Dummy Fisik (Bisa beli 1-3 barang sekaligus dalam 1 waktu)
                    metode = random.choice(["Tunai", "Tunai", "QRIS", "Tempo"]) # Tunai lebih dominan
                    jumlah_macam_barang = random.randint(1, 3)
                    
                    for _ in range(jumlah_macam_barang):
                        prod = random.choice(dummy_products)
                        qty = random.randint(1, 2)
                        total = prod[3] * qty
                        profit = (prod[3] - prod[2]) * qty
                        cur.execute("INSERT INTO sales (shift_id, tgl, produk, qty, total, profit, metode, cabang, is_ppob) VALUES (?,?,?,?,?,?,?,?,?)",
                                    (shift_id, tgl_str, prod[0], qty, total, profit, metode, "Pusat", 0))
                        
                    if metode == "Tempo":
                        cur.execute("INSERT INTO piutang (tgl, nama_pelanggan, nominal, status) VALUES (?,?,?,?)", 
                                    (tgl_str, f"Pelanggan Dummy {random.randint(1,100)}", total, random.choice(["Lunas", "Belum Lunas"])))

            # Sesekali Top-Up PPOB Dummy jika saldo menipis
            if saldo_ppob_berjalan < 500000:
                saldo_ppob_berjalan += 2000000
                cur.execute("INSERT INTO ppob_ledger (tgl, jenis, nominal, saldo_akhir, keterangan, user) VALUES (?,?,?,?,?,?)",
                            (waktu_tutup.strftime("%Y-%m-%d %H:%M"), "Top-Up", 2000000, saldo_ppob_berjalan, "Restock Dummy", "owner"))

        conn_dummy.commit()
    conn_dummy.close()

# Eksekusi Database
conn = init_db(DB_NAME)
if st.session_state.db_mode == 'Dummy':
    generate_dummy_data_if_needed(DB_NAME)

# --- HELPER: AMBIL SALDO PPOB ---
def get_ppob_balance():
    cur = conn.cursor()
    cur.execute("SELECT saldo_akhir FROM ppob_ledger ORDER BY id DESC LIMIT 1")
    res = cur.fetchone()
    return res[0] if res else 0

# --- FUNGSI GENERATE EXCEL TEMPLATE ---
def generate_excel_template():
    df = pd.DataFrame(columns=["Nama Barang", "Kategori", "Harga Modal", "Harga Jual", "Stok Awal", "Min Stok", "Nama Supplier"])
    df.loc[0] = ["Contoh: Kuota Tsel 10GB", "Paket Data", 25000, 28000, 50, 5, "PT. Telkomsel"]
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Template_Barang')
    return output.getvalue()

# --- FUNGSI CETAK STRUK MULTI-ITEM (FPDF) ---
def generate_struk(tgl, kasir, cart_items, grand_total, metode, uang_diterima=0, kembalian=0):
    pdf = FPDF(format=(80, 200)) # Tinggi kertas disesuaikan lebih panjang
    pdf.add_page()
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(60, 5, "RIZKI CELL", ln=True, align='C')
    pdf.set_font("Arial", '', 8)
    pdf.cell(60, 4, "Sistem ERP Terpadu V12", ln=True, align='C')
    pdf.cell(60, 4, f"Tgl: {tgl}", ln=True, align='C')
    pdf.cell(60, 4, f"Kasir: {kasir}", ln=True, align='C')
    pdf.cell(60, 4, "-"*30, ln=True, align='C')
    
    # Loop isi keranjang belanja
    for item in cart_items:
        pdf.cell(60, 4, f"{item['produk']}", ln=True)
        pdf.cell(60, 4, f"  {item['qty']} x {item['harga_satuan']:,.0f} = Rp {item['subtotal']:,.0f}", ln=True)
        
    pdf.cell(60, 4, "-"*30, ln=True, align='C')
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(60, 5, f"TOTAL   : Rp {grand_total:,.0f}", ln=True)
    pdf.set_font("Arial", '', 8)
    pdf.cell(60, 4, f"Metode  : {metode}", ln=True)
    
    if metode == "Tunai":
        pdf.cell(60, 4, f"Tunai   : Rp {uang_diterima:,.0f}", ln=True)
        pdf.cell(60, 4, f"Kembali : Rp {kembalian:,.0f}", ln=True)
        
    pdf.cell(60, 5, "-"*30, ln=True, align='C')
    pdf.cell(60, 5, "Terima Kasih Atas Kunjungan Anda!", ln=True, align='C')
    return pdf.output(dest='S').encode('latin-1')

# --- UI LOGIN ---
if not st.session_state.is_logged_in:
    st.title("🔐 Rizki Cell ERP - V12")
    if st.session_state.db_mode == 'Dummy':
        st.warning("⚠️ Berjalan dalam MODE DUMMY (Data Palsu Simulasi).")
        
    with st.container():
        u = st.text_input("Username")
        p = st.text_input("Password", type='password')
        if st.button("Masuk ke Sistem", use_container_width=True):
            cur = conn.cursor()
            cur.execute("SELECT role, cabang_nama FROM users WHERE username=? AND password=?", (u, hash_pass(p)))
            res = cur.fetchone()
            if res:
                st.session_state.update({'is_logged_in': True, 'role': res[0], 'cabang': res[1], 'user': u})
                log_and_notify(u, "LOGIN", "sistem", f"Selamat datang, {u}!", data_baru=f"Login ke {res[1]}")
                st.rerun()
            else: 
                st.error("Kredensial Salah atau Akses Ditolak!")
    st.stop()

# --- SIDEBAR NAVIGASI ---
st.sidebar.header(f"🏪 {st.session_state.cabang}")
st.sidebar.write(f"Halo, **{st.session_state.user}**")

menu_options = [
    "📊 Dashboard & Keuntungan",
    "🛒 Kasir Umum (Fisik)", 
    "⚡ Kasir PPOB (Pulsa)",
    "💳 Manajemen Saldo PPOB", 
    "📦 Inventori & Excel Import", 
    "👥 Karyawan & Cabang",
    "📝 Buku Piutang", 
    "📜 Histori & Audit",
    "🏁 Selesai Shift"
]

menu = st.sidebar.selectbox("Menu Utama", menu_options)

# Fitur Kontrol Dummy untuk Owner
if st.session_state.role == "Owner":
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Database Mode")
    db_selector = st.sidebar.radio("Lingkungan Server:", ["Real Data (Asli)", "Dummy Data (Test)"], 
                                   index=0 if st.session_state.db_mode == "Real" else 1)
    
    if db_selector == "Real Data (Asli)" and st.session_state.db_mode != "Real":
        st.session_state.db_mode = "Real"
        st.session_state.cart = [] # Kosongkan keranjang saat pindah mode
        st.rerun()
    elif db_selector == "Dummy Data (Test)" and st.session_state.db_mode != "Dummy":
        st.session_state.db_mode = "Dummy"
        st.session_state.cart = []
        st.rerun()

if st.sidebar.button("🚪 Keluar"):
    log_and_notify(st.session_state.user, "LOGOUT", "sistem", "Berhasil Log Out dari sistem.")
    st.session_state.is_logged_in = False
    st.session_state.cart = []
    st.rerun()

# --- MODUL 1: DASHBOARD ---
if menu == "📊 Dashboard & Keuntungan":
    if st.session_state.role != "Owner":
        st.error("Khusus Owner!")
    else:
        judul_tambahan = "(Mode Simulasi 3 Bulan)" if st.session_state.db_mode == "Dummy" else ""
        st.header(f"📈 Ringkasan Bisnis Rizki Cell {judul_tambahan}")
        df_all = pd.read_sql("SELECT * FROM sales", conn)
        saldo_ppob = get_ppob_balance()
        
        if saldo_ppob < 100000:
            st.error(f"⚠️ PERINGATAN: Saldo PPOB kritis (Rp {saldo_ppob:,.0f}). Segera Top-Up!")
            
        if not df_all.empty:
            hari_ini = datetime.now().strftime("%Y-%m-%d")
            df_today = df_all[df_all['tgl'].str.startswith(hari_ini)]
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Omzet Hari Ini", f"Rp {df_today['total'].sum():,.0f}")
            c2.metric("✨ Profit Hari Ini", f"Rp {df_today['profit'].sum():,.0f}")
            c3.metric("💳 Saldo PPOB", f"Rp {saldo_ppob:,.0f}")
            
            st.markdown("---")
            tab1, tab2, tab3 = st.tabs(["Tren Omzet Harian", "Kontribusi Cabang", "Fisik vs PPOB"])
            with tab1:
                df_all['tgl_date'] = pd.to_datetime(df_all['tgl']).dt.date
                df_trend = df_all.groupby('tgl_date')['total'].sum().reset_index()
                st.plotly_chart(px.line(df_trend, x='tgl_date', y='total', title="Tren Pergerakan Omzet Harian (Time Series)", markers=True), use_container_width=True)
            with tab2:
                st.plotly_chart(px.bar(df_all.groupby('cabang')['total'].sum().reset_index(), x='cabang', y='total', color='cabang', title="Total Omzet per Cabang"), use_container_width=True)
            with tab3:
                st.plotly_chart(px.pie(df_all, values='total', names='is_ppob', title="Proporsi Penjualan Fisik (0) vs PPOB (1)"), use_container_width=True)

# --- MODUL 2: KASIR UMUM (DENGAN SISTEM KERANJANG) ---
elif menu == "🛒 Kasir Umum (Fisik)":
    st.header("Kasir Penjualan Fisik (Sistem Keranjang)")
    
    if st.session_state.role == "Admin" and st.session_state.shift_id is None:
        st.warning("Anda belum membuka shift. Silakan buka shift untuk mulai melayani.")
        modal = st.number_input("Input Uang Modal (Tunai di Laci):", min_value=0)
        konfirmasi_shift = st.checkbox("Saya mengonfirmasi jumlah uang modal sudah benar.")
        if st.button("Mulai Buka Shift", disabled=not konfirmasi_shift):
            tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
            cur = conn.cursor()
            cur.execute("INSERT INTO shifts (user, cabang, waktu_buka, modal_awal, status) VALUES (?,?,?,?,?)", 
                       (st.session_state.user, st.session_state.cabang, tgl, modal, "OPEN"))
            conn.commit()
            st.session_state.shift_id = cur.lastrowid
            log_and_notify(st.session_state.user, "BUKA_SHIFT", "shifts", "Shift berhasil dibuka!", data_baru=f"Modal: Rp {modal}")
            st.rerun()
        st.stop()

    # LAYAR 1: TAMPILAN KERANJANG & INPUT BARANG
    df_p = pd.read_sql("SELECT * FROM products WHERE stok > 0", conn)
    
    if not st.session_state.struk_ready:
        if not df_p.empty:
            with st.container(border=True):
                st.subheader("🛍️ Tambah Barang ke Keranjang")
                col1, col2, col3 = st.columns([3,1,1])
                pilih_item = col1.selectbox("Cari Produk (Ketik untuk mencari)", df_p['nama'])
                pilih_qty = col2.number_input("Jumlah", min_value=1, step=1)
                
                if col3.button("➕ Tambah Barang", use_container_width=True):
                    # Validasi Stok
                    res_p = df_p[df_p['nama'] == pilih_item].iloc[0]
                    # Cek jumlah barang yang sama yang sudah ada di keranjang
                    qty_di_keranjang = sum([item['qty'] for item in st.session_state.cart if item['produk'] == pilih_item])
                    if pilih_qty + qty_di_keranjang > res_p['stok']:
                        st.toast(f"Stok tidak cukup! Sisa stok fisik: {res_p['stok']}", icon="❌")
                    else:
                        subtotal = res_p['jual'] * pilih_qty
                        profit_item = (res_p['jual'] - res_p['hpp']) * pilih_qty
                        st.session_state.cart.append({
                            'id_produk': res_p['id'],
                            'produk': pilih_item,
                            'harga_satuan': res_p['jual'],
                            'qty': pilih_qty,
                            'subtotal': subtotal,
                            'profit': profit_item
                        })
                        st.rerun()

        # TAMPILKAN ISI KERANJANG JIKA ADA
        if st.session_state.cart:
            st.markdown("### Isi Keranjang Belanja:")
            df_cart = pd.DataFrame(st.session_state.cart)
            
            # Tampilkan tabel keranjang dengan format yang rapi
            st.dataframe(
                df_cart[['produk', 'harga_satuan', 'qty', 'subtotal']],
                column_config={
                    "produk": "Nama Barang",
                    "harga_satuan": st.column_config.NumberColumn("Harga Satuan", format="Rp %d"),
                    "qty": "Jumlah",
                    "subtotal": st.column_config.NumberColumn("Subtotal", format="Rp %d")
                },
                use_container_width=True
            )
            
            if st.button("🗑️ Kosongkan Keranjang"):
                st.session_state.cart = []
                st.rerun()
            
            grand_total = sum(item['subtotal'] for item in st.session_state.cart)
            st.markdown(f"<h2 style='text-align: right; color: #28a745;'>Total Tagihan: Rp {grand_total:,.0f}</h2>", unsafe_allow_html=True)
            
            st.markdown("---")
            st.subheader("💳 Proses Pembayaran")
            col_m1, col_m2 = st.columns(2)
            metode = col_m1.radio("Metode Pembayaran", ["Tunai", "QRIS", "Tempo"], horizontal=True)
            pelanggan = col_m2.text_input("Nama Pelanggan (Wajib untuk Tempo)") if metode == "Tempo" else ""
            
            # Kalkulasi Kembalian
            uang_diterima = 0
            kembalian = 0
            validasi_bayar = True

            if metode == "Tunai":
                uang_diterima = col_m1.number_input("Uang Diterima (Rp)", min_value=0, step=1000)
                if uang_diterima > 0:
                    kembalian = uang_diterima - grand_total
                    if kembalian < 0:
                        st.error(f"⚠️ Uang kurang Rp {abs(kembalian):,.0f}")
                        validasi_bayar = False
                    else:
                        st.success(f"✅ Uang Cukup. **Kembalian: Rp {kembalian:,.0f}**")
                else:
                    validasi_bayar = False

            # Konfirmasi & Tombol Proses
            konfirmasi_trx = st.checkbox("Konfirmasi: Semua barang di keranjang dan metode pembayaran sudah benar?")
            tombol_aktif = konfirmasi_trx and validasi_bayar
            
            if st.button("🛒 Selesaikan Pembayaran", type="primary", use_container_width=True, disabled=not tombol_aktif):
                if metode == "Tempo" and not pelanggan:
                    st.toast("Gagal: Nama pelanggan wajib diisi untuk Tempo!", icon="❌")
                else:
                    tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
                    with conn:
                        for cart_item in st.session_state.cart:
                            # Masukkan setiap barang ke tabel sales dengan timestamp yang persis sama (sebagai 1 struk/trx)
                            conn.execute("INSERT INTO sales (shift_id, tgl, produk, qty, total, profit, metode, cabang, is_ppob) VALUES (?,?,?,?,?,?,?,?,?)",
                                        (st.session_state.shift_id, tgl, cart_item['produk'], cart_item['qty'], cart_item['subtotal'], cart_item['profit'], metode, st.session_state.cabang, 0))
                            # Kurangi stok
                            conn.execute("UPDATE products SET stok = stok - ? WHERE id = ?", (cart_item['qty'], int(cart_item['id_produk'])))
                        
                        if metode == "Tempo":
                            conn.execute("INSERT INTO piutang (tgl, nama_pelanggan, nominal, status) VALUES (?,?,?,?)", (tgl, pelanggan, grand_total, "Belum Lunas"))
                    
                    log_and_notify(st.session_state.user, "SALE_FISIK_MULTI", "sales", f"Transaksi berhasil! Total: Rp {grand_total:,.0f}", data_baru=f"{len(st.session_state.cart)} jenis barang")
                    
                    # Generate PDF Struk menggunakan data cart list
                    pdf_bytes = generate_struk(tgl, st.session_state.user, st.session_state.cart, grand_total, metode, uang_diterima, kembalian)
                    st.session_state.struk_data = pdf_bytes
                    st.session_state.struk_filename = f"Struk_{tgl.replace(':','')}.pdf"
                    st.session_state.struk_ready = True
                    
                    # Simpan data terakhir untuk tampilan UI sebelum dikosongkan
                    st.session_state.last_grand_total = grand_total
                    st.session_state.last_metode = metode
                    st.session_state.last_kembalian = kembalian
                    
                    # Bersihkan keranjang
                    st.session_state.cart = []
                    st.rerun()
        else:
            st.info("🛒 Keranjang belanja masih kosong. Silakan pilih barang di atas.")
    else:
        # LAYAR 2: TAMPILAN SETELAH TRANSAKSI BERHASIL (STRUK READY)
        st.success("✅ Transaksi Terakhir Berhasil Diproses.")
        
        if st.session_state.get('last_metode') == "QRIS":
            qr = qrcode.make(f"RIZKI-CELL-{st.session_state.last_grand_total}"); buf = BytesIO(); qr.save(buf)
            st.image(buf, caption=f"Scan QRIS: Rp {st.session_state.last_grand_total:,.0f}", width=250)
        if st.session_state.get('last_metode') == "Tunai":
            st.info(f"Selesai! Jangan lupa berikan kembalian pelanggan: **Rp {st.session_state.last_kembalian:,.0f}**")
            
        col_a, col_b = st.columns(2)
        col_a.download_button(
            label="🖨️ Cetak/Unduh Struk PDF",
            data=st.session_state.struk_data,
            file_name=st.session_state.struk_filename,
            mime="application/pdf",
            use_container_width=True
        )
        if col_b.button("🔄 Lanjut Transaksi Baru", type="primary", use_container_width=True):
            st.session_state.struk_ready = False
            st.session_state.struk_data = None
            st.rerun()

# --- MODUL 3: KASIR PPOB ---
elif menu == "⚡ Kasir PPOB (Pulsa)":
    st.header("Transaksi Pulsa & PPOB Digital")
    saldo_saat_ini = get_ppob_balance()
    st.info(f"💳 Sisa Saldo Server Anda: **Rp {saldo_saat_ini:,.0f}**")
    
    with st.container(border=True):
        nomor = st.text_input("Nomor Tujuan Pelanggan", placeholder="08xxx / No Meteran PLN")
        kategori = st.selectbox("Jenis Layanan", ["Pulsa Reguler", "Paket Data", "Token PLN", "Topup E-Wallet", "Bayar Tagihan"])
        harga_modal = st.selectbox("Modal Server (Terpotong dari Saldo) Rp", [5000, 10000, 20000, 50000, 100000, 150000, 200000])
        markup = st.number_input("Markup Keuntungan Toko (Rp)", value=2000, step=500)
        harga_jual = harga_modal + markup
        st.markdown(f"### Tagihan Pelanggan: **Rp {harga_jual:,.0f}**")
        
        konfirmasi_ppob = st.checkbox(f"Konfirmasi: Tembak Saldo PPOB ke nomor {nomor}?")
        
        if st.button("🚀 Eksekusi Tembak Saldo", type="primary", disabled=not konfirmasi_ppob):
            if saldo_saat_ini < harga_modal:
                st.toast("Gagal: Saldo server tidak mencukupi!", icon="❌")
            elif not nomor:
                st.toast("Gagal: Nomor tujuan kosong!", icon="❌")
            else:
                tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
                saldo_baru = saldo_saat_ini - harga_modal
                with conn:
                    conn.execute("INSERT INTO sales (shift_id, tgl, produk, qty, total, profit, metode, cabang, is_ppob) VALUES (?,?,?,?,?,?,?,?,?)",
                                (st.session_state.shift_id, tgl, f"{kategori} {harga_modal} ({nomor})", 1, harga_jual, markup, "Tunai", st.session_state.cabang, 1))
                    conn.execute("INSERT INTO ppob_ledger (tgl, jenis, nominal, saldo_akhir, keterangan, user) VALUES (?,?,?,?,?,?)",
                                (tgl, "Transaksi", harga_modal, saldo_baru, f"Trx {nomor}", st.session_state.user))
                
                log_and_notify(st.session_state.user, "PPOB_TRX", "ppob_ledger", f"Sukses tembak saldo! Sisa: Rp {saldo_baru:,.0f}", data_baru=f"Trx {nomor}")
                st.rerun()

# --- MODUL 4: MANAJEMEN SALDO PPOB ---
elif menu == "💳 Manajemen Saldo PPOB":
    st.header("Buku Besar & Deposit Saldo PPOB")
    saldo_akhir = get_ppob_balance()
    st.metric("Saldo Deposit Aktif Saat Ini", f"Rp {saldo_akhir:,.0f}")
    
    if st.session_state.role == "Owner":
        with st.expander("➕ Top-Up Deposit Saldo Server"):
            nominal_topup = st.number_input("Nominal Top-Up yang ditransfer (Rp):", min_value=0, step=50000)
            keterangan = st.text_input("Keterangan Referensi (Misal: Trf Mandiri ke Digiflazz)")
            
            konf_topup = st.checkbox("Konfirmasi: Dana mutasi sudah berhasil masuk ke server pusat.")
            if st.button("Proses Top-Up", type="primary", disabled=not konf_topup):
                if nominal_topup > 0:
                    tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
                    saldo_baru = saldo_akhir + nominal_topup
                    with conn:
                        conn.execute("INSERT INTO ppob_ledger (tgl, jenis, nominal, saldo_akhir, keterangan, user) VALUES (?,?,?,?,?,?)",
                                    (tgl, "Top-Up", nominal_topup, saldo_baru, keterangan, st.session_state.user))
                    log_and_notify(st.session_state.user, "TOPUP_PPOB", "ppob_ledger", "Top-Up sistem berhasil! Saldo bertambah.", data_baru=f"+{nominal_topup}")
                    st.rerun()

    st.subheader("Riwayat Keluar Masuk Saldo PPOB")
    df_ledger = pd.read_sql("SELECT tgl, jenis, nominal, saldo_akhir, keterangan, user FROM ppob_ledger ORDER BY id DESC", conn)
    st.dataframe(df_ledger, use_container_width=True)

# --- MODUL 5: INVENTORI & EXCEL ---
elif menu == "📦 Inventori & Excel Import":
    st.header("Manajemen Inventori & Stok Fisik")
    tabs = st.tabs(["📋 Daftar Stok Keseluruhan", "✍️ Input Manual Satuan", "📥 Import Massal (Via Excel)"])
    
    with tabs[0]:
        st.dataframe(pd.read_sql("SELECT * FROM products", conn), use_container_width=True)
        
    with tabs[1]:
        if st.session_state.role == "Owner":
            df_sup = pd.read_sql("SELECT nama FROM suppliers", conn)
            list_sup = df_sup['nama'].tolist() if not df_sup.empty else ["Belum Ada Supplier"]
            with st.form("input_manual"):
                c1, c2, c3 = st.columns(3)
                n = c1.text_input("Nama Barang Baru")
                k = c2.selectbox("Kategori Barang", ["Pulsa Fisik", "Paket Data", "Aksesoris", "Voucher", "HP/Gadget"])
                sup = c3.selectbox("Supplier Asal", list_sup)
                h_b = c1.number_input("Harga Modal Beli (HPP)", min_value=0)
                h_j = c2.number_input("Harga Jual ke Pelanggan", min_value=0)
                stk = c3.number_input("Jumlah Stok Awal", step=1)
                
                if st.form_submit_button("Simpan Barang ke Database", type="primary"):
                    if n:
                        conn.execute("INSERT INTO products (nama, kategori, hpp, jual, stok, min_stok, supplier_nama) VALUES (?,?,?,?,?,?,?)", (n, k, h_b, h_j, stk, 5, sup))
                        conn.commit()
                        log_and_notify(st.session_state.user, "ADD_PRODUCT", "products", f"Barang {n} berhasil ditambahkan!")
                        st.rerun()
                    else:
                        st.error("Nama barang tidak boleh kosong.")
        else:
            st.warning("Hanya Owner yang dapat menambah barang baru secara manual.")

    with tabs[2]:
        if st.session_state.role == "Owner":
            st.download_button("⬇️ Download Template Excel", data=generate_excel_template(), file_name="Template_Rizki_Cell.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            st.info("Silakan isi data barang di file Excel di atas, lalu upload kembali di bawah ini untuk memperbarui sistem secara otomatis.")
            uploaded_file = st.file_uploader("Upload File .xlsx yang sudah diisi", type=['xlsx'])
            if uploaded_file is not None:
                konf_import = st.checkbox("Konfirmasi: Data di Excel sudah final dan siap ditimpa ke database.")
                if st.button("🚀 Proses Import Data", disabled=not konf_import):
                    df_import = pd.read_excel(uploaded_file, engine='openpyxl')
                    cur = conn.cursor()
                    for _, row in df_import.iterrows():
                        if str(row['Nama Barang']).startswith("Contoh:"): continue
                        try:
                            nama_sup = str(row['Nama Supplier'])
                            cur.execute("SELECT id FROM suppliers WHERE nama=?", (nama_sup,))
                            if not cur.fetchone(): cur.execute("INSERT INTO suppliers (nama, kontak) VALUES (?,?)", (nama_sup, "-"))
                            
                            cur.execute("SELECT id FROM products WHERE nama=?", (str(row['Nama Barang']),))
                            if cur.fetchone():
                                cur.execute("UPDATE products SET hpp=?, jual=?, stok=stok+?, supplier_nama=? WHERE nama=?", (float(row['Harga Modal']), float(row['Harga Jual']), int(row['Stok Awal']), nama_sup, str(row['Nama Barang'])))
                            else:
                                cur.execute("INSERT INTO products (nama, kategori, hpp, jual, stok, min_stok, supplier_nama) VALUES (?,?,?,?,?,?,?)", (str(row['Nama Barang']), str(row['Kategori']), float(row['Harga Modal']), float(row['Harga Jual']), int(row['Stok Awal']), int(row['Min Stok']), nama_sup))
                        except Exception as e: 
                            st.write(f"Baris dilewati karena error: {e}")
                            pass
                    conn.commit()
                    log_and_notify(st.session_state.user, "IMPORT_EXCEL", "products", "Import Data Excel Selesai!")
                    st.rerun()
        else:
            st.warning("Hanya Owner yang dapat melakukan import data massal.")

# --- MODUL 6: MANAJEMEN KARYAWAN & CABANG ---
elif menu == "👥 Karyawan & Cabang":
    if st.session_state.role != "Owner":
        st.error("Modul ini dikhususkan secara eksklusif untuk Manajemen (Owner).")
    else:
        st.header("Manajemen Sumber Daya Manusia (HR & Cabang)")
        tab1, tab2 = st.tabs(["👤 Data Karyawan (Pengguna Sistem)", "🏪 Data Outlet (Cabang)"])
        
        with tab1:
            st.subheader("Daftar Akun Akses Sistem")
            df_users = pd.read_sql("SELECT id, username, role, cabang_nama FROM users", conn)
            st.dataframe(df_users, use_container_width=True)
            
            with st.expander("➕ Tambah Karyawan / Akun Baru"):
                df_cab = pd.read_sql("SELECT nama FROM cabang", conn)
                list_cab = df_cab['nama'].tolist() if not df_cab.empty else ["Pusat"]
                
                c1, c2 = st.columns(2)
                u_new = c1.text_input("Username Baru (Tanpa Spasi)")
                p_new = c2.text_input("Password Login", type="password")
                r_new = c1.selectbox("Hak Akses (Role)", ["Admin", "Owner"])
                cab_new = c2.selectbox("Penempatan Tugas Cabang", list_cab)
                
                konf_user = st.checkbox("Konfirmasi Penambahan Data Karyawan")
                if st.button("Simpan Karyawan Baru", disabled=not konf_user):
                    try:
                        with conn:
                            conn.execute("INSERT INTO users (username, password, role, cabang_nama) VALUES (?,?,?,?)", 
                                         (u_new.strip(), hash_pass(p_new), r_new, cab_new))
                        log_and_notify(st.session_state.user, "CREATE_USER", "users", f"User {u_new} berhasil dibuat!", data_baru=f"Role: {r_new}, Cabang: {cab_new}")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.toast("Gagal: Username tersebut sudah digunakan sebelumnya!", icon="❌")
        
        with tab2:
            st.subheader("Daftar Outlet (Cabang)")
            df_cabang = pd.read_sql("SELECT * FROM cabang", conn)
            st.dataframe(df_cabang, use_container_width=True)
            
            with st.expander("➕ Buka Cabang / Outlet Baru"):
                cab_n = st.text_input("Nama Cabang (Misal: Cabang Sudirman)")
                cab_a = st.text_area("Alamat Lengkap Operasional")
                
                konf_cab = st.checkbox("Konfirmasi Pembuatan Cabang Baru")
                if st.button("Simpan Data Cabang", disabled=not konf_cab):
                    try:
                        with conn:
                            conn.execute("INSERT INTO cabang (nama, alamat) VALUES (?,?)", (cab_n, cab_a))
                        log_and_notify(st.session_state.user, "CREATE_CABANG", "cabang", f"Cabang {cab_n} resmi ditambahkan!", data_baru=cab_a)
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.toast("Gagal: Nama cabang tersebut sudah terdaftar!", icon="❌")

# --- MODUL 7: BUKU PIUTANG ---
elif menu == "📝 Buku Piutang":
    st.header("Catatan Kasbon & Piutang Pelanggan")
    st.info("Semua transaksi fisik yang menggunakan metode 'Tempo' akan otomatis tercatat di halaman ini.")
    df_p = pd.read_sql("SELECT * FROM piutang WHERE status='Belum Lunas'", conn)
    st.dataframe(df_p, use_container_width=True)
    
    if not df_p.empty and st.session_state.role == "Owner":
        st.markdown("---")
        st.subheader("Pelunasan Piutang")
        p_id = st.selectbox("Pilih ID Piutang yang akan dilunasi pelanggan:", df_p['id'])
        
        konf_piutang = st.checkbox("Konfirmasi: Uang pelunasan kasbon sudah saya terima sepenuhnya.")
        if st.button("Tandai Lunas di Sistem", type="primary", disabled=not konf_piutang):
            conn.execute("UPDATE piutang SET status='Lunas' WHERE id=?", (p_id,))
            conn.commit()
            log_and_notify(st.session_state.user, "LUNAS_PIUTANG", "piutang", f"Piutang dengan ID {p_id} resmi dilunasi!", data_baru=f"ID {p_id} -> Lunas")
            st.rerun()

# --- MODUL 8: HISTORI & AUDIT ---
elif menu == "📜 Histori & Audit":
    st.header("Jejak Digital & Log Audit Sistem Terpusat")
    st.info("Seluruh aktivitas sensitif (Login, Buka Shift, Transaksi, Tambah Barang, Dll) terekam secara permanen di tabel ini untuk mencegah kecurangan.")
    df_audit = pd.read_sql("SELECT tgl, user, aksi, tabel, data_baru FROM audit_logs ORDER BY id DESC", conn)
    st.dataframe(df_audit, use_container_width=True)

# --- MODUL 9: PENUTUPAN SHIFT ---
elif menu == "🏁 Selesai Shift":
    st.header("Rekonsiliasi & Tutup Shift Kasir")
    if st.session_state.shift_id:
        st.warning("⚠️ Perhatian: Pastikan Anda telah menghitung seluruh uang fisik di dalam laci kasir dengan teliti sebelum menekan tombol tutup shift.")
        fisik = st.number_input("Masukkan Total Perhitungan Uang Tunai Fisik di Laci (Rp):", min_value=0, step=1000)
        
        konf_shift = st.checkbox("Saya dengan sadar menyatakan bahwa perhitungan uang fisik di atas sudah benar dan sesuai dengan keadaan sebenarnya.")
        if st.button("🔴 Tutup Shift & Akhiri Sesi", type="primary", disabled=not konf_shift):
            conn.execute("UPDATE shifts SET waktu_tutup=?, total_tunai=?, status=? WHERE id=?", 
                        (datetime.now().strftime("%Y-%m-%d %H:%M"), fisik, "CLOSED", st.session_state.shift_id))
            conn.commit()
            shift_sekarang = st.session_state.shift_id
            st.session_state.shift_id = None
            log_and_notify(st.session_state.user, "TUTUP_SHIFT", "shifts", "Sesi Shift Kasir berhasil ditutup. Terima kasih atas kerja keras Anda!", data_baru=f"Laporan Uang Fisik Shift {shift_sekarang}: Rp {fisik}")
            st.rerun()
    else: 
        st.info("Anda tidak memiliki sesi shift yang sedang aktif. Silakan buka shift terlebih dahulu di menu Kasir Umum jika ingin melayani pelanggan.")
