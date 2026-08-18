# -*- coding: utf-8 -*-
from odoo import models, api, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    groq_api_key = fields.Char(string='Groq API Key')
    open_router_key = fields.Char(string='OpenRouter API Key')
    openrouter_model = fields.Char(string='OpenRouter Model', help="Custom OpenRouter AI model ID. If empty, falls back to backend default.")
    chatting_model = fields.Char(string='Chatting Model', help="Custom OpenRouter model ID for Chatting AI.")
    chatting_system_prompt = fields.Text(string='Chatting System Prompt', help="Custom system prompt to guide AI response logic for chat interaction.")


    @api.model_create_multi
    def create(self, vals_list):
        users = super(ResUsers, self).create(vals_list)
        dashboard_action = self.env.ref('analytix_finance_dashboard.action_analytix_finance_dashboard', raise_if_not_found=False)
        if dashboard_action:
            for user in users:
                if not user.share and not user.action_id:
                    user.sudo().write({'action_id': dashboard_action.id})
        return users
