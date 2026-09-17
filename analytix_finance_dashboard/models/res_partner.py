# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    mother_lang = fields.Char(string='Arabic Name')
    building_no = fields.Char(string='Building No', size=10, help='4-digit Saudi Building Number')
    additional_no = fields.Char(string='Additional No', size=10, help='4-digit Saudi Secondary Number')
    district = fields.Char(string='District', help='Neighborhood or District in KSA')
    street_ar = fields.Char(string='Arabic Street', help='Street address in Arabic')
    city_ar = fields.Char(string='Arabic City', help='City name in Arabic')
    state_ar = fields.Char(string='Arabic State', help='State/Region name in Arabic')

    show_arabic_address = fields.Boolean(
        string='Show Arabic Address',
        compute='_compute_show_arabic_address',
    )

    @api.depends_context('allowed_company_ids')
    def _compute_show_arabic_address(self):
        """
        Show the KSA Arabic address block ONLY when the user's currently
        active company has country = Saudi Arabia.
        Uses depends_context('allowed_company_ids') so it recomputes
        automatically when the user switches companies in multi-company mode.
        """
        is_ksa = self.env.company.country_id.code == 'SA'
        for partner in self:
            partner.show_arabic_address = is_ksa
