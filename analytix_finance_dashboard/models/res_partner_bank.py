# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    iban = fields.Char(string='IBAN')
    swift_code = fields.Char(string='SWIFT Code')

    is_saudi_company = fields.Boolean(
        string='Is Saudi Company',
        compute='_compute_is_saudi_company',
    )

    @api.depends('company_id', 'company_id.country_id')
    def _compute_is_saudi_company(self):
        for bank in self:
            comp = bank.company_id or self.env.company
            bank.is_saudi_company = bool(comp and comp.country_id and comp.country_id.code == 'SA')
