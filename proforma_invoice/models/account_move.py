from odoo import models, fields

class AccountMove(models.Model):
    _inherit = 'account.move'

    proforma_id = fields.Many2one('sale.order.proforma', string="Proforma Reference", copy=False)
