# -*- coding: utf-8 -*-
{
    'name': 'New Login Form',
    'version': '19.0.1.0.0',
    'summary': 'Custom split-screen login page for Odoo 19',
    'description': 'Replaces the default Odoo 19 login page with a premium split-screen design.',
    'category': 'Web',
    'author': 'Custom',
    'depends': ['web', 'auth_signup'],
    'data': [
        'views/login_template.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'new_login_form/static/src/css/login.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
