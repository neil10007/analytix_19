# -*- coding: utf-8 -*-

from odoo import fields, models, api, _


class AccountCashBookReport(models.TransientModel):
    _inherit = "account.cashbook.report"

    def check_report(self):
        if self._context.get('excel_report'):
            data = {}
            data['form'] = self.read(['target_move', 'date_from', 'date_to', 'journal_ids', 'account_ids',
                                      'sortby', 'initial_balance', 'display_account'])[0]
            comparison_context = self._build_comparison_context(data)
            data['form']['comparison_context'] = comparison_context
            return self.env.ref(
                'om_account_book_excel.action_report_cash_book_excel').report_action(self,
                                                                                  data=data)
        else:
            return super(AccountCashBookReport, self).check_report()

