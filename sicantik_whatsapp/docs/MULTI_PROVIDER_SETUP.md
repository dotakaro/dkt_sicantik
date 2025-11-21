# Setup Multi-Provider WhatsApp

Panduan konfigurasi untuk menggunakan berbagai provider WhatsApp (Meta, Watzap.id, Fonnte) dalam sistem SICANTIK.

## Overview

Sistem SICANTIK mendukung 3 provider WhatsApp:
1. **Meta (WhatsApp Official)** - Via modul Odoo Enterprise, memerlukan opt-in
2. **Watzap.id** - Gateway Indonesia, tidak memerlukan opt-in ketat
3. **Fonnte** - Gateway alternatif

## Strategi Hybrid

### Routing Logic
- **Partner sudah opt-in Meta** → gunakan Meta (lebih cepat, gratis dalam limit)
- **Partner belum opt-in** → gunakan provider gateway (Watzap/Fonnte) + sisipkan link opt-in
- **Fallback otomatis** jika provider utama gagal

### Keuntungan
- Compliance dengan kebijakan Meta untuk partner yang mau opt-in
- Tetap bisa kirim notifikasi ke partner lama yang belum opt-in
- Cost-effective (Meta gratis dalam conversation limit)

## Setup Langkah demi Langkah

### 1. Konfigurasi Provider

#### A. Meta Official (Optional - jika ingin opt-in)

1. Buka **WhatsApp → Konfigurasi → Profil Provider**
2. Buat provider baru dengan tipe `Meta`
3. Pilih **Meta Account** dari dropdown (akun yang sudah connected di Odoo)
4. Set namespace (biasanya business namespace Anda)
5. Klik **Mark as Configured**

#### B. Watzap.id (Recommended untuk fallback)

**Prasyarat:**
- Daftar di [https://app.watzap.id](https://app.watzap.id)
- Dapatkan API Key dan Device ID dari dashboard

**Setup di Odoo:**
1. Buka **WhatsApp → Konfigurasi → Profil Provider**
2. Buat provider baru dengan tipe `Watzap.id`
3. Isi field:
   - **API Key**: dari dashboard Watzap
   - **Device ID**: dari dashboard Watzap
   - **Base URL**: `https://api.watzap.id/v1` (default)
4. Klik **Mark as Configured**

#### C. Fonnte (Optional - provider alternatif)

**Prasyarat:**
- Daftar di [https://fonnte.com](https://fonnte.com)
- Dapatkan API Token dari dashboard

**Setup di Odoo:**
1. Buka **WhatsApp → Konfigurasi → Profil Provider**
2. Buat provider baru dengan tipe `Fonnte`
3. Isi field:
   - **API Token**: dari dashboard Fonnte
   - **Device**: identifier device (optional)
   - **API URL**: `https://api.fonnte.com` (default)
4. Klik **Mark as Configured**

### 2. Set Default Provider

1. Buka **Settings → General Settings**
2. Scroll ke section **WhatsApp Notifications**
3. Pilih **Default Provider** (biasanya Meta jika ada, atau Watzap.id sebagai fallback)
4. Klik **Save**

### 3. Konfigurasi Master Templates

Master template adalah template yang kompatibel dengan semua provider.

#### Cara Setup:

1. Buka **WhatsApp → Konfigurasi → Master Templates**
2. Untuk setiap template default, lakukan konfigurasi per provider:

**Untuk Meta:**
- Set **Meta Template Name** (e.g., `izin_selesai_diproses`)
- Klik **Sync from Meta** (akan auto-detect template dari WhatsApp Account)
- Atau pilih manual dari dropdown **Meta Template**

**Untuk Watzap.id:**
- Buat template di [dashboard Watzap.id](https://app.watzap.id)
- Copy **Template ID** dan paste ke field **Watzap Template ID**
- Set **Watzap Status** menjadi `Configured`

**Untuk Fonnte:**
- Buat template di [dashboard Fonnte](https://fonnte.com)
- Copy **Template ID** dan paste ke field **Fonnte Template ID**
- Set **Fonnte Status** menjadi `Configured`

### 4. Template Parameter Mapping

Parameter di master template menggunakan nama generik (e.g., `partner_name`, `permit_number`).
Sistem akan otomatis konversi ke format masing-masing provider:

**Format Generik:**
```
{{partner_name}}, izin {{permit_number}} Anda dengan status {{status}}
```

**Konversi otomatis ke:**
- **Meta**: `{{1}}`, `{{2}}`, `{{3}}` (indexed)
- **Watzap**: `{"1": "value1", "2": "value2", "3": "value3"}`
- **Fonnte**: `{"var1": "value1", "var2": "value2", "var3": "value3"}`

**Parameter List:**
Setiap master template memiliki field `parameter_list` dalam format JSON array:
```json
["partner_name", "permit_number", "status"]
```

Urutan parameter ini akan menentukan mapping ke {{1}}, {{2}}, {{3}} dst.

## Testing

### Test Provider Connection

1. Buka provider profile
2. Klik tombol **Test Connection** (akan ditambahkan di update berikutnya)

### Test Template Sending

1. Buka record Permit
2. Klik **Test Notification**
3. Sistem akan otomatis memilih provider yang tepat
4. Log akan mencatat provider mana yang digunakan

## Opt-In Flow

### Auto Opt-In (Meta)
- Partner yang kirim pesan inbound ke WhatsApp Business Account → auto opt-in
- Webhook Meta akan trigger opt-in otomatis

### Manual Opt-In Request (via Watzap/Fonnte)
- Partner lama yang belum opt-in akan receive message via Watzap/Fonnte
- Message include link opt-in atau QR code
- Setelah opt-in, sistem switch ke Meta untuk message berikutnya

## Troubleshooting

### Provider tidak bisa kirim pesan

**Meta:**
- Pastikan partner sudah opt-in atau ada inbound message < 24 jam
- Cek WhatsApp Account sudah connected
- Cek template sudah approved di Meta Console

**Watzap.id:**
- Pastikan API Key valid
- Cek quota di dashboard Watzap
- Pastikan device/sender sudah active

**Fonnte:**
- Pastikan API Token valid
- Cek saldo/quota di dashboard Fonnte

### Template tidak ditemukan

- Pastikan template sudah dikonfigurasi di ketiga tab (Meta/Watzap/Fonnte)
- Set status template menjadi `Configured` atau `Approved`
- Sync template dari Meta jika menggunakan Meta

## Environment Variables (Optional)

Jika ingin set credentials via environment variables instead of UI:

```env
# .env file atau docker-compose.yml

# Watzap.id
WATZAP_API_KEY=your_api_key_here
WATZAP_DEVICE_ID=your_device_id

# Fonnte
FONNTE_TOKEN=your_token_here
FONNTE_DEVICE=your_device_id
```

Provider akan prioritize nilai dari UI, fallback ke env var jika tidak ada.

## API Documentation References

- **Meta WhatsApp Business API**: https://developers.facebook.com/docs/whatsapp
- **Watzap.id**: https://api-docs.watzap.id
- **Fonnte**: https://docs.fonnte.com

