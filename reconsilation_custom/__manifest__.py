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
        'views/account_account_reconcile_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'reconsilation_custom/static/src/**/*',
        ],
    },
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
