# -*- coding: utf-8 -*-
{
    'name': 'Analytix360 Email Templates',
    'version': '19.0.1.0.0',
    'summary': 'Customizes auth_signup email templates to use Analytix360 branding',
    'description': """
        Overrides the default Odoo invitation and signup email templates
        from auth_signup to use the Analytix360 brand name instead of Odoo.

        Templates customized:
        - New Internal User Invite (set_password_email)
        - Unregistered User Reminder (mail_template_data_unregistered_users)
        - New Portal Sign Up (mail_template_user_signup_account_created)
        - New Portal User Invite (portal_set_password_email)
    """,
    'category': 'Technical',
    'author': 'Analytix360',
    'website': 'https://www.analytix360.com',
    'depends': [
        'auth_signup',
        'mail',
        'base',
        'account',
        'advanced_vat_invoice',
        'account_dynamic_reports',
    ],
    'data': [
        'data/mail_template_data.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
