import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime
import qrcode
from io import BytesIO
from fpdf import FPDF
import hashlib
import os
import shutil
import urllib.parse

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Rizki Cell ERP V10", layout="wide", page_icon="🚀")

# --- KEAMANAN & UTILITAS ---
def hash_pass(password):
    return hashlib.sha256(password.encode()).hexdigest()

def log_audit(user, aksi, tabel, data_lama="-", data_baru="-"):
    tgl = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect('rizki_cell_v10.db') as conn:
        conn.execute("INSERT INTO audit_logs (tgl, user, aksi, tabel, data_lama, data_baru) VALUES (?,?,?,?,?,?)", 
                     (tgl, user, aksi, tabel, str(data_lama), str(data_baru)))

# --- DATABASE ENGINE (V10 SCHEMA) ---
def init_db():
    conn = sqlite3.connect('rizki_cell_v10.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # 1. Produk & Supplier
    cursor.execute('''CREATE TABLE IF NOT EXISTS suppliers 
        (id INTEGER PRIMARY KEY, nama TEXT, kontak TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS products 
        (id INTEGER PRIMARY KEY, nama TEXT, kategori TEXT, hpp REAL, jual REAL, stok INTEGER, min_stok INTEGER, supplier_nama TEXT)''')
    
    # 2. Penjualan & Shift
    cursor.execute('''CREATE TABLE IF NOT EXISTS sales 
        (id INTEGER PRIMARY KEY, shift_id INTEGER, tgl TEXT, produk TEXT, qty INTEGER, total REAL, profit REAL, metode TEXT, cabang TEXT, is_ppob INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS shifts 
        (id INTEGER PRIMARY KEY, user TEXT, cabang TEXT, waktu_buka TEXT, waktu_tutup TEXT, modal_awal REAL, total_tunai REAL, status TEXT)''')
    
    # 3. Users, Piutang, Audit
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
        (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT, cabang TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS piutang (id INTEGER PRIMARY KEY, tgl TEXT, nama_pelanggan TEXT, nominal REAL, status TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY, tgl TEXT, user TEXT, aksi TEXT, tabel TEXT, data_lama TEXT, data_baru TEXT)''')
    
    # Data Default
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password, role, cabang) VALUES (?,?,?,?)", ("owner", hash_pass("master"), "Owner", "Pusat"))
        cursor.execute("INSERT INTO users (username, password, role, cabang) VALUES (?,?,?,?)", ("admin1", hash_pass("admin"), "Admin", "Cabang 1"))
        cursor.execute("INSERT INTO suppliers (nama, kontak) VALUES (?,?)", ("Supplier Umum", "-"))
    
    conn.commit()
    return conn

conn = init_db()

# --- FUNGSI GENERATE EXCEL TEMPLATE ---
def generate_excel_template():
    df = pd.DataFrame(columns=["Nama Barang", "Kategori", "Harga Modal", "Harga Jual", "Stok Awal", "Min Stok", "Nama Supplier"])
    # Isi 1 baris contoh agar user paham
    df.loc[0] = ["Contoh: Kuota Tsel 10GB", "Paket Data", 25000, 28000, 50, 5, "PT. Telkomsel"]
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Template_Barang')
    return output.getvalue()

# --- SESSION STATE ---
if 'is_logged_in' not in st.session_state:
    st.session_state.update({'is_logged_in': False, 'user': None, 'role': None, 'cabang': None, 'shift_id': None})

# --- UI LOGIN ---
if not st.session_state.is_logged_in:
    st.title("🔐 Rizki Cell ERP - V10 Ultimate")
    with st.container():
        u = st.text_input("Username")
        p = st.text_input("Password", type='password')
        if st.button("Masuk ke Sistem", use_container_width=True, type="primary"):
            cur = conn.cursor()
            cur.execute("SELECT role, cabang FROM users WHERE username=? AND password=?", (u, hash_pass(p)))
            res = cur.fetchone()
            if res:
                st.session_state.update({'is_logged_in': True, 'role': res[0], 'cabang': res[1], 'user': u})
                st.rerun()
            else: st.error("Akses Ditolak!")
    st.stop()

# --- SIDEBAR NAVIGASI ---
st.sidebar.header(f"🏪 {st.session_state.cabang}")
st.sidebar.write(f"Halo, **{st.session_state.user}**")

menu = st.sidebar.selectbox("Menu Utama", [
    "📊 Dashboard & Keuntungan",
    "🛒 Kasir Umum (Fisik)", 
    "⚡ Kasir PPOB (Pulsa)",
    "📦 Inventori & Excel Import", 
    "📝 Buku Piutang", 
    "📜 Histori & Audit",
    "🏁 Selesai Shift"
])

if st.sidebar.button("🚪 Keluar"):
    st.session_state.is_logged_in = False
    st.rerun()

# --- MODUL 1: DASHBOARD (KEUNTUNGAN HARIAN) ---
if menu == "📊 Dashboard & Keuntungan":
    if st.session_state.role != "Owner":
        st.error("Khusus Owner!")
    else:
        st.header("📈 Ringkasan Bisnis Rizki Cell")
        df_all = pd.read_sql("SELECT * FROM sales", conn)
        
        if not df_all.empty:
            # Ambil data HARI INI
            hari_ini = datetime.now().strftime("%Y-%m-%d")
            df_today = df_all[df_all['tgl'].str.startswith(hari_ini)]
            
            st.subheader("🔥 Pencapaian HARI INI")
            c1, c2, c3 = st.columns(3)
            c1.metric("Omzet Hari Ini", f"Rp {df_today['total'].sum():,.0f}")
            c2.metric("✨ Profit Hari Ini", f"Rp {df_today['profit'].sum():,.0f}", "Keuntungan Bersih")
            c3.metric("Transaksi Hari Ini", len(df_today))
            
            st.markdown("---")
            st.subheader("📊 Statistik Sepanjang Waktu (All Time)")
            c4, c5 = st.columns(2)
            c4.metric("Total Omzet Semua", f"Rp {df_all['total'].sum():,.0f}")
            c5.metric("Total Profit Semua", f"Rp {df_all['profit'].sum():,.0f}")
            
            # Grafik Interaktif
            tab1, tab2 = st.tabs(["Tren Penjualan per Cabang", "Produk Terlaris"])
            with tab1:
                st.plotly_chart(px.bar(df_all.groupby('cabang')['total'].sum().reset_index(), x='cabang', y='total', color='cabang'), use_container_width=True)
            with tab2:
                st.plotly_chart(px.pie(df_all, values='qty', names='produk', title="Distribusi Penjualan"), use_container_width=True)
        else:
            st.info("Belum ada data transaksi yang tercatat.")

# --- MODUL 2: KASIR UMUM ---
elif menu == "🛒 Kasir Umum (Fisik)":
    st.header("Kasir Penjualan Fisik")
    if st.session_state.role == "Admin" and st.session_state.shift_id is None:
        modal = st.number_input("Modal Awal (Tunai):", min_value=0)
        if st.button("Buka Shift"):
            tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
            cur = conn.cursor()
            cur.execute("INSERT INTO shifts (user, cabang, waktu_buka, modal_awal, status) VALUES (?,?,?,?,?)", 
                       (st.session_state.user, st.session_state.cabang, tgl, modal, "OPEN"))
            conn.commit()
            st.session_state.shift_id = cur.lastrowid
            st.rerun()
        st.stop()

    df_p = pd.read_sql("SELECT * FROM products WHERE stok > 0", conn)
    if not df_p.empty:
        col1, col2, col3 = st.columns([2,1,2])
        item = col1.selectbox("Cari Produk Fisik", df_p['nama'])
        qty = col2.number_input("Jumlah", min_value=1, step=1)
        metode = col3.radio("Metode", ["Tunai", "QRIS", "Tempo"], horizontal=True)
        
        pelanggan = ""
        if metode == "Tempo":
            pelanggan = st.text_input("Nama Pelanggan (Wajib untuk Tempo)")

        if st.button("🛒 Proses Pembayaran", type="primary", use_container_width=True):
            if metode == "Tempo" and not pelanggan:
                st.error("Nama wajib diisi jika berhutang!")
            else:
                res = df_p[df_p['nama'] == item].iloc[0]
                total, profit = res['jual']*qty, (res['jual']-res['hpp'])*qty
                tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                with conn:
                    conn.execute("INSERT INTO sales (shift_id, tgl, produk, qty, total, profit, metode, cabang, is_ppob) VALUES (?,?,?,?,?,?,?,?,?)",
                                (st.session_state.shift_id, tgl, item, qty, total, profit, metode, st.session_state.cabang, 0))
                    conn.execute("UPDATE products SET stok = stok - ? WHERE id = ?", (qty, int(res['id'])))
                    if metode == "Tempo":
                        conn.execute("INSERT INTO piutang (tgl, nama_pelanggan, nominal, status) VALUES (?,?,?,?)", (tgl, pelanggan, total, "Belum Lunas"))
                
                log_audit(st.session_state.user, "SALE_FISIK", "sales", data_baru={"produk": item, "total": total})
                st.success(f"Berhasil! Omzet bertambah Rp {total:,.0f}")
                
                # Fitur QRIS Otomatis
                if metode == "QRIS":
                    qr = qrcode.make(f"RIZKI-CELL-{total}"); buf = BytesIO(); qr.save(buf)
                    st.image(buf, caption=f"Scan QRIS: Rp {total:,.0f}", width=200)
                st.rerun()
    else: st.info("Stok kosong. Silakan input barang di menu Inventori.")

# --- MODUL 3: KASIR PPOB ---
elif menu == "⚡ Kasir PPOB (Pulsa)":
    st.header("Transaksi Pulsa & Paket Data")
    # (Logika PPOB disederhanakan sama seperti V9, disesuaikan)
    nomor = st.text_input("Nomor Tujuan", placeholder="08xxx")
    kategori = st.selectbox("Layanan", ["Pulsa Reguler", "Paket Data", "Token PLN"])
    nominal = st.selectbox("Nominal", [5000, 10000, 20000, 50000, 100000])
    harga_jual = nominal + 2000 # Margin PPOB
    
    st.info(f"Tagihan Pelanggan: **Rp {harga_jual:,.0f}**")
    
    if st.button("🚀 Tembak Saldo"):
        tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
        with conn:
            conn.execute("INSERT INTO sales (shift_id, tgl, produk, qty, total, profit, metode, cabang, is_ppob) VALUES (?,?,?,?,?,?,?,?,?)",
                        (st.session_state.shift_id, tgl, f"{kategori} {nominal} ({nomor})", 1, harga_jual, 2000, "Tunai", st.session_state.cabang, 1))
        st.success("Transaksi Sukses!")
        st.balloons()

# --- MODUL 4: INVENTORI & EXCEL IMPORT ---
elif menu == "📦 Inventori & Excel Import":
    st.header("Manajemen Inventori & Supplier")
    
    tabs = st.tabs(["Daftar Stok & Supplier", "Input Manual", "📥 Import Massal (Excel)"])
    
    with tabs[0]:
        df_inv = pd.read_sql("SELECT * FROM products", conn)
        st.dataframe(df_inv, use_container_width=True)
        
    with tabs[1]:
        if st.session_state.role == "Owner":
            # Ambil data supplier untuk Dropdown
            df_sup = pd.read_sql("SELECT nama FROM suppliers", conn)
            list_sup = df_sup['nama'].tolist() if not df_sup.empty else ["Belum Ada Supplier"]
            
            with st.form("input_manual"):
                st.subheader("Input Barang Satuan")
                c1, c2, c3 = st.columns(3)
                n = c1.text_input("Nama Barang")
                k = c2.selectbox("Kategori", ["Pulsa Fisik", "Paket Data", "Aksesoris", "Voucher"])
                sup = c3.selectbox("Pilih Supplier", list_sup)
                
                h_b = c1.number_input("Modal (HPP)", min_value=0)
                h_j = c2.number_input("Harga Jual", min_value=0)
                stk = c3.number_input("Stok", step=1, min_value=0)
                
                if st.form_submit_button("Simpan Barang", type="primary"):
                    with conn:
                        conn.execute("INSERT INTO products (nama, kategori, hpp, jual, stok, min_stok, supplier_nama) VALUES (?,?,?,?,?,?,?)", 
                                     (n, k, h_b, h_j, stk, 5, sup))
                    st.success("Barang tersimpan!")
                    st.rerun()

    with tabs[2]:
        if st.session_state.role == "Owner":
            st.subheader("Import Ratusan Barang Sekaligus")
            st.write("Gunakan fitur ini untuk memperbarui stok atau memasukkan barang baru dari file Excel.")
            
            # Tombol Download Template
            template_bytes = generate_excel_template()
            st.download_button(label="1️⃣ Download Template Excel", 
                               data=template_bytes, 
                               file_name="Template_Rizki_Cell.xlsx", 
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
            st.markdown("---")
            st.write("2️⃣ Upload File yang sudah diisi:")
            uploaded_file = st.file_uploader("Pilih File .xlsx", type=['xlsx'])
            
            if uploaded_file is not None:
                try:
                    df_import = pd.read_excel(uploaded_file, engine='openpyxl')
                    st.write("Pratinjau Data yang akan dimasukkan:")
                    st.dataframe(df_import.head())
                    
                    if st.button("🚀 Proses Import ke Database", type="primary"):
                        sukses, gagal = 0, 0
                        with st.spinner('Menyimpan data...'):
                            cur = conn.cursor()
                            for _, row in df_import.iterrows():
                                # Lewati baris contoh
                                if str(row['Nama Barang']).startswith("Contoh:"):
                                    continue
                                
                                try:
                                    # Pengecekan otomatis: Jika supplier belum ada, buatkan otomatis
                                    nama_sup = str(row['Nama Supplier'])
                                    cur.execute("SELECT id FROM suppliers WHERE nama=?", (nama_sup,))
                                    if not cur.fetchone():
                                        cur.execute("INSERT INTO suppliers (nama, kontak) VALUES (?,?)", (nama_sup, "-"))
                                    
                                    # Cek apakah barang sudah ada di db (Update Stok) atau Baru (Insert)
                                    cur.execute("SELECT id FROM products WHERE nama=?", (str(row['Nama Barang']),))
                                    p_exist = cur.fetchone()
                                    
                                    if p_exist:
                                        # Jika ada, tambah stok dan update harga
                                        cur.execute("UPDATE products SET hpp=?, jual=?, stok=stok+?, supplier_nama=? WHERE id=?",
                                                    (float(row['Harga Modal']), float(row['Harga Jual']), int(row['Stok Awal']), nama_sup, p_exist[0]))
                                    else:
                                        # Jika baru, insert
                                        cur.execute("INSERT INTO products (nama, kategori, hpp, jual, stok, min_stok, supplier_nama) VALUES (?,?,?,?,?,?,?)",
                                                    (str(row['Nama Barang']), str(row['Kategori']), float(row['Harga Modal']), float(row['Harga Jual']), int(row['Stok Awal']), int(row['Min Stok']), nama_sup))
                                    sukses += 1
                                except Exception as e:
                                    gagal += 1
                                    
                            conn.commit()
                        st.success(f"Import Selesai! Berhasil: {sukses} barang | Gagal/Dilewati: {gagal} barang")
                        log_audit(st.session_state.user, "IMPORT_EXCEL", "products", data_baru=f"{sukses} items")
                except Exception as e:
                    st.error(f"Format Excel salah atau file rusak. Gunakan template resmi.")

# --- MODUL 5: PIUTANG & AUDIT ---
elif menu == "📝 Buku Piutang":
    st.header("Catatan Kasbon Pelanggan")
    df_p = pd.read_sql("SELECT * FROM piutang WHERE status='Belum Lunas'", conn)
    st.dataframe(df_p, use_container_width=True)
    if not df_p.empty and st.session_state.role == "Owner":
        p_id = st.selectbox("ID Piutang yang mau dilunasi", df_p['id'])
        if st.button("Tandai Lunas"):
            conn.execute("UPDATE piutang SET status='Lunas' WHERE id=?", (p_id,))
            conn.commit()
            st.rerun()

elif menu == "📜 Histori & Audit":
    st.header("Jejak Digital Keamanan")
    st.dataframe(pd.read_sql("SELECT tgl, user, aksi, tabel, data_baru FROM audit_logs ORDER BY id DESC", conn), use_container_width=True)

# --- MODUL 6: SHIFT ---
elif menu == "🏁 Selesai Shift":
    if st.session_state.shift_id:
        fisik = st.number_input("Uang di Laci Fisik (Rp):", min_value=0)
        if st.button("Tutup Shift Kasir"):
            conn.execute("UPDATE shifts SET waktu_tutup=?, total_tunai=?, status=? WHERE id=?", 
                        (datetime.now().strftime("%Y-%m-%d %H:%M"), fisik, "CLOSED", st.session_state.shift_id))
            conn.commit()
            st.session_state.shift_id = None
            st.success("Shift Ditutup. Laporan terkirim ke Owner.")
    else: st.info("Tidak ada shift aktif.")