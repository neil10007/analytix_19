# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    company_arabic_name = fields.Char(string='Company Arabic Name')
    street1_arabic = fields.Char(string='Street 1 Arabic')
    street2_arabic = fields.Char(string='Street 2 Arabic')
    city_arabic = fields.Char(string='City Arabic')
    state_arabic = fields.Char(string='State Arabic')
    country_arabic = fields.Char(string='Country Arabic')

    is_saudi_company = fields.Boolean(
        string='Is Saudi Company',
        compute='_compute_is_saudi_company',
    )

    @api.depends('country_id')
    def _compute_is_saudi_company(self):
        for company in self:
            company.is_saudi_company = bool(company.country_id and company.country_id.code == 'SA')
