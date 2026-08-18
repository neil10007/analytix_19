from odoo import models, fields
from .ai_gl_config import EXPENSE_BILLS_TYPES

class AccountMove(models.Model):
    _inherit = 'account.move'

    expense_bills_type = fields.Selection(
        selection=EXPENSE_BILLS_TYPES,
        string='AI Expense Type',
        help='Expense Category detected by AI Document Processor'
    )

    partner_street = fields.Char(
        string='Street',
        related='partner_id.street',
        readonly=False,
    )
    partner_street2 = fields.Char(
        string='Street 2',
        related='partner_id.street2',
        readonly=False,
    )
    partner_city = fields.Char(
        string='City',
        related='partner_id.city',
        readonly=False,
    )
    partner_state_id = fields.Many2one(
        'res.country.state',
        string='State',
        related='partner_id.state_id',
        readonly=False,
    )
    partner_zip = fields.Char(
        string='ZIP',
        related='partner_id.zip',
        readonly=False,
    )
    partner_country_id = fields.Many2one(
        'res.country',
        string='Country',
        related='partner_id.country_id',
        readonly=False,
    )
    partner_vat = fields.Char(
        string='Tax ID',
        related='partner_id.vat',
        readonly=False,
    )

    ai_validation_status = fields.Selection([
        ('matched', 'Fully Matched'),
        ('warning', 'Mismatch / Warning Detected'),
    ], string='AI Validation Status', default='matched')

    ai_validation_notes = fields.Text(
        string='AI Validation Details & Mismatches',
        help='Summarizes inventory, tax, and total mismatches detected during AI document parsing.'
    )
