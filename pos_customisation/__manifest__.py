# -*- coding: utf-8 -*-
{
    'name': 'POS Customisation - Saudi Simplified Tax Invoice Receipt',
    'version': '19.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Customized POS receipt print matching Saudi Simplified Tax Invoice specifications',
    'description': """
POS Customisation: Saudi Simplified Tax Invoice Receipt
=======================================================
- Custom header with Arabic/English company details & simplified tax invoice title.
- Order details box (Invoice number, Issue date & time, Date of supply).
- 4-column product table (Nature of goods/services, Unit price, Quantity, Item Subtotal Inc. VAT).
- Dual language totals table (Taxable amount excl. VAT, Discounts, Total VAT 15%, Total amount due).
- Amount in words (SAR / Halala).
- Total item count, Payment method, Paid status, and Balance.
- Large bottom ZATCA QR code.
- Footer with Cashier name, Invoice number, Print Date, and Barcode.
    """,
    'author': 'Analytix',
    'license': 'LGPL-3',
    'depends': [
        'point_of_sale',
        'l10n_sa_pos',
        'l10n_gcc_pos',
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
