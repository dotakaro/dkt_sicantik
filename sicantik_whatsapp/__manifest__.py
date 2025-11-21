# -*- coding: utf-8 -*-

{
    "name": "SICANTIK WhatsApp Notifications",
    "version": "1.0.0",
    "category": "SICANTIK",
    "summary": "Sistem Notifikasi WhatsApp untuk SICANTIK Companion",
    "description": """
SICANTIK WhatsApp Notifications
================================

Modul ini mengintegrasikan sistem notifikasi WhatsApp untuk SICANTIK Companion App.

Fitur Utama:
------------
* Notifikasi otomatis ke pemohon izin
* Notifikasi ke staff DPMPTSP untuk dokumen baru
* Notifikasi approval ke pejabat berwenang
* Peringatan masa berlaku izin (90/60/30/7 hari sebelum expired)
* Notifikasi perpanjangan izin disetujui
* Reminder dokumen pending
* Update status perizinan

Menggunakan modul WhatsApp Enterprise Odoo untuk integrasi dengan Meta Cloud API.

Kepatuhan WhatsApp Business:
----------------------------
* Manajemen Opt-In sesuai kebijakan Meta
* 24-hour window untuk pesan respons
* Export nomor untuk pre-approval Meta
* Tracking status pengiriman pesan
    """,
    "author": "DPMPTSP Kabupaten Karo",
    "website": "https://perizinan.karokab.go.id",
    "depends": [
        "whatsapp",  # Odoo Enterprise WhatsApp module
        "sicantik_connector",
        "sicantik_tte",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/sicantik_whatsapp_provider_views.xml",
        "views/whatsapp_template_master_views.xml",  # Master templates
        "views/res_config_settings_views.xml",
        "wizard/sicantik_whatsapp_cleanup_wizard_views.xml",
        "wizard/export_phone_numbers_wizard_views.xml",
        "wizard/test_multi_provider_wizard_views.xml",  # Must load before menus
        "views/sicantik_whatsapp_menus.xml",  # Menu untuk WhatsApp
        "data/master_templates_data.xml",  # Default master templates
        "data/whatsapp_templates.xml",
        "data/cron_data.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
    "images": [
        "static/description/main.png",
    ],
}
