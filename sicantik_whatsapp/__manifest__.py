# -*- coding: utf-8 -*-

{
    'name': 'SICANTIK WhatsApp Notifications',
    'version': '1.0.0',
    'category': 'SICANTIK',
    'summary': 'Sistem Notifikasi WhatsApp untuk SICANTIK Companion',
    'description': """
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
    """,
    'author': 'DPMPTSP Kabupaten Karo',
    'website': 'https://perizinan.karokab.go.id',
    'depends': [
        'whatsapp',  # Odoo Enterprise WhatsApp module
        'sicantik_connector',
        'sicantik_tte',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/sicantik_whatsapp_cleanup_wizard_views.xml',
        'wizard/export_phone_numbers_wizard_views.xml',
        'data/whatsapp_templates.xml',
        'data/cron_data.xml',
        # 'views/sicantik_whatsapp_menus.xml',  # Disabled - menu dapat ditambahkan manual jika diperlukan
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

