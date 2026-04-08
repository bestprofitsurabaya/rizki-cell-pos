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
st.set_page_config(page_title="Rizki Cell ERP V11", layout="wide", page_icon="🚀")

# --- KEAMANAN & UTILITAS ---
def hash_pass(password):
    return hashlib.sha256(password.encode()).hexdigest()

def log_audit(user, aksi, tabel, data_lama="-", data_baru="-"):
    tgl = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect('rizki_cell_v11.db') as conn:
        conn.execute("INSERT INTO audit_logs (tgl, user, aksi, tabel, data_lama, data_baru) VALUES (?,?,?,?,?,?)", 
                     (tgl, user, aksi, tabel, str(data_lama), str(data_baru)))

# --- DATABASE ENGINE (V11 SCHEMA) ---
def init_db():
    conn = sqlite3.connect('rizki_cell_v11.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # 1. Produk & Supplier
    cursor.execute('''CREATE TABLE IF NOT EXISTS suppliers (id INTEGER PRIMARY KEY, nama TEXT, kontak TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, nama TEXT, kategori TEXT, hpp REAL, jual REAL, stok INTEGER, min_stok INTEGER, supplier_nama TEXT)''')
    
    # 2. Penjualan & Shift
    cursor.execute('''CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY, shift_id INTEGER, tgl TEXT, produk TEXT, qty INTEGER, total REAL, profit REAL, metode TEXT, cabang TEXT, is_ppob INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS shifts (id INTEGER PRIMARY KEY, user TEXT, cabang TEXT, waktu_buka TEXT, waktu_tutup TEXT, modal_awal REAL, total_tunai REAL, status TEXT)''')
    
    # 3. Users, Piutang, Audit
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT, cabang TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS piutang (id INTEGER PRIMARY KEY, tgl TEXT, nama_pelanggan TEXT, nominal REAL, status TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY, tgl TEXT, user TEXT, aksi TEXT, tabel TEXT, data_lama TEXT, data_baru TEXT)''')
    
    # 4. TABEL BARU: BUKU BESAR PPOB (LEDGER)
    cursor.execute('''CREATE TABLE IF NOT EXISTS ppob_ledger (id INTEGER PRIMARY KEY, tgl TEXT, jenis TEXT, nominal REAL, saldo_akhir REAL, keterangan TEXT, user TEXT)''')
    
    # Data Default
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password, role, cabang) VALUES (?,?,?,?)", ("owner", hash_pass("master"), "Owner", "Pusat"))
        cursor.execute("INSERT INTO users (username, password, role, cabang) VALUES (?,?,?,?)", ("admin1", hash_pass("admin"), "Admin", "Cabang 1"))
        cursor.execute("INSERT INTO suppliers (nama, kontak) VALUES (?,?)", ("Supplier Umum", "-"))
        # Saldo Awal PPOB 0
        cursor.execute("INSERT INTO ppob_ledger (tgl, jenis, nominal, saldo_akhir, keterangan, user) VALUES (?,?,?,?,?,?)", 
                       (datetime.now().strftime("%Y-%m-%d %H:%M"), "Sistem", 0, 0, "Inisialisasi Sistem", "system"))
    
    conn.commit()
    return conn

conn = init_db()

# --- HELPER: AMBIL SALDO PPOB TERAKHIR ---
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

# --- SESSION STATE ---
if 'is_logged_in' not in st.session_state:
    st.session_state.update({'is_logged_in': False, 'user': None, 'role': None, 'cabang': None, 'shift_id': None})

# --- UI LOGIN ---
if not st.session_state.is_logged_in:
    st.title("🔐 Rizki Cell ERP - V11")
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

menu_options = [
    "📊 Dashboard & Keuntungan",
    "🛒 Kasir Umum (Fisik)", 
    "⚡ Kasir PPOB (Pulsa)",
    "💳 Manajemen Saldo PPOB", 
    "📦 Inventori & Excel Import", 
    "📝 Buku Piutang", 
    "📜 Histori & Audit",
    "🏁 Selesai Shift"
]

menu = st.sidebar.selectbox("Menu Utama", menu_options)

if st.sidebar.button("🚪 Keluar"):
    st.session_state.is_logged_in = False
    st.rerun()

# --- MODUL 1: DASHBOARD ---
if menu == "📊 Dashboard & Keuntungan":
    if st.session_state.role != "Owner":
        st.error("Khusus Owner!")
    else:
        st.header("📈 Ringkasan Bisnis Rizki Cell")
        df_all = pd.read_sql("SELECT * FROM sales", conn)
        saldo_ppob = get_ppob_balance()
        
        # Peringatan Saldo
        if saldo_ppob < 100000:
            st.error(f"⚠️ PERINGATAN: Saldo Deposit PPOB Anda kritis (Rp {saldo_ppob:,.0f}). Segera lakukan Top-Up!")
            
        if not df_all.empty:
            hari_ini = datetime.now().strftime("%Y-%m-%d")
            df_today = df_all[df_all['tgl'].str.startswith(hari_ini)]
            
            st.subheader("🔥 Pencapaian HARI INI")
            c1, c2, c3 = st.columns(3)
            c1.metric("Omzet Hari Ini", f"Rp {df_today['total'].sum():,.0f}")
            c2.metric("✨ Profit Hari Ini", f"Rp {df_today['profit'].sum():,.0f}")
            c3.metric("💳 Saldo PPOB Saat Ini", f"Rp {saldo_ppob:,.0f}")
            
            st.markdown("---")
            st.subheader("📊 Statistik Sepanjang Waktu")
            c4, c5 = st.columns(2)
            c4.metric("Total Omzet", f"Rp {df_all['total'].sum():,.0f}")
            c5.metric("Total Profit", f"Rp {df_all['profit'].sum():,.0f}")
            
            tab1, tab2 = st.tabs(["Tren Penjualan Cabang", "Fisik vs PPOB"])
            with tab1:
                st.plotly_chart(px.bar(df_all.groupby('cabang')['total'].sum().reset_index(), x='cabang', y='total', color='cabang'), use_container_width=True)
            with tab2:
                st.plotly_chart(px.pie(df_all, values='total', names='is_ppob', title="0: Fisik | 1: PPOB"), use_container_width=True)

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
        
        pelanggan = st.text_input("Nama Pelanggan (Wajib untuk Tempo)") if metode == "Tempo" else ""

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
                
                st.success(f"Berhasil! Omzet bertambah Rp {total:,.0f}")
                st.rerun()
    else: st.info("Stok kosong.")

# --- MODUL 3: KASIR PPOB ---
elif menu == "⚡ Kasir PPOB (Pulsa)":
    st.header("Transaksi Pulsa & Paket Data")
    
    saldo_saat_ini = get_ppob_balance()
    st.info(f"💳 Sisa Deposit Saldo Server: **Rp {saldo_saat_ini:,.0f}**")
    
    with st.container():
        nomor = st.text_input("Nomor Tujuan", placeholder="08xxx")
        kategori = st.selectbox("Layanan", ["Pulsa Reguler", "Paket Data", "Token PLN", "Topup E-Wallet"])
        harga_modal = st.selectbox("Nominal / Harga Modal Server", [5000, 10000, 20000, 50000, 100000])
        markup = st.number_input("Keuntungan / Markup (Rp)", value=2000, step=500)
        
        harga_jual = harga_modal + markup
        st.write(f"**Tagihan Pelanggan: Rp {harga_jual:,.0f}**")
        
        if st.button("🚀 Tembak Saldo", type="primary"):
            if saldo_saat_ini < harga_modal:
                st.error(f"❌ Transaksi Gagal: Saldo server tidak mencukupi. Sisa saldo: Rp {saldo_saat_ini:,.0f}")
            elif not nomor:
                st.warning("Masukkan nomor tujuan terlebih dahulu!")
            else:
                tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
                saldo_baru = saldo_saat_ini - harga_modal
                
                with conn:
                    # 1. Catat Penjualan
                    conn.execute("INSERT INTO sales (shift_id, tgl, produk, qty, total, profit, metode, cabang, is_ppob) VALUES (?,?,?,?,?,?,?,?,?)",
                                (st.session_state.shift_id, tgl, f"{kategori} {harga_modal} ({nomor})", 1, harga_jual, markup, "Tunai", st.session_state.cabang, 1))
                    # 2. Potong Saldo PPOB
                    conn.execute("INSERT INTO ppob_ledger (tgl, jenis, nominal, saldo_akhir, keterangan, user) VALUES (?,?,?,?,?,?)",
                                (tgl, "Transaksi", harga_modal, saldo_baru, f"Trx {nomor}", st.session_state.user))
                
                st.success(f"Sukses! Saldo server dipotong Rp {harga_modal:,.0f}. Sisa saldo: Rp {saldo_baru:,.0f}")
                log_audit(st.session_state.user, "PPOB_TRX", "ppob_ledger", data_baru=f"Sisa {saldo_baru}")
                st.rerun()

# --- MODUL 4: MANAJEMEN SALDO PPOB ---
elif menu == "💳 Manajemen Saldo PPOB":
    st.header("Buku Besar Saldo PPOB (Deposit)")
    
    saldo_akhir = get_ppob_balance()
    st.metric("Saldo Deposit Saat Ini", f"Rp {saldo_akhir:,.0f}")
    
    if st.session_state.role == "Owner":
        with st.expander("➕ Top-Up Deposit Saldo (Tambah Saldo)"):
            nominal_topup = st.number_input("Nominal Top-Up (Rp):", min_value=0, step=50000)
            keterangan = st.text_input("Keterangan (Misal: Trf via BCA ke Digiflazz)")
            if st.button("Konfirmasi Top-Up"):
                if nominal_topup > 0:
                    tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
                    saldo_baru = saldo_akhir + nominal_topup
                    with conn:
                        conn.execute("INSERT INTO ppob_ledger (tgl, jenis, nominal, saldo_akhir, keterangan, user) VALUES (?,?,?,?,?,?)",
                                    (tgl, "Top-Up", nominal_topup, saldo_baru, keterangan, st.session_state.user))
                    st.success("Saldo berhasil ditambahkan!")
                    log_audit(st.session_state.user, "TOPUP_PPOB", "ppob_ledger", data_baru=f"+{nominal_topup}")
                    st.rerun()

    st.subheader("Riwayat Mutasi Saldo")
    df_ledger = pd.read_sql("SELECT tgl, jenis, nominal, saldo_akhir, keterangan, user FROM ppob_ledger ORDER BY id DESC", conn)
    st.dataframe(df_ledger, use_container_width=True)

# --- MODUL 5: INVENTORI & EXCEL ---
elif menu == "📦 Inventori & Excel Import":
    st.header("Manajemen Inventori Fisik")
    tabs = st.tabs(["Daftar Stok", "Input Manual", "📥 Import Massal (Excel)"])
    
    with tabs[0]:
        st.dataframe(pd.read_sql("SELECT * FROM products", conn), use_container_width=True)
        
    with tabs[1]:
        if st.session_state.role == "Owner":
            df_sup = pd.read_sql("SELECT nama FROM suppliers", conn)
            list_sup = df_sup['nama'].tolist() if not df_sup.empty else ["Belum Ada Supplier"]
            with st.form("input_manual"):
                c1, c2, c3 = st.columns(3)
                n, k, sup = c1.text_input("Nama"), c2.selectbox("Kategori", ["Pulsa Fisik", "Paket Data", "Aksesoris", "Voucher"]), c3.selectbox("Supplier", list_sup)
                h_b, h_j, stk = c1.number_input("Modal", min_value=0), c2.number_input("Jual", min_value=0), c3.number_input("Stok", step=1)
                if st.form_submit_button("Simpan", type="primary"):
                    conn.execute("INSERT INTO products (nama, kategori, hpp, jual, stok, min_stok, supplier_nama) VALUES (?,?,?,?,?,?,?)", (n, k, h_b, h_j, stk, 5, sup))
                    conn.commit()
                    st.rerun()

    with tabs[2]:
        if st.session_state.role == "Owner":
            st.download_button("Download Template Excel", data=generate_excel_template(), file_name="Template_Rizki_Cell.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            uploaded_file = st.file_uploader("Upload File .xlsx yang sudah diisi", type=['xlsx'])
            if uploaded_file is not None:
                if st.button("Proses Import Data"):
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
                        except: pass
                    conn.commit()
                    st.success("Import selesai!")

# --- MODUL 6: PIUTANG ---
elif menu == "📝 Buku Piutang":
    st.header("Catatan Kasbon Pelanggan")
    df_p = pd.read_sql("SELECT * FROM piutang WHERE status='Belum Lunas'", conn)
    st.dataframe(df_p, use_container_width=True)
    if not df_p.empty and st.session_state.role == "Owner":
        p_id = st.selectbox("Pilih ID Piutang Lunas", df_p['id'])
        if st.button("Tandai Lunas"):
            conn.execute("UPDATE piutang SET status='Lunas' WHERE id=?", (p_id,))
            conn.commit()
            st.rerun()

# --- MODUL 7: HISTORI & AUDIT ---
elif menu == "📜 Histori & Audit":
    st.header("Jejak Digital Keamanan")
    st.dataframe(pd.read_sql("SELECT tgl, user, aksi, tabel, data_baru FROM audit_logs ORDER BY id DESC", conn), use_container_width=True)

# --- MODUL 8: SHIFT ---
elif menu == "🏁 Selesai Shift":
    if st.session_state.shift_id:
        fisik = st.number_input("Uang Laci Fisik (Rp):", min_value=0)
        if st.button("Tutup Shift"):
            conn.execute("UPDATE shifts SET waktu_tutup=?, total_tunai=?, status=? WHERE id=?", (datetime.now().strftime("%Y-%m-%d %H:%M"), fisik, "CLOSED", st.session_state.shift_id))
            conn.commit()
            st.session_state.shift_id = None
            st.success("Shift Ditutup.")
            st.rerun()
    else: st.info("Tidak ada shift aktif.")