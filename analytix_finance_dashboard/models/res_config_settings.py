# -*- coding: utf-8 -*-
from odoo import models, fields
from .res_users import OPENROUTER_MODEL_SELECTION


class ResCompany(models.Model):
    """Stores the per-company ZATCA dashboard alert toggle and master AI config."""
    _inherit = 'res.company'

    analytix_zatca_enabled = fields.Boolean(
        string='Show ZATCA VAT Return Alert',
        default=False,
        help="When enabled, the Analytix 360 Finance Dashboard will display "
             "a ZATCA VAT return deadline alert in the Alerts section.",
    )
    groq_api_key = fields.Char(string='Groq API Key')
    open_router_key = fields.Char(string='OpenRouter API Key')
    openrouter_model = fields.Selection(
        selection=OPENROUTER_MODEL_SELECTION,
        string='OpenRouter Model',
        default='google/gemini-2.5-flash',
        help="Select OpenRouter AI model for OCR extraction. Defaults to Google Gemini 2.5 Flash.",
    )

    def get_effective_openrouter_model(self):
        """Return effective OpenRouter model string for this company."""
        self.ensure_one()
        return self.openrouter_model or 'google/gemini-2.5-flash'


class ResConfigSettings(models.TransientModel):
    """Exposes the ZATCA toggle and AI config in Accounting → Configuration → Settings."""
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
    openrouter_model = fields.Selection(
        related='company_id.openrouter_model',
        readonly=False,
        string='OpenRouter Model',
    )

