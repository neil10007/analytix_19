import re
from odoo import models, api


class AccountTaxReport(models.TransientModel):
    _inherit = 'account.tax.report.wizard'

    @api.onchange('target_move', 'date_from', 'date_to')
    def onchange_clear(self):
        self.report_details = ''

    def _compute_display_name(self):
        for record in self:
            record.display_name = f'Tax Report'

    def _view_report(self, data):
        report_ref = 'accounting_pdf_reports.action_report_account_tax'
        report_details = self.env.ref('accounting_pdf_reports.action_report_account_tax').\
            _render_qweb_html(report_ref, self, data=data)[0]
        decoded_html = report_details.decode('utf-8')
        self.report_details = re.sub(r'(<[^>]*\s)(encoding=(["\'][^"\']*?["\']|[^\s\n\r>]+)(\s[^>]*|/)?>)', "", decoded_html,
                                flags=re.IGNORECASE | re.DOTALL)
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_id': self.env.ref('accounting_pdf_reports.accounting_tax_report_view').id,
            'res_model': self._name,
            'res_id': self.id
        }
