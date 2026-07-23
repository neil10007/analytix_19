# -*- coding: utf-8 -*-
{
    'name': 'Access Rights Users Control',
    'version': '19.0.1.0.0',
    'category': 'Administration',
    'summary': 'Control Super Admin visibility, restrict developer mode, and manage user access tiers',
    'description': """
        This module implements a three-tier access control system:

        - **Super Admin**: Full access to everything. Visible only to other super admins.
        - **Normal Admin**: Can manage and create users, but cannot see super admin accounts
          in Settings > Users. Cannot activate Developer Mode.
        - **Users**: Standard access. Cannot see super admin accounts. Cannot activate Developer Mode.
    """,
    'author': 'Custom',
    'depends': ['base', 'base_setup', 'web'],
    'data': [
        'security/access_groups.xml',
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
        'views/res_config_settings_views.xml',
        'views/user_creation_limit_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'acces_right_users/static/src/js/hide_dev_mode.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
