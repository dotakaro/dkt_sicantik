# DKT SICANTIK - SICANTIK Companion App

Odoo modules untuk integrasi dengan sistem perizinan Kabupaten Karo (SICANTIK).

## 📦 Modules

### 1. `sicantik_connector`
Modul utama untuk integrasi dengan API SICANTIK:
- Sync data izin dari sistem SICANTIK
- Manajemen jenis izin
- Tracking masa berlaku izin
- Auto-create/update partner dari data pemohon
- Integrasi dengan MinIO untuk storage dokumen

### 2. `sicantik_tte`
Digital signature workflow dengan TTE BSRE:
- Upload dokumen ke MinIO
- Workflow tanda tangan elektronik
- Integrasi dengan BSRE API
- QR code untuk verifikasi dokumen
- Public verification portal

### 3. `sicantik_whatsapp`
WhatsApp notification untuk status izin:
- Notifikasi masa berlaku izin
- Notifikasi status perubahan izin
- Notifikasi izin selesai diproses
- Test notification feature
- Opt-in management untuk Meta WhatsApp Business API

## 🚀 Installation

1. Clone repository ini ke folder `addons_odoo` di Odoo:
```bash
git clone https://github.com/dotakaro/dkt_sicantik.git addons_odoo
```

2. Install modules melalui Odoo Apps:
   - `sicantik_connector`
   - `sicantik_tte` (optional, requires sicantik_connector)
   - `sicantik_whatsapp` (optional, requires sicantik_connector)

## 📋 Requirements

- Odoo 18.4 Enterprise Edition
- Python dependencies (akan diinstall otomatis):
  - `requests`
  - `minio`
  - `cryptography`

## ⚙️ Configuration

### SICANTIK Connector
1. Buka menu **SICANTIK → Configuration**
2. Konfigurasi API endpoint dan credentials
3. Test koneksi
4. Sync data izin

### MinIO Storage
1. Buka menu **SICANTIK → MinIO Configuration**
2. Konfigurasi MinIO server (host, port, access key, secret key)
3. Test koneksi

### WhatsApp Integration
1. Install module `sicantik_whatsapp`
2. Konfigurasi WhatsApp Business Account di Odoo
3. Sync templates dari Meta
4. Setup opt-in untuk nomor penerima

## 📝 License

[License information]

## 👥 Authors

- Dota Karo Teknologi

## 🔗 Links

- Repository: https://github.com/dotakaro/dkt_sicantik
- SICANTIK: http://perizinan.karokab.go.id

