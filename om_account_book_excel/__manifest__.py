# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Cash Book Excel, Day Book Excel, Bank Book Excel Reports',
    'version': '1.0',
    'category': 'Invoicing Management',
    'summary': 'Cash Book Excel, Day Book Excel and Bank Book Excel Report For Odoo 19',
    'description': 'Cash Book Excel, Day Book Excel and Bank Book Excel Report For Odoo 19',
    'sequence': '10',
    'author': 'Odoo Mates',
    'license': 'OPL-1',
    'company': 'Odoo Mates',
    'maintainer': 'Odoo Mates',
    'price': 10,
    'currency': 'USD',
    'support': 'odoomates@gmail.com',
    'website': 'https://www.odoomates.tech',
    'depends': ['om_account_daily_reports'],
    'live_test_url': '',
    'demo': [],
    'data': [
        'wizard/daybook_view.xml',
        'wizard/cashbook_view.xml',
        'wizard/bankbook_view.xml',
        'report/reports.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'live_test_url': 'https://www.youtube.com/watch?v=9HKGCCSyhp4',
    'images': ['static/description/banner.gif'],
}
