# Changelog: Multi-Provider WhatsApp Integration

## Versi 2.0.0 - Multi-Provider Support

### ✨ Features Baru

#### 1. **Multi-Provider Architecture**
- Dukungan untuk 3 provider WhatsApp:
  - **Meta** (WhatsApp Official via Odoo Enterprise)
  - **Watzap.id** (Gateway Indonesia)
  - **Fonnte** (Gateway alternatif)
- Routing otomatis berdasarkan opt-in status
- Fallback otomatis jika provider utama tidak tersedia

#### 2. **Model Baru**

**`sicantik.whatsapp.provider`**
- Menyimpan profil & credential masing-masing provider
- Field spesifik per provider (Meta account, Watzap API key, Fonnte token)
- Status tracking (draft, configured, error)

**`sicantik.whatsapp.template.master`**
- Template universal yang kompatibel dengan semua provider
- Mapping ke template ID per provider
- Parameter generik dengan placeholder bernama
- Tracking usage & statistics

**`sicantik.whatsapp.dispatcher` (Service)**
- Routing logic untuk pemilihan provider otomatis
- Parameter conversion ke format provider
- Error handling & fallback

#### 3. **Template Compatibility Layer**

**Parameter Converter:**
- Format generik: `{{partner_name}}`, `{{permit_number}}`, dsb
- Auto-convert ke format Meta: `{{1}}`, `{{2}}`, `{{3}}`
- Auto-convert ke format Watzap: `{"1": "value1", "2": "value2"}`
- Auto-convert ke format Fonnte: `{"var1": "value1", "var2": "value2"}`

**Default Templates:**
- `permit_ready` - Izin Selesai Diproses
- `permit_reminder` - Peringatan Masa Berlaku
- `status_update` - Update Status Perizinan
- `renewal_approved` - Perpanjangan Disetujui
- `meta_opt_in_request` - Request Meta Opt-In

#### 4. **Provider Implementation**

**Watzap.id Provider:**
- HTTP API client untuk `https://api.watzap.id/v1`
- Send template & text message
- Status checking
- Phone normalization

**Fonnte Provider:**
- HTTP API client untuk `https://api.fonnte.com`
- Send template & text message
- Phone normalization

#### 5. **Testing Tools**

**Test Multi-Provider Wizard:**
- Testing manual routing & pengiriman
- Force provider atau auto-select
- Mock data untuk testing
- Result display dengan detail

#### 6. **Configuration Integration**

**Settings:**
- Menu Settings → General Settings → WhatsApp Notifications
- Pilih default provider via dropdown

**Provider Management:**
- Menu WhatsApp → Konfigurasi → Profil Provider
- Form per provider dengan tab credential
- Mark as configured/error

**Template Management:**
- Menu WhatsApp → Konfigurasi → Master Templates
- Sync from Meta button
- Manual configuration untuk Watzap/Fonnte

### 🎯 Routing Strategy

```
┌─────────────────────────────────────┐
│  Perlu kirim notifikasi WhatsApp   │
└──────────────┬──────────────────────┘
               │
               ▼
      ┌────────────────────┐
      │ Check Default      │
      │ Provider dari      │
      │ Settings           │
      └────────┬───────────┘
               │
               ├─────────► Meta?
               │              │
               │              ▼
               │       ┌──────────────┐
               │       │ Check Opt-In │
               │       │ Status       │
               │       └──────┬───────┘
               │              │
               │              ├─────► Opt-In? ──► Kirim via Meta
               │              │
               │              └─────► Belum? ──┐
               │                                │
               ├─────────► Watzap/Fonnte? ─────┤
               │                                │
               └────────────────────────────────┘
                                                │
                                                ▼
                                    ┌────────────────────────┐
                                    │ Kirim via              │
                                    │ Watzap/Fonnte          │
                                    │ + Link Opt-In Meta     │
                                    └────────────────────────┘
```

### 📋 Migration Path

**Existing System (Meta only):**
- Semua message via Meta
- Partner harus opt-in dulu

**New System (Hybrid):**
- Partner lama: receive via Watzap/Fonnte (tanpa opt-in)
- Partner baru: auto-route sesuai opt-in
- Gradual migration: partner lama bisa opt-in via link di message

### 🔧 Technical Details

**File Structure:**
```
addons_odoo/sicantik_whatsapp/
├── models/
│   ├── whatsapp_provider.py           # Provider profiles
│   ├── whatsapp_template_master.py    # Master templates
│   ├── whatsapp_dispatcher.py         # Routing service
│   └── res_config_settings.py         # Settings integration
├── tools/
│   ├── parameter_converter.py         # Parameter formatting
│   ├── watzap_provider.py             # Watzap.id client
│   └── fonnte_provider.py             # Fonnte client
├── views/
│   ├── sicantik_whatsapp_provider_views.xml
│   ├── whatsapp_template_master_views.xml
│   └── res_config_settings_views.xml
├── wizard/
│   └── test_multi_provider_wizard.py  # Testing tool
├── data/
│   └── master_templates_data.xml      # Default templates
└── docs/
    └── MULTI_PROVIDER_SETUP.md        # Setup guide
```

**Database Schema:**
- `sicantik_whatsapp_provider` - Provider credentials
- `sicantik_whatsapp_template_master` - Universal templates
- `ir_config_parameter` - Default provider config

### 🚀 Next Steps

1. **Registrasi Provider:**
   - Daftar di Watzap.id: https://app.watzap.id
   - Daftar di Fonnte: https://fonnte.com
   - Dapatkan API credentials

2. **Konfigurasi di Odoo:**
   - Buat profil provider di menu **WhatsApp → Profil Provider**
   - Set default provider di **Settings → General Settings**
   - Konfigurasi master templates

3. **Testing:**
   - Buka **WhatsApp → Pantauan & Laporan → 🧪 Test Multi-Provider**
   - Pilih partner dengan nomor HP
   - Run test untuk verify routing & pengiriman

4. **Production:**
   - Monitor logs untuk routing decisions
   - Track opt-in conversion rate
   - Optimize provider selection based on cost/reliability

### 📊 Benefits

**Compliance:**
- ✅ Meta policy compliant (opt-in required)
- ✅ Tetap bisa kirim ke partner lama

**Cost Optimization:**
- ✅ Meta gratis dalam conversation limit
- ✅ Gateway untuk volume tinggi

**Reliability:**
- ✅ Fallback otomatis
- ✅ Multiple provider untuk redundancy

**User Experience:**
- ✅ Seamless untuk end-user
- ✅ Gradual migration tanpa disruption

---

## Breaking Changes

### ⚠️ Perubahan dari v1.x

**Tidak ada breaking changes.**

Modul tetap kompatibel dengan setup existing. Provider Meta tetap berfungsi seperti sebelumnya. Fitur multi-provider bersifat opt-in.

### Migration Notes

- Existing templates Meta tetap bisa digunakan
- Cukup set default provider di Settings (default ke Meta jika tidak di-set)
- Tidak perlu migrasi data

---

## Support

Untuk pertanyaan teknis atau issue, hubungi:
- Email: support@dpmptsp.karokab.go.id
- Phone: 0628-20XXX

Dokumentasi lengkap: `docs/MULTI_PROVIDER_SETUP.md`

