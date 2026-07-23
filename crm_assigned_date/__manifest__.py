# -*- coding: utf-8 -*-
{
    'name': 'CRM Assigned Date',
    'version': '1.0',
    'summary': 'Adds an Assigned Date field to CRM leads/opportunities',
    'description': """
        This module adds an 'Assigned Date' field to CRM leads and opportunities.
        The field appears above the Salesperson field in the form view, and
        is also visible as a column in the list view.
    """,
    'category': 'CRM',
    'author': 'Custom',
    'depends': ['crm'],
    'data': [
        'views/crm_lead_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
