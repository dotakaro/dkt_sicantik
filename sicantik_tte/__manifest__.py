# -*- coding: utf-8 -*-
{
    'name': 'SICANTIK TTE - Digital Signature',
    'version': '1.0.0',
    'category': 'Document Management',
    'summary': 'Digital signature dengan TTE BSRE dan QR Code verification',
    'description': """
SICANTIK TTE Module
===================

Modul untuk tanda tangan elektronik (TTE) menggunakan BSRE Indonesia dan QR Code verification.

Fitur Utama:
------------
* Upload PDF dokumen izin oleh admin
* Integrasi dengan MinIO untuk storage aman
* Tanda tangan elektronik via BSRE API
* Generate QR Code untuk verifikasi
* Embed QR Code ke dalam PDF
* Audit trail lengkap
* Workflow approval

Technical:
----------
* MinIO S3-compatible storage
* BSRE API integration
* QR Code generation (qrcode library)
* PDF manipulation (PyPDF2, reportlab)
* Signature verification
    """,
    'author': 'Dota Karo Teknologi',
    'website': 'https://dotakaro.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'sicantik_connector',  # Depend on Phase 1 module
    ],
    'external_dependencies': {
        'python': [
            'boto3',        # MinIO S3 client
            'qrcode',       # QR code generation
            'PyPDF2',       # PDF manipulation
            'reportlab',    # PDF generation
            'Pillow',       # Image processing for QR
        ],
    },
    'data': [
        # Security
        'security/ir.model.access.csv',
        
        # Data
        'data/document_sequence.xml',
        'data/bsre_config_data.xml',  # Default BSRE configuration
        
        # Views - signature_workflow_views.xml HARUS di-load SEBELUM sicantik_document_views.xml
        # karena sicantik_document_views.xml mereferensikan action_signature_workflow
        'views/signature_workflow_views.xml',
        'views/bsre_config_views.xml',
        'views/sicantik_document_views.xml',
        'views/sicantik_tte_menus.xml',
        
        # Templates (Public pages)
        'views/templates/verification_templates.xml',
        
        # Wizards
        'wizard/document_upload_wizard_views.xml',
        'wizard/batch_sign_wizard_views.xml',
        'wizard/sign_passphrase_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sicantik_tte/static/src/js/document_upload.js',
            'sicantik_tte/static/src/css/tte_styles.css',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}

