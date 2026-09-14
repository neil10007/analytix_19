# -*- coding: utf-8 -*-
{
    'name': 'Reconciliation Custom',
    'version': '19.0.1.0.0',
    'summary': 'Custom Reconciliation Menu - Transactions under Finance Entries',
    'author': 'Custom',
    'category': 'Accounting/Accounting',
    'depends': [
        'account',
        'account_reconcile_oca',
    ],
    'data': [
        'views/account_reconcile_menu.xml',
    ],
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
