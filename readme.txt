# 📖 PANDUAN PENGGUNAAN (USER MANUAL)
**Sistem Manajemen Terpadu: Rizki Cell ERP V10**

Dokumen ini memuat panduan lengkap penggunaan seluruh fitur aplikasi Rizki Cell, mulai dari manajemen kasir, inventaris, hingga laporan keuangan.

## 1. Hak Akses & Kredensial Login
Sistem dilengkapi dengan keamanan enkripsi ganda. Terdapat dua tingkatan akses default saat aplikasi pertama kali dijalankan:

| Tipe Akun | Username | Password | Wilayah Akses | Hak Istimewa |
| :--- | :--- | :--- | :--- | :--- |
| **Owner (Pemilik)** | `owner` | `master` | Pusat | Akses penuh (Dashboard, Audit, Edit, Hapus) |
| **Admin (Kasir)** | `admin1` | `admin` | Cabang 1 | Terbatas (Hanya Kasir, Buka/Tutup Shift) |

---

## 2. Modul Kasir Umum (Fisik)
Modul ini digunakan untuk mencatat transaksi penjualan barang fisik seperti HP, Aksesoris, dan Voucher Fisik.

* **Buka Shift:** Admin diwajibkan memasukkan modal uang receh (tunai) di laci kasir sebelum bisa memulai transaksi.
* **Pencarian Barang:** Gunakan kotak *dropdown* untuk mengetik dan mencari nama barang dengan cepat.
* **Metode Pembayaran (QRIS):** Jika pelanggan memilih QRIS, sistem akan memunculkan *barcode* unik di layar yang bisa langsung di-*scan* oleh pelanggan.
* **Metode Pembayaran (Tempo):** Digunakan untuk pelanggan yang berhutang (Kasbon). Anda **wajib** mengisi nama pelanggan agar sistem bisa mencatatnya ke dalam Buku Piutang.

---

## 3. Modul Kasir PPOB (Pulsa & Tagihan)
Modul khusus untuk produk digital (Pulsa, Paket Data, Token Listrik) tanpa memotong stok fisik di inventaris.

* **Input Nomor:** Masukkan nomor tujuan pelanggan.
* **Pilih Nominal:** Pilih besaran nominal pulsa/kuota. Sistem otomatis menambahkan *margin* keuntungan (misal: markup Rp 2.000).
* **Proses Tembak:** Menekan tombol transaksi akan mencatat penjualan PPOB secara terpisah di laporan keuangan, membedakannya dari omzet toko fisik.

---

## 4. Modul Inventori & Excel Import (Khusus Owner)
Pusat kendali barang dan harga. Terdapat tiga tab utama di dalam modul ini:

* **Daftar Stok & Supplier:** Menampilkan tabel seluruh barang yang tersedia beserta nama supplier-nya.
* **Input Manual:** Formulir untuk memasukkan satu per satu barang baru. Anda bisa memilih nama supplier dari daftar yang sudah ada.
* **Import Massal (Excel):** Fitur untuk memasukkan ratusan barang sekaligus.
    1.  Klik **Download Template Excel**.
    2.  Isi data di komputer menggunakan Microsoft Excel.
    3.  *Upload* kembali file tersebut. Sistem akan otomatis membuatkan nama supplier baru jika belum terdaftar, memperbarui stok jika barang sudah ada, dan menambah barang baru jika belum terdaftar.

---

## 5. Buku Piutang (Kasbon)
Modul untuk memantau arus piutang dan tagihan pelanggan.

* **Pemantauan Hutang:** Menampilkan tabel daftar pelanggan yang memiliki transaksi dengan metode "Tempo" (Belum Lunas).
* **Pelunasan:** Owner dapat memilih ID transaksi dari *dropdown* dan menekan tombol **Tandai Lunas**. Data hutang akan otomatis hilang dari daftar tunggu dan tercatat lunas di log sistem.

---

## 6. Dashboard & Keuntungan (Khusus Owner)
Pusat analitik bisnis yang menampilkan ringkasan keuangan secara visual.

* **Pencapaian HARI INI:** Panel atas menampilkan Omzet, Jumlah Transaksi, dan Profit Bersih khusus untuk hari tersebut (di-*reset* setiap tengah malam).
* **Statistik Sepanjang Waktu:** Menampilkan akumulasi seluruh penjualan sejak toko beroperasi.
* **Grafik Interaktif:** Menyajikan diagram batang (penjualan per cabang) dan diagram lingkaran (distribusi barang terlaris).

---

## 7. Histori & Audit (Sistem Keamanan)
Mata-mata sistem yang mencatat seluruh jejak digital pengguna.

* **Log Aktivitas:** Merekam tanggal, nama akun (user), jenis aksi (Login, Import Excel, Transaksi, Edit Barang), dan detail perubahannya.
* **Transparansi:** Mencegah kecurangan admin karena setiap perubahan sekecil apa pun tidak bisa dihapus dari log ini.

---

## 8. Selesai Shift (Penutupan)
Langkah wajib bagi kasir sebelum meninggalkan toko.

* **Perhitungan Fisik:** Admin wajib menghitung ulang uang tunai yang ada di dalam laci secara manual dan menginputnya ke sistem.
* **Penutupan:** Menekan tombol "Tutup Shift" akan mengunci sesi kasir tersebut dan memastikan data uang di laci terekam di database untuk dicocokkan oleh Owner keesokan harinya.