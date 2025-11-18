# -*- coding: utf-8 -*-
{
    'name': 'SICANTIK Connector',
    'version': '1.0.0',
    'category': 'Integration',
    'summary': 'Integration with SICANTIK Perizinan System',
    'description': """
SICANTIK Connector Module
==========================

This module provides integration with SICANTIK (Sistem Informasi Perizinan Kabupaten Karo).

Features:
---------
* API Integration with production SICANTIK server
* Automated data synchronization
* Permit management and tracking
* Expiry date monitoring (with workaround solution)
* Dashboard and statistics
* Logging and error handling

Technical Details:
------------------
* Base URL: https://perizinan.karokab.go.id/backoffice/api/
* Polling interval: Configurable (default: 15 minutes)
* Expiry sync: Daily at 02:00 AM (workaround solution)
* Rate limiting: 10 requests/second

Note:
-----
Expiry date sync currently uses a workaround solution (two-step API process).
This will be optimized after API update (100x performance improvement).

Author: SICANTIK Development Team
License: LGPL-3
    """,
    'author': 'SICANTIK Development Team',
    'website': 'https://perizinan.karokab.go.id',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        
        # Data
        'data/sicantik_config_data.xml',
        'data/minio_config_data.xml',
        'data/cron_data.xml',
        
        # Views
        'views/sicantik_config_views.xml',
        'views/sicantik_permit_views.xml',
        'views/sicantik_permit_type_views.xml',
        'views/minio_connector_views.xml',
        'views/sicantik_menus.xml',
        
        # Wizards
        'wizard/sicantik_expiry_sync_wizard_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/icon.png'],
}

