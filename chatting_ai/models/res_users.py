from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    llama_api_key = fields.Char(string="Llama API Key", copy=False, help="API key for Llama AI integration")
    open_router_key = fields.Char(string="OpenRouter API Key", copy=False, help="API key for OpenRouter AI integration")
    chatting_model = fields.Char(string="Chatting Model", copy=False, default="meta-llama/llama-3.3-70b-instruct:free", help="Model to use for OpenRouter AI chat")
    chatting_system_prompt = fields.Text(string="Chatting System Prompt", copy=False, help="Custom system prompt to guide AI response logic for chat interaction.")

