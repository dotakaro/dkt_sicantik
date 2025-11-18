# 📱 Strategi Opt-In WhatsApp untuk Production

## 🎯 Masalah

Meta WhatsApp Business API **WAJIB** memerlukan opt-in sebelum bisa mengirim template messages. Ini menjadi tantangan untuk aplikasi dengan:
- Ribuan nomor yang sudah terdaftar
- Pendaftaran nomor baru setiap saat
- Tidak mungkin manual opt-in untuk setiap nomor

## ✅ Solusi yang Diimplementasikan

### 1. **24-Hour Window Strategy** ⏰

**Konsep:**
- Setelah user mengirim pesan ke WhatsApp Business Account, kita punya **24 jam** untuk mengirim template messages tanpa perlu opt-in
- Ini adalah fitur resmi dari Meta WhatsApp Business API

**Cara Kerja:**
1. User mengirim pesan ke nomor WhatsApp Business Account (dotakaro-wa)
2. Sistem otomatis mendeteksi pesan inbound
3. Sistem mencatat waktu pesan terakhir
4. Dalam 24 jam berikutnya, template messages bisa dikirim tanpa opt-in

**Implementasi:**
- `WhatsAppOptInManager.check_can_send_template()` mengecek:
  - Apakah user sudah opt-in? ✅
  - ATAU masih dalam 24-hour window? ✅
  - Jika salah satu true, bisa kirim template message

### 2. **Auto Opt-In dari Inbound Message** 🔄

**Konsep:**
- Ketika user mengirim pesan inbound, sistem otomatis menandai sebagai opt-in
- Odoo core sudah handle ini via `phone.blacklist` mechanism

**Cara Kerja:**
1. User mengirim pesan ke WhatsApp Business Account
2. Odoo otomatis remove dari blacklist (artinya opt-in)
3. Sistem juga set `whatsapp_opt_in = True` di partner record

### 3. **Opt-In Flow di Form Pendaftaran** 📝

**Konsep:**
- Saat user mendaftar izin baru, minta persetujuan untuk notifikasi WhatsApp
- Simpan consent di database

**Implementasi (TODO):**
- Tambahkan checkbox "Saya setuju menerima notifikasi WhatsApp" di form pendaftaran
- Set `whatsapp_opt_in = True` saat user centang

### 4. **Fallback ke SMS/Email** 📧

**Konsep:**
- Jika user belum opt-in dan tidak dalam 24-hour window, kirim via SMS atau Email
- SMS/Email berisi link untuk opt-in WhatsApp

**Implementasi (TODO):**
- `WhatsAppOptInManager.request_opt_in_via_sms_or_email()`
- Kirim SMS/Email dengan link: `https://perizinan.karokab.go.id/opt-in-whatsapp/{token}`

### 5. **Pre-Approval untuk Nomor Terdaftar** ✅

**Konsep:**
- Untuk nomor yang sudah terdaftar di sistem, request pre-approval di Meta Business Manager
- Pre-approval memungkinkan kirim template messages tanpa perlu opt-in manual

**Cara:**
1. Export daftar nomor yang sudah terdaftar
2. Upload ke Meta Business Manager → Phone Numbers → Contacts
3. Request approval untuk nomor-nomor tersebut

## 📋 Workflow Production

### Scenario 1: User Baru Mendaftar Izin

```
1. User mendaftar izin baru
   ↓
2. Sistem cek: Apakah nomor sudah opt-in?
   ├─ Ya → Kirim template message langsung ✅
   └─ Tidak → 
       ├─ Cek 24-hour window?
       │   ├─ Ya → Kirim template message ✅
       │   └─ Tidak → Kirim SMS/Email dengan link opt-in 📧
       └─ Setelah user klik link → Opt-in → Kirim template message ✅
```

### Scenario 2: User Mengirim Pesan ke WhatsApp Business

```
1. User mengirim pesan ke WhatsApp Business Account
   ↓
2. Sistem otomatis:
   ├─ Remove dari blacklist (opt-in)
   ├─ Set whatsapp_opt_in = True
   └─ Catat waktu pesan terakhir
   ↓
3. Sistem bisa kirim template messages dalam 24 jam berikutnya ✅
```

### Scenario 3: Notifikasi Otomatis (Cron)

```
1. Cron job trigger (misalnya: peringatan masa berlaku)
   ↓
2. Untuk setiap permit:
   ├─ Cek opt-in status atau 24-hour window
   ├─ Jika bisa → Kirim template message ✅
   └─ Jika tidak bisa → Skip atau fallback ke SMS/Email
```

## 🔧 Implementasi Teknis

### File yang Dibuat:

1. **`whatsapp_opt_in_manager.py`**
   - `check_can_send_template()`: Cek apakah bisa kirim template
   - `request_opt_in_via_sms_or_email()`: Request opt-in via SMS/Email
   - `auto_opt_in_from_inbound_message()`: Auto opt-in dari inbound message

2. **`sicantik_permit_inherit.py`** (Modified)
   - `_kirim_notifikasi_izin_selesai()`: Sudah di-update untuk cek opt-in
   - Method lain akan di-update juga

### Cara Penggunaan:

```python
# Di method yang akan kirim notifikasi
opt_in_manager = self.env['whatsapp.opt.in.manager']
can_send_check = opt_in_manager.check_can_send_template(
    partner_id=record.partner_id.id,
    wa_account_id=template.wa_account_id.id
)

if can_send_check['can_send']:
    # Kirim template message
    composer._send_whatsapp_template(force_send_by_cron=True)
else:
    # Fallback ke SMS/Email atau skip
    _logger.warning(f"Skip: {can_send_check['reason']}")
```

## 📊 Monitoring & Analytics

### Metrics yang Perlu Di-track:

1. **Opt-in Rate**: Berapa % user yang sudah opt-in?
2. **24-Hour Window Usage**: Berapa % notifikasi yang menggunakan 24-hour window?
3. **Fallback Rate**: Berapa % notifikasi yang fallback ke SMS/Email?
4. **Delivery Rate**: Berapa % template messages yang berhasil terkirim?

### Logging:

- Setiap notifikasi yang dikirim, log:
  - Opt-in status
  - 24-hour window status
  - Delivery status
  - Error jika ada

## 🚀 Best Practices

1. **Proaktif Request Opt-In**
   - Saat user mendaftar, minta consent untuk WhatsApp notifications
   - Berikan benefit jelas (notifikasi real-time, link download, dll)

2. **Leverage 24-Hour Window**
   - Setelah user mengirim pesan, manfaatkan 24-hour window untuk kirim notifikasi penting
   - Contoh: Setelah user tanya status izin, kirim notifikasi update status

3. **Fallback Strategy**
   - Jangan skip notifikasi penting jika user belum opt-in
   - Gunakan SMS/Email sebagai fallback
   - SMS/Email berisi link untuk opt-in WhatsApp

4. **Pre-Approval untuk Nomor Terdaftar**
   - Untuk nomor yang sudah terdaftar di sistem, request pre-approval di Meta Business Manager
   - Ini akan mempermudah proses opt-in untuk user existing

5. **Monitoring & Optimization**
   - Track opt-in rate dan delivery rate
   - Optimize berdasarkan data
   - A/B test untuk opt-in messages

## ⚠️ Catatan Penting

1. **24-Hour Window**: Hanya berlaku untuk template messages, bukan interactive messages
2. **Opt-Out**: User bisa opt-out kapan saja dengan kirim pesan "STOP"
3. **Blacklist**: Nomor yang opt-out akan masuk blacklist dan tidak bisa dikirimi template messages
4. **Compliance**: Pastikan mematuhi regulasi data privacy (GDPR, dll)

## 📝 TODO

- [ ] Implementasi opt-in checkbox di form pendaftaran
- [ ] Implementasi SMS/Email fallback dengan link opt-in
- [ ] Buat endpoint untuk opt-in via link
- [ ] Export dan upload nomor terdaftar ke Meta Business Manager
- [ ] Dashboard untuk monitoring opt-in rate dan delivery rate
- [ ] A/B test untuk opt-in messages

