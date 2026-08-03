import re
from odoo import fields, models, api, _


class AccountPartnerLedger(models.TransientModel):
    _inherit = "account.report.partner.ledger"

    @api.onchange('target_move', 'reconciled', 'partner_ids', 'journal_ids',
                  'date_from', 'date_to', 'result_selection')
    def onchange_clear(self):
        self.report_details = ''

    def _compute_display_name(self):
        for record in self:
            record.display_name = f'Partner Ledger'

    def _view_report(self, data):
        data = self._get_report_data(data)
        report_ref = 'accounting_pdf_reports.action_report_partnerledger'
        report_details = self.env.ref('accounting_pdf_reports.action_report_partnerledger').\
            _render_qweb_html(report_ref, docids=None, data=data)[0]
        decoded_html = report_details.decode('utf-8')
        self.report_details = re.sub(r'(<[^>]*\s)(encoding=(["\'][^"\']*?["\']|[^\s\n\r>]+)(\s[^>]*|/)?>)', "", decoded_html, flags=re.IGNORECASE | re.DOTALL)
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_id': self.env.ref('accounting_pdf_reports.account_report_partner_ledger_view').id,
            'res_model': self._name,
            'res_id': self.id
        }

