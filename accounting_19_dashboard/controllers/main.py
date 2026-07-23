# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta


class AccountingDashboardController(http.Controller):

    @http.route('/accounting_dashboard/data', type='json', auth='user', csrf=False)
    def get_dashboard_data(self, **kwargs):
        env     = request.env
        today   = date.today()
        sym     = env.company.currency_id.symbol or '$'
        company_name = env.company.name

        month_start      = today.replace(day=1)
        last_month_start = month_start - relativedelta(months=1)
        last_month_end   = month_start - timedelta(days=1)

        # ── 1. Receivables ───────────────────────────────────────────────────
        total_receivable   = 0.0
        overdue_receivable = 0.0
        try:
            moves = env['account.move'].search([
                ('move_type', '=', 'out_invoice'),
                ('state',     '=', 'posted'),
            ])
            total_receivable   = sum(moves.mapped('amount_residual'))
            overdue_receivable = sum(
                m.amount_residual for m in moves
                if m.invoice_date_due and m.invoice_date_due < today
            )
        except Exception:
            pass

        # ── 2. Payables ──────────────────────────────────────────────────────
        total_payable   = 0.0
        overdue_payable = 0.0
        try:
            bills = env['account.move'].search([
                ('move_type', '=', 'in_invoice'),
                ('state',     '=', 'posted'),
            ])
            total_payable   = sum(bills.mapped('amount_residual'))
            overdue_payable = sum(
                b.amount_residual for b in bills
                if b.invoice_date_due and b.invoice_date_due < today
            )
        except Exception:
            pass

        # ── 3. Bank & Cash ───────────────────────────────────────────────────
        bank_accounts = []
        total_bank    = 0.0
        try:
            journals = env['account.journal'].search([
                ('type', 'in', ['bank', 'cash']),
            ])
            for j in journals:
                bal = 0.0
                if j.default_account_id:
                    lines = env['account.move.line'].search([
                        ('account_id',   '=', j.default_account_id.id),
                        ('parent_state', '=', 'posted'),
                    ])
                    bal = sum(lines.mapped('balance'))
                total_bank += bal
                bank_accounts.append({
                    'name'    : j.name,
                    'balance' : round(bal, 2),
                    'currency': sym,
                    'type'    : j.type,
                })
        except Exception:
            pass

        # ── 4. Revenue MTD ───────────────────────────────────────────────────
        revenue_mtd  = 0.0
        revenue_prev = 0.0
        try:
            inv_mtd = env['account.move'].search([
                ('move_type', 'in', ['out_invoice', 'out_refund']),
                ('state',     '=',  'posted'),
                ('invoice_date', '>=', month_start),
                ('invoice_date', '<=', today),
            ])
            revenue_mtd = sum(inv_mtd.mapped('amount_total'))

            inv_prev = env['account.move'].search([
                ('move_type', 'in', ['out_invoice', 'out_refund']),
                ('state',     '=',  'posted'),
                ('invoice_date', '>=', last_month_start),
                ('invoice_date', '<=', last_month_end),
            ])
            revenue_prev = sum(inv_prev.mapped('amount_total'))
        except Exception:
            pass

        revenue_change = 0.0
        if revenue_prev:
            revenue_change = round(((revenue_mtd - revenue_prev) / revenue_prev) * 100, 1)

        # ── 5. Expenses MTD + Tax ─────────────────────────────────────────────
        expense_mtd     = 0.0
        expense_tax_mtd = 0.0
        direct_cost_mtd = 0.0   # COGS / expense_direct_cost
        opex_mtd        = 0.0   # Operating expenses (expense + expense_depreciation)
        try:
            bills_mtd = env['account.move'].search([
                ('move_type', 'in', ['in_invoice', 'in_refund']),
                ('state',     '=',  'posted'),
                ('invoice_date', '>=', month_start),
                ('invoice_date', '<=', today),
            ])
            expense_mtd     = sum(bills_mtd.mapped('amount_untaxed'))
            expense_tax_mtd = sum(bills_mtd.mapped('amount_tax'))

            # Split expenses by account type for Gross/Net profit
            for bill in bills_mtd:
                for line in bill.line_ids:
                    if line.account_id.account_type == 'expense_direct_cost':
                        direct_cost_mtd += abs(line.balance)
                    elif line.account_id.account_type in ('expense', 'expense_depreciation'):
                        opex_mtd += abs(line.balance)
        except Exception:
            pass

        # ── Gross Profit & Net Profit ───────────────────────────────────
        # Gross Profit = Revenue - Direct Costs (COGS)
        gross_profit = revenue_mtd - direct_cost_mtd
        # Net Profit   = Gross Profit - Operating Expenses - Tax
        net_profit   = gross_profit - opex_mtd - expense_tax_mtd

        # ── 6. Unpaid counts ─────────────────────────────────────────────────
        unpaid_invoices = 0
        unpaid_bills    = 0
        try:
            unpaid_invoices = env['account.move'].search_count([
                ('move_type',     '=', 'out_invoice'),
                ('state',         '=', 'posted'),
                ('payment_state', 'in', ['not_paid', 'partial']),
            ])
            unpaid_bills = env['account.move'].search_count([
                ('move_type',     '=', 'in_invoice'),
                ('state',         '=', 'posted'),
                ('payment_state', 'in', ['not_paid', 'partial']),
            ])
        except Exception:
            pass

        # ── 7. Monthly chart — last 6 months ─────────────────────────────────
        monthly_chart = []
        try:
            for i in range(5, -1, -1):
                ms = month_start - relativedelta(months=i)
                me = (ms + relativedelta(months=1)) - timedelta(days=1)

                inc_moves = env['account.move'].search([
                    ('move_type', 'in', ['out_invoice', 'out_refund']),
                    ('state',     '=',  'posted'),
                    ('invoice_date', '>=', ms),
                    ('invoice_date', '<=', me),
                ])
                exp_moves = env['account.move'].search([
                    ('move_type', 'in', ['in_invoice', 'in_refund']),
                    ('state',     '=',  'posted'),
                    ('invoice_date', '>=', ms),
                    ('invoice_date', '<=', me),
                ])
                monthly_chart.append({
                    'month'  : ms.strftime('%b %Y'),
                    'income' : round(sum(inc_moves.mapped('amount_total')), 2),
                    'expense': round(sum(exp_moves.mapped('amount_total')), 2),
                })
        except Exception:
            pass

        # ── 8. Recent invoices & bills ─────────────────────────────────────
        invoices_data = []
        bills_data = []
        try:
            recent = env['account.move'].search([
                ('move_type', '=', 'out_invoice'),
                ('state',     '=', 'posted'),
            ], order='invoice_date desc', limit=8)
            for inv in recent:
                invoices_data.append({
                    'name'    : inv.name or '',
                    'partner' : inv.partner_id.name or '',
                    'date'    : inv.invoice_date.strftime('%d %b %Y') if inv.invoice_date else '',
                    'amount'  : round(inv.amount_total, 2),
                    'currency': sym,
                    'state'   : inv.payment_state or 'not_paid',
                })
        except Exception:
            pass
        try:
            recent_bills = env['account.move'].search([
                ('move_type', '=', 'in_invoice'),
                ('state',     '=', 'posted'),
            ], order='invoice_date desc', limit=8)
            for bill in recent_bills:
                bills_data.append({
                    'name'    : bill.name or '',
                    'partner' : bill.partner_id.name or '',
                    'date'    : bill.invoice_date.strftime('%d %b %Y') if bill.invoice_date else '',
                    'amount'  : round(bill.amount_total, 2),
                    'currency': sym,
                    'state'   : bill.payment_state or 'not_paid',
                })
        except Exception:
            pass

        # ── 9. Balance Sheet ─────────────────────────────────────────────────
        balance_sheet = {
            'assets': {
                'current': [],
                'non_current': [],
                'total_current': 0.0,
                'total_non_current': 0.0,
                'total': 0.0,
            },
            'liabilities': {
                'current': [],
                'non_current': [],
                'total_current': 0.0,
                'total_non_current': 0.0,
                'total': 0.0,
            },
            'equity': {
                'items': [],
                'total': 0.0,
            },
        }

        # Account type → balance sheet bucket mapping
        ASSET_CURRENT = ['asset_cash', 'asset_receivable', 'asset_prepayments', 'asset_current']
        ASSET_NON_CURRENT = ['asset_fixed', 'asset_non_current', 'asset_non_current_receivable', 'asset_goodwill']
        LIABILITY_CURRENT = ['liability_payable', 'liability_current', 'liability_credit_card']
        LIABILITY_NON_CURRENT = ['liability_non_current', 'liability_long_term']
        EQUITY_TYPES = ['equity', 'equity_unaffected']

        try:
            all_accounts = env['account.account'].search([('deprecated', '=', False)])
            for account in all_accounts:
                atype = account.account_type
                # compute balance from posted move lines
                lines = env['account.move.line'].search([
                    ('account_id', '=', account.id),
                    ('parent_state', '=', 'posted'),
                ])
                bal = round(sum(lines.mapped('balance')), 2)
                if bal == 0.0:
                    continue
                item = {'name': account.name, 'code': account.code, 'balance': bal}

                if atype in ASSET_CURRENT:
                    balance_sheet['assets']['current'].append(item)
                    balance_sheet['assets']['total_current'] += bal
                elif atype in ASSET_NON_CURRENT:
                    balance_sheet['assets']['non_current'].append(item)
                    balance_sheet['assets']['total_non_current'] += bal
                elif atype in LIABILITY_CURRENT:
                    balance_sheet['liabilities']['current'].append(item)
                    balance_sheet['liabilities']['total_current'] += bal
                elif atype in LIABILITY_NON_CURRENT:
                    balance_sheet['liabilities']['non_current'].append(item)
                    balance_sheet['liabilities']['total_non_current'] += bal
                elif atype in EQUITY_TYPES:
                    balance_sheet['equity']['items'].append(item)
                    balance_sheet['equity']['total'] += bal

            balance_sheet['assets']['total'] = round(
                balance_sheet['assets']['total_current'] + balance_sheet['assets']['total_non_current'], 2)
            balance_sheet['liabilities']['total'] = round(
                balance_sheet['liabilities']['total_current'] + balance_sheet['liabilities']['total_non_current'], 2)
            balance_sheet['assets']['total_current']          = round(balance_sheet['assets']['total_current'], 2)
            balance_sheet['assets']['total_non_current']      = round(balance_sheet['assets']['total_non_current'], 2)
            balance_sheet['liabilities']['total_current']     = round(balance_sheet['liabilities']['total_current'], 2)
            balance_sheet['liabilities']['total_non_current'] = round(balance_sheet['liabilities']['total_non_current'], 2)
            balance_sheet['equity']['total']                  = round(balance_sheet['equity']['total'], 2)
        except Exception as e:
            pass

        return {
            'currency'          : sym,
            'company'           : company_name,
            'total_receivable'  : round(total_receivable, 2),
            'overdue_receivable': round(overdue_receivable, 2),
            'total_payable'     : round(total_payable, 2),
            'overdue_payable'   : round(overdue_payable, 2),
            'total_bank'        : round(total_bank, 2),
            'bank_accounts'     : bank_accounts,
            'revenue_this_month': round(revenue_mtd, 2),
            'revenue_last_month': round(revenue_prev, 2),
            'revenue_change'    : revenue_change,
            'expense_this_month': round(expense_mtd, 2),
            'expense_tax_mtd'   : round(expense_tax_mtd, 2),
            'gross_profit'      : round(gross_profit, 2),
            'net_profit'        : round(net_profit, 2),
            'unpaid_invoices'   : unpaid_invoices,
            'unpaid_bills'      : unpaid_bills,
            'monthly_chart'     : monthly_chart,
            'recent_invoices'   : invoices_data,
            'recent_bills'      : bills_data,
            'balance_sheet'     : balance_sheet,
        }
