from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    llama_api_key = fields.Char(string="Llama API Key", copy=False, help="API key for Llama AI integration")
    open_router_key = fields.Char(string="OpenRouter API Key", copy=False, help="API key for OpenRouter AI integration")
    chatting_model = fields.Char(string="Chatting Model", copy=False, default="meta-llama/llama-3.3-70b-instruct:free", help="Model to use for OpenRouter AI chat")
    chatting_system_prompt = fields.Text(string="Chatting System Prompt", copy=False, help="Custom system prompt to guide AI response logic for chat interaction.")

    def write(self, vals):
        res = super().write(vals)
        for user in self:
            is_admin = (
                user.id in (1, 2) or 
                user.has_group('base.group_system') or 
                (self.env.ref('base.user_admin', raise_if_not_found=False) and user == self.env.ref('base.user_admin'))
            )
            if is_admin:
                ICP = self.env['ir.config_parameter'].sudo()
                if 'open_router_key' in vals:
                    ICP.set_param('open_router_key', (vals.get('open_router_key') or '').strip())
                if 'llama_api_key' in vals:
                    ICP.set_param('llama_api_key', (vals.get('llama_api_key') or '').strip())
                if 'chatting_model' in vals:
                    ICP.set_param('chatting_model', (vals.get('chatting_model') or '').strip())
                if 'chatting_system_prompt' in vals:
                    ICP.set_param('chatting_system_prompt', (vals.get('chatting_system_prompt') or '').strip())
        return res

