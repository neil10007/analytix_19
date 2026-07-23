{
    'name': "Proforma Invoice",
    'summary': "Create and manage proforma invoices linked to sale orders",
    'description': """
        Allows creating proforma invoices (PI) from sale orders,
        with an approval workflow and PDF report generation.
    """,
    'author': "My Company",
    'website': "https://www.yourcompany.com",
    'category': 'Sales/Sales',
    'version': '19.0.1.0.0',
    'application': True,
    'installable': True,
    'license': 'LGPL-3',

    'depends': [
        'base',
        'sale',
        'account',
        'sale_management',
        'analytic',
        'uom',
    ],

    'data': [
        'security/proforma_security.xml',
        'security/ir.model.access.csv',
        'report/accounts_performa_invoice_template.xml',
        'views/sale_order_proforma.xml',
    ],
}
