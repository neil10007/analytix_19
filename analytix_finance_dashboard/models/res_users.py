# -*- coding: utf-8 -*-
from odoo import models, api, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    groq_api_key = fields.Char(string='Groq API Key')
    open_router_key = fields.Char(string='OpenRouter API Key')


    @api.model_create_multi
    def create(self, vals_list):
        users = super(ResUsers, self).create(vals_list)
        dashboard_action = self.env.ref('analytix_finance_dashboard.action_analytix_finance_dashboard', raise_if_not_found=False)
        if dashboard_action:
            for user in users:
                if not user.share and not user.action_id:
                    user.sudo().write({'action_id': dashboard_action.id})
        return users
