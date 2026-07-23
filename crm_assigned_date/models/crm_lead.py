# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    assigned_date = fields.Date(
        string='Assigned Date',
        help='The date when this lead/opportunity was assigned to a salesperson.',
        tracking=True,
    )
