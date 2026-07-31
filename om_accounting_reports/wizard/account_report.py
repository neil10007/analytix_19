import re
from odoo import api, fields, models


class AccountingReport(models.TransientModel):
    _inherit = "accounting.report"

    @api.onchange('account_report_id', 'enable_filter', 'date_from',
                  'target_move', 'filter_cmp', 'date_to',
                  'label_filter', 'date_from_cmp', 'date_to_cmp', 'debit_credit')
    def onchange_clear(self):
        self.report_details = ''

    def _view_report(self, data):
        data['form'].update(self.read(
            ['date_from_cmp', 'debit_credit', 'date_to_cmp', 'filter_cmp',
             'account_report_id', 'enable_filter',
             'label_filter', 'target_move'])[0])

        c_data = {}
        c_data['form'] = self.read(['account_report_id', 'date_from_cmp',
                                    'date_to_cmp', 'journal_ids', 'filter_cmp', 'target_move'])[0]
        for field in ['account_report_id']:
            if isinstance(c_data['form'][field], tuple):
                c_data['form'][field] = c_data['form'][field][0]
        comparison_context = self._build_comparison_context(c_data)
        data['form']['comparison_context'] = comparison_context
        report_ref = 'accounting_pdf_reports.action_report_financial'
        report_details = self.env.ref('accounting_pdf_reports.action_report_financial').\
            with_context(active_model='accounting.report', active_id=self.id)._render_qweb_html(report_ref, docids=None,
                                                                                                         data=data)[0]
        decoded_html = report_details.decode('utf-8')
        self.report_details = re.sub(r'(<[^>]*\s)(encoding=(["\'][^"\']*?["\']|[^\s\n\r>]+)(\s[^>]*|/)?>)', "", decoded_html,
                                flags=re.IGNORECASE | re.DOTALL)
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_id': self.env.ref('accounting_pdf_reports.accounting_report_view').id,
            'res_model': self._name,
            'res_id': self.id
        }
