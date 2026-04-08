# 📖 PANDUAN PENGGUNAAN (USER MANUAL)
**Sistem Manajemen Terpadu: Rizki Cell ERP V12**

Dokumen ini memuat panduan lengkap operasional aplikasi Rizki Cell, mencakup manajemen multi-cabang, sistem kasir ganda (Fisik & PPOB), rekam jejak audit, dan keamanan sistem.

## 1. Hak Akses & Kredensial Login
Sistem dilengkapi keamanan enkripsi *hash*. Terdapat dua akun bawaan (default) saat pertama kali digunakan:

| Tipe Akun | Username | Password | Penempatan | Hak Istimewa |
| :--- | :--- | :--- | :--- | :--- |
| **Owner** | `owner` | `master` | Pusat | Akses penuh seluruh modul & pengaturan HR. |
| **Admin** | `admin1` | `admin` | Cabang 1 | Terbatas pada kasir, absen shift, & pelunasan. |

> **Catatan Keamanan:** Setiap aksi di dalam sistem akan terekam atas nama *Username* yang sedang *login*. Jangan membagikan *password* Anda kepada staf lain.

---

## 2. Alur Kerja Harian (Standard Operating Procedure)
Untuk memastikan data tidak berantakan, ikuti urutan kerja harian berikut:
1.  **Buka Toko:** Admin *login*, masuk ke menu "Kasir", lalu menginput uang tunai modal awal untuk membuka *shift*.
2.  **Operasional:** Admin melayani transaksi Fisik maupun PPOB.
3.  **Tutup Toko:** Admin menghitung uang fisik di laci, masuk ke menu "Selesai Shift", dan menutup *shift* tersebut.

---

## 3. Penjelasan Lengkap Modul Sistem

### 📊 Dashboard & Keuntungan (Khusus Owner)
Pusat analitik bisnis yang memberikan ringkasan keuangan *real-time*.
* **Pencapaian HARI INI:** Menampilkan total Omzet dan Profit yang akan otomatis di-*reset* ke angka nol (0) setiap jam 12 malam.
* **Peringatan Saldo:** Jika Saldo Deposit PPOB (Server) di bawah Rp 100.000, akan muncul peringatan merah menyala agar Owner segera melakukan *Top-Up*.
* **Statistik Sepanjang Waktu:** Menampilkan akumulasi penjualan fisik maupun PPOB beserta grafiknya.

### 👥 Karyawan & Cabang (Khusus Owner)
Modul Human Resources (HR) untuk mengelola *franchise* / cabang.
* **Data Cabang:** Fitur untuk membuat lokasi cabang baru (Misal: Cabang Sudirman).
* **Data Karyawan:** Fitur untuk membuat akun staf baru. Anda **wajib** menempatkan staf tersebut di cabang tertentu. Transaksi staf tersebut nantinya akan otomatis masuk ke laporan cabang yang dituju.

### 💳 Manajemen Saldo PPOB (Khusus Owner)
Buku besar (*Ledger*) untuk mengatur uang virtual (deposit pulsa).
* **Top-Up Saldo:** Jika Owner mentransfer uang ke aplikasi agen (misal Digiflazz), Owner wajib mencatatnya di sini agar kasir bisa mulai berjualan pulsa.
* **Riwayat Mutasi:** Menampilkan aliran dana PPOB (Uang Masuk dari Top-Up, Uang Keluar dari Transaksi Kasir).

### 📦 Inventori & Excel Import
Pusat manajemen stok barang fisik (Casing, HP, Voucher, dll).
* **Input Manual:** Mendaftarkan barang satu per satu beserta nama *supplier*-nya.
* **Import Massal (Excel):** Fitur memperbarui ratusan barang dalam 1 detik.
    1. Klik **Download Template Excel**.
    2. Isi data menggunakan Microsoft Excel.
    3. *Upload* kembali file tersebut. Sistem pintar akan otomatis menambah stok (jika barang sudah ada) atau membuat barang baru (jika belum ada).

### 🛒 Kasir Umum (Fisik)
Modul untuk menjual barang berwujud fisik yang memotong stok inventori.
* Sistem mewajibkan Admin mencentang **Kotak Konfirmasi** sebelum tombol "Proses Pembayaran" bisa diklik (Mencegah salah klik).
* Mendukung fitur kasbon dengan memilih metode **"Tempo"**. Nama pelanggan wajib diisi.
* Mendukung fitur **QRIS** yang otomatis memunculkan *barcode* di layar.

### ⚡ Kasir PPOB (Pulsa & Digital)
Modul khusus produk digital yang **tidak memotong stok barang**, melainkan **memotong Saldo Deposit PPOB**.
* Kasir cukup memasukkan Nomor HP dan memilih Modal Server.
* Sistem secara pintar menghitung tagihan berdasarkan *Markup* keuntungan yang ditentukan.
* Jika saldo server di sistem kurang dari modal transaksi, tombol transaksi akan terkunci dan menampilkan pesan *Error*.

### 📝 Buku Piutang
Fitur penagihan pelanggan yang sering melakukan kasbon.
* Menampilkan daftar pelanggan yang status transaksinya masih **"Belum Lunas"**.
* Saat pelanggan membayar, Admin/Owner bisa memilih ID Transaksi dan mengklik tombol **"Tandai Lunas"**. Data akan otomatis hilang dari daftar tunggu.

### 📜 Histori & Audit (Mata-Mata Sistem)
Jejak digital (CCTV Sistem) yang tidak bisa dihapus oleh siapa pun.
* Mencatat seluruh notifikasi yang muncul di layar (Pojok Kanan Atas).
* Merekam **Siapa** yang melakukan, **Kapan** dilakukan, dan **Apa** yang diubah (misalnya detail omzet yang didapat atau uang fisik yang dilaporkan saat tutup shift).

### 🏁 Selesai Shift
Modul khusus untuk sinkronisasi kas toko di penghujung hari kerja.
* Admin **wajib** menghitung fisik uang tunai di dalam laci toko.
* Setelah menekan tombol konfirmasi dan "Tutup Shift", sistem akan mengunci akun admin dari transaksi lebih lanjut hingga ia membuka *shift* baru keesokan harinya.
