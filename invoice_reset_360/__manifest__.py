# -*- coding: utf-8 -*-
{
    'name': 'Invoice Reset 360',
    'version': '19.0.1.1.0',
    'category': 'Accounting/Accounting',
    'summary': 'Prevent resetting posted invoices to draft when QR code is generated, with configurable user permissions and validity period',
    'description': """
Invoice Reset 360
=================
This module prevents users from resetting posted invoices or vendor bills to draft once an official QR code has been generated.

Key Features:
-------------
* Validates invoice state and QR code presence before allowing 'Reset to Draft'.
* Prevents resetting to draft if the invoice is in 'posted' state and has a generated QR code.
* Role-based permissions: Administrators can grant specific users permission to reset to draft.
* Time-based validity: Optionally configure a 'Valid From' and 'Valid Until' period for user permissions.
* Displays a clear and informative ValidationError message guiding unauthorized users to issue a Credit Note or Debit Note instead.
* Fully compatible with standard Odoo and Saudi / ZATCA e-Invoicing modules (e.g. advanced_vat_invoice, l10n_sa_edi).
    """,
    'author': 'Analytix360',
    'website': 'https://www.analytix360.com',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'advanced_vat_invoice',
    ],
    'data': [
        'security/invoice_reset_security.xml',
        'views/res_users_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
