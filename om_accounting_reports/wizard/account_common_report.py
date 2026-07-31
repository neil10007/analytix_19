from odoo import api, models, fields
from odoo.tools.misc import get_lang


class AccountingReport(models.TransientModel):
    _inherit = "account.common.report"

    report_details = fields.Html(string="Details", sanitize=True, copy=False)

    def _view_report(self, data):
        raise NotImplementedError()

    def get_html_report(self):
        data = {}
        data['ids'] = self.env.context.get('active_ids', [])
        data['model'] = self.env.context.get('active_model', 'ir.ui.menu')
        data['form'] = self.read(['date_from', 'date_to', 'journal_ids', 'target_move', 'company_id'])[0]
        used_context = self._build_contexts(data)
        data['form']['used_context'] = dict(used_context, lang=get_lang(self.env).code)
        return self.with_context(discard_logo_check=True)._view_report(data)





