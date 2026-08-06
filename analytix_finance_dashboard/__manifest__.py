{
    'name': 'Analytix 360 Finance Dashboard',
    'version': '1.4',
    'category': 'Accounting/Accounting',
    'summary': 'All in all dashboard for financial overview',
    'description': """
        Analytix 360 Finance Dashboard.
        Provides a comprehensive overview of the company's financial situation.
    """,
    'depends': ['account', 'web', 'l10n_sa', 'mail', 'proforma_invoice'],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'views/dashboard_action.xml',
        'views/finance_alert_views.xml',
        'views/menu_views.xml',
        'views/set_home_action.xml',
        'views/account_move_views.xml',
        # 'views/report_invoice.xml',
        # 'views/report_vat_invoice.xml',
        'views/zatca_settings.xml',
        'views/groq_settings_views.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'analytix_finance_dashboard/static/src/components/**/*',
        ],
        'web.report_assets_common': [
            'analytix_finance_dashboard/static/src/css/report_style.css',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'post_migrate_hook': 'post_migrate_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
