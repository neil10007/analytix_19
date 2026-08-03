# -*- coding: utf-8 -*-
from odoo import models, fields

class AccountMove(models.Model):
    _inherit = 'account.move'

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
