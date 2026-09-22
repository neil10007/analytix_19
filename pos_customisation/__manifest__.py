# -*- coding: utf-8 -*-
{
    'name': 'POS Customisation - Manage Receipt QR Codes',
    'version': '19.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Control and customize QR codes on Point of Sale receipts (hide top header QR code)',
    'description': """
POS Customisation: Receipt QR Codes Management
==============================================
This module allows users to configure the display of QR codes on POS receipts:
- Option to hide or show the QR code displayed right below the company logo.
- Clean configuration setting in Point of Sale -> Settings.
    """,
    'author': 'Analytix',
    'license': 'LGPL-3',
    'depends': [
        'point_of_sale',
        'l10n_sa_pos',
    ],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_customisation/static/src/**/*',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
