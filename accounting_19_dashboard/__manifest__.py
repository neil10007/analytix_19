# -*- coding: utf-8 -*-
{
    'name': 'Accounting Custom Dashboard',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'A stylish, comprehensive custom dashboard for the Accounting module',
    'description': """
        This module adds a beautiful custom dashboard inside the Accounting module,
        showing key financial KPIs, charts, and summaries.
    """,
    'author': 'Custom',
    'depends': ['account', 'base'],
    'data': [
        'security/ir.model.access.csv',
        'views/dashboard_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'accounting_19_dashboard/static/src/css/dashboard.css',
            'accounting_19_dashboard/static/src/js/dashboard.js',
            'accounting_19_dashboard/static/src/xml/dashboard_template.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
