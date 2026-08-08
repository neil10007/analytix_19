{
    'name': 'Database Audit & User Logs History',
    'version': '19.0.1.0.0',
    'category': 'Administration/Audit',
    'summary': 'Track all database operations (Create, Write, Delete) by users with detailed list and form views in Settings',
    'description': """
        User Activity & Database Logs History Module for Odoo 19.
        ===========================================================
        - Tracks Create, Write/Update, and Unlink/Delete operations across all database models.
        - Records User, Timestamp, Model, Record ID/Name, Field changes, and IP Address.
        - Provides rich List, Form, and Search views.
        - Accessible directly from the Settings menu with user range filters.
        - Restricted exclusively to Super Admin (User ID 2).
    """,
    'author': 'Custom Developer',
    'website': 'https://www.odoo.com',
    'depends': ['base'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/user_logs_history_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
