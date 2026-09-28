# -*- coding: utf-8 -*-
from odoo import models, api, fields

OPENROUTER_MODEL_SELECTION = [
    ('google/gemini-2.5-flash', 'Google: Gemini 2.5 Flash (Recommended - Fast & Accurate)'),
    ('google/gemini-2.5-pro', 'Google: Gemini 2.5 Pro (Advanced Reasoning)'),
    ('google/gemini-2.0-flash-001', 'Google: Gemini 2.0 Flash'),
    ('openai/gpt-4o', 'OpenAI: GPT-4o'),
    ('openai/gpt-4o-mini', 'OpenAI: GPT-4o Mini'),
    ('anthropic/claude-3.5-sonnet', 'Anthropic: Claude 3.5 Sonnet'),
    ('meta-llama/llama-3.2-11b-vision-instruct', 'Meta: Llama 3.2 11B Vision'),
    ('qwen/qwen-2.5-vl-72b-instruct', 'Qwen: Qwen 2.5 VL 72B'),
    ('custom', 'Custom Model ID (Enter below)'),
]


class ResUsers(models.Model):
    _inherit = 'res.users'

    groq_api_key = fields.Char(string='Groq API Key')
    open_router_key = fields.Char(string='OpenRouter API Key')
    openrouter_model = fields.Selection(
        selection=OPENROUTER_MODEL_SELECTION,
        string='OpenRouter Model',
        default='google/gemini-2.5-flash',
        help="Select OpenRouter AI model for OCR extraction. Defaults to Google Gemini 2.5 Flash.",
    )
    chatting_model = fields.Char(string='Chatting Model', help="Custom OpenRouter model ID for Chatting AI.")
    chatting_system_prompt = fields.Text(string='Chatting System Prompt', help="Custom system prompt to guide AI response logic for chat interaction.")

    is_super_admin_user = fields.Boolean(
        string="Is Super Admin User",
        compute="_compute_is_super_admin_user",
        store=False,
    )

    @api.depends_context('uid')
    def _compute_is_super_admin_user(self):
        admin_ref = self.env.ref('base.user_admin', raise_if_not_found=False)
        for user in self:
            is_sa = False
            if user.has_group('analytix_finance_dashboard.group_groq_super_admin'):
                is_sa = True
            elif admin_ref and user.id == admin_ref.id:
                is_sa = True
            elif user.id == 2:
                is_sa = True
            user.is_super_admin_user = is_sa

    def get_effective_openrouter_model(self):
        """Return the effective OpenRouter model string for this user."""
        self.ensure_one()
        return self.openrouter_model or 'google/gemini-2.5-flash'

    def write(self, vals):
        res = super(ResUsers, self).write(vals)
        for user in self:
            if user.is_super_admin_user:
                param = self.env['ir.config_parameter'].sudo()
                if 'open_router_key' in vals or (user.open_router_key and not param.get_param('analytix.open_router_key')):
                    val_key = (user.open_router_key or '').strip()
                    if val_key:
                        param.set_param('analytix.open_router_key', val_key)
                if 'openrouter_model' in vals or not param.get_param('analytix.openrouter_model'):
                    eff_model = user.get_effective_openrouter_model()
                    if eff_model:
                        param.set_param('analytix.openrouter_model', eff_model)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        users = super(ResUsers, self).create(vals_list)
        dashboard_action = self.env.ref('analytix_finance_dashboard.action_analytix_finance_dashboard', raise_if_not_found=False)
        if dashboard_action:
            for user in users:
                if not user.share and not user.action_id:
                    user.sudo().write({'action_id': dashboard_action.id})
        return users
