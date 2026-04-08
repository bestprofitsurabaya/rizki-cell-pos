import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime
import qrcode
from io import BytesIO
from fpdf import FPDF

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Rizki Cell POS Ultimate", layout="wide", page_icon="📱")

# --- DATABASE ENGINE ---
def init_db():
    conn = sqlite3.connect('rizki_cell_enterprise.db', check_same_thread=False)
    cursor = conn.cursor()
    # Produk: ID, Nama, Kategori, HPP, Jual, Stok, Min_Stok
    cursor.execute('''CREATE TABLE IF NOT EXISTS products 
        (id INTEGER PRIMARY KEY, nama TEXT, kategori TEXT, hpp REAL, jual REAL, stok INTEGER, min_stok INTEGER)''')
    # Sales: ID, Shift_ID, Tgl, Produk, Qty, Total, Profit, Metode, Poin
    cursor.execute('''CREATE TABLE IF NOT EXISTS sales 
        (id INTEGER PRIMARY KEY, shift_id INTEGER, tgl TEXT, produk TEXT, qty INTEGER, total REAL, profit REAL, metode TEXT, poin INTEGER)''')
    # Shifts: ID, User, Waktu_Buka, Waktu_Tutup, Modal_Awal, Total_Tunai, Status
    cursor.execute('''CREATE TABLE IF NOT EXISTS shifts 
        (id INTEGER PRIMARY KEY, user TEXT, waktu_buka TEXT, waktu_tutup TEXT, modal_awal REAL, total_tunai REAL, status TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# --- FUNGSI GENERATE STRUK PDF ---
def generate_pdf(nota_id, tgl, items_df):
    try:
        pdf = FPDF(format=(80, 150))
        pdf.add_page()
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, "RIZKI CELL", ln=True, align='C')
        pdf.set_font("Arial", size=8)
        pdf.cell(0, 4, f"Nota: {nota_id} | {tgl}", ln=True, align='C')
        pdf.cell(0, 4, "-"*35, ln=True, align='C')
        
        total_belanja = 0
        for _, row in items_df.iterrows():
            pdf.cell(0, 6, f"{row['produk']} x{row['qty']}", ln=False)
            pdf.cell(0, 6, f"Rp{row['total']:,.0f}", ln=True, align='R')
            total_belanja += row['total']
            
        pdf.cell(0, 4, "-"*35, ln=True, align='C')
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, f"TOTAL: Rp {total_belanja:,.0f}", ln=True, align='R')
        pdf.set_font("Arial", 'I', 7)
        pdf.cell(0, 8, "Simpan struk ini untuk klaim poin!", ln=True, align='C')
        return pdf.output(dest='S').encode('latin-1')
    except:
        return None

# --- SESSION STATE (PERBAIKAN ERROR TYPERROR) ---
if 'is_logged_in' not in st.session_state:
    st.session_state.is_logged_in = False
    st.session_state.user_role = None
    st.session_state.user_name = None
    st.session_state.active_shift_id = None

# --- LOGIN SCREEN ---
if not st.session_state.is_logged_in:
    st.title("🔐 Rizki Cell POS Enterprise")
    with st.container(border=True):
        col_l, col_r = st.columns(2)
        with col_l:
            u = st.text_input("Username", key="login_u")
            p = st.text_input("Password", type='password', key="login_p")
            if st.button("Login System", use_container_width=True):
                if u == "owner" and p == "master":
                    st.session_state.is_logged_in = True
                    st.session_state.user_role = "Owner"
                    st.session_state.user_name = u
                    st.rerun()
                elif u == "admin" and p == "admin":
                    st.session_state.is_logged_in = True
                    st.session_state.user_role = "Admin"
                    st.session_state.user_name = u
                    st.rerun()
                else:
                    st.error("Kredensial Salah!")
    st.stop()

# --- SIDEBAR ---
st.sidebar.header(f"📱 {st.session_state.user_role} Panel")
st.sidebar.write(f"User aktif: **{st.session_state.user_name}**")
menu = st.sidebar.radio("Navigasi", ["🛒 Kasir (POS)", "📦 Inventori Stok", "📊 Dashboard Owner", "🏁 Selesai Shift"])

if st.sidebar.button("Keluar Aplikasi", fg_color="red"):
    st.session_state.is_logged_in = False
    st.session_state.user_role = None
    st.session_state.user_name = None
    st.session_state.active_shift_id = None
    st.rerun()

# --- MODUL 1: KASIR (POS) ---
if menu == "🛒 Kasir (POS)":
    st.header("Point of Sale & Loyalty")
    
    # Check Shift (Khusus Admin)
    if st.session_state.user_role == "Admin" and st.session_state.active_shift_id is None:
        with st.container(border=True):
            st.subheader("Buka Shift Baru")
            modal = st.number_input("Input Modal Tunai Awal (Rp):", min_value=0)
            if st.button("Mulai Tugas"):
                tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
                cur = conn.cursor()
                cur.execute("INSERT INTO shifts (user, waktu_buka, modal_awal, status) VALUES (?,?,?,?)", 
                           (st.session_state.user_name, tgl, modal, "OPEN"))
                conn.commit()
                st.session_state.active_shift_id = cur.lastrowid
                st.rerun()
        st.stop()

    # Transaksi Area
    df_p = pd.read_sql("SELECT * FROM products WHERE stok > 0", conn)
    
    if not df_p.empty:
        # Alert Stok
        low_stock = df_p[df_p['stok'] <= df_p['min_stok']]
        if not low_stock.empty:
            st.warning(f"⚠️ Stok Menipis: {', '.join(low_stock['nama'].tolist())}")

        with st.container(border=True):
            col1, col2, col3 = st.columns([2,1,1])
            item = col1.selectbox("Pilih Barang", df_p['nama'])
            qty = col2.number_input("Qty", min_value=1, step=1)
            metode = col3.radio("Metode", ["Tunai", "QRIS"], horizontal=True)
            
            if st.button("Proses Transaksi", use_container_width=True):
                res = df_p[df_p['nama'] == item].iloc[0]
                total = res['jual'] * qty
                profit = (res['jual'] - res['hpp']) * qty
                poin = int(total // 25000)
                tgl = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                with conn:
                    conn.execute("INSERT INTO sales (shift_id, tgl, produk, qty, total, profit, metode, poin) VALUES (?,?,?,?,?,?,?,?)",
                                (st.session_state.active_shift_id, tgl, item, qty, total, profit, metode, poin))
                    conn.execute("UPDATE products SET stok = stok - ? WHERE id = ?", (qty, int(res['id'])))
                
                st.success(f"Transaksi Berhasil! Total Rp {total:,.0f} | Poin Didapat: {poin}")
                
                if metode == "QRIS":
                    qr = qrcode.make(f"RIZKI-CELL-{total}")
                    buf = BytesIO(); qr.save(buf)
                    st.image(buf, caption="Scan QRIS", width=200)
                
                nota_df = pd.DataFrame([{'produk': item, 'qty': qty, 'total': total}])
                pdf_bytes = generate_pdf(f"RC{datetime.now().second}", tgl, nota_df)
                if pdf_bytes:
                    st.download_button("🖨️ Cetak Struk (PDF)", data=pdf_bytes, file_name=f"struk_{datetime.now().strftime('%H%M%S')}.pdf")
    else:
        st.info("Harap Owner menginput produk di menu Inventori terlebih dahulu.")

# --- MODUL 2: INVENTORI ---
elif menu == "📦 Inventori Stok":
    st.header("Manajemen Inventori & HPP")
    
    if st.session_state.user_role == "Owner":
        with st.expander("➕ Tambah/Update Barang Baru"):
            c1, c2, c3 = st.columns(3)
            nama = c1.text_input("Nama Barang")
            kat = c2.selectbox("Kategori", ["Pulsa", "Paket Data", "Aksesoris", "Voucher"])
            hpp = c3.number_input("Harga Modal (HPP)")
            jual = c1.number_input("Harga Jual")
            stok = c2.number_input("Jumlah Stok", step=1)
            alert = c3.number_input("Min. Stok Alert", value=5)
            
            if st.button("Simpan Data Barang"):
                with conn:
                    conn.execute("INSERT INTO products (nama, kategori, hpp, jual, stok, min_stok) VALUES (?,?,?,?,?,?)",
                                (nama, kat, hpp, jual, stok, alert))
                st.success("Barang Terdaftar!")
                st.rerun()

    df_inv = pd.read_sql("SELECT id, nama, kategori, hpp, jual, stok, min_stok FROM products", conn)
    st.dataframe(df_inv, use_container_width=True)

# --- MODUL 3: OWNER DASHBOARD ---
elif menu == "📊 Dashboard Owner":
    if st.session_state.user_role != "Owner":
        st.error("Hanya Owner yang dapat melihat laporan keuangan.")
    else:
        st.header("Laporan Performa Bisnis")
        df_sales = pd.read_sql("SELECT * FROM sales", conn)
        
        if not df_sales.empty:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Omzet", f"Rp {df_sales['total'].sum():,.0f}")
            m2.metric("Profit Bersih", f"Rp {df_sales['profit'].sum():,.0f}")
            m3.metric("Total Poin", f"{df_sales['poin'].sum()} Pts")
            m4.metric("Jumlah Transaksi", len(df_sales))
            
            c1, c2 = st.columns(2)
            with c1:
                fig1 = px.bar(df_sales.groupby('produk')['qty'].sum().reset_index(), x='produk', y='qty', title="Produk Terlaris")
                st.plotly_chart(fig1)
            with c2:
                fig2 = px.pie(df_sales, values='total', names='metode', title="Metode Pembayaran")
                st.plotly_chart(fig2)
            
            if st.button("📥 Ekspor Laporan Ke Excel"):
                df_sales.to_excel("Laporan_Rizki_Cell.xlsx", index=False)
                st.success("File 'Laporan_Rizki_Cell.xlsx' berhasil dibuat!")
        else:
            st.info("Belum ada data penjualan.")

# --- MODUL 4: SELESAI SHIFT ---
elif menu == "🏁 Selesai Shift":
    st.header("Penutupan Kasir")
    if st.session_state.active_shift_id:
        tunai_fisik = st.number_input("Hitung Uang Tunai di Laci (Fisik):", min_value=0)
        if st.button("Tutup Shift & Konfirmasi"):
            tgl_tutup = datetime.now().strftime("%Y-%m-%d %H:%M")
            with conn:
                conn.execute("UPDATE shifts SET waktu_tutup=?, total_tunai=?, status=? WHERE id=?", 
                            (tgl_tutup, tunai_fisik, "CLOSED", st.session_state.active_shift_id))
            st.session_state.active_shift_id = None
            st.success("Shift ditutup. Uang fisik tercatat.")
    else:
        st.info("Tidak ada shift yang aktif untuk ditutup.")