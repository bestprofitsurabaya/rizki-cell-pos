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
import json

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Rizki Cell Enterprise V8", layout="wide", page_icon="📱")

# --- KEAMANAN & BACKUP ---
def hash_pass(password):
    return hashlib.sha256(password.encode()).hexdigest()

def backup_db():
    if not os.path.exists('backup_db'):
        os.makedirs('backup_db')
    tgl = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy('rizki_cell_enterprise.db', f'backup_db/backup_{tgl}.db')
    return tgl

# --- DATABASE ENGINE ---
def init_db():
    conn = sqlite3.connect('rizki_cell_enterprise.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS products 
        (id INTEGER PRIMARY KEY, nama TEXT, kategori TEXT, hpp REAL, jual REAL, stok INTEGER, min_stok INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS sales 
        (id INTEGER PRIMARY KEY, shift_id INTEGER, tgl TEXT, produk TEXT, qty INTEGER, total REAL, profit REAL, metode TEXT, poin INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS shifts 
        (id INTEGER PRIMARY KEY, user TEXT, waktu_buka TEXT, waktu_tutup TEXT, modal_awal REAL, total_tunai REAL, status TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
        (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS piutang 
        (id INTEGER PRIMARY KEY, tgl TEXT, nama_pelanggan TEXT, nominal REAL, status TEXT)''')
    
    # TABEL AUDIT YANG DIPERBARUI (Lebih Detail)
    cursor.execute('''CREATE TABLE IF NOT EXISTS audit_logs 
        (id INTEGER PRIMARY KEY, tgl TEXT, user TEXT, aksi TEXT, tabel TEXT, data_lama TEXT, data_baru TEXT)''')
    
    # User Default
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)", ("owner", hash_pass("master"), "Owner"))
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)", ("admin", hash_pass("admin"), "Admin"))
    
    conn.commit()
    return conn

conn = init_db()

# --- FUNGSI AUDIT DETAIL ---
def log_audit(user, aksi, tabel, data_lama="-", data_baru="-"):
    tgl = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with conn:
        conn.execute("INSERT INTO audit_logs (tgl, user, aksi, tabel, data_lama, data_baru) VALUES (?,?,?,?,?,?)", 
                     (tgl, user, aksi, tabel, str(data_lama), str(data_baru)))

# --- FUNGSI STRUK PDF ---
def generate_pdf(nota_id, tgl, items_df):
    try:
        pdf = FPDF(format=(80, 150))
        pdf.add_page()
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, "RIZKI CELL", ln=True, align='C')
        pdf.set_font("Arial", size=8)
        pdf.cell(0, 4, f"Nota: {nota_id} | {tgl}", ln=True, align='C')
        pdf.cell(0, 4, "-"*35, ln=True, align='C')
        total_belanja = sum(row['total'] for _, row in items_df.iterrows())
        for _, row in items_df.iterrows():
            pdf.cell(0, 6, f"{row['produk']} x{row['qty']}", ln=False)
            pdf.cell(0, 6, f"Rp{row['total']:,.0f}", ln=True, align='R')
        pdf.cell(0, 4, "-"*35, ln=True, align='C')
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, f"TOTAL: Rp {total_belanja:,.0f}", ln=True, align='R')
        return pdf.output(dest='S').encode('latin-1')
    except:
        return None

# --- SESSION STATE ---
if 'is_logged_in' not in st.session_state:
    st.session_state.is_logged_in = False
    st.session_state.user_role = None
    st.session_state.user_name = None
    st.session_state.active_shift_id = None

# --- LOGIN SCREEN ---
if not st.session_state.is_logged_in:
    st.title("🔐 Rizki Cell POS Enterprise V8")
    with st.container():
        col_l, col_r = st.columns(2)
        with col_l:
            u = st.text_input("Username", key="login_u")
            p = st.text_input("Password", type='password', key="login_p")
            if st.button("Login System", use_container_width=True):
                cur = conn.cursor()
                cur.execute("SELECT role FROM users WHERE username=? AND password=?", (u, hash_pass(p)))
                user_data = cur.fetchone()
                
                if user_data:
                    st.session_state.is_logged_in = True
                    st.session_state.user_role = user_data[0]
                    st.session_state.user_name = u
                    log_audit(u, "LOGIN", "sistem")
                    st.rerun()
                else:
                    log_audit(u, "LOGIN GAGAL", "sistem", data_baru="Kredensial salah")
                    st.error("Kredensial Salah!")
    st.stop()

# --- SIDEBAR ---
st.sidebar.header(f"📱 {st.session_state.user_role} Panel")
st.sidebar.write(f"User: **{st.session_state.user_name}**")
menu = st.sidebar.radio("Navigasi", [
    "🛒 Kasir (POS)", 
    "📦 Inventori Stok (CRUD)", 
    "📜 Histori Transaksi (CRUD)", 
    "📝 Buku Piutang / Kasbon", 
    "📊 Dashboard & Audit", 
    "🏁 Selesai Shift"
])

if st.sidebar.button("Keluar Aplikasi"):
    log_audit(st.session_state.user_name, "LOGOUT", "sistem")
    st.session_state.is_logged_in = False
    st.session_state.user_role = None
    st.session_state.user_name = None
    st.session_state.active_shift_id = None
    st.rerun()

# --- MODUL 1: KASIR ---
if menu == "🛒 Kasir (POS)":
    st.header("Point of Sale")
    
    if st.session_state.user_role == "Admin" and st.session_state.active_shift_id is None:
        modal = st.number_input("Modal Tunai Awal (Rp):", min_value=0)
        if st.button("Buka Shift"):
            tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
            cur = conn.cursor()
            cur.execute("INSERT INTO shifts (user, waktu_buka, modal_awal, status) VALUES (?,?,?,?)", 
                       (st.session_state.user_name, tgl, modal, "OPEN"))
            conn.commit()
            st.session_state.active_shift_id = cur.lastrowid
            log_audit(st.session_state.user_name, "CREATE", "shifts", data_baru={"shift_id": st.session_state.active_shift_id, "modal": modal})
            st.rerun()
        st.stop()

    df_p = pd.read_sql("SELECT * FROM products WHERE stok > 0", conn)
    if not df_p.empty:
        col1, col2, col3 = st.columns([2,1,2])
        item_name = col1.selectbox("Pilih Barang", df_p['nama'])
        qty = col2.number_input("Qty", min_value=1, step=1)
        metode = col3.radio("Metode Bayar", ["Tunai", "QRIS", "Tempo"], horizontal=True)
        
        pelanggan = ""
        if metode == "Tempo":
            pelanggan = st.text_input("Nama Pelanggan (Wajib)")

        if st.button("Proses Transaksi", use_container_width=True):
            if metode == "Tempo" and not pelanggan:
                st.error("Nama pelanggan wajib diisi!")
            else:
                res = df_p[df_p['nama'] == item_name].iloc[0]
                total = res['jual'] * qty
                profit = (res['jual'] - res['hpp']) * qty
                poin = int(total // 25000)
                tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                with conn:
                    cur = conn.cursor()
                    cur.execute("INSERT INTO sales (shift_id, tgl, produk, qty, total, profit, metode, poin) VALUES (?,?,?,?,?,?,?,?)",
                                (st.session_state.active_shift_id, tgl, item_name, qty, total, profit, metode, poin))
                    sale_id = cur.lastrowid
                    conn.execute("UPDATE products SET stok = stok - ? WHERE id = ?", (qty, int(res['id'])))
                    
                    if metode == "Tempo":
                        conn.execute("INSERT INTO piutang (tgl, nama_pelanggan, nominal, status) VALUES (?,?,?,?)", (tgl, pelanggan, total, "Belum Lunas"))
                
                # Audit Kasir
                data_b = {"id": sale_id, "produk": item_name, "qty": qty, "total": total, "metode": metode}
                log_audit(st.session_state.user_name, "CREATE", "sales", data_baru=data_b)
                
                st.success(f"Berhasil! Total Rp {total:,.0f}")
                st.rerun()
    else: st.info("Stok kosong.")

# --- MODUL 2: INVENTORI CRUD ---
elif menu == "📦 Inventori Stok (CRUD)":
    st.header("Manajemen Inventori Terpusat")
    df_inv = pd.read_sql("SELECT * FROM products", conn)
    
    tabs = st.tabs(["Daftar Barang", "Tambah Baru", "Edit / Hapus"])
    
    with tabs[0]:
        st.dataframe(df_inv, use_container_width=True)
        
    with tabs[1]: # CREATE
        c1, c2 = st.columns(2)
        n = c1.text_input("Nama")
        k = c2.selectbox("Kategori", ["Pulsa", "Paket", "Aksesoris", "Voucher"])
        h = c1.number_input("Modal (HPP)", min_value=0)
        j = c2.number_input("Harga Jual", min_value=0)
        s = c1.number_input("Stok", step=1)
        a = c2.number_input("Min Alert", value=5)
        
        if st.button("Simpan Baru"):
            with conn:
                conn.execute("INSERT INTO products (nama, kategori, hpp, jual, stok, min_stok) VALUES (?,?,?,?,?,?)", (n, k, h, j, s, a))
            data_baru = {"nama": n, "hpp": h, "jual": j, "stok": s}
            log_audit(st.session_state.user_name, "CREATE", "products", data_baru=data_baru)
            st.success("Tersimpan!")
            st.rerun()

    with tabs[2]: # UPDATE / DELETE
        if not df_inv.empty:
            p_edit = st.selectbox("Pilih Barang untuk Diedit/Dihapus:", df_inv['nama'])
            row = df_inv[df_inv['nama'] == p_edit].iloc[0]
            
            with st.form("form_edit_prod"):
                st.write(f"Mengedit: **{row['nama']}**")
                e_n = st.text_input("Nama", value=row['nama'])
                e_h = st.number_input("HPP", value=float(row['hpp']))
                e_j = st.number_input("Jual", value=float(row['jual']))
                e_s = st.number_input("Stok", value=int(row['stok']))
                
                col_btn1, col_btn2 = st.columns(2)
                submit_update = col_btn1.form_submit_button("💾 Update Data", type="primary")
                submit_delete = col_btn2.form_submit_button("🗑️ Hapus Data")
                
                if submit_update:
                    with conn:
                        conn.execute("UPDATE products SET nama=?, hpp=?, jual=?, stok=? WHERE id=?", (e_n, e_h, e_j, e_s, int(row['id'])))
                    old_data = {"nama": row['nama'], "hpp": row['hpp'], "jual": row['jual'], "stok": row['stok']}
                    new_data = {"nama": e_n, "hpp": e_h, "jual": e_j, "stok": e_s}
                    log_audit(st.session_state.user_name, "UPDATE", "products", data_lama=old_data, data_baru=new_data)
                    st.success("Update Berhasil!")
                    st.rerun()
                    
                if submit_delete:
                    with conn:
                        conn.execute("DELETE FROM products WHERE id=?", (int(row['id']),))
                    old_data = {"nama": row['nama'], "sisa_stok": row['stok']}
                    log_audit(st.session_state.user_name, "DELETE", "products", data_lama=old_data)
                    st.success("Barang Dihapus!")
                    st.rerun()

# --- MODUL 3: HISTORI TRANSAKSI CRUD ---
elif menu == "📜 Histori Transaksi (CRUD)":
    st.header("Manajemen Histori Penjualan")
    df_sales = pd.read_sql("SELECT * FROM sales ORDER BY id DESC", conn)
    
    st.dataframe(df_sales, use_container_width=True)
    
    if not df_sales.empty:
        st.subheader("Edit / Hapus (Void) Transaksi")
        t_id = st.selectbox("Pilih ID Transaksi:", df_sales['id'])
        t_row = df_sales[df_sales['id'] == t_id].iloc[0]
        
        with st.form("form_edit_trx"):
            st.info(f"Produk: {t_row['produk']} | Tgl: {t_row['tgl']}")
            new_qty = st.number_input("Kuantitas (Qty)", value=int(t_row['qty']), min_value=1)
            new_metode = st.radio("Metode", ["Tunai", "QRIS", "Tempo"], index=["Tunai", "QRIS", "Tempo"].index(t_row['metode']), horizontal=True)
            
            c_u, c_d = st.columns(2)
            btn_update = c_u.form_submit_button("💾 Update Transaksi", type="primary")
            btn_void = c_d.form_submit_button("🗑️ Void (Hapus) Transaksi")
            
            if btn_update:
                # Logika: Jika Qty berubah, kalkulasi ulang stok & total
                diff_qty = new_qty - int(t_row['qty'])
                
                # Cari harga terbaru produk untuk hitung ulang (asumsi harga tidak berubah, ambil dari HPP/Jual saat ini)
                cur = conn.cursor()
                cur.execute("SELECT hpp, jual FROM products WHERE nama=?", (t_row['produk'],))
                p_data = cur.fetchone()
                
                if p_data:
                    p_hpp, p_jual = p_data
                    new_total = new_qty * p_jual
                    new_profit = new_qty * (p_jual - p_hpp)
                    new_poin = int(new_total // 25000)
                    
                    with conn:
                        # Potong/Tambah Stok sesuai selisih Qty
                        conn.execute("UPDATE products SET stok = stok - ? WHERE nama=?", (diff_qty, t_row['produk']))
                        # Update Transaksi
                        conn.execute("UPDATE sales SET qty=?, total=?, profit=?, metode=?, poin=? WHERE id=?", 
                                    (new_qty, new_total, new_profit, new_metode, int(t_row['id'])))
                        
                    old_data = {"qty": int(t_row['qty']), "total": t_row['total'], "metode": t_row['metode']}
                    new_data = {"qty": new_qty, "total": new_total, "metode": new_metode}
                    log_audit(st.session_state.user_name, "UPDATE", "sales", data_lama=old_data, data_baru=new_data)
                    st.success("Transaksi diupdate. Stok & Omzet disesuaikan!")
                    st.rerun()
                else:
                    st.error("Produk sudah dihapus dari inventori, tidak bisa diupdate.")

            if btn_void:
                # Kembalikan stok
                with conn:
                    conn.execute("UPDATE products SET stok = stok + ? WHERE nama=?", (int(t_row['qty']), t_row['produk']))
                    conn.execute("DELETE FROM sales WHERE id=?", (int(t_row['id']),))
                
                old_data = {"produk": t_row['produk'], "qty": int(t_row['qty']), "total": t_row['total']}
                log_audit(st.session_state.user_name, "DELETE (VOID)", "sales", data_lama=old_data)
                st.warning("Transaksi dibatalkan. Stok dikembalikan.")
                st.rerun()

# --- MODUL 4: BUKU PIUTANG ---
elif menu == "📝 Buku Piutang / Kasbon":
    st.header("Buku Piutang Pelanggan")
    df_piutang = pd.read_sql("SELECT * FROM piutang WHERE status='Belum Lunas'", conn)
    st.dataframe(df_piutang, use_container_width=True)
    if not df_piutang.empty:
        with st.form("pelunasan"):
            p_id = st.selectbox("ID Piutang", df_piutang['id'])
            if st.form_submit_button("Tandai Lunas"):
                with conn:
                    conn.execute("UPDATE piutang SET status='Lunas' WHERE id=?", (p_id,))
                log_audit(st.session_state.user_name, "UPDATE", "piutang", data_lama={"status":"Belum Lunas"}, data_baru={"status":"Lunas"})
                st.rerun()

# --- MODUL 5: DASHBOARD & AUDIT ---
elif menu == "📊 Dashboard & Audit":
    tabs = st.tabs(["Laporan Keuangan", "Sistem Audit Trail"])
    
    with tabs[0]:
        df_sales = pd.read_sql("SELECT * FROM sales", conn)
        m1, m2 = st.columns(2)
        m1.metric("Total Omzet", f"Rp {df_sales['total'].sum():,.0f}")
        m2.metric("Profit Bersih", f"Rp {df_sales['profit'].sum():,.0f}")
        if not df_sales.empty:
            st.plotly_chart(px.bar(df_sales.groupby('produk')['qty'].sum().reset_index(), x='produk', y='qty', title="Barang Terlaris"))
    
    with tabs[1]:
        st.subheader("Log Aktivitas Sistem (Keamanan)")
        st.write("Catatan detail setiap perubahan data (CRUD) beserta nilai sebelum dan sesudahnya.")
        
        df_audit = pd.read_sql("SELECT id, tgl, user, aksi, tabel, data_lama, data_baru FROM audit_logs ORDER BY id DESC", conn)
        
        # Fitur Filter Audit
        f_user = st.selectbox("Filter User:", ["Semua"] + df_audit['user'].unique().tolist())
        if f_user != "Semua":
            df_audit = df_audit[df_audit['user'] == f_user]
            
        st.dataframe(df_audit, use_container_width=True)

# --- MODUL 6: SHIFT ---
elif menu == "🏁 Selesai Shift":
    if st.session_state.active_shift_id:
        fisik = st.number_input("Hitung Uang Fisik (Laci):", min_value=0)
        if st.button("Tutup Shift & Backup"):
            tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
            with conn:
                conn.execute("UPDATE shifts SET waktu_tutup=?, total_tunai=?, status=? WHERE id=?", (tgl, fisik, "CLOSED", st.session_state.active_shift_id))
            b_file = backup_db()
            log_audit(st.session_state.user_name, "UPDATE", "shifts", data_baru={"status": "CLOSED", "uang_fisik": fisik})
            st.session_state.active_shift_id = None
            st.success(f"Shift ditutup. Backup db: {b_file}")
    else: st.info("Tidak ada shift aktif.")