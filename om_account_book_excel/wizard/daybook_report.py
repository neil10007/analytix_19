# -*- coding: utf-8 -*-

from odoo import fields, models, _


class AccountDayBookReport(models.TransientModel):
    _inherit = "account.daybook.report"

    def check_report(self):
        if self._context.get('excel_report'):
            data = {}
            data['form'] = self.read(['target_move', 'date_from', 'date_to', 'journal_ids', 'account_ids'])[0]
            comparison_context = self._build_comparison_context(data)
            data['form']['comparison_context'] = comparison_context
            return self.env.ref(
                'om_account_book_excel.action_report_day_book_excel').report_action(self, data=data)
        else:
            return super(AccountDayBookReport, self).check_report()

