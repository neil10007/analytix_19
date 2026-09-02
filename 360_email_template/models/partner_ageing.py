# -*- coding: utf-8 -*-
from odoo import models


class InsPartnerAgeing(models.TransientModel):
    _inherit = 'ins.partner.ageing'

    def prepare_detailed_lines(self, move_line_ids=[], account_id=False):
        """Override prepare_detailed_lines to fix a.code SQL query error in Odoo 19."""
        as_on_date = self.as_on_date
        period_dict = self.prepare_bucket_list()
        company_id = self.env.company
        if account_id:
            select = """SELECT m.name AS move_name,
                            l.id AS lid, 
                            m.id AS move_id,
                            l.date AS date,
                            l.date_maturity AS date_maturity, 
                            j.code AS journal_code,
                            cc.id AS company_currency_id,
                            a.code_store->>'%s' AS account_code, """ % company_id.id
            for period in period_dict:
                if period_dict[period].get('start') and period_dict[period].get('stop'):
                    select += """ CASE 
                        WHEN 
                            COALESCE(l.date_maturity,l.date) >= '%s' AND 
                            COALESCE(l.date_maturity,l.date) <= '%s'
                        THEN
                            sum(l.balance) +
                            sum(
                                COALESCE(
                                    (SELECT 
                                        SUM(amount)
                                    FROM account_partial_reconcile
                                    WHERE credit_move_id = l.id AND max_date <= '%s'), 0
                                    )
                                ) -
                            sum(
                                COALESCE(
                                    (SELECT 
                                        SUM(amount) 
                                    FROM account_partial_reconcile 
                                    WHERE debit_move_id = l.id AND max_date <= '%s'), 0
                                    )
                                )
                        ELSE
                            0
                        END AS %s,""" % (period_dict[period].get('stop'),
                                         period_dict[period].get('start'),
                                         as_on_date,
                                         as_on_date,
                                         'range_' + str(period),
                                         )
                elif not period_dict[period].get('start'):
                    select += """ CASE 
                            WHEN 
                                COALESCE(l.date_maturity,l.date) >= '%s' 
                            THEN
                                sum(
                                    l.balance
                                    ) +
                                sum(
                                    COALESCE(
                                        (SELECT 
                                            SUM(amount)
                                        FROM account_partial_reconcile
                                        WHERE credit_move_id = l.id AND max_date <= '%s'), 0
                                        )
                                    ) -
                                sum(
                                    COALESCE(
                                        (SELECT 
                                            SUM(amount) 
                                        FROM account_partial_reconcile 
                                        WHERE debit_move_id = l.id AND max_date <= '%s'), 0
                                        )
                                    )
                            ELSE
                                0
                            END AS %s,""" % (
                    period_dict[period].get('stop'), as_on_date, as_on_date, 'range_' + str(period))
                else:
                    select += """ CASE
                            WHEN
                                COALESCE(l.date_maturity,l.date) <= '%s' 
                            THEN
                                sum(
                                    l.balance
                                    ) +
                                sum(
                                    COALESCE(
                                        (SELECT 
                                            SUM(amount)
                                        FROM account_partial_reconcile
                                        WHERE credit_move_id = l.id AND max_date <= '%s'), 0
                                        )
                                    ) -
                                sum(
                                    COALESCE(
                                        (SELECT 
                                            SUM(amount) 
                                        FROM account_partial_reconcile 
                                        WHERE debit_move_id = l.id AND max_date <= '%s'), 0
                                        )
                                    )
                            ELSE
                                0
                            END AS %s """ % (
                    period_dict[period].get('start'), as_on_date, as_on_date, 'range_' + str(period))

            sql = """
                FROM
                    account_move_line AS l
                LEFT JOIN
                    account_move AS m ON m.id = l.move_id
                LEFT JOIN
                    account_account AS a ON a.id = l.account_id
                LEFT JOIN
                    account_journal AS j ON l.journal_id = j.id
                LEFT JOIN 
                    res_currency AS cc ON l.company_currency_id = cc.id
                WHERE
                    l.balance <> 0 and l.id in %s
                GROUP BY
                    l.date, l.date_maturity, m.id, m.name, j.code, a.code_store, cc.id, l.id
            """ % str(tuple(move_line_ids) + tuple([0]))

            self.env.cr.execute(select + sql)
            final_list = self.env.cr.dictfetchall() or []
            move_lines = []
            for m in final_list:
                m['total'] = m['range_0'] + m['range_1'] + m['range_2'] + m['range_3'] + m['range_4'] + m['range_5'] + m['range_6']
                if (m['range_0'] or m['range_1'] or m['range_2'] or m['range_3'] or m['range_4'] or m['range_5'] or m['range_6']):
                    move_lines.append(m)
            return move_lines
        return []
