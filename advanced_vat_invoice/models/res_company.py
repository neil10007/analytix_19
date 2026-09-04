# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = 'res.company'

    company_arabic_name = fields.Char(string='Company Arabic Name')
    street1_arabic = fields.Char(string='Street 1 Arabic')
    street2_arabic = fields.Char(string='Street 2 Arabic')
    city_arabic = fields.Char(string='City Arabic')
    state_arabic = fields.Char(string='State Arabic')
    country_arabic = fields.Char(string='Country Arabic')

    bank_account_name = fields.Char(string='Account Name')
    bank_account_number = fields.Char(string='Account Number')
    bank_iban = fields.Char(string='IBAN')
    bank_name = fields.Char(string='Bank Name')
    bank_swift = fields.Char(string='SWIFT')

    is_saudi_company = fields.Boolean(
        string='Is Saudi Company',
        compute='_compute_is_saudi_company',
    )

    @api.depends('country_id')
    def _compute_is_saudi_company(self):
        for company in self:
            company.is_saudi_company = bool(company.country_id and company.country_id.code == 'SA')

    def _register_hook(self):
        """
        Runs on every server start (not just -u).
        Auto-creates missing columns in res_company so that database restores
        never cause UndefinedColumn crashes — ADD COLUMN IF NOT EXISTS is
        completely safe to run even when the column already exists.
        """
        super()._register_hook()

        # All custom columns added by this module
        columns = [
            ('company_arabic_name', 'VARCHAR'),
            ('street1_arabic',      'VARCHAR'),
            ('street2_arabic',      'VARCHAR'),
            ('city_arabic',         'VARCHAR'),
            ('state_arabic',        'VARCHAR'),
            ('country_arabic',      'VARCHAR'),
            ('bank_account_name',   'VARCHAR'),
            ('bank_account_number', 'VARCHAR'),
            ('bank_iban',           'VARCHAR'),
            ('bank_name',           'VARCHAR'),
            ('bank_swift',          'VARCHAR'),
        ]

        for col_name, col_type in columns:
            try:
                self.env.cr.execute(
                    f"ALTER TABLE res_company ADD COLUMN IF NOT EXISTS {col_name} {col_type};"
                )
                _logger.debug(
                    "advanced_vat_invoice: ensured column res_company.%s exists.", col_name
                )
            except Exception as e:
                _logger.warning(
                    "advanced_vat_invoice: could not ensure column res_company.%s — %s",
                    col_name, e
                )
