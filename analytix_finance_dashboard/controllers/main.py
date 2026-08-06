# -*- coding: utf-8 -*-
from odoo import models, api, fields
from dateutil.relativedelta import relativedelta
from datetime import date, datetime

class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def _get_currency_symbol(self, currency):
        if not currency:
            return ''
        return (currency.symbol or currency.name or '').strip()

    @api.model
    def get_analytix_dashboard_data(self, filter_name='this_month', date_from=None, date_to=None):
        self = self.sudo()
        today = date.today()
        if filter_name == 'this_month':
            start_date = today.replace(day=1)
            end_date = start_date + relativedelta(months=1, days=-1)
            prev_start_date = start_date - relativedelta(months=1)
            prev_end_date = start_date - relativedelta(days=1)
        elif filter_name == 'last_3_months':
            start_date = today.replace(day=1) - relativedelta(months=2)
            end_date = start_date + relativedelta(months=3, days=-1)
            prev_start_date = start_date - relativedelta(months=3)
            prev_end_date = start_date - relativedelta(days=1)
        elif filter_name == 'this_year':
            start_date = today.replace(month=1, day=1)
            end_date = today.replace(month=12, day=31)
            prev_start_date = start_date - relativedelta(years=1)
            prev_end_date = start_date - relativedelta(days=1)
        elif filter_name == 'custom' and date_from and date_to:
            try:
                start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                end_date   = datetime.strptime(date_to,   '%Y-%m-%d').date()
            except Exception:
                start_date = today.replace(day=1)
                end_date   = start_date + relativedelta(months=1, days=-1)
            duration = (end_date - start_date).days + 1
            prev_end_date   = start_date - relativedelta(days=1)
            prev_start_date = prev_end_date - relativedelta(days=duration - 1)
        else: # Default this month
            start_date = today.replace(day=1)
            end_date = start_date + relativedelta(months=1, days=-1)
            prev_start_date = start_date - relativedelta(months=1)
            prev_end_date = start_date - relativedelta(days=1)

        company_ids = self.env.companies.ids

        domain_revenue = [('move_type', '=', 'out_invoice'), ('state', '=', 'posted'), ('company_id', 'in', company_ids)]
        domain_expense = [('move_type', '=', 'in_invoice'), ('state', '=', 'posted'), ('company_id', 'in', company_ids)]
        
        # Current Period
        domain_rev_curr = domain_revenue + [('invoice_date', '>=', start_date), ('invoice_date', '<=', end_date)]
        domain_exp_curr = domain_expense + [('invoice_date', '>=', start_date), ('invoice_date', '<=', end_date)]
        
        # Previous Period
        domain_rev_prev = domain_revenue + [('invoice_date', '>=', prev_start_date), ('invoice_date', '<=', prev_end_date)]
        domain_exp_prev = domain_expense + [('invoice_date', '>=', prev_start_date), ('invoice_date', '<=', prev_end_date)]

        company_currency = self.env.company.currency_id
        
        def get_total(domain):
            moves = self.search(domain)
            total = 0.0
            for move in moves:
                amount = move.amount_untaxed_signed
                if move.company_id.currency_id != company_currency:
                    amount = move.company_id.currency_id._convert(
                        amount,
                        company_currency,
                        move.company_id,
                        move.invoice_date or today
                    )
                total += amount
            return total

        rev_curr = abs(get_total(domain_rev_curr))
        exp_curr = abs(get_total(domain_exp_curr))
        rev_prev = abs(get_total(domain_rev_prev))
        exp_prev = abs(get_total(domain_exp_prev))

        def calc_perc(curr, prev):
            if prev == 0:
                return 100 if curr > 0 else 0
            return round(((curr - prev) / prev) * 100, 1)

        rev_perc = calc_perc(rev_curr, rev_prev)
        exp_perc = calc_perc(exp_curr, exp_prev)
        
        net_curr = rev_curr - exp_curr
        net_prev = rev_prev - exp_prev
        net_perc = calc_perc(net_curr, net_prev)
        
        margin_curr = round((net_curr / rev_curr) * 100, 1) if rev_curr > 0 else 0

        # Invoices this period
        domain_inv_period = domain_revenue + [('invoice_date', '>=', start_date), ('invoice_date', '<=', end_date)]
        invoices_period = self.search(domain_inv_period)
        sales_today = len(invoices_period)
        paid_today = len(invoices_period.filtered(lambda m: m.payment_state in ('paid', 'in_payment', 'reversed')))
        pending_today = sales_today - paid_today

        # Unpaid Receivables
        receivables_domain = [('move_type', '=', 'out_invoice'), ('state', '=', 'posted'), ('payment_state', 'in', ('not_paid', 'partial')), ('company_id', 'in', company_ids)]
        receivables = self.search(receivables_domain)
        unpaid_amount = 0.0
        unpaid_clients_set = set()
        for move in receivables:
            unpaid_clients_set.add(move.partner_id.id)
            amount = move.amount_residual
            if move.company_id.currency_id != company_currency:
                amount = move.company_id.currency_id._convert(
                    amount,
                    company_currency,
                    move.company_id,
                    move.invoice_date or today
                )
            unpaid_amount += amount
        unpaid_clients = len(unpaid_clients_set)

        # Chart Data
        chart_labels = []
        chart_rev = []
        chart_exp = []
        chart_title = ""
        
        if filter_name == 'this_month':
            chart_title = "This month (by week)"
            for i in range(3, -1, -1):
                w_start = today - relativedelta(weeks=i, days=today.weekday())
                w_end = w_start + relativedelta(days=6)
                chart_labels.append(w_start.strftime("%d %b"))
                r_domain = domain_revenue + [('invoice_date', '>=', w_start), ('invoice_date', '<=', w_end)]
                e_domain = domain_expense + [('invoice_date', '>=', w_start), ('invoice_date', '<=', w_end)]
                chart_rev.append(abs(get_total(r_domain)))
                chart_exp.append(abs(get_total(e_domain)))

        elif filter_name == 'last_3_months':
            chart_title = "Last 3 months"
            for i in range(2, -1, -1):
                m_date = today.replace(day=1) - relativedelta(months=i)
                e_date = m_date + relativedelta(months=1, days=-1)
                chart_labels.append(m_date.strftime("%b"))
                r_domain = domain_revenue + [('invoice_date', '>=', m_date), ('invoice_date', '<=', e_date)]
                e_domain = domain_expense + [('invoice_date', '>=', m_date), ('invoice_date', '<=', e_date)]
                chart_rev.append(abs(get_total(r_domain)))
                chart_exp.append(abs(get_total(e_domain)))

        elif filter_name == 'this_year':
            chart_title = "This year"
            for i in range(11, -1, -1):
                m_date = today.replace(day=1) - relativedelta(months=i)
                e_date = m_date + relativedelta(months=1, days=-1)
                chart_labels.append(m_date.strftime("%b"))
                r_domain = domain_revenue + [('invoice_date', '>=', m_date), ('invoice_date', '<=', e_date)]
                e_domain = domain_expense + [('invoice_date', '>=', m_date), ('invoice_date', '<=', e_date)]
                chart_rev.append(abs(get_total(r_domain)))
                chart_exp.append(abs(get_total(e_domain)))

        elif filter_name == 'custom':
            # Show month-by-month breakdown for the custom range
            chart_title = "Custom range"
            cur = start_date.replace(day=1)
            while cur <= end_date:
                m_end = min(cur + relativedelta(months=1, days=-1), end_date)
                chart_labels.append(cur.strftime("%b %Y"))
                r_domain = domain_revenue + [('invoice_date', '>=', cur), ('invoice_date', '<=', m_end)]
                e_domain = domain_expense + [('invoice_date', '>=', cur), ('invoice_date', '<=', m_end)]
                chart_rev.append(abs(get_total(r_domain)))
                chart_exp.append(abs(get_total(e_domain)))
                cur = cur + relativedelta(months=1)

        else:
            chart_title = "Last 6 months"
            for i in range(5, -1, -1):
                m_date = today.replace(day=1) - relativedelta(months=i)
                e_date = m_date + relativedelta(months=1, days=-1)
                chart_labels.append(m_date.strftime("%b"))
                r_domain = domain_revenue + [('invoice_date', '>=', m_date), ('invoice_date', '<=', e_date)]
                e_domain = domain_expense + [('invoice_date', '>=', m_date), ('invoice_date', '<=', e_date)]
                chart_rev.append(abs(get_total(r_domain)))
                chart_exp.append(abs(get_total(e_domain)))

        # Top Customers
        top_customers_data = []
        if company_ids:
            self.env.cr.execute("""
                SELECT p.name, m.company_id, sum(m.amount_untaxed_signed) as total
                FROM account_move m
                JOIN res_partner p ON m.partner_id = p.id
                WHERE m.move_type = 'out_invoice' AND m.state = 'posted' AND m.company_id IN %s
                GROUP BY p.name, m.company_id
            """, (tuple(company_ids),))
            
            partner_totals = {}
            for row in self.env.cr.fetchall():
                p_name = row[0]
                m_comp_id = row[1]
                total = row[2]
                
                comp = self.env['res.company'].browse(m_comp_id)
                if comp.currency_id != company_currency:
                    total = comp.currency_id._convert(
                        total,
                        company_currency,
                        comp,
                        today
                    )
                
                if p_name not in partner_totals:
                    partner_totals[p_name] = 0.0
                partner_totals[p_name] += total

            sorted_partners = sorted(partner_totals.items(), key=lambda item: abs(item[1]), reverse=True)[:5]
            
            for i, (p_name, total) in enumerate(sorted_partners):
                top_customers_data.append({
                    'rank': i + 1,
                    'name': p_name,
                    'revenue': abs(total)
                })

        # Top Vendors
        top_vendors_data = []
        if company_ids:
            self.env.cr.execute("""
                SELECT p.name, m.company_id, sum(m.amount_untaxed_signed) as total
                FROM account_move m
                JOIN res_partner p ON m.partner_id = p.id
                WHERE m.move_type = 'in_invoice' AND m.state = 'posted' AND m.company_id IN %s
                GROUP BY p.name, m.company_id
            """, (tuple(company_ids),))
            
            vendor_totals = {}
            for row in self.env.cr.fetchall():
                p_name = row[0]
                m_comp_id = row[1]
                total = row[2]
                
                comp = self.env['res.company'].browse(m_comp_id)
                if comp.currency_id != company_currency:
                    total = comp.currency_id._convert(
                        total,
                        company_currency,
                        comp,
                        today
                    )
                
                if p_name not in vendor_totals:
                    vendor_totals[p_name] = 0.0
                vendor_totals[p_name] += total

            sorted_vendors = sorted(vendor_totals.items(), key=lambda item: abs(item[1]), reverse=True)[:5]
            
            for i, (p_name, total) in enumerate(sorted_vendors):
                top_vendors_data.append({
                    'rank': i + 1,
                    'name': p_name,
                    'expense': abs(total)
                })

        # --- Alerts ---
        alerts = []
        sym = company_currency.symbol or company_currency.name

        def fmt_amount(amount):
            """Format amount for display in alerts."""
            if amount >= 1000:
                return '{} {:,.0f}'.format(sym, amount)
            return '{} {:.2f}'.format(sym, amount)

        def convert_to_company_currency(move, amount):
            if move.company_id.currency_id != company_currency:
                return move.company_id.currency_id._convert(
                    amount, company_currency, move.company_id, move.invoice_date or today
                )
            return amount

        # 1. Overdue customer invoices (due date < today, still unpaid)
        overdue_inv = self.search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['not_paid', 'partial']),
            ('invoice_date_due', '<', today),
            ('company_id', 'in', company_ids),
        ])
        if overdue_inv:
            overdue_total = sum(convert_to_company_currency(m, m.amount_residual) for m in overdue_inv)
            top_partners = {}
            for m in overdue_inv:
                name = m.partner_id.name or 'Unknown'
                top_partners[name] = top_partners.get(name, 0) + convert_to_company_currency(m, m.amount_residual)
            sorted_partners = sorted(top_partners.items(), key=lambda x: x[1], reverse=True)[:3]
            detail = ' · '.join(['{} ({})'.format(n, fmt_amount(v)) for n, v in sorted_partners])
            alerts.append({
                'type': 'danger',
                'title': '{} invoice{} overdue'.format(len(overdue_inv), 's' if len(overdue_inv) > 1 else ''),
                'detail': detail,
                'action': 'overdue_invoices',
                'cta': 'View all',
                'total': overdue_total,
            })

        # 2. Vendor bills due within the next 7 days (unpaid)
        week_ahead = today + relativedelta(days=7)
        bills_due_soon = self.search([
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['not_paid', 'partial']),
            ('invoice_date_due', '>=', today),
            ('invoice_date_due', '<=', week_ahead),
            ('company_id', 'in', company_ids),
        ])
        if bills_due_soon:
            bills_total = sum(convert_to_company_currency(m, m.amount_residual) for m in bills_due_soon)
            vendors = list({m.partner_id.name or 'Unknown' for m in bills_due_soon})[:3]
            detail = 'Total {} due this week — {}'.format(
                fmt_amount(bills_total), ', '.join(vendors)
            )
            alerts.append({
                'type': 'warning',
                'title': '{} bill{} awaiting payment'.format(len(bills_due_soon), 's' if len(bills_due_soon) > 1 else ''),
                'detail': detail,
                'action': 'bills_due_soon',
                'cta': 'Review',
                'total': bills_total,
            })

        # 3. Customers with receivables unpaid for > 30 days
        thirty_days_ago = today - relativedelta(days=30)
        long_overdue = self.search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['not_paid', 'partial']),
            ('invoice_date_due', '<', thirty_days_ago),
            ('company_id', 'in', company_ids),
        ])
        if long_overdue:
            long_total = sum(convert_to_company_currency(m, m.amount_residual) for m in long_overdue)
            top_clients = list({m.partner_id.name or 'Unknown' for m in long_overdue})[:3]
            detail = '{} outstanding — {}'.format(fmt_amount(long_total), ', '.join(top_clients))
            alerts.append({
                'type': 'info',
                'title': '{} client{} with receivables over 30 days'.format(
                    len({m.partner_id.id for m in long_overdue}),
                    's' if len({m.partner_id.id for m in long_overdue}) > 1 else ''
                ),
                'detail': detail,
                'action': 'long_overdue',
                'cta': 'Review',
                'total': long_total,
            })

        # 4. ZATCA VAT return due date alert
        # Controlled by: Accounting → Configuration → Settings → ZATCA VAT Return toggle
        # The field 'analytix_zatca_enabled' is stored on res.company.
        if self.env.company.analytix_zatca_enabled:
            # Quarters: Q1 Apr 30, Q2 Jul 31, Q3 Oct 31, Q4 Jan 31
            QUARTER_DEADLINES = [
                (date(today.year,     4, 30), 'Q1 {}'.format(today.year)),
                (date(today.year,     7, 31), 'Q2 {}'.format(today.year)),
                (date(today.year,    10, 31), 'Q3 {}'.format(today.year)),
                (date(today.year + 1, 1, 31), 'Q4 {}'.format(today.year)),
            ]
            for due_date, quarter_label in QUARTER_DEADLINES:
                days_left = (due_date - today).days
                if 0 <= days_left <= 30:
                    alerts.append({
                        'type': 'orange',
                        'title': 'ZATCA VAT return due in {} day{}'.format(
                            days_left, 's' if days_left != 1 else ''),
                        'detail': '{} filing deadline: {} \u2014 GAZT portal submission required'.format(
                            quarter_label, due_date.strftime('%d %b %Y')),
                        'action': 'vat_summary',
                        'cta': 'File now',
                    })
                    break
        # 5. Custom Alerts
        custom_alerts = self.env['analytix.finance.alert'].search([
            ('notify_dashboard', '=', True),
            ('active', '=', True),
            ('company_id', 'in', company_ids),
            ('state', '!=', 'completed'),
        ])
        for ca in custom_alerts:
            color_map = {
                'critical': 'danger',
                'high': 'orange',
                'medium': 'warning',
                'low': 'info',
            }
            alerts.append({
                'type': color_map.get(ca.priority, 'info'),
                'title': ca.name,
                'detail': ca.alert_description or ca.rule_description or 'Custom Alert',
                'action': f'custom_alert_{ca.id}',
                'cta': ca.action_button_label or 'Review',
            })

        return {
            'currency': self._get_currency_symbol(company_currency),
            'companies': ', '.join(self.env.companies.mapped('name')),
            'company_ids': company_ids,
            'date_range': {
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d'),
            },
            'revenue': {
                'value': rev_curr,
                'percentage': rev_perc,
                'today': abs(get_total(domain_revenue + [('invoice_date', '=', today)]))
            },
            'expenses': {
                'value': exp_curr,
                'percentage': exp_perc,
                'today': abs(get_total(domain_expense + [('invoice_date', '=', today)]))
            },
            'net_profit': {
                'value': net_curr,
                'percentage': net_perc,
                'margin': margin_curr
            },
            'invoices': {
                'sales': sales_today,
                'paid': paid_today,
                'pending': pending_today
            },
            'receivables': {
                'value': unpaid_amount,
                'clients': unpaid_clients
            },
            'chart': {
                'title': chart_title,
                'labels': chart_labels,
                'revenue': chart_rev,
                'expenses': chart_exp
            },
            'top_customers': top_customers_data,
            'top_vendors': top_vendors_data,
            'alerts': alerts
        }

    @api.model
    def get_analytix_invoices_data(self, filter_name='this_month', move_type='customer', date_from=None, date_to=None):
        """Return invoice list data for the Invoices tab."""
        self = self.sudo()
        today = date.today()

        # ── Date range ────────────────────────────────────────────────────
        if filter_name == 'this_month':
            start_date = today.replace(day=1)
            end_date = start_date + relativedelta(months=1, days=-1)
        elif filter_name == 'last_3_months':
            start_date = today.replace(day=1) - relativedelta(months=2)
            end_date = start_date + relativedelta(months=3, days=-1)
        elif filter_name == 'this_year':
            start_date = today.replace(month=1, day=1)
            end_date = today.replace(month=12, day=31)
        elif filter_name == 'custom' and date_from and date_to:
            try:
                start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                end_date   = datetime.strptime(date_to,   '%Y-%m-%d').date()
            except Exception:
                start_date = today.replace(day=1)
                end_date   = start_date + relativedelta(months=1, days=-1)
        else:
            start_date = today.replace(day=1)
            end_date = start_date + relativedelta(months=1, days=-1)

        company_ids = self.env.companies.ids
        company_currency = self.env.company.currency_id

        # ── Company colour palette (cycles through 10 colours) ────────────
        COMPANY_COLORS = [
            {'bg': '#e8f4fd', 'text': '#1565c0', 'dot': '#1e88e5'},  # blue
            {'bg': '#e8f5e9', 'text': '#2e7d32', 'dot': '#43a047'},  # green
            {'bg': '#fce4ec', 'text': '#880e4f', 'dot': '#e91e63'},  # pink
            {'bg': '#fff3e0', 'text': '#e65100', 'dot': '#fb8c00'},  # orange
            {'bg': '#ede7f6', 'text': '#4527a0', 'dot': '#7e57c2'},  # purple
            {'bg': '#e0f7fa', 'text': '#00695c', 'dot': '#00897b'},  # teal
            {'bg': '#fff8e1', 'text': '#f57f17', 'dot': '#fdd835'},  # yellow
            {'bg': '#fbe9e7', 'text': '#bf360c', 'dot': '#f4511e'},  # deep-orange
            {'bg': '#e8eaf6', 'text': '#283593', 'dot': '#3949ab'},  # indigo
            {'bg': '#e0f2f1', 'text': '#004d40', 'dot': '#00897b'},  # teal-2
        ]

        companies = self.env['res.company'].browse(company_ids)
        company_color_map = {}
        for idx, comp in enumerate(companies):
            company_color_map[comp.id] = COMPANY_COLORS[idx % len(COMPANY_COLORS)]

        # ── Move type filter ──────────────────────────────────────────────
        if move_type == 'customer':
            type_domain = [('move_type', '=', 'out_invoice')]
        elif move_type == 'vendor':
            type_domain = [('move_type', '=', 'in_invoice')]
        elif move_type == 'credit_note':
            type_domain = [('move_type', 'in', ['out_refund', 'in_refund'])]
        else:
            type_domain = [('move_type', 'in', ['out_invoice', 'in_invoice', 'out_refund', 'in_refund'])]

        domain = (
            type_domain
            + [('state', 'in', ['posted', 'draft', 'cancel'])]
            + [('company_id', 'in', company_ids)]
            + [('invoice_date', '>=', start_date), ('invoice_date', '<=', end_date)]
        )

        moves = self.search(domain, order='invoice_date desc, id desc', limit=200)

        # ── Status label & colour config ──────────────────────────────────
        STATUS_CFG = {
            'paid':       {'label': 'Paid',        'bg': '#e8f5e9', 'text': '#2e7d32', 'dot': '#43a047'},
            'in_payment': {'label': 'In Payment',  'bg': '#e3f2fd', 'text': '#1565c0', 'dot': '#1e88e5'},
            'partial':    {'label': 'Partial',      'bg': '#fff3e0', 'text': '#e65100', 'dot': '#fb8c00'},
            'not_paid':   {'label': 'Unpaid',       'bg': '#fce4ec', 'text': '#880e4f', 'dot': '#e91e63'},
            'reversed':   {'label': 'Reversed',     'bg': '#ede7f6', 'text': '#4527a0', 'dot': '#7e57c2'},
            'cancelled':  {'label': 'Cancelled',    'bg': '#f5f5f5', 'text': '#757575', 'dot': '#9e9e9e'},
            'draft':      {'label': 'Draft',        'bg': '#f5f5f5', 'text': '#607d8b', 'dot': '#90a4ae'},
        }

        MOVE_TYPE_LABELS = {
            'out_invoice': {'label': 'Customer Invoice', 'icon': 'fa-file-text-o',   'color': '#1e88e5'},
            'in_invoice':  {'label': 'Vendor Bill',      'icon': 'fa-file-text',     'color': '#e53935'},
            'out_refund':  {'label': 'Credit Note',      'icon': 'fa-undo',          'color': '#7e57c2'},
            'in_refund':   {'label': 'Refund',           'icon': 'fa-undo',          'color': '#f57c00'},
        }

        records = []
        total_amount = 0.0
        paid_amount = 0.0
        unpaid_amount = 0.0

        for move in moves:
            # Status
            if move.state == 'draft':
                status_key = 'draft'
            elif move.state == 'cancel':
                status_key = 'cancelled'
            else:
                status_key = move.payment_state or 'not_paid'
            status = STATUS_CFG.get(status_key, STATUS_CFG['not_paid'])

            # Amount in company currency
            amount = move.amount_total
            if move.company_id.currency_id != company_currency:
                try:
                    amount = move.company_id.currency_id._convert(
                        amount, company_currency, move.company_id,
                        move.invoice_date or today
                    )
                except Exception:
                    pass

            # Overdue?
            is_overdue = (
                move.state == 'posted'
                and move.payment_state in ('not_paid', 'partial')
                and move.invoice_date_due
                and move.invoice_date_due < today
            )

            company_color = company_color_map.get(move.company_id.id, COMPANY_COLORS[0])
            move_type_info = MOVE_TYPE_LABELS.get(move.move_type, MOVE_TYPE_LABELS['out_invoice'])

            # Totals
            if move.state == 'posted':
                total_amount += amount
                if move.payment_state in ('paid', 'in_payment', 'reversed'):
                    paid_amount += amount
                else:
                    unpaid_amount += amount

            records.append({
                'id':             move.id,
                'name':           move.name or '/',
                'partner':        move.partner_id.name or '—',
                'partner_ref':    move.ref or '',
                'invoice_date':   move.invoice_date.strftime('%Y-%m-%d') if move.invoice_date else '',
                'due_date':       move.invoice_date_due.strftime('%Y-%m-%d') if move.invoice_date_due else '',
                'amount':         amount,
                'amount_display': '{} {:,.2f}'.format(
                    move.currency_id.symbol or move.currency_id.name, move.amount_total
                ),
                'currency_sym':   move.currency_id.symbol or move.currency_id.name,
                'company_id':     move.company_id.id,
                'company_name':   move.company_id.name,
                'company_color':  company_color,
                'move_type':      move.move_type,
                'move_type_label': move_type_info['label'],
                'move_type_icon': move_type_info['icon'],
                'move_type_color': move_type_info['color'],
                'status_key':     status_key,
                'status_label':   status['label'],
                'status_bg':      status['bg'],
                'status_text':    status['text'],
                'status_dot':     status['dot'],
                'is_overdue':     is_overdue,
                'journal':        move.journal_id.name or '',
            })

        return {
            'records':        records,
            'total_count':    len(records),
            'total_amount':   total_amount,
            'paid_amount':    paid_amount,
            'unpaid_amount':  unpaid_amount,
            'currency_sym':   company_currency.symbol or company_currency.name,
            'companies':      [{'id': c.id, 'name': c.name, 'color': company_color_map.get(c.id, COMPANY_COLORS[0])} for c in companies],
            'date_range':     {'start': start_date.strftime('%Y-%m-%d'), 'end': end_date.strftime('%Y-%m-%d')},
        }

    @api.model
    def get_analytix_vat_data(self, filter_name='this_month', date_from=None, date_to=None):
        """Return VAT tax lines split into output (invoices) and input (bills)."""
        self = self.sudo()
        today = date.today()
        if filter_name == 'this_month':
            start_date = today.replace(day=1)
            end_date = start_date + relativedelta(months=1, days=-1)
        elif filter_name == 'last_3_months':
            start_date = today.replace(day=1) - relativedelta(months=2)
            end_date = start_date + relativedelta(months=3, days=-1)
        elif filter_name == 'this_year':
            start_date = today.replace(month=1, day=1)
            end_date = today.replace(month=12, day=31)
        elif filter_name == 'custom' and date_from and date_to:
            try:
                start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                end_date   = datetime.strptime(date_to,   '%Y-%m-%d').date()
            except Exception:
                start_date = today.replace(day=1)
                end_date   = start_date + relativedelta(months=1, days=-1)
        else:
            start_date = today.replace(day=1)
            end_date = start_date + relativedelta(months=1, days=-1)

        company_ids = self.env.companies.ids
        company_currency = self.env.company.currency_id
        COMPANY_COLORS = [
            {'bg': '#e8f4fd', 'text': '#1565c0', 'dot': '#1e88e5'},
            {'bg': '#e8f5e9', 'text': '#2e7d32', 'dot': '#43a047'},
            {'bg': '#fce4ec', 'text': '#880e4f', 'dot': '#e91e63'},
            {'bg': '#fff3e0', 'text': '#e65100', 'dot': '#fb8c00'},
            {'bg': '#ede7f6', 'text': '#4527a0', 'dot': '#7e57c2'},
        ]
        companies = self.env['res.company'].browse(company_ids)
        company_color_map = {c.id: COMPANY_COLORS[i % len(COMPANY_COLORS)] for i, c in enumerate(companies)}

        def fetch_lines(move_types):
            return self.env['account.move.line'].search([
                ('move_id.state', '=', 'posted'),
                ('move_id.move_type', 'in', move_types),
                ('move_id.invoice_date', '>=', start_date),
                ('move_id.invoice_date', '<=', end_date),
                ('move_id.company_id', 'in', company_ids),
                ('tax_line_id', '!=', False),
            ], order='move_id desc')

        def build_records(lines):
            rows = []
            total = 0.0
            for line in lines:
                move = line.move_id
                amt = abs(line.balance)
                if move.company_id.currency_id != company_currency:
                    try:
                        amt = move.company_id.currency_id._convert(
                            amt, company_currency, move.company_id, move.invoice_date or today)
                    except Exception:
                        pass
                total += amt
                co = company_color_map.get(move.company_id.id, COMPANY_COLORS[0])
                rows.append({
                    'id':           move.id,
                    'move_name':    move.name or '/',
                    'partner':      move.partner_id.name or '—',
                    'tax_name':     line.tax_line_id.name or '—',
                    'tax_amount':   amt,
                    'tax_display':  '{} {:,.2f}'.format(
                        move.currency_id.symbol or move.currency_id.name,
                        abs(line.balance)),
                    'invoice_date': move.invoice_date.strftime('%Y-%m-%d') if move.invoice_date else '',
                    'move_type':    move.move_type,
                    'company_id':   move.company_id.id,
                    'company_name': move.company_id.name,
                    'company_color':co,
                    'currency_sym': move.currency_id.symbol or move.currency_id.name,
                })
            return rows, total

        out_lines = fetch_lines(['out_invoice', 'out_refund'])
        in_lines  = fetch_lines(['in_invoice',  'in_refund'])
        out_records, output_vat = build_records(out_lines)
        in_records,  input_vat  = build_records(in_lines)

        sym = company_currency.symbol or company_currency.name
        return {
            'output_records': out_records,
            'input_records':  in_records,
            'output_count':   len(out_records),
            'input_count':    len(in_records),
            'total_count':    len(out_records) + len(in_records),
            'output_vat':     output_vat,
            'input_vat':      input_vat,
            'net_vat':        output_vat - input_vat,
            'currency_sym':   sym,
            'companies':      [{'id': c.id, 'name': c.name, 'color': company_color_map.get(c.id, COMPANY_COLORS[0])} for c in companies],
            'date_range':     {'start': start_date.strftime('%Y-%m-%d'), 'end': end_date.strftime('%Y-%m-%d')},
        }

    @api.model
    def get_analytix_journals_data(self, filter_name='this_month', date_from=None, date_to=None):
        """Return list of journal entries (account.move) for the selected period across multi-company setup."""
        self = self.sudo()
        today = date.today()
        company_ids = self.env.companies.ids
        company_currency = self.env.company.currency_id

        COMPANY_COLORS = [
            {'bg': '#e8f4fd', 'text': '#1565c0', 'dot': '#1e88e5'},
            {'bg': '#e8f5e9', 'text': '#2e7d32', 'dot': '#43a047'},
            {'bg': '#fce4ec', 'text': '#880e4f', 'dot': '#e91e63'},
            {'bg': '#fff3e0', 'text': '#e65100', 'dot': '#fb8c00'},
            {'bg': '#ede7f6', 'text': '#4527a0', 'dot': '#7e57c2'},
        ]
        JOURNAL_TYPE_CFG = {
            'sale':     {'label': 'Sales',     'bg': '#e3f2fd', 'text': '#1565c0', 'dot': '#1e88e5', 'icon': 'fa-file-text-o'},
            'purchase': {'label': 'Purchase',  'bg': '#fce4ec', 'text': '#c62828', 'dot': '#e53935', 'icon': 'fa-file-text'},
            'cash':     {'label': 'Cash',      'bg': '#e8f5e9', 'text': '#2e7d32', 'dot': '#43a047', 'icon': 'fa-money'},
            'bank':     {'label': 'Bank',      'bg': '#e8f5e9', 'text': '#1b5e20', 'dot': '#388e3c', 'icon': 'fa-university'},
            'general':  {'label': 'Misc',      'bg': '#f3e5f5', 'text': '#6a1b9a', 'dot': '#8e24aa', 'icon': 'fa-pencil'},
        }
        STATUS_CFG = {
            'posted': {'label': 'Posted', 'bg': '#e8f5e9', 'text': '#2e7d32', 'dot': '#43a047'},
            'draft':  {'label': 'Draft',  'bg': '#f5f5f5', 'text': '#607d8b', 'dot': '#90a4ae'},
            'cancel': {'label': 'Cancelled', 'bg': '#f5f5f5', 'text': '#757575', 'dot': '#9e9e9e'},
        }

        domain = [
            ('company_id', 'in', company_ids),
            ('state', '=', 'posted'),
        ]
        start_date = None
        end_date = None

        if filter_name == 'this_month':
            start_date = today.replace(day=1)
            end_date = start_date + relativedelta(months=1, days=-1)
            domain.extend([('date', '>=', start_date), ('date', '<=', end_date)])
        elif filter_name == 'last_3_months':
            start_date = today.replace(day=1) - relativedelta(months=2)
            end_date = start_date + relativedelta(months=3, days=-1)
            domain.extend([('date', '>=', start_date), ('date', '<=', end_date)])
        elif filter_name == 'this_year':
            start_date = today.replace(month=1, day=1)
            end_date = today.replace(month=12, day=31)
            domain.extend([('date', '>=', start_date), ('date', '<=', end_date)])
        elif filter_name == 'custom' and date_from and date_to:
            try:
                start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                end_date   = datetime.strptime(date_to,   '%Y-%m-%d').date()
                domain.extend([('date', '>=', start_date), ('date', '<=', end_date)])
            except Exception:
                pass

        companies = self.env['res.company'].browse(company_ids)
        company_color_map = {c.id: COMPANY_COLORS[i % len(COMPANY_COLORS)] for i, c in enumerate(companies)}

        moves = self.env['account.move'].search(domain, order='date desc, id desc', limit=1000)

        records = []
        total_amount = 0.0

        for move in moves:
            j = move.journal_id
            jtype = j.type or 'general'
            jcfg = JOURNAL_TYPE_CFG.get(jtype, JOURNAL_TYPE_CFG['general'])
            stcfg = STATUS_CFG.get(move.state, STATUS_CFG['draft'])
            co_color = company_color_map.get(move.company_id.id, COMPANY_COLORS[0])

            amt = move.amount_total
            if move.company_id.currency_id != company_currency:
                try:
                    amt = move.company_id.currency_id._convert(
                        amt, company_currency, move.company_id, move.date or today)
                except Exception:
                    pass

            if move.state == 'posted':
                total_amount += amt

            records.append({
                'id':             move.id,
                'name':           move.name or '/',
                'date':           move.date.strftime('%Y-%m-%d') if move.date else '',
                'journal_id':     j.id if j else False,
                'journal_name':   j.name if j else '—',
                'journal_code':   j.code if j else '',
                'type':           jtype,
                'type_label':     jcfg['label'],
                'type_bg':        jcfg['bg'],
                'type_text':      jcfg['text'],
                'type_dot':       jcfg['dot'],
                'type_icon':      jcfg['icon'],
                'partner':        move.partner_id.name if move.partner_id else '—',
                'ref':            move.ref or '',
                'state':          move.state,
                'state_label':    stcfg['label'],
                'state_bg':       stcfg['bg'],
                'state_text':     stcfg['text'],
                'state_dot':      stcfg['dot'],
                'amount':         amt,
                'amount_display': '{} {:,.2f}'.format(company_currency.symbol or company_currency.name, amt),
                'company_id':     move.company_id.id,
                'company_name':   move.company_id.name,
                'company_color':  co_color,
            })

        return {
            'records':      records,
            'total_count':  len(records),
            'total_amount': total_amount,
            'currency_sym': company_currency.symbol or company_currency.name,
            'companies':    [{'id': c.id, 'name': c.name, 'color': company_color_map.get(c.id, COMPANY_COLORS[0])} for c in companies],
            'date_range':   {'start': start_date.strftime('%Y-%m-%d') if start_date else 'All Time', 'end': end_date.strftime('%Y-%m-%d') if end_date else 'All Time'},
        }

    @api.model
    def get_analytix_pl_data(self, filter_name='this_month', date_from=None, date_to=None):
        """Return P&L (Profit & Loss) data for dashboard modal preview."""
        self = self.sudo()
        today = date.today()
        if filter_name == 'this_month':
            start_date = today.replace(day=1)
            end_date   = start_date + relativedelta(months=1, days=-1)
        elif filter_name == 'last_3_months':
            start_date = today.replace(day=1) - relativedelta(months=2)
            end_date   = start_date + relativedelta(months=3, days=-1)
        elif filter_name == 'this_year':
            start_date = today.replace(month=1, day=1)
            end_date   = today.replace(month=12, day=31)
        elif filter_name == 'custom' or (date_from and date_to):
            if date_from and date_to:
                try:
                    start_date = datetime.strptime(str(date_from), '%Y-%m-%d').date()
                    end_date   = datetime.strptime(str(date_to),   '%Y-%m-%d').date()
                except Exception:
                    start_date = today.replace(day=1)
                    end_date   = start_date + relativedelta(months=1, days=-1)
            elif date_from:
                try:
                    start_date = datetime.strptime(str(date_from), '%Y-%m-%d').date()
                    end_date   = today
                except Exception:
                    start_date = today.replace(day=1)
                    end_date   = start_date + relativedelta(months=1, days=-1)
            elif date_to:
                try:
                    end_date   = datetime.strptime(str(date_to), '%Y-%m-%d').date()
                    start_date = end_date.replace(day=1)
                except Exception:
                    start_date = today.replace(day=1)
                    end_date   = start_date + relativedelta(months=1, days=-1)
            else:
                start_date = today.replace(day=1)
                end_date   = start_date + relativedelta(months=1, days=-1)
        else:
            start_date = today.replace(day=1)
            end_date   = start_date + relativedelta(months=1, days=-1)

        company_ids = self.env.companies.ids or [self.env.company.id]
        company_currency = self.env.company.currency_id
        sym = company_currency.symbol or company_currency.name

        def fetch_section(account_types, negate=False):
            """Return list of {id, name, balance} and section total.
            Uses ORM read_group so Odoo 19 jsonb name fields are translated correctly."""
            if not account_types:
                return [], 0.0
            groups = self.env['account.move.line'].read_group(
                domain=[
                    ('move_id.state', '=', 'posted'),
                    ('move_id.date', '>=', start_date),
                    ('move_id.date', '<=', end_date),
                    ('account_id.account_type', 'in', account_types),
                    ('company_id', 'in', company_ids),
                ],
                fields=['account_id', 'balance:sum'],
                groupby=['account_id'],
            )
            accounts = []
            total = 0.0
            for g in groups:
                raw_bal = g.get('balance') or 0.0
                if raw_bal == 0.0:
                    continue
                bal = -raw_bal if negate else raw_bal
                acc_data = g.get('account_id')
                if isinstance(acc_data, (list, tuple)):
                    acc_id, acc_name = acc_data[0], acc_data[1]
                else:
                    acc_id, acc_name = acc_data, str(acc_data)
                accounts.append({'id': acc_id, 'name': acc_name, 'balance': round(bal, 2)})
                total += bal
            accounts.sort(key=lambda x: x['name'])
            return accounts, round(total, 2)

        # Income accounts are credit-normal → negate balance to get positive revenue
        income_accs,  income_total  = fetch_section(['income'],                negate=True)
        cogs_accs,    cogs_total    = fetch_section(['expense_direct_cost'],   negate=False)
        expense_accs, expense_total = fetch_section(['expense', 'expense_depreciation'], negate=False)
        oincome_accs, oincome_total = fetch_section(['income_other'],          negate=True)

        gross_profit          = round(income_total - cogs_total,            2)
        net_operating_income  = round(gross_profit - expense_total,         2)
        net_other_income      = round(oincome_total,                        2)
        net_income            = round(net_operating_income + net_other_income, 2)

        return {
            'period_label': '{} – {}'.format(
                start_date.strftime('%d %b %Y'), end_date.strftime('%d %b %Y')),
            'year':         end_date.year,
            'currency_sym': sym,
            'company':      ', '.join(self.env.companies.mapped('name')),
            'income':       {'accounts': income_accs,  'total': income_total},
            'cogs':         {'accounts': cogs_accs,    'total': cogs_total},
            'gross_profit': gross_profit,
            'expense':      {'accounts': expense_accs, 'total': expense_total},
            'net_operating_income': net_operating_income,
            'other_income': {'accounts': oincome_accs, 'total': oincome_total},
            'net_other_income':     net_other_income,
            'net_income':           net_income,
        }

    @api.model
    def get_analytix_balance_sheet_data(self, as_of_date_str=None, compare_date_str=None):
        """
        Balance Sheet — cumulative snapshot as of a given date.
        Supports optional comparison column (compare_date_str).
        Multi-company aware.
        """
        self = self.sudo()
        today = date.today()
        company_ids = self.env.companies.ids or [self.env.company.id]
        sym = self.env.company.currency_id.symbol or self.env.company.currency_id.name

        def parse_display(s):
            """Parse date for display — keeps selected date even if future."""
            if not s:
                return today
            try:
                return datetime.strptime(s, '%Y-%m-%d').date()
            except Exception:
                return today

        def parse_query(s):
            """Parse date for DB query — always capped to today."""
            return min(parse_display(s), today)

        # Display dates (what user selected — shown in header)
        as_of_display = parse_display(as_of_date_str) if as_of_date_str else today
        cmp_display   = parse_display(compare_date_str) if compare_date_str else None

        # Query cutoff dates (capped to today — used in DB filter)
        as_of    = parse_query(as_of_date_str) if as_of_date_str else today
        cmp_date = parse_query(compare_date_str) if compare_date_str else None

        def fetch_section(account_types, cutoff, negate=False):
            if not account_types:
                return [], 0.0
            groups = self.env['account.move.line'].read_group(
                domain=[
                    ('move_id.state', '=', 'posted'),
                    ('move_id.date', '<=', cutoff),
                    ('account_id.account_type', 'in', account_types),
                    ('company_id', 'in', company_ids),
                ],
                fields=['account_id', 'balance:sum'],
                groupby=['account_id'],
            )
            accounts, total = [], 0.0
            for g in groups:
                raw = g.get('balance') or 0.0
                if raw == 0.0:
                    continue
                bal = -raw if negate else raw
                ad = g.get('account_id')
                acc_id, acc_name = (ad[0], ad[1]) if isinstance(ad, (list, tuple)) else (ad, str(ad))
                accounts.append({'id': acc_id, 'name': acc_name, 'balance': round(bal, 2)})
                total += bal
            accounts.sort(key=lambda x: x['name'])
            return accounts, round(total, 2)

        def build_bs(cutoff):
            bk_a, bk_t = fetch_section(['asset_cash'],         cutoff)
            rv_a, rv_t = fetch_section(['asset_receivable'],   cutoff)
            ca_a, ca_t = fetch_section(['asset_current'],      cutoff)
            tca = round(bk_t + rv_t + ca_t, 2)
            fa_a, fa_t = fetch_section(['asset_fixed'],        cutoff)
            oa_a, oa_t = fetch_section(['asset_non_current'],  cutoff)
            ta  = round(tca + fa_t + oa_t, 2)

            pa_a, pa_t = fetch_section(['liability_payable'],     cutoff, negate=True)
            cc_a, cc_t = fetch_section(['liability_credit_card'], cutoff, negate=True)
            cl_a, cl_t = fetch_section(['liability_current'],     cutoff, negate=True)
            tcl = round(pa_t + cc_t + cl_t, 2)
            nl_a, nl_t = fetch_section(['liability_non_current'], cutoff, negate=True)
            tl  = round(tcl + nl_t, 2)

            eq_a, eq_t = fetch_section(['equity'],             cutoff, negate=True)
            eu_a, eu_t = fetch_section(['equity_unaffected'],  cutoff, negate=True)
            cye = round(ta - tl - eq_t - eu_t, 2)
            pye = eu_t
            teq = round(eq_t + eu_t + cye, 2)
            tle = round(tl + teq, 2)

            return {
                'bank_cash':                  {'accounts': bk_a, 'total': bk_t},
                'receivable':                 {'accounts': rv_a, 'total': rv_t},
                'current_assets':             {'accounts': ca_a, 'total': ca_t},
                'total_current_assets':       tca,
                'fixed_assets':               {'accounts': fa_a, 'total': fa_t},
                'other_assets':               {'accounts': oa_a, 'total': oa_t},
                'total_assets':               ta,
                'payable':                    {'accounts': pa_a, 'total': pa_t},
                'credit_cards':               {'accounts': cc_a, 'total': cc_t},
                'current_liabilities':        {'accounts': cl_a, 'total': cl_t},
                'total_current_liabilities':  tcl,
                'noncurrent_liabilities':     {'accounts': nl_a, 'total': nl_t},
                'total_liabilities':          tl,
                'equity':                     {'accounts': eq_a, 'total': eq_t},
                'current_year_earnings':      cye,
                'prev_year_earnings':         pye,
                'total_equity':               teq,
                'total_liabilities_equity':   tle,
            }

        primary = build_bs(as_of)
        compare = build_bs(cmp_date) if cmp_date else None

        result = {
            'as_of_date':   as_of_display.strftime('%m/%d/%Y'),
            'as_of_iso':    str(as_of_display),
            'compare_date': cmp_display.strftime('%m/%d/%Y') if cmp_display else None,
            'compare_iso':  str(cmp_display) if cmp_display else None,
            'currency_sym': sym,
            'company':      ', '.join(self.env.companies.mapped('name')),
        }
        result.update(primary)
        if compare:
            result['compare'] = compare
        return result

    @api.model
    def get_analytix_trial_balance_data(self, filter_name='this_month', date_from=None, date_to=None):
        """Return trial balance data: per-account debit/credit/balance grouped by account type."""
        self = self.sudo()
        today = date.today()
        if filter_name == 'this_month':
            start_date = today.replace(day=1)
            end_date = start_date + relativedelta(months=1, days=-1)
        elif filter_name == 'last_3_months':
            start_date = today.replace(day=1) - relativedelta(months=2)
            end_date = start_date + relativedelta(months=3, days=-1)
        elif filter_name == 'this_year':
            start_date = today.replace(month=1, day=1)
            end_date = today.replace(month=12, day=31)
        elif filter_name == 'custom' and date_from and date_to:
            try:
                start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                end_date   = datetime.strptime(date_to,   '%Y-%m-%d').date()
            except Exception:
                start_date = today.replace(day=1)
                end_date   = start_date + relativedelta(months=1, days=-1)
        else:
            start_date = today.replace(day=1)
            end_date   = start_date + relativedelta(months=1, days=-1)

        company_ids = self.env.companies.ids or [self.env.company.id]
        company_currency = self.env.company.currency_id
        sym = company_currency.symbol or company_currency.name

        COMPANY_COLORS = [
            {'bg': '#e8f4fd', 'text': '#1565c0', 'dot': '#1e88e5'},
            {'bg': '#e8f5e9', 'text': '#2e7d32', 'dot': '#43a047'},
            {'bg': '#fce4ec', 'text': '#880e4f', 'dot': '#e91e63'},
            {'bg': '#fff3e0', 'text': '#e65100', 'dot': '#fb8c00'},
            {'bg': '#ede7f6', 'text': '#4527a0', 'dot': '#7e57c2'},
        ]
        companies = self.env['res.company'].browse(company_ids)
        company_color_map = {c.id: COMPANY_COLORS[i % len(COMPANY_COLORS)] for i, c in enumerate(companies)}

        # Account type → display group mapping
        TYPE_GROUP_MAP = {
            'asset_receivable':      'asset',
            'asset_cash':            'asset',
            'asset_current':         'asset',
            'asset_non_current':     'asset',
            'asset_fixed':           'asset',
            'asset_prepayments':     'asset',
            'liability_payable':     'liability',
            'liability_credit_card': 'liability',
            'liability_current':     'liability',
            'liability_non_current': 'liability',
            'income':                'income',
            'income_other':          'income',
            'expense':               'expense',
            'expense_depreciation':  'expense',
            'expense_direct_cost':   'expense',
            'equity':                'equity',
            'equity_unaffected':     'equity',
            'off_balance':           'equity',
        }

        TYPE_CFG = {
            'asset':     {'label': 'Asset',    'bg': '#e3f2fd', 'text': '#1565c0', 'dot': '#1e88e5', 'icon': 'fa-bank'},
            'liability': {'label': 'Liability', 'bg': '#fce4ec', 'text': '#c62828', 'dot': '#e53935', 'icon': 'fa-credit-card'},
            'income':    {'label': 'Income',   'bg': '#e8f5e9', 'text': '#2e7d32', 'dot': '#43a047', 'icon': 'fa-arrow-up'},
            'expense':   {'label': 'Expense',  'bg': '#fff3e0', 'text': '#e65100', 'dot': '#fb8c00', 'icon': 'fa-arrow-down'},
            'equity':    {'label': 'Equity',   'bg': '#f3e5f5', 'text': '#6a1b9a', 'dot': '#8e24aa', 'icon': 'fa-pie-chart'},
        }

        # Read initial balances (posted lines before start_date)
        init_groups = self.env['account.move.line'].read_group(
            domain=[
                ('move_id.state', '=', 'posted'),
                ('move_id.date', '<', start_date),
                ('company_id', 'in', company_ids),
            ],
            fields=['account_id', 'debit:sum', 'credit:sum', 'company_id'],
            groupby=['account_id', 'company_id'],
            lazy=False,
        )

        # Read period activity (posted lines from start_date to end_date)
        period_groups = self.env['account.move.line'].read_group(
            domain=[
                ('move_id.state', '=', 'posted'),
                ('move_id.date', '>=', start_date),
                ('move_id.date', '<=', end_date),
                ('company_id', 'in', company_ids),
            ],
            fields=['account_id', 'debit:sum', 'credit:sum', 'company_id'],
            groupby=['account_id', 'company_id'],
            lazy=False,
        )

        data_by_key = {}
        for g in init_groups:
            acc_data = g.get('account_id')
            if not acc_data:
                continue
            acc_id = acc_data[0] if isinstance(acc_data, (list, tuple)) else acc_data
            co_data = g.get('company_id')
            co_id = co_data[0] if isinstance(co_data, (list, tuple)) else (co_data or company_ids[0])
            key = (acc_id, co_id)
            if key not in data_by_key:
                data_by_key[key] = {
                    'acc_name': acc_data[1] if isinstance(acc_data, (list, tuple)) else '',
                    'init_debit': 0.0, 'init_credit': 0.0,
                    'debit': 0.0, 'credit': 0.0
                }
            data_by_key[key]['init_debit'] = g.get('debit') or 0.0
            data_by_key[key]['init_credit'] = g.get('credit') or 0.0

        for g in period_groups:
            acc_data = g.get('account_id')
            if not acc_data:
                continue
            acc_id = acc_data[0] if isinstance(acc_data, (list, tuple)) else acc_data
            co_data = g.get('company_id')
            co_id = co_data[0] if isinstance(co_data, (list, tuple)) else (co_data or company_ids[0])
            key = (acc_id, co_id)
            if key not in data_by_key:
                data_by_key[key] = {
                    'acc_name': acc_data[1] if isinstance(acc_data, (list, tuple)) else '',
                    'init_debit': 0.0, 'init_credit': 0.0,
                    'debit': 0.0, 'credit': 0.0
                }
            if not data_by_key[key]['acc_name'] and isinstance(acc_data, (list, tuple)):
                data_by_key[key]['acc_name'] = acc_data[1]
            data_by_key[key]['debit'] = g.get('debit') or 0.0
            data_by_key[key]['credit'] = g.get('credit') or 0.0

        records = []
        total_initial = 0.0
        total_debit = 0.0
        total_credit = 0.0
        total_period = 0.0
        total_ending = 0.0

        for (acc_id, co_id), val in data_by_key.items():
            acc_obj = self.env['account.account'].browse(acc_id)
            if not acc_obj.exists():
                continue
            acc_code = acc_obj.code or ''
            acc_name = val['acc_name'] or acc_obj.name or str(acc_id)
            acc_type = acc_obj.account_type or 'asset_current'
            co_obj = self.env['res.company'].browse(co_id)

            init_bal = round(val['init_debit'] - val['init_credit'], 2)
            debit = round(val['debit'], 2)
            credit = round(val['credit'], 2)
            period_bal = round(debit - credit, 2)
            ending_bal = round(init_bal + period_bal, 2)

            if init_bal == 0.0 and debit == 0.0 and credit == 0.0 and period_bal == 0.0 and ending_bal == 0.0:
                continue

            type_group = TYPE_GROUP_MAP.get(acc_type, 'asset')
            tcfg = TYPE_CFG.get(type_group, TYPE_CFG['asset'])
            co_color = company_color_map.get(co_id, COMPANY_COLORS[0])

            total_initial += init_bal
            total_debit += debit
            total_credit += credit
            total_period += period_bal
            total_ending += ending_bal

            records.append({
                'id':                   acc_id,
                'code':                 acc_code,
                'name':                 acc_name,
                'account_type':         acc_type,
                'type_group':           type_group,
                'type_label':           tcfg['label'],
                'type_bg':              tcfg['bg'],
                'type_text':            tcfg['text'],
                'type_dot':             tcfg['dot'],
                'type_icon':            tcfg['icon'],
                'company_id':           co_id,
                'company_name':         co_obj.name,
                'company_color':        co_color,
                'initial_balance':      init_bal,
                'debit':                debit,
                'credit':               credit,
                'period_balance':       period_bal,
                'ending_balance':       ending_bal,
                'initial_display':      '{} {:,.2f}'.format(sym, init_bal),
                'debit_display':        '{} {:,.2f}'.format(sym, debit),
                'credit_display':       '{} {:,.2f}'.format(sym, credit),
                'period_display':       '{} {:,.2f}'.format(sym, period_bal),
                'ending_display':       '{} {:,.2f}'.format(sym, ending_bal),
                'currency_sym':         sym,
            })

        # Default sort by account code
        records.sort(key=lambda r: (r['code'] or '', r['name']))

        return {
            'records':        records,
            'total_accounts': len(records),
            'total_initial':  round(total_initial, 2),
            'total_debit':    round(total_debit, 2),
            'total_credit':   round(total_credit, 2),
            'total_period':   round(total_period, 2),
            'total_ending':   round(total_ending, 2),
            'total_initial_display': '{} {:,.2f}'.format(sym, total_initial),
            'total_debit_display':   '{} {:,.2f}'.format(sym, total_debit),
            'total_credit_display':  '{} {:,.2f}'.format(sym, total_credit),
            'total_period_display':  '{} {:,.2f}'.format(sym, total_period),
            'total_ending_display':  '{} {:,.2f}'.format(sym, total_ending),
            'currency_sym':   sym,
            'company':        ', '.join(self.env.companies.mapped('name')),
            'companies':      [{'id': c.id, 'name': c.name, 'color': company_color_map.get(c.id, COMPANY_COLORS[0])} for c in companies],
            'date_range':     {'start': start_date.strftime('%Y-%m-%d'), 'end': end_date.strftime('%Y-%m-%d')},
        }
