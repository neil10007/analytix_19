import re
from odoo import api, fields, models, _


class AccountAgedTrialBalance(models.TransientModel):
    _inherit = 'account.aged.trial.balance'

    @api.onchange('target_move', 'partner_ids',  'result_selection',
                  'date_from', 'period_length')
    def onchange_clear(self):
        self.report_details = ''

    def _compute_display_name(self):
        for record in self:
            record.display_name = f'Aged Partner Report'

    def _view_report(self, data):
        data = self._get_report_data(data)
        report_ref = 'accounting_pdf_reports.action_report_aged_partner_balance'
        report_details = self.env.ref('accounting_pdf_reports.action_report_aged_partner_balance').\
            with_context(active_model='account.aged.trial.balance',active_id=self.id)._render_qweb_html(report_ref, docids=None, data=data)[0]
        decoded_html = report_details.decode('utf-8')
        self.report_details = re.sub(r'(<[^>]*\s)(encoding=(["\'][^"\']*?["\']|[^\s\n\r>]+)(\s[^>]*|/)?>)', "", decoded_html,
                                flags=re.IGNORECASE | re.DOTALL)
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_id': self.env.ref('accounting_pdf_reports.account_aged_balance_view').id,
            'res_model': self._name,
            'res_id': self.id
        }

