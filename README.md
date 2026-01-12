# Rekber Bot - Sistem Rekening Bersama Telegram

Bot Telegram modern untuk layanan rekber (rekening bersama) dengan interface yang intuitif dan database Supabase.

## Fitur Utama

### Untuk User
- Buat transaksi rekber dengan mudah
- Semua interaksi dilakukan di private message (DM)
- Tracking status transaksi real-time
- Riwayat transaksi lengkap
- Notifikasi otomatis di setiap tahap
- Interface dengan inline buttons yang modern

### Untuk Admin
- Panel admin lengkap dan intuitif
- Approve/reject transaksi
- Kelola metode pembayaran (Bank & E-Wallet)
- Broadcast message ke semua user
- Statistik real-time
- Kelola user (ban/unban)

### Keamanan
- Database Supabase dengan RLS (Row Level Security)
- Tracking lengkap setiap transaksi
- Transaction logs untuk audit
- Verifikasi admin untuk setiap aksi penting

## Teknologi

- **Python 3.9+**
- **Aiogram 3.4.1** - Framework bot Telegram modern
- **Supabase** - Database PostgreSQL cloud
- **FSM (Finite State Machine)** - State management yang rapi

## Instalasi

1. Clone repository ini

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Setup environment variables:
   - Copy `.env.example` ke `.env`
   - Isi semua nilai yang diperlukan

4. Database sudah otomatis disetup di Supabase

5. Jalankan bot:
```bash
python bot.py
```

## Environment Variables

```env
BOT_TOKEN=your_bot_token_here
ADMIN_ID=your_admin_telegram_id
CHANNEL=@your_channel_username
SUPABASE_URL=your_supabase_project_url
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
```

## Flow Transaksi

### 1. Buyer membuat transaksi
- Buyer klik "Buat Transaksi Baru"
- Isi format dengan data seller, buyer, barang, harga
- Transaksi masuk ke admin untuk approval

### 2. Admin approve
- Admin terima notifikasi transaksi baru
- Admin review dan approve/reject
- Buyer dapat notifikasi hasil approval

### 3. Buyer transfer
- Buyer lihat metode pembayaran
- Transfer ke rekening yang ditentukan
- Upload bukti transfer ke bot

### 4. Admin verifikasi & notifikasi seller
- Admin terima bukti transfer
- Admin konfirmasi ke seller bahwa dana aman
- Seller dapat notifikasi untuk kirim barang

### 5. Seller kirim barang
- Seller kirim barang/akun ke buyer
- Seller konfirmasi pengiriman di bot
- Buyer dapat notifikasi untuk cek barang

### 6. Buyer konfirmasi
- Buyer cek barang yang diterima
- Buyer konfirmasi jika sesuai
- Admin dapat notifikasi untuk cairkan dana

### 7. Admin cairkan dana
- Admin transfer dana ke seller
- Seller dapat notifikasi dana dicairkan
- Transaksi selesai

## Perintah Bot

### User Commands
- `/start` - Mulai bot dan lihat menu utama
- Semua fitur tersedia via inline buttons

### Admin Commands
- `/admin` - Buka panel admin
- Kelola transaksi, payment, broadcast, user management

## Database Schema

### Tables
- **users** - Data user dan status
- **transactions** - Data transaksi
- **transaction_logs** - Audit log transaksi
- **payment_methods** - Metode pembayaran

## Deployment

Bot ini siap di-deploy ke Render.com:

1. Push ke repository
2. Connect ke Render
3. Environment variables akan auto-populated dari Supabase
4. Deploy otomatis

## Perbedaan dengan Versi Lama

### Yang Dihapus
- Tidak perlu buat grup lagi
- Tidak perlu command `.pay`, `.masuk`, `.done`
- Tidak perlu manual link grup
- SQLite diganti Supabase

### Yang Ditambahkan
- Semua di private message (DM)
- UI modern dengan inline buttons
- Database cloud (Supabase)
- State management yang lebih baik
- Notifikasi otomatis lebih lengkap
- Admin panel yang lebih intuitif
- Transaction logs untuk audit
- Riwayat transaksi per user

## Support

Untuk pertanyaan atau issue, hubungi admin bot.
