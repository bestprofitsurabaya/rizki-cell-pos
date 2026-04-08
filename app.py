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

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Rizki Cell ERP V12", layout="wide", page_icon="🚀")

# --- KEAMANAN & UTILITAS ---
def hash_pass(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Fungsi Log Audit & Notifikasi (Toast) Terpadu
def log_and_notify(user, aksi, tabel, pesan_toast, data_lama="-", data_baru="-", icon="✅"):
    tgl = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect('rizki_cell_v12.db') as conn:
        conn.execute("INSERT INTO audit_logs (tgl, user, aksi, tabel, data_lama, data_baru) VALUES (?,?,?,?,?,?)", 
                     (tgl, user, aksi, tabel, str(data_lama), str(data_baru)))
    # Munculkan Notifikasi di Pojok Kanan Atas
    st.toast(pesan_toast, icon=icon)

# --- DATABASE ENGINE (V12 SCHEMA) ---
def init_db():
    conn = sqlite3.connect('rizki_cell_v12.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # 1. Produk & Supplier
    cursor.execute('''CREATE TABLE IF NOT EXISTS suppliers (id INTEGER PRIMARY KEY, nama TEXT, kontak TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, nama TEXT, kategori TEXT, hpp REAL, jual REAL, stok INTEGER, min_stok INTEGER, supplier_nama TEXT)''')
    
    # 2. Penjualan, Shift, PPOB Ledger
    cursor.execute('''CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY, shift_id INTEGER, tgl TEXT, produk TEXT, qty INTEGER, total REAL, profit REAL, metode TEXT, cabang TEXT, is_ppob INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS shifts (id INTEGER PRIMARY KEY, user TEXT, cabang TEXT, waktu_buka TEXT, waktu_tutup TEXT, modal_awal REAL, total_tunai REAL, status TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS ppob_ledger (id INTEGER PRIMARY KEY, tgl TEXT, jenis TEXT, nominal REAL, saldo_akhir REAL, keterangan TEXT, user TEXT)''')
    
    # 3. Users, Cabang, Piutang, Audit (BARU: Tabel Cabang)
    cursor.execute('''CREATE TABLE IF NOT EXISTS cabang (id INTEGER PRIMARY KEY, nama TEXT UNIQUE, alamat TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT, cabang_nama TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS piutang (id INTEGER PRIMARY KEY, tgl TEXT, nama_pelanggan TEXT, nominal REAL, status TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY, tgl TEXT, user TEXT, aksi TEXT, tabel TEXT, data_lama TEXT, data_baru TEXT)''')
    
    # Data Default Inisialisasi
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
    st.title("🔐 Rizki Cell ERP - V12")
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
                st.toast("Kredensial Salah atau Akses Ditolak!", icon="❌")
                st.error("Akses Ditolak!")
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

if st.sidebar.button("🚪 Keluar"):
    log_and_notify(st.session_state.user, "LOGOUT", "sistem", "Berhasil Log Out dari sistem.", icon="ℹ️")
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
        
        if saldo_ppob < 100000:
            st.error(f"⚠️ PERINGATAN: Saldo PPOB kritis (Rp {saldo_ppob:,.0f}).")
            
        if not df_all.empty:
            hari_ini = datetime.now().strftime("%Y-%m-%d")
            df_today = df_all[df_all['tgl'].str.startswith(hari_ini)]
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Omzet Hari Ini", f"Rp {df_today['total'].sum():,.0f}")
            c2.metric("✨ Profit Hari Ini", f"Rp {df_today['profit'].sum():,.0f}")
            c3.metric("💳 Saldo PPOB", f"Rp {saldo_ppob:,.0f}")
            
            st.markdown("---")
            tab1, tab2 = st.tabs(["Tren Penjualan Cabang", "Fisik vs PPOB"])
            with tab1:
                st.plotly_chart(px.bar(df_all.groupby('cabang')['total'].sum().reset_index(), x='cabang', y='total', color='cabang'), use_container_width=True)
            with tab2:
                st.plotly_chart(px.pie(df_all, values='total', names='is_ppob', title="0: Fisik | 1: PPOB"), use_container_width=True)

# --- MODUL 2: KASIR UMUM ---
elif menu == "🛒 Kasir Umum (Fisik)":
    st.header("Kasir Penjualan Fisik")
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

    df_p = pd.read_sql("SELECT * FROM products WHERE stok > 0", conn)
    if not df_p.empty:
        col1, col2, col3 = st.columns([2,1,2])
        item = col1.selectbox("Cari Produk", df_p['nama'])
        qty = col2.number_input("Jumlah", min_value=1, step=1)
        metode = col3.radio("Metode", ["Tunai", "QRIS", "Tempo"], horizontal=True)
        
        pelanggan = st.text_input("Nama Pelanggan (Wajib untuk Tempo)") if metode == "Tempo" else ""
        
        # FITUR KEAMANAN: Checkbox Konfirmasi
        st.markdown("---")
        konfirmasi_trx = st.checkbox(f"Konfirmasi: Jual **{qty}x {item}** menggunakan **{metode}**?")
        
        if st.button("🛒 Proses Pembayaran", type="primary", use_container_width=True, disabled=not konfirmasi_trx):
            if metode == "Tempo" and not pelanggan:
                st.toast("Gagal: Nama pelanggan wajib diisi!", icon="❌")
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
                
                log_and_notify(st.session_state.user, "SALE_FISIK", "sales", f"Transaksi berhasil! Omzet: Rp {total:,.0f}", data_baru=f"{item} x{qty}")
                
                if metode == "QRIS":
                    qr = qrcode.make(f"RIZKI-CELL-{total}"); buf = BytesIO(); qr.save(buf)
                    st.image(buf, caption=f"Scan QRIS: Rp {total:,.0f}", width=200)
    else: st.info("Stok barang fisik kosong.")

# --- MODUL 3: KASIR PPOB ---
elif menu == "⚡ Kasir PPOB (Pulsa)":
    st.header("Transaksi Pulsa & PPOB")
    saldo_saat_ini = get_ppob_balance()
    st.info(f"💳 Sisa Saldo Server: **Rp {saldo_saat_ini:,.0f}**")
    
    with st.container():
        nomor = st.text_input("Nomor Tujuan", placeholder="08xxx")
        kategori = st.selectbox("Layanan", ["Pulsa Reguler", "Paket Data", "Token PLN", "Topup E-Wallet"])
        harga_modal = st.selectbox("Modal Server (Rp)", [5000, 10000, 20000, 50000, 100000])
        markup = st.number_input("Markup Keuntungan (Rp)", value=2000, step=500)
        harga_jual = harga_modal + markup
        st.write(f"**Tagihan Pelanggan: Rp {harga_jual:,.0f}**")
        
        # FITUR KEAMANAN: Konfirmasi
        konfirmasi_ppob = st.checkbox(f"Konfirmasi: Tembak PPOB ke {nomor}?")
        
        if st.button("🚀 Tembak Saldo", type="primary", disabled=not konfirmasi_ppob):
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

# --- MODUL BARU: MANAJEMEN KARYAWAN & CABANG ---
elif menu == "👥 Karyawan & Cabang":
    if st.session_state.role != "Owner":
        st.error("Modul ini dikhususkan untuk Manajemen (Owner).")
    else:
        st.header("Manajemen Sumber Daya Manusia (HR)")
        tab1, tab2 = st.tabs(["Data Karyawan (Users)", "Data Cabang (Outlet)"])
        
        with tab1:
            st.subheader("Daftar Akun Akses Sistem")
            df_users = pd.read_sql("SELECT id, username, role, cabang_nama FROM users", conn)
            st.dataframe(df_users, use_container_width=True)
            
            with st.expander("➕ Tambah Karyawan Baru"):
                df_cab = pd.read_sql("SELECT nama FROM cabang", conn)
                list_cab = df_cab['nama'].tolist() if not df_cab.empty else ["Pusat"]
                
                c1, c2 = st.columns(2)
                u_new = c1.text_input("Username Baru")
                p_new = c2.text_input("Password", type="password")
                r_new = c1.selectbox("Hak Akses (Role)", ["Admin", "Owner"])
                cab_new = c2.selectbox("Penempatan Cabang", list_cab)
                
                konf_user = st.checkbox("Konfirmasi Penambahan Karyawan")
                if st.button("Simpan Karyawan", disabled=not konf_user):
                    try:
                        with conn:
                            conn.execute("INSERT INTO users (username, password, role, cabang_nama) VALUES (?,?,?,?)", 
                                         (u_new, hash_pass(p_new), r_new, cab_new))
                        log_and_notify(st.session_state.user, "CREATE_USER", "users", f"User {u_new} berhasil dibuat!", data_baru=f"Role: {r_new}, Cabang: {cab_new}")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.toast("Gagal: Username sudah digunakan!", icon="❌")
        
        with tab2:
            st.subheader("Daftar Outlet (Cabang)")
            df_cabang = pd.read_sql("SELECT * FROM cabang", conn)
            st.dataframe(df_cabang, use_container_width=True)
            
            with st.expander("➕ Tambah Cabang Baru"):
                cab_n = st.text_input("Nama Cabang (Misal: Cabang Sudirman)")
                cab_a = st.text_area("Alamat Lengkap")
                
                konf_cab = st.checkbox("Konfirmasi Pembuatan Cabang")
                if st.button("Simpan Cabang", disabled=not konf_cab):
                    try:
                        with conn:
                            conn.execute("INSERT INTO cabang (nama, alamat) VALUES (?,?)", (cab_n, cab_a))
                        log_and_notify(st.session_state.user, "CREATE_CABANG", "cabang", f"Cabang {cab_n} berhasil ditambahkan!", data_baru=cab_a)
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.toast("Gagal: Nama cabang sudah ada!", icon="❌")

# --- MODUL 4: MANAJEMEN SALDO PPOB ---
elif menu == "💳 Manajemen Saldo PPOB":
    st.header("Buku Besar Saldo PPOB (Deposit)")
    saldo_akhir = get_ppob_balance()
    st.metric("Saldo Deposit Saat Ini", f"Rp {saldo_akhir:,.0f}")
    
    if st.session_state.role == "Owner":
        with st.expander("➕ Top-Up Deposit Saldo (Tambah Saldo)"):
            nominal_topup = st.number_input("Nominal Top-Up (Rp):", min_value=0, step=50000)
            keterangan = st.text_input("Keterangan (Misal: Trf BCA ke Digiflazz)")
            
            konf_topup = st.checkbox("Konfirmasi: Dana sudah masuk ke server.")
            if st.button("Konfirmasi Top-Up", disabled=not konf_topup):
                if nominal_topup > 0:
                    tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
                    saldo_baru = saldo_akhir + nominal_topup
                    with conn:
                        conn.execute("INSERT INTO ppob_ledger (tgl, jenis, nominal, saldo_akhir, keterangan, user) VALUES (?,?,?,?,?,?)",
                                    (tgl, "Top-Up", nominal_topup, saldo_baru, keterangan, st.session_state.user))
                    log_and_notify(st.session_state.user, "TOPUP_PPOB", "ppob_ledger", "Top-Up berhasil! Saldo bertambah.", data_baru=f"+{nominal_topup}")
                    st.rerun()

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
                
                # Checkbox dalam form st.form tidak langsung trigger, tapi amannya menggunakan submit button
                if st.form_submit_button("Simpan", type="primary"):
                    conn.execute("INSERT INTO products (nama, kategori, hpp, jual, stok, min_stok, supplier_nama) VALUES (?,?,?,?,?,?,?)", (n, k, h_b, h_j, stk, 5, sup))
                    conn.commit()
                    log_and_notify(st.session_state.user, "ADD_PRODUCT", "products", f"Barang {n} ditambahkan!")
                    st.rerun()

    with tabs[2]:
        if st.session_state.role == "Owner":
            st.download_button("Download Template Excel", data=generate_excel_template(), file_name="Template_Rizki_Cell.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            uploaded_file = st.file_uploader("Upload File .xlsx yang sudah diisi", type=['xlsx'])
            if uploaded_file is not None:
                konf_import = st.checkbox("Konfirmasi: Data di Excel sudah benar dan siap dimasukkan ke database.")
                if st.button("Proses Import Data", disabled=not konf_import):
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
                    log_and_notify(st.session_state.user, "IMPORT_EXCEL", "products", "Import Excel Berhasil Selesai!")

# --- MODUL 6: PIUTANG ---
elif menu == "📝 Buku Piutang":
    st.header("Catatan Kasbon Pelanggan")
    df_p = pd.read_sql("SELECT * FROM piutang WHERE status='Belum Lunas'", conn)
    st.dataframe(df_p, use_container_width=True)
    if not df_p.empty and st.session_state.role == "Owner":
        p_id = st.selectbox("Pilih ID Piutang yang akan dilunasi", df_p['id'])
        
        konf_piutang = st.checkbox("Konfirmasi: Uang pelunasan sudah saya terima.")
        if st.button("Tandai Lunas", disabled=not konf_piutang):
            conn.execute("UPDATE piutang SET status='Lunas' WHERE id=?", (p_id,))
            conn.commit()
            log_and_notify(st.session_state.user, "LUNAS_PIUTANG", "piutang", f"Piutang ID {p_id} dilunasi!", data_baru=f"ID {p_id} -> Lunas")
            st.rerun()

# --- MODUL 7: HISTORI & AUDIT ---
elif menu == "📜 Histori & Audit":
    st.header("Jejak Digital & Notifikasi Sistem")
    st.info("Semua notifikasi pop-up yang muncul di layar terekam secara permanen di tabel ini untuk proses audit.")
    st.dataframe(pd.read_sql("SELECT tgl, user, aksi, tabel, data_baru FROM audit_logs ORDER BY id DESC", conn), use_container_width=True)

# --- MODUL 8: SHIFT ---
elif menu == "🏁 Selesai Shift":
    if st.session_state.shift_id:
        st.warning("Perhatian: Pastikan Anda telah menghitung uang fisik di laci dengan teliti sebelum menutup shift.")
        fisik = st.number_input("Total Uang Tunai Fisik di Laci (Rp):", min_value=0)
        
        konf_shift = st.checkbox("Saya menyatakan bahwa perhitungan uang fisik sudah benar dan sesuai.")
        if st.button("Tutup Shift Kasir", type="primary", disabled=not konf_shift):
            conn.execute("UPDATE shifts SET waktu_tutup=?, total_tunai=?, status=? WHERE id=?", 
                        (datetime.now().strftime("%Y-%m-%d %H:%M"), fisik, "CLOSED", st.session_state.shift_id))
            conn.commit()
            st.session_state.shift_id = None
            log_and_notify(st.session_state.user, "TUTUP_SHIFT", "shifts", "Shift berhasil ditutup. Terima kasih!", data_baru=f"Uang Fisik: Rp {fisik}")
            st.rerun()
    else: st.info("Anda tidak memiliki shift yang sedang aktif.")