# -*- coding: utf-8 -*-
from odoo import models, fields


class ResCompany(models.Model):
    """Stores the per-company ZATCA dashboard alert toggle."""
    _inherit = 'res.company'

    analytix_zatca_enabled = fields.Boolean(
        string='Show ZATCA VAT Return Alert',
        default=False,
        help="When enabled, the Analytix 360 Finance Dashboard will display "
             "a ZATCA VAT return deadline alert in the Alerts section.",
    )
    groq_api_key = fields.Char(string='Groq API Key')
    open_router_key = fields.Char(string='OpenRouter API Key')


class ResConfigSettings(models.TransientModel):
    """Exposes the ZATCA toggle in Accounting → Configuration → Settings."""
    _inherit = 'res.config.settings'

    analytix_zatca_enabled = fields.Boolean(
        related='company_id.analytix_zatca_enabled',
        readonly=False,
        string='ZATCA VAT Return',
        help="Show ZATCA VAT return deadline alerts on the Analytix 360 Finance Dashboard.",
    )
    groq_api_key = fields.Char(
        related='company_id.groq_api_key',
        readonly=False,
        string='Groq API Key',
    )
    open_router_key = fields.Char(
        related='company_id.open_router_key',
        readonly=False,
        string='OpenRouter API Key',
    )

