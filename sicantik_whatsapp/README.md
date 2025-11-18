# SICANTIK WhatsApp Notifications

Modul untuk sistem notifikasi WhatsApp otomatis pada SICANTIK Companion App.

## Deskripsi

Modul ini mengintegrasikan sistem notifikasi WhatsApp menggunakan modul WhatsApp Enterprise Odoo untuk mengirimkan notifikasi otomatis kepada:
- **Pemohon izin** - Status perizinan & download link
- **Staff DPMPTSP** - Dokumen baru & reminder
- **Pejabat** - Approval request

## Fitur

### 7 Skenario Notifikasi

1. **Izin Selesai Diproses** (`izin_selesai_diproses`)
   - Trigger: Status izin = 'active' dan ada permit_number
   - Recipient: Pemohon izin
   - Template: `izin_selesai_diproses`

2. **Dokumen Baru untuk Tandatangan** (`dokumen_baru_untuk_tandatangan`)
   - Trigger: Dokumen baru diupload dan status = 'pending_signature'
   - Recipient: Staff DPMPTSP
   - Template: `dokumen_baru_untuk_tandatangan`

3. **Dokumen Perlu Approval** (`dokumen_perlu_approval`)
   - Trigger: Dokumen perlu approval pejabat
   - Recipient: Pejabat berwenang
   - Template: `dokumen_perlu_approval`

4. **Update Status Perizinan** (`update_status_perizinan`)
   - Trigger: Status izin berubah
   - Recipient: Pemohon & Staff terkait
   - Template: `update_status_perizinan`

5. **Reminder Dokumen Pending** (`reminder_dokumen_pending`)
   - Trigger: Cron job (daily) - Dokumen pending > 24 jam
   - Recipient: Staff yang bertanggung jawab
   - Template: `reminder_dokumen_pending`

6. **Peringatan Masa Berlaku Izin** (`peringatan_masa_berlaku_izin`)
   - Trigger: Cron job (daily) - Izin akan habis dalam 90/60/30/7 hari
   - Recipient: Pemohon izin
   - Template: `peringatan_masa_berlaku_izin`
   - Schedule: 90 hari, 60 hari, 30 hari, 7 hari sebelum expired

7. **Perpanjangan Izin Disetujui** (`perpanjangan_izin_disetujui`)
   - Trigger: Perpanjangan izin selesai diproses
   - Recipient: Pemohon izin
   - Template: `perpanjangan_izin_disetujui`

## Dependencies

- `whatsapp` - Odoo Enterprise WhatsApp module
- `sicantik_connector` - Modul connector SICANTIK
- `sicantik_tte` - Modul digital signature

## Instalasi

1. Pastikan modul WhatsApp Enterprise sudah terinstall
2. **Jika upgrade modul dan ada error "missing 2" atau variabel error:**
   - Hapus template WhatsApp SICANTIK yang sudah ada melalui UI:
     - WhatsApp → Templates
     - Cari template dengan nama "Izin Selesai Diproses", "Dokumen Baru", dll
     - Hapus semua template SICANTIK yang sudah ada
   - Atau jalankan script SQL di `data/cleanup_templates.sql` untuk menghapus template yang sudah ada
3. Install/Upgrade modul `sicantik_whatsapp`
4. Konfigurasi WhatsApp Business Account di Odoo:
   - Settings → WhatsApp → WhatsApp Accounts
   - Tambahkan akun WhatsApp Business (Meta Cloud API)
5. Approve template-template WhatsApp:
   - WhatsApp → Templates
   - Submit template ke Meta untuk approval
   - Tunggu approval (24-48 jam)

## Konfigurasi

### WhatsApp Business Account

1. Buat Facebook Business Manager account
2. Verifikasi bisnis
3. Tambahkan nomor telepon
4. Dapatkan API credentials:
   - App ID
   - App Secret
   - Account ID
   - Phone Number ID
   - Access Token

### Template WhatsApp

Semua template sudah dibuat otomatis saat instalasi modul. Template perlu di-submit ke Meta untuk approval sebelum bisa digunakan.

**Catatan:** Template menggunakan Bahasa Indonesia dan variabel dinamis sesuai dengan data izin.

## Cron Jobs

### 1. Cek Izin Mendekati Masa Berlaku
- **Schedule:** Setiap hari jam 09:00
- **Function:** `cron_check_expiring_permits()`
- **Deskripsi:** Mengecek izin yang akan expired dalam 90/60/30/7 hari dan mengirim notifikasi

### 2. Reminder Dokumen Pending
- **Schedule:** Setiap hari jam 10:00
- **Function:** `cron_reminder_dokumen_pending()`
- **Deskripsi:** Mengirim reminder untuk dokumen yang pending lebih dari 24 jam

## Struktur Modul

```
sicantik_whatsapp/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── sicantik_permit_inherit.py    # Trigger notifikasi dari permit
│   └── sicantik_document_inherit.py  # Trigger notifikasi dari document
├── views/
│   └── sicantik_whatsapp_menus.xml
├── data/
│   ├── whatsapp_templates.xml        # 7 template notifikasi
│   └── cron_data.xml                 # Cron jobs
├── security/
│   └── ir.model.access.csv
└── README.md
```

## Penggunaan

### Notifikasi Otomatis

Notifikasi akan dikirim otomatis saat:
- Izin selesai diproses (status = 'active')
- Status izin berubah
- Dokumen baru diupload
- Dokumen perlu approval
- Perpanjangan izin disetujui

### Notifikasi Scheduled

- **Peringatan masa berlaku:** Otomatis setiap hari jam 09:00
- **Reminder dokumen:** Otomatis setiap hari jam 10:00

## Variabel Template

Setiap template menggunakan variabel dinamis yang diambil dari data izin/dokumen:

- `{{1}}` - Nama pemohon
- `{{2}}` - Jenis izin
- `{{3}}` - Nomor surat
- `{{4}}` - Tanggal terbit/berakhir
- `{{5}}` - Link download/dashboard
- `{{6}}` - Link perpanjangan (untuk expiry warning)
- `{{7}}` - Kontak DPMPTSP (untuk expiry warning)

## Troubleshooting

### Template tidak ditemukan
- Pastikan template sudah di-submit ke Meta dan status = 'approved'
- Cek nama template (`template_name`) sesuai dengan yang digunakan di code

### Notifikasi tidak terkirim
- Cek nomor WhatsApp partner sudah benar dan valid
- Pastikan WhatsApp Business Account sudah dikonfigurasi dengan benar
- Cek log Odoo untuk error detail

### Cron job tidak berjalan
- Cek cron job sudah aktif di Settings → Technical → Automation → Scheduled Actions
- Pastikan timezone server sudah benar

## Catatan Penting

1. **Template Approval:** Semua template perlu di-approve oleh Meta sebelum bisa digunakan (24-48 jam)
2. **Rate Limiting:** WhatsApp Business API memiliki rate limit (60 pesan/menit)
3. **Nomor WhatsApp:** Pastikan partner memiliki nomor WhatsApp yang valid
4. **Free Text Variables:** Beberapa variabel menggunakan free_text yang perlu di-set manual di code (link perpanjangan, kontak)

## Support

Untuk pertanyaan atau masalah, hubungi tim development SICANTIK Companion.

