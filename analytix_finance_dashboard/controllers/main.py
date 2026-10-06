# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import UserError, ValidationError
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

        company_currency = self.env.company.currency_id

        def get_revenue_for_period(s_date, e_date):
            if not company_ids:
                return 0.0
            self.env.cr.execute("""
                SELECT l.company_id, l.date, sum(l.balance)
                FROM account_move_line l
                JOIN account_move m ON l.move_id = m.id
                JOIN account_account a ON l.account_id = a.id
                WHERE m.state = 'posted'
                  AND l.date >= %s AND l.date <= %s
                  AND a.account_type IN ('income', 'income_other')
                  AND l.company_id IN %s
                GROUP BY l.company_id, l.date
            """, (s_date, e_date, tuple(company_ids)))
            total = 0.0
            for row in self.env.cr.fetchall():
                comp_id, l_date, bal = row[0], row[1], row[2]
                amount = -bal
                comp = self.env['res.company'].browse(comp_id)
                if comp.currency_id != company_currency:
                    amount = comp.currency_id._convert(
                        amount, company_currency, comp, l_date or today
                    )
                total += amount
            return round(max(0.0, total), 2)

        def get_expense_for_period(s_date, e_date):
            if not company_ids:
                return 0.0
            self.env.cr.execute("""
                SELECT l.company_id, l.date, sum(l.balance)
                FROM account_move_line l
                JOIN account_move m ON l.move_id = m.id
                JOIN account_account a ON l.account_id = a.id
                WHERE m.state = 'posted'
                  AND l.date >= %s AND l.date <= %s
                  AND a.account_type IN ('expense', 'expense_depreciation', 'expense_direct_cost')
                  AND l.company_id IN %s
                GROUP BY l.company_id, l.date
            """, (s_date, e_date, tuple(company_ids)))
            total = 0.0
            for row in self.env.cr.fetchall():
                comp_id, l_date, bal = row[0], row[1], row[2]
                amount = bal
                comp = self.env['res.company'].browse(comp_id)
                if comp.currency_id != company_currency:
                    amount = comp.currency_id._convert(
                        amount, company_currency, comp, l_date or today
                    )
                total += amount
            return round(max(0.0, total), 2)

        rev_curr = get_revenue_for_period(start_date, end_date)
        exp_curr = get_expense_for_period(start_date, end_date)
        rev_prev = get_revenue_for_period(prev_start_date, prev_end_date)
        exp_prev = get_expense_for_period(prev_start_date, prev_end_date)

        def calc_perc(curr, prev):
            if prev == 0:
                return 100 if curr > 0 else 0
            return round(((curr - prev) / prev) * 100, 1)

        rev_perc = calc_perc(rev_curr, rev_prev)
        exp_perc = calc_perc(exp_curr, exp_prev)
        
        net_curr = round(rev_curr - exp_curr, 2)
        net_prev = round(rev_prev - exp_prev, 2)
        net_perc = calc_perc(net_curr, net_prev)
        
        margin_curr = round((net_curr / rev_curr) * 100, 1) if rev_curr > 0 else 0

        # Invoices & POS Sales this period (supports both B2B customer invoices and B2C POS orders)
        domain_inv_period = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('company_id', 'in', company_ids),
            '|',
            '&', ('invoice_date', '!=', False), '&', ('invoice_date', '>=', start_date), ('invoice_date', '<=', end_date),
            '&', ('invoice_date', '=', False), '&', ('date', '>=', start_date), ('date', '<=', end_date),
        ]
        invoices_period = self.search(domain_inv_period)
        inv_sales_count = len(invoices_period)
        inv_paid_count = len(invoices_period.filtered(lambda m: m.payment_state in ('paid', 'in_payment', 'reversed')))

        pos_sales_count = 0
        pos_paid_count = 0
        if 'pos.order' in self.env:
            try:
                start_dt = datetime.combine(start_date, datetime.min.time())
                end_dt = datetime.combine(end_date, datetime.max.time())
                pos_orders = self.env['pos.order'].search([
                    ('company_id', 'in', company_ids),
                    ('date_order', '>=', start_dt),
                    ('date_order', '<=', end_dt),
                    ('state', 'in', ['paid', 'done', 'invoiced']),
                ])
                unlinked_pos = pos_orders.filtered(lambda o: not o.account_move or o.account_move.id not in invoices_period.ids)
                pos_sales_count = len(unlinked_pos)
                pos_paid_count = len(unlinked_pos.filtered(lambda o: o.state in ['paid', 'done', 'invoiced']))
            except Exception:
                pass

        sales_today = inv_sales_count + pos_sales_count
        paid_today = inv_paid_count + pos_paid_count
        pending_today = max(0, sales_today - paid_today)

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
                chart_rev.append(get_revenue_for_period(w_start, w_end))
                chart_exp.append(get_expense_for_period(w_start, w_end))

        elif filter_name == 'last_3_months':
            chart_title = "Last 3 months"
            for i in range(2, -1, -1):
                m_date = today.replace(day=1) - relativedelta(months=i)
                e_date = m_date + relativedelta(months=1, days=-1)
                chart_labels.append(m_date.strftime("%b"))
                chart_rev.append(get_revenue_for_period(m_date, e_date))
                chart_exp.append(get_expense_for_period(m_date, e_date))

        elif filter_name == 'this_year':
            chart_title = "This year"
            for i in range(11, -1, -1):
                m_date = today.replace(day=1) - relativedelta(months=i)
                e_date = m_date + relativedelta(months=1, days=-1)
                chart_labels.append(m_date.strftime("%b"))
                chart_rev.append(get_revenue_for_period(m_date, e_date))
                chart_exp.append(get_expense_for_period(m_date, e_date))

        elif filter_name == 'custom':
            # Show month-by-month breakdown for the custom range
            chart_title = "Custom range"
            cur = start_date.replace(day=1)
            while cur <= end_date:
                m_end = min(cur + relativedelta(months=1, days=-1), end_date)
                chart_labels.append(cur.strftime("%b %Y"))
                chart_rev.append(get_revenue_for_period(cur, m_end))
                chart_exp.append(get_expense_for_period(cur, m_end))
                cur = cur + relativedelta(months=1)

        else:
            chart_title = "Last 6 months"
            for i in range(5, -1, -1):
                m_date = today.replace(day=1) - relativedelta(months=i)
                e_date = m_date + relativedelta(months=1, days=-1)
                chart_labels.append(m_date.strftime("%b"))
                chart_rev.append(get_revenue_for_period(m_date, e_date))
                chart_exp.append(get_expense_for_period(m_date, e_date))

        # Top Customers (supports B2B customer invoices and B2C Point of Sale retail clients)
        top_customers_data = []
        if company_ids:
            partner_totals = {}
            # 1. B2B Invoices
            try:
                self.env.cr.execute("""
                    SELECT p.name, m.company_id, sum(m.amount_untaxed_signed) as total
                    FROM account_move m
                    JOIN res_partner p ON m.partner_id = p.id
                    WHERE m.move_type = 'out_invoice' AND m.state = 'posted' AND m.company_id IN %s
                    GROUP BY p.name, m.company_id
                """, (tuple(company_ids),))
                for row in self.env.cr.fetchall():
                    p_name, m_comp_id, total = row[0], row[1], row[2]
                    comp = self.env['res.company'].browse(m_comp_id)
                    if comp.currency_id != company_currency:
                        total = comp.currency_id._convert(total, company_currency, comp, today)
                    partner_totals[p_name] = partner_totals.get(p_name, 0.0) + abs(total)
            except Exception:
                pass

            # 2. B2C POS Orders
            if 'pos.order' in self.env:
                try:
                    self.env.cr.execute("""
                        SELECT coalesce(p.name, 'Walk-in Retail') as customer_name, o.company_id, sum(o.amount_total) as total
                        FROM pos_order o
                        LEFT JOIN res_partner p ON o.partner_id = p.id
                        WHERE o.state IN ('paid', 'done', 'invoiced') AND o.company_id IN %s
                        GROUP BY customer_name, o.company_id
                    """, (tuple(company_ids),))
                    for row in self.env.cr.fetchall():
                        p_name, m_comp_id, total = row[0], row[1], row[2]
                        comp = self.env['res.company'].browse(m_comp_id)
                        if comp.currency_id != company_currency:
                            total = comp.currency_id._convert(total, company_currency, comp, today)
                        partner_totals[p_name] = partner_totals.get(p_name, 0.0) + abs(total)
                except Exception:
                    pass

            sorted_partners = sorted(partner_totals.items(), key=lambda item: abs(item[1]), reverse=True)[:5]
            for i, (p_name, total) in enumerate(sorted_partners):
                top_customers_data.append({
                    'rank': i + 1,
                    'name': p_name,
                    'revenue': round(abs(total), 2)
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
        sym = self._get_currency_symbol(company_currency)

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
                'is_overdue': True,
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
            # Exclude completed state
            if ca.state == 'completed':
                continue

            # Validate Recurrence Expiration
            if ca.recurring_type == 'recurring':
                if ca.repeat_type == 'until' and ca.repeat_until and today > ca.repeat_until:
                    continue

            # Validate Start Date
            if ca.start_from and today < ca.start_from:
                continue

            # Validate Due Date & Trigger Condition
            is_overdue = False
            if ca.due_date:
                if today > ca.due_date:
                    is_overdue = True
                elif ca.trigger_when == 'overdue':
                    continue

            # Alert Color & Formatting
            color_map = {
                'critical': 'danger',
                'high': 'orange',
                'medium': 'warning',
                'low': 'info',
            }
            # Automatically assign danger (Red) if due date is over
            alert_type = 'danger' if is_overdue else color_map.get(ca.priority, 'info')

            title = ca.alert_title or ca.name
            detail_text = ca.alert_description or ca.rule_description or ca.name
            if is_overdue and not detail_text.startswith('Overdue'):
                detail = f"Overdue ({ca.due_date.strftime('%d %b %Y')}) · {detail_text}"
            else:
                detail = detail_text

            alerts.append({
                'type': alert_type,
                'title': title,
                'detail': detail,
                'action': f'custom_alert_{ca.id}',
                'cta': ca.action_button_label or 'Review',
                'is_overdue': is_overdue,
            })

        # Sort alerts: Overdue / Danger alerts appear at the VERY TOP of the alerts section
        priority_order = {'danger': 0, 'orange': 1, 'warning': 2, 'info': 3}
        alerts.sort(key=lambda a: (0 if (a.get('is_overdue') or a.get('type') == 'danger') else 1, priority_order.get(a.get('type'), 4)))

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
                'today': get_revenue_for_period(today, today)
            },
            'expenses': {
                'value': exp_curr,
                'percentage': exp_perc,
                'today': get_expense_for_period(today, today)
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
    def get_analytix_inventory_data(self):
        """Return product list and company currency symbol for the Inventory tab."""
        self = self.sudo()
        company_currency = self.env.company.currency_id
        sym = self._get_currency_symbol(company_currency)

        fields = ['id', 'name', 'default_code', 'list_price', 'standard_price',
                  'qty_available', 'virtual_available', 'uom_id', 'type',
                  'active', 'barcode', 'categ_id']
        products = self.env['product.template'].search_read(
            [('active', '=', True)],
            fields=fields,
            limit=200,
            order='name asc'
        )

        return {
            'records': products,
            'currency_sym': sym,
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
                    self._get_currency_symbol(move.currency_id), move.amount_total
                ),
                'currency_sym':   self._get_currency_symbol(move.currency_id),
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
            'currency_sym':   self._get_currency_symbol(company_currency),
            'companies':      [{'id': c.id, 'name': c.name, 'color': company_color_map.get(c.id, COMPANY_COLORS[0])} for c in companies],
            'date_range':     {'start': start_date.strftime('%Y-%m-%d'), 'end': end_date.strftime('%Y-%m-%d')},
        }

    @api.model
    def get_analytix_vat_data(self, filter_name='this_month', date_from=None, date_to=None, include_prior=False):
        """Return VAT tax lines split into output (invoices) and input (bills), plus ZATCA VAT Return structure."""
        self = self.sudo()
        today = date.today()
        include_prior = bool(include_prior)

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

        # Initialize ZATCA VAT Return structure
        sales_boxes = {
            '1':   {'box': '1',   'description': 'Standard rated domestic sales (15%)', 'amount': 0.0, 'adjustment': 0.0, 'vat_amount': 0.0, 'move_ids': set(), 'invoices_map': {}},
            '1.1': {'box': '1.1', 'description': 'Standard rated domestic sales (5%)',  'amount': 0.0, 'adjustment': 0.0, 'vat_amount': 0.0, 'move_ids': set(), 'invoices_map': {}},
            '2':   {'box': '2',   'description': 'Private Healthcare/Private Education/First house sales to citizens', 'amount': 0.0, 'adjustment': 0.0, 'vat_amount': 0.0, 'move_ids': set(), 'invoices_map': {}},
            '3':   {'box': '3',   'description': 'Zero rated domestic sales',           'amount': 0.0, 'adjustment': 0.0, 'vat_amount': 0.0, 'move_ids': set(), 'invoices_map': {}},
            '4':   {'box': '4',   'description': 'Exports',                             'amount': 0.0, 'adjustment': 0.0, 'vat_amount': 0.0, 'move_ids': set(), 'invoices_map': {}},
            '5':   {'box': '5',   'description': 'Exempt sales',                         'amount': 0.0, 'adjustment': 0.0, 'vat_amount': 0.0, 'move_ids': set(), 'invoices_map': {}},
        }

        purchase_boxes = {
            '7':   {'box': '7',   'description': 'Standard rated domestic purchases (15%)', 'amount': 0.0, 'adjustment': 0.0, 'vat_amount': 0.0, 'move_ids': set(), 'invoices_map': {}},
            '7.1': {'box': '7.1', 'description': 'Standard rated domestic purchases (5%)',  'amount': 0.0, 'adjustment': 0.0, 'vat_amount': 0.0, 'move_ids': set(), 'invoices_map': {}},
            '8':   {'box': '8',   'description': 'Imports subject to VAT paid at customs (15%)', 'amount': 0.0, 'adjustment': 0.0, 'vat_amount': 0.0, 'move_ids': set(), 'invoices_map': {}},
            '8.1': {'box': '8.1', 'description': 'Imports subject to VAT paid at customs (5%)',  'amount': 0.0, 'adjustment': 0.0, 'vat_amount': 0.0, 'move_ids': set(), 'invoices_map': {}},
            '9':   {'box': '9',   'description': 'Imports subject to VAT accounted for through reverse charge mechanism (15%)', 'amount': 0.0, 'adjustment': 0.0, 'vat_amount': 0.0, 'move_ids': set(), 'invoices_map': {}},
            '9.1': {'box': '9.1', 'description': 'Imports subject to VAT accounted for through reverse charge mechanism (5%)',  'amount': 0.0, 'adjustment': 0.0, 'vat_amount': 0.0, 'move_ids': set(), 'invoices_map': {}},
            '10':  {'box': '10',  'description': 'Zero rated purchases', 'amount': 0.0, 'adjustment': 0.0, 'vat_amount': 0.0, 'move_ids': set(), 'invoices_map': {}},
            '11':  {'box': '11',  'description': 'Exempt purchases',     'amount': 0.0, 'adjustment': 0.0, 'vat_amount': 0.0, 'move_ids': set(), 'invoices_map': {}},
        }

        # Check for overlapping filed tax periods
        overlapping_filings = self.env['analytix.tax.filing'].search([
            ('company_id', 'in', company_ids),
            ('status', '=', 'filed'),
            ('date_from', '<=', end_date),
            ('date_to', '>=', start_date),
        ], order='date_from asc')

        exact_match = (
            len(overlapping_filings) == 1 and
            overlapping_filings[0].date_from == start_date and
            overlapping_filings[0].date_to == end_date
        )

        if overlapping_filings and not exact_match:
            conflict_msgs = []
            for f in overlapping_filings:
                if f.date_from == start_date and f.date_to == end_date:
                    continue
                month_name = f.date_from.strftime('%B %Y') if (f.date_from.month == f.date_to.month and f.date_from.year == f.date_to.year) else f"{f.date_from} to {f.date_to}"
                next_valid_date = f.date_to + relativedelta(days=1)
                conflict_msgs.append(
                    _("Tax filing has already been completed and locked for the period %(period)s (%(d_from)s to %(d_to)s).\n\n"
                      "You cannot select a date range that overlaps with an already filed tax period. "
                      "Please adjust your date range to start after %(d_to)s (e.g. from %(next_date)s), or reopen / unlock the %(period)s tax filing first.") % {
                        'period': month_name,
                        'd_from': f.date_from,
                        'd_to': f.date_to,
                        'next_date': next_valid_date,
                    }
                )
            raise ValidationError("\n\n".join(conflict_msgs))

        existing_filing = overlapping_filings[0] if exact_match else self.env['analytix.tax.filing'].browse()
        is_period_filed = bool(existing_filing)
        if is_period_filed and existing_filing:
            include_prior = bool(existing_filing.prior_move_ids)

        def fetch_lines(move_types, type_tax_use=None):
            if existing_filing:
                curr_domain = [
                    ('move_id', 'in', existing_filing.move_ids.ids),
                    ('tax_line_id', '!=', False),
                ]
                if type_tax_use:
                    curr_domain.append(('tax_line_id.type_tax_use', '=', type_tax_use))
                else:
                    curr_domain.append(('move_id.move_type', 'in', move_types))
                curr_lines = self.env['account.move.line'].search(curr_domain, order='move_id desc')

                prior_domain = [
                    ('move_id', 'in', existing_filing.prior_move_ids.ids),
                    ('tax_line_id', '!=', False),
                ]
                if type_tax_use:
                    prior_domain.append(('tax_line_id.type_tax_use', '=', type_tax_use))
                else:
                    prior_domain.append(('move_id.move_type', 'in', move_types))
                prior_lines = self.env['account.move.line'].search(prior_domain, order='move_id desc')
                return curr_lines, prior_lines

            # 1. Regular current period posted lines (with invoice_date or date fallback)
            curr_domain = [
                ('move_id.state', '=', 'posted'),
                '|',
                '&', ('move_id.invoice_date', '!=', False),
                     '&', ('move_id.invoice_date', '>=', start_date),
                          ('move_id.invoice_date', '<=', end_date),
                '&', ('move_id.invoice_date', '=', False),
                     '&', ('move_id.date', '>=', start_date),
                          ('move_id.date', '<=', end_date),
                ('move_id.company_id', 'in', company_ids),
                ('tax_line_id', '!=', False),
            ]
            if type_tax_use:
                curr_domain.append(('tax_line_id.type_tax_use', '=', type_tax_use))
            else:
                curr_domain.append(('move_id.move_type', 'in', move_types))
            curr_lines = self.env['account.move.line'].search(curr_domain, order='move_id desc')

            # 2. Prior unfiled posted lines (e.g. February invoice entered late)
            prior_domain = [
                ('move_id.state', '=', 'posted'),
                '|',
                '&', ('move_id.invoice_date', '!=', False), ('move_id.invoice_date', '<', start_date),
                '&', ('move_id.invoice_date', '=', False), ('move_id.date', '<', start_date),
                ('move_id.company_id', 'in', company_ids),
                ('tax_line_id', '!=', False),
                '|', ('move_id.tax_filing_status', '=', 'unfiled'), ('move_id.tax_filing_status', '=', False)
            ]
            if type_tax_use:
                prior_domain.append(('tax_line_id.type_tax_use', '=', type_tax_use))
            else:
                prior_domain.append(('move_id.move_type', 'in', move_types))
            prior_lines = self.env['account.move.line'].search(prior_domain, order='move_id desc')
            return curr_lines, prior_lines

        prior_invoices_map = {}

        def build_records(curr_lines, prior_lines, type_use):
            rows = []
            curr_vat_total = 0.0
            prior_vat_total = 0.0
            prior_base_total = 0.0

            # 1. Process current period lines
            for line in curr_lines:
                move = line.move_id
                amt = abs(line.balance)
                total_amt = move.amount_total
                base_amt = abs(line.tax_base_amount)
                m_date = move.invoice_date or move.date or today

                if move.company_id.currency_id != company_currency:
                    try:
                        amt = move.company_id.currency_id._convert(
                            amt, company_currency, move.company_id, m_date)
                    except Exception:
                        pass
                    try:
                        total_amt = move.company_id.currency_id._convert(
                            total_amt, company_currency, move.company_id, m_date)
                    except Exception:
                        pass
                    try:
                        base_amt = move.company_id.currency_id._convert(
                            base_amt, company_currency, move.company_id, m_date)
                    except Exception:
                        pass

                is_refund = move.move_type in ['out_refund', 'in_refund'] or (move.move_type == 'entry' and (line.balance > 0 if type_use == 'sale' else line.balance < 0))
                if is_refund:
                    curr_vat_total -= amt
                else:
                    curr_vat_total += amt

                co = company_color_map.get(move.company_id.id, COMPANY_COLORS[0])
                tax = line.tax_line_id
                name_lower = (tax.name or '').lower()
                rate = abs(tax.amount)
                box_key = None
                box_desc = ''

                if type_use == 'sale':
                    if rate == 15.0:
                        box_key = '1'
                    elif rate == 5.0:
                        box_key = '1.1'
                    elif any(k in name_lower for k in ['healthcare', 'medical', 'education', 'citizen', 'first house', 'first_house']):
                        box_key = '2'
                    elif rate == 0.0 or 'zero' in name_lower or '0%' in name_lower:
                        if 'export' in name_lower or 'خارج' in name_lower:
                            box_key = '4'
                        elif 'exempt' in name_lower or 'معفى' in name_lower or 'معفاه' in name_lower:
                            box_key = '5'
                        else:
                            box_key = '3'
                    else:
                        box_key = '1' if rate > 0 else '3'

                    box = sales_boxes[box_key]
                    box_desc = box['description']
                    if is_refund:
                        box['adjustment'] += base_amt
                        box['vat_amount'] -= amt
                    else:
                        box['amount'] += base_amt
                        box['vat_amount'] += amt

                    box['move_ids'].add(move.id)
                    inv_map = box['invoices_map']
                    signed_base = -base_amt if is_refund else base_amt
                    signed_vat = -amt if is_refund else amt
                    if move.id in inv_map:
                        inv_map[move.id]['base_amount'] += signed_base
                        inv_map[move.id]['tax_amount'] += signed_vat
                    else:
                        inv_map[move.id] = {
                            'id': move.id,
                            'move_name': move.name or '/',
                            'partner_name': move.partner_id.name or '—',
                            'invoice_date': (move.invoice_date or move.date).strftime('%Y-%m-%d') if (move.invoice_date or move.date) else '',
                            'tax_name': line.tax_line_id.name or '—',
                            'tax_rate': rate,
                            'base_amount': signed_base,
                            'tax_amount': signed_vat,
                            'total_amount': total_amt,
                            'move_type': move.move_type,
                            'tax_filing_status': move.tax_filing_status or 'unfiled',
                            'is_locked': bool(move.tax_filing_status == 'filed'),
                            'tax_filing_period': move.tax_filing_period or '',
                            'tax_filing_date': move.tax_filing_date.strftime('%Y-%m-%d') if move.tax_filing_date else '',
                            'state': move.state,
                            'currency_sym': self._get_currency_symbol(move.currency_id),
                            'company_name': move.company_id.name,
                            'box_key': box_key,
                            'box_desc': box_desc,
                        }

                elif type_use == 'purchase':
                    if rate == 15.0:
                        if any(k in name_lower for k in ['import', 'custom', 'الجمارك', 'استيراد']):
                            box_key = '8'
                        elif any(k in name_lower for k in ['rcm', 'reverse', 'عكسي', 'r c']):
                            box_key = '9'
                        else:
                            box_key = '7'
                    elif rate == 5.0:
                        if any(k in name_lower for k in ['import', 'custom', 'الجمارك', 'استيراد']):
                            box_key = '8.1'
                        elif any(k in name_lower for k in ['rcm', 'reverse', 'عكسي', 'r c']):
                            box_key = '9.1'
                        else:
                            box_key = '7.1'
                    elif rate == 0.0 or 'zero' in name_lower or '0%' in name_lower:
                        if 'exempt' in name_lower or 'معفى' in name_lower or 'معفاه' in name_lower:
                            box_key = '11'
                        else:
                            box_key = '10'
                    else:
                        box_key = '7' if rate > 0 else '10'

                    box = purchase_boxes[box_key]
                    box_desc = box['description']
                    if is_refund:
                        box['adjustment'] += base_amt
                        box['vat_amount'] -= amt
                    else:
                        box['amount'] += base_amt
                        box['vat_amount'] += amt

                    box['move_ids'].add(move.id)
                    inv_map = box['invoices_map']
                    signed_base = -base_amt if is_refund else base_amt
                    signed_vat = -amt if is_refund else amt
                    if move.id in inv_map:
                        inv_map[move.id]['base_amount'] += signed_base
                        inv_map[move.id]['tax_amount'] += signed_vat
                    else:
                        inv_map[move.id] = {
                            'id': move.id,
                            'move_name': move.name or '/',
                            'partner_name': move.partner_id.name or '—',
                            'invoice_date': (move.invoice_date or move.date).strftime('%Y-%m-%d') if (move.invoice_date or move.date) else '',
                            'tax_name': line.tax_line_id.name or '—',
                            'tax_rate': rate,
                            'base_amount': signed_base,
                            'tax_amount': signed_vat,
                            'total_amount': total_amt,
                            'move_type': move.move_type,
                            'tax_filing_status': move.tax_filing_status or 'unfiled',
                            'is_locked': bool(move.tax_filing_status == 'filed'),
                            'tax_filing_period': move.tax_filing_period or '',
                            'tax_filing_date': move.tax_filing_date.strftime('%Y-%m-%d') if move.tax_filing_date else '',
                            'state': move.state,
                            'currency_sym': self._get_currency_symbol(move.currency_id),
                            'company_name': move.company_id.name,
                            'box_key': box_key,
                            'box_desc': box_desc,
                        }

                rows.append({
                    'id':           move.id,
                    'move_name':    move.name or '/',
                    'partner':      move.partner_id.name or '—',
                    'tax_name':     line.tax_line_id.name or '—',
                    'tax_rate':     rate,
                    'tax_amount':   amt,
                    'tax_display':  '{} {:,.2f}'.format(self._get_currency_symbol(move.currency_id), abs(line.balance)),
                    'base_amount':  base_amt,
                    'base_display': '{} {:,.2f}'.format(self._get_currency_symbol(move.currency_id), base_amt),
                    'total_amount': total_amt,
                    'total_display':'{} {:,.2f}'.format(self._get_currency_symbol(move.currency_id), move.amount_total),
                    'invoice_date': (move.invoice_date or move.date).strftime('%Y-%m-%d') if (move.invoice_date or move.date) else '',
                    'move_type':    move.move_type,
                    'company_id':   move.company_id.id,
                    'company_name': move.company_id.name,
                    'company_color':co,
                    'currency_sym': self._get_currency_symbol(move.currency_id),
                    'box_key':      box_key or '—',
                    'box_desc':     box_desc,
                    'is_locked':    bool(move.tax_filing_status == 'filed'),
                    'is_prior_period': False,
                    'tax_filing_status': move.tax_filing_status or 'unfiled',
                    'status':       move.state,
                })

            # 2. Process prior period lines (compute totals always; add to rows only if include_prior)
            prior_rows = []
            for line in prior_lines:
                move = line.move_id
                amt = abs(line.balance)
                total_amt = move.amount_total
                base_amt = abs(line.tax_base_amount)
                m_date = move.invoice_date or move.date or today

                if move.company_id.currency_id != company_currency:
                    try:
                        amt = move.company_id.currency_id._convert(
                            amt, company_currency, move.company_id, m_date)
                    except Exception:
                        pass
                    try:
                        total_amt = move.company_id.currency_id._convert(
                            total_amt, company_currency, move.company_id, m_date)
                    except Exception:
                        pass
                    try:
                        base_amt = move.company_id.currency_id._convert(
                            base_amt, company_currency, move.company_id, m_date)
                    except Exception:
                        pass

                is_refund = move.move_type in ['out_refund', 'in_refund'] or (move.move_type == 'entry' and (line.balance > 0 if type_use == 'sale' else line.balance < 0))
                if is_refund:
                    prior_vat_total -= amt
                    prior_base_total -= base_amt
                else:
                    prior_vat_total += amt
                    prior_base_total += base_amt

                co = company_color_map.get(move.company_id.id, COMPANY_COLORS[0])
                tax = line.tax_line_id
                rate = abs(tax.amount)

                signed_base = -base_amt if is_refund else base_amt
                signed_vat = -amt if is_refund else amt
                if move.id in prior_invoices_map:
                    prior_invoices_map[move.id]['base_amount'] += signed_base
                    prior_invoices_map[move.id]['tax_amount'] += signed_vat
                else:
                    prior_invoices_map[move.id] = {
                        'id': move.id,
                        'move_name': move.name or '/',
                        'partner_name': move.partner_id.name or '—',
                        'invoice_date': (move.invoice_date or move.date).strftime('%Y-%m-%d') if (move.invoice_date or move.date) else '',
                        'tax_name': line.tax_line_id.name or '—',
                        'tax_rate': rate,
                        'base_amount': signed_base,
                        'tax_amount': signed_vat,
                        'total_amount': total_amt,
                        'move_type': move.move_type,
                        'tax_filing_status': move.tax_filing_status or 'unfiled',
                        'is_locked': bool(move.tax_filing_status == 'filed'),
                        'tax_filing_period': move.tax_filing_period or '',
                        'tax_filing_date': move.tax_filing_date.strftime('%Y-%m-%d') if move.tax_filing_date else '',
                        'state': move.state,
                        'currency_sym': self._get_currency_symbol(move.currency_id),
                        'company_name': move.company_id.name,
                        'box_key': '14',
                        'box_desc': 'Prior Period Adjustment',
                    }

                prior_rows.append({
                    'id':           move.id,
                    'move_name':    move.name or '/',
                    'partner':      move.partner_id.name or '—',
                    'tax_name':     line.tax_line_id.name or '—',
                    'tax_rate':     rate,
                    'tax_amount':   amt,
                    'tax_display':  '{} {:,.2f}'.format(self._get_currency_symbol(move.currency_id), abs(line.balance)),
                    'base_amount':  base_amt,
                    'base_display': '{} {:,.2f}'.format(self._get_currency_symbol(move.currency_id), base_amt),
                    'total_amount': total_amt,
                    'total_display':'{} {:,.2f}'.format(self._get_currency_symbol(move.currency_id), move.amount_total),
                    'invoice_date': (move.invoice_date or move.date).strftime('%Y-%m-%d') if (move.invoice_date or move.date) else '',
                    'move_type':    move.move_type,
                    'company_id':   move.company_id.id,
                    'company_name': move.company_id.name,
                    'company_color':co,
                    'currency_sym': self._get_currency_symbol(move.currency_id),
                    'box_key':      '14',
                    'box_desc':     'Prior Period Adjustment (Unfiled)',
                    'is_locked':    bool(move.tax_filing_status == 'filed'),
                    'is_prior_period': True,
                    'tax_filing_status': move.tax_filing_status or 'unfiled',
                    'status':       move.state,
                })

            if include_prior:
                rows.extend(prior_rows)

            return rows, curr_vat_total, prior_vat_total, prior_base_total

        out_curr_lines, out_prior_lines = fetch_lines(['out_invoice', 'out_refund', 'entry'], type_tax_use='sale')
        in_curr_lines, in_prior_lines   = fetch_lines(['in_invoice',  'in_refund',  'entry'], type_tax_use='purchase')

        out_records, curr_sales_vat, prior_sales_adj, prior_sales_base = build_records(out_curr_lines, out_prior_lines, 'sale')
        in_records,  curr_purch_vat, prior_purch_adj, prior_purch_base = build_records(in_curr_lines,  in_prior_lines,  'purchase')

        prior_out_moves = set(l.move_id.id for l in out_prior_lines)
        prior_in_moves  = set(l.move_id.id for l in in_prior_lines)
        prior_move_ids  = list(prior_out_moves.union(prior_in_moves))
        prior_unfiled_count = len(prior_move_ids)
        prior_sales_count   = len(prior_out_moves)
        prior_purch_count   = len(prior_in_moves)
        prior_net_adj       = prior_sales_adj - prior_purch_adj

        # Finalize Sales Boxes lists and aggregated invoices
        for b in sales_boxes.values():
            b['move_ids'] = sorted(list(b.get('move_ids', set())))
            b['count'] = len(b['move_ids'])
            b['invoices'] = list(b.get('invoices_map', {}).values())
            b.pop('invoices_map', None)

        sales_total_moves = set()
        sales_total_invs = {}
        for b in [sales_boxes['1'], sales_boxes['1.1'], sales_boxes['2'], sales_boxes['3'], sales_boxes['4'], sales_boxes['5']]:
            sales_total_moves.update(b.get('move_ids', []))
            for inv in b.get('invoices', []):
                if inv['id'] in sales_total_invs:
                    sales_total_invs[inv['id']]['base_amount'] += inv['base_amount']
                    sales_total_invs[inv['id']]['tax_amount'] += inv['tax_amount']
                else:
                    sales_total_invs[inv['id']] = dict(inv)

        sales_list = [
            sales_boxes['1'], sales_boxes['1.1'], sales_boxes['2'],
            sales_boxes['3'], sales_boxes['4'], sales_boxes['5'],
        ]
        total_sales_amt = sum(b['amount'] for b in sales_boxes.values())
        total_sales_adj = sum(b['adjustment'] for b in sales_boxes.values())
        total_sales_vat = sum(b['vat_amount'] for b in sales_boxes.values())

        sales_total_box = {
            'box': '6',
            'description': 'Total Sales',
            'amount': total_sales_amt,
            'adjustment': total_sales_adj,
            'vat_amount': total_sales_vat,
            'move_ids': sorted(list(sales_total_moves)),
            'count': len(sales_total_moves),
            'invoices': list(sales_total_invs.values()),
        }
        sales_list.append(sales_total_box)

        # Finalize Purchases Boxes list and aggregated invoices
        for b in purchase_boxes.values():
            b['move_ids'] = sorted(list(b.get('move_ids', set())))
            b['count'] = len(b['move_ids'])
            b['invoices'] = list(b.get('invoices_map', {}).values())
            b.pop('invoices_map', None)

        purch_total_moves = set()
        purch_total_invs = {}
        for b in [purchase_boxes['7'], purchase_boxes['7.1'], purchase_boxes['8'], purchase_boxes['8.1'], purchase_boxes['9'], purchase_boxes['9.1'], purchase_boxes['10'], purchase_boxes['11']]:
            purch_total_moves.update(b.get('move_ids', []))
            for inv in b.get('invoices', []):
                if inv['id'] in purch_total_invs:
                    purch_total_invs[inv['id']]['base_amount'] += inv['base_amount']
                    purch_total_invs[inv['id']]['tax_amount'] += inv['tax_amount']
                else:
                    purch_total_invs[inv['id']] = dict(inv)

        purchases_list = [
            purchase_boxes['7'], purchase_boxes['7.1'], purchase_boxes['8'],
            purchase_boxes['8.1'], purchase_boxes['9'], purchase_boxes['9.1'],
            purchase_boxes['10'], purchase_boxes['11'],
        ]
        total_purch_amt = sum(b['amount'] for b in purchase_boxes.values())
        total_purch_adj = sum(b['adjustment'] for b in purchase_boxes.values())
        total_purch_vat = sum(b['vat_amount'] for b in purchase_boxes.values())

        purch_total_box = {
            'box': '12',
            'description': 'Total purchases',
            'amount': total_purch_amt,
            'adjustment': total_purch_adj,
            'vat_amount': total_purch_vat,
            'move_ids': sorted(list(purch_total_moves)),
            'count': len(purch_total_moves),
            'invoices': list(purch_total_invs.values()),
        }
        purchases_list.append(purch_total_box)

        # Net VAT (Section 3: Net VAT Due / (Refundable))
        # Prior adjustments are ONLY displayed here in Box 14, in the VAT Amount column.
        curr_net_vat = curr_sales_vat - curr_purch_vat
        curr_all_move_ids = sorted(list(sales_total_moves.union(purch_total_moves)))
        curr_all_invoices = list(sales_total_invs.values()) + list(purch_total_invs.values())

        net_vat_box = {
            'box': '13',
            'description': 'Total VAT due for current period',
            'amount': 0.0,
            'adjustment': 0.0,
            'vat_amount': curr_net_vat,
            'move_ids': curr_all_move_ids,
            'count': len(curr_all_move_ids),
            'invoices': curr_all_invoices,
        }

        prior_invoices_list = list(prior_invoices_map.values())
        if include_prior:
            corrections_box = {
                'box': '14',
                'description': f'Corrections from previous periods ({prior_unfiled_count} unfiled transactions adjusted)' if prior_unfiled_count else 'Corrections from previous periods',
                'amount': 0.0,
                'adjustment': prior_net_adj,
                'vat_amount': prior_net_adj,
                'is_active': True,
                'move_ids': sorted(list(prior_move_ids)),
                'count': prior_unfiled_count,
                'invoices': prior_invoices_list,
            }
            final_net_due = curr_net_vat + prior_net_adj
            output_vat = curr_sales_vat
            input_vat = curr_purch_vat
        else:
            corrections_box = {
                'box': '14',
                'description': 'Corrections from previous periods',
                'amount': 0.0,
                'adjustment': 0.0,
                'vat_amount': 0.0,
                'is_active': False,
                'move_ids': [],
                'count': 0,
                'invoices': [],
            }
            final_net_due = curr_net_vat
            output_vat = curr_sales_vat
            input_vat = curr_purch_vat

        all_due_move_ids = sorted(list(set(curr_all_move_ids).union(set(prior_move_ids if include_prior else []))))
        all_due_invoices = curr_all_invoices + (prior_invoices_list if include_prior else [])
        net_due_box = {
            'box': '15',
            'description': 'Net VAT due (or reclaimed)',
            'amount': 0.0,
            'adjustment': 0.0,
            'vat_amount': final_net_due,
            'move_ids': all_due_move_ids,
            'count': len(all_due_move_ids),
            'invoices': all_due_invoices,
        }

        net_list = [
            net_vat_box,
            corrections_box,
            net_due_box
        ]

        active_comp = self.env.company
        addr_parts = [p for p in [active_comp.street, active_comp.city, active_comp.country_id.name] if p]
        company_info = {
            'id': active_comp.id,
            'name': active_comp.name,
            'vat': active_comp.vat or '',
            'cr': getattr(active_comp, 'company_registry', '') or '',
            'address': ', '.join(addr_parts),
            'phone': active_comp.phone or '',
            'email': active_comp.email or '',
            'website': active_comp.website or '',
            'currency': active_comp.currency_id.name or '',
        }

        sym = self._get_currency_symbol(company_currency)
        return {
            'output_records': out_records,
            'input_records':  in_records,
            'output_count':   len(out_records),
            'input_count':    len(in_records),
            'total_count':    len(out_records) + len(in_records),
            'output_vat':     output_vat,
            'input_vat':      input_vat,
            'net_vat':        final_net_due,
            'curr_output_vat':curr_sales_vat,
            'curr_input_vat': curr_purch_vat,
            'curr_net_vat':   curr_net_vat,
            'currency_sym':   sym,
            'company_info':   company_info,
            'companies':      [{'id': c.id, 'name': c.name, 'vat': c.vat or '', 'color': company_color_map.get(c.id, COMPANY_COLORS[0])} for c in companies],
            'date_range':     {'start': start_date.strftime('%Y-%m-%d'), 'end': end_date.strftime('%Y-%m-%d')},
            'vat_return_sales': sales_list,
            'vat_return_purchases': purchases_list,
            'vat_return_net': net_list,
            'is_period_locked': is_period_filed,
            'filing_id':       existing_filing.id if existing_filing else False,
            'filing_name':     existing_filing.name if existing_filing else None,
            'filing_date':     existing_filing.filing_date.strftime('%Y-%m-%d') if (existing_filing and existing_filing.filing_date) else None,
            'lock_status_label': 'Filed & Locked' if is_period_filed else 'Open / To-be Filed',
            'include_prior':   include_prior,
            'prior_count':     prior_unfiled_count,
            'prior_unfiled_count': prior_unfiled_count,
            'prior_sales_count':   prior_sales_count,
            'prior_purch_count':   prior_purch_count,
            'prior_sales_base':    prior_sales_base,
            'prior_sales_adj':     prior_sales_adj,
            'prior_purch_base':    prior_purch_base,
            'prior_purch_adj':     prior_purch_adj,
            'prior_net_adj':       prior_net_adj,
            'prior_move_ids':      prior_move_ids,
        }


    @api.model
    def export_analytix_vat_xlsx(self, filter_name='this_month', date_from=None, date_to=None, include_prior=False):
        """Generate and return a base64 encoded native .xlsx binary file for ZATCA VAT Return."""
        import io
        import base64
        import xlsxwriter

        vat_data = self.get_analytix_vat_data(filter_name=filter_name, date_from=date_from, date_to=date_to, include_prior=include_prior)
        sym = vat_data.get('currency_sym', '')
        date_range = vat_data.get('date_range', {})
        start_str = date_range.get('start', '')
        end_str = date_range.get('end', '')

        companies = [c['name'] for c in vat_data.get('companies', [])]
        company_str = ', '.join(companies) if companies else (self.env.company.name or 'All Companies')

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('VAT Return Summary')

        # Enable grid lines explicitly
        worksheet.hide_gridlines(2)

        # Set Column Widths
        worksheet.set_column(0, 0, 10)  # Box #
        worksheet.set_column(1, 1, 65)  # Description
        worksheet.set_column(2, 2, 22)  # Amount (Base)
        worksheet.set_column(3, 3, 22)  # Adjustment
        worksheet.set_column(4, 4, 22)  # VAT Amount

        # Formats
        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 16, 'font_name': 'Arial',
            'bg_color': '#0f172a', 'font_color': '#ffffff',
            'align': 'center', 'valign': 'vcenter'
        })
        meta_fmt = workbook.add_format({
            'font_size': 11, 'font_name': 'Arial',
            'bg_color': '#f8fafc', 'font_color': '#475569',
            'align': 'center', 'valign': 'vcenter'
        })
        section_hdr_fmt = workbook.add_format({
            'bold': True, 'font_size': 13, 'font_name': 'Arial',
            'bg_color': '#1e3a8a', 'font_color': '#ffffff',
            'align': 'left', 'valign': 'vcenter',
            'border': 1, 'border_color': '#1e3a8a'
        })
        tbl_hdr_fmt = workbook.add_format({
            'bold': True, 'font_size': 11, 'font_name': 'Arial',
            'bg_color': '#e2e8f0', 'font_color': '#0f172a',
            'border': 1, 'border_color': '#cbd5e1', 'align': 'center', 'valign': 'vcenter'
        })
        cell_box_fmt = workbook.add_format({
            'font_size': 11, 'font_name': 'Arial',
            'border': 1, 'border_color': '#cbd5e1', 'align': 'center', 'valign': 'vcenter'
        })
        cell_desc_fmt = workbook.add_format({
            'font_size': 11, 'font_name': 'Arial',
            'border': 1, 'border_color': '#cbd5e1', 'align': 'left', 'valign': 'vcenter'
        })
        cell_num_fmt = workbook.add_format({
            'font_size': 11, 'font_name': 'Arial',
            'num_format': '#,##0.00', 'border': 1, 'border_color': '#cbd5e1', 'align': 'right', 'valign': 'vcenter'
        })
        total_lbl_fmt = workbook.add_format({
            'bold': True, 'font_size': 11, 'font_name': 'Arial',
            'bg_color': '#f1f5f9', 'font_color': '#0f172a',
            'border': 1, 'border_color': '#cbd5e1', 'align': 'left', 'valign': 'vcenter'
        })
        total_num_fmt = workbook.add_format({
            'bold': True, 'font_size': 11, 'font_name': 'Arial',
            'bg_color': '#f1f5f9', 'num_format': '#,##0.00', 'border': 1, 'border_color': '#cbd5e1', 'align': 'right', 'valign': 'vcenter'
        })
        adj_lbl_fmt = workbook.add_format({
            'bold': True, 'font_size': 11, 'font_name': 'Arial', 'italic': True,
            'bg_color': '#f0fdf4', 'font_color': '#166534',
            'border': 1, 'border_color': '#bbf7d0', 'align': 'left', 'valign': 'vcenter'
        })
        adj_num_fmt = workbook.add_format({
            'bold': True, 'font_size': 11, 'font_name': 'Arial',
            'bg_color': '#f0fdf4', 'font_color': '#166534',
            'num_format': '#,##0.00', 'border': 1, 'border_color': '#bbf7d0', 'align': 'right', 'valign': 'vcenter'
        })
        adj_box_fmt = workbook.add_format({
            'bold': True, 'font_size': 11, 'font_name': 'Arial',
            'bg_color': '#f0fdf4', 'font_color': '#166534',
            'border': 1, 'border_color': '#bbf7d0', 'align': 'center', 'valign': 'vcenter'
        })
        net_lbl_fmt = workbook.add_format({
            'bold': True, 'font_size': 12, 'font_name': 'Arial',
            'bg_color': '#f0fdf4', 'font_color': '#166534',
            'border': 2, 'border_color': '#86efac', 'align': 'left', 'valign': 'vcenter'
        })
        net_num_fmt = workbook.add_format({
            'bold': True, 'font_size': 12, 'font_name': 'Arial',
            'bg_color': '#f0fdf4', 'num_format': '#,##0.00', 'border': 2, 'border_color': '#86efac', 'align': 'right', 'valign': 'vcenter'
        })

        # Row height settings
        worksheet.set_row(0, 35)
        worksheet.merge_range(0, 0, 0, 4, '  VAT RETURN SUMMARY (ZATCA)', title_fmt)
        worksheet.set_row(1, 24)
        meta_text = f"Company: {company_str}  |  Period: {start_str} to {end_str}  |  Currency: {sym}"
        worksheet.merge_range(1, 0, 1, 4, meta_text, meta_fmt)

        row = 3

        def write_headers(r):
            worksheet.set_row(r, 26)
            worksheet.write(r, 0, 'Box #', tbl_hdr_fmt)
            worksheet.write(r, 1, 'Description', tbl_hdr_fmt)
            worksheet.write(r, 2, f'Amount (Base) ({sym})', tbl_hdr_fmt)
            worksheet.write(r, 3, f'Adjustment ({sym})', tbl_hdr_fmt)
            worksheet.write(r, 4, f'VAT Amount ({sym})', tbl_hdr_fmt)

        # 1. VAT on Sales
        worksheet.set_row(row, 28)
        worksheet.merge_range(row, 0, row, 4, ' 1. VAT on Sales', section_hdr_fmt)
        row += 1
        write_headers(row)
        
        sales_data = vat_data.get('vat_return_sales', [])
        for box in sales_data:
            row += 1
            worksheet.set_row(row, 22)
            is_tot = (box['box'] == '6')
            is_adj = bool(box.get('is_adjustment_row'))
            fmt_lbl = total_lbl_fmt if is_tot else (adj_lbl_fmt if is_adj else cell_desc_fmt)
            fmt_num = total_num_fmt if is_tot else (adj_num_fmt if is_adj else cell_num_fmt)
            fmt_box = total_lbl_fmt if is_tot else (adj_box_fmt if is_adj else cell_box_fmt)
            
            worksheet.write(row, 0, box['box'], fmt_box)
            worksheet.write(row, 1, box['description'], fmt_lbl)
            worksheet.write(row, 2, '' if is_adj else box['amount'], fmt_num)
            worksheet.write(row, 3, box['adjustment'], fmt_num)
            worksheet.write(row, 4, '' if is_adj else box['vat_amount'], fmt_num)

        row += 2
        # 2. VAT on Purchases
        worksheet.set_row(row, 28)
        worksheet.merge_range(row, 0, row, 4, ' 2. VAT on Purchases', section_hdr_fmt)
        row += 1
        write_headers(row)
        
        purchases_data = vat_data.get('vat_return_purchases', [])
        for box in purchases_data:
            row += 1
            worksheet.set_row(row, 22)
            is_tot = (box['box'] == '12')
            is_adj = bool(box.get('is_adjustment_row'))
            fmt_lbl = total_lbl_fmt if is_tot else (adj_lbl_fmt if is_adj else cell_desc_fmt)
            fmt_num = total_num_fmt if is_tot else (adj_num_fmt if is_adj else cell_num_fmt)
            fmt_box = total_lbl_fmt if is_tot else (adj_box_fmt if is_adj else cell_box_fmt)
            
            worksheet.write(row, 0, box['box'], fmt_box)
            worksheet.write(row, 1, box['description'], fmt_lbl)
            worksheet.write(row, 2, '' if is_adj else box['amount'], fmt_num)
            worksheet.write(row, 3, box['adjustment'], fmt_num)
            worksheet.write(row, 4, '' if is_adj else box['vat_amount'], fmt_num)

        row += 2
        # 3. Net VAT Due
        worksheet.set_row(row, 28)
        worksheet.merge_range(row, 0, row, 4, ' 3. Net VAT Due', section_hdr_fmt)
        row += 1
        write_headers(row)
        
        net_data = vat_data.get('vat_return_net', [])
        for box in net_data:
            row += 1
            worksheet.set_row(row, 24)
            is_net_final = (box['box'] == '15')
            is_box_14 = (box['box'] == '14')
            fmt_lbl = net_lbl_fmt if is_net_final else (adj_lbl_fmt if (is_box_14 and box.get('is_active')) else cell_desc_fmt)
            fmt_num = net_num_fmt if is_net_final else (adj_num_fmt if (is_box_14 and box.get('is_active')) else cell_num_fmt)
            fmt_box = net_lbl_fmt if is_net_final else (adj_box_fmt if (is_box_14 and box.get('is_active')) else cell_box_fmt)
            
            worksheet.write(row, 0, box['box'], fmt_box)
            worksheet.write(row, 1, box['description'], fmt_lbl)
            worksheet.write(row, 2, box['amount'] if box.get('amount') else '', fmt_num)
            worksheet.write(row, 3, box['adjustment'] if (not is_box_14 and box.get('adjustment')) else '', fmt_num)
            worksheet.write(row, 4, box['vat_amount'] if (box.get('vat_amount') or is_net_final or (is_box_14 and box.get('is_active'))) else '', fmt_num)

        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read()).decode('utf-8')
        filename = f"Tax_Summary_{start_str}_to_{end_str}.xlsx"

        return {
            'filename': filename,
            'file_content': file_data,
        }

    @api.model
    def export_analytix_vat_detailed_xlsx(self, filter_name='custom', date_from=None, date_to=None, company_filter='all', search_query='', sort_col=None, sort_dir='asc', include_prior=False):
        """Generate and return a base64 encoded native .xlsx binary file for Detailed VAT Return."""
        import io
        import base64
        import xlsxwriter

        vat_data = self.get_analytix_vat_data(filter_name=filter_name, date_from=date_from, date_to=date_to, include_prior=include_prior)
        sym = vat_data.get('currency_sym', '')
        date_range = vat_data.get('date_range', {})
        start_str = date_range.get('start', '')
        end_str = date_range.get('end', '')

        companies = [c['name'] for c in vat_data.get('companies', [])]
        company_str = ', '.join(companies) if companies else (self.env.company.name or 'All Companies')

        out_records = vat_data.get('output_records', [])
        in_records = vat_data.get('input_records', [])

        # Filter by company
        if company_filter != 'all':
            try:
                cid = int(company_filter)
                out_records = [r for r in out_records if r['company_id'] == cid]
                in_records = [r for r in in_records if r['company_id'] == cid]
            except ValueError:
                pass

        # Filter by search query
        if search_query and search_query.strip():
            q = search_query.strip().lower()
            out_records = [r for r in out_records if q in (r.get('move_name') or '').lower() or q in (r.get('partner') or '').lower() or q in (r.get('tax_name') or '').lower()]
            in_records = [r for r in in_records if q in (r.get('move_name') or '').lower() or q in (r.get('partner') or '').lower() or q in (r.get('tax_name') or '').lower()]

        # Sort records
        if sort_col:
            reverse = sort_dir == 'desc'
            def get_val(r):
                val = r.get(sort_col)
                if val is None:
                    return ''
                if isinstance(val, str):
                    return val.lower()
                return val
            
            out_records.sort(key=get_val, reverse=reverse)
            in_records.sort(key=get_val, reverse=reverse)

        # Recalculate totals
        total_output_vat = sum(r.get('tax_amount', 0.0) for r in out_records)
        total_input_vat = sum(r.get('tax_amount', 0.0) for r in in_records)
        net_vat_payable = total_output_vat - total_input_vat
        total_count = len(out_records) + len(in_records)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Detailed VAT Report')

        # Enable grid lines explicitly
        worksheet.hide_gridlines(2)

        # Set Column Widths
        worksheet.set_column(0, 0, 20)  # Document
        worksheet.set_column(1, 1, 35)  # Customer / Vendor
        worksheet.set_column(2, 2, 20)  # Tax
        worksheet.set_column(3, 3, 20)  # Company
        worksheet.set_column(4, 4, 15)  # Date
        worksheet.set_column(5, 5, 20)  # Total Amount
        worksheet.set_column(6, 6, 20)  # VAT Amount

        # Formats
        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 14, 'font_name': 'Arial',
            'bg_color': '#0f172a', 'font_color': '#ffffff',
            'align': 'center', 'valign': 'vcenter'
        })
        meta_fmt = workbook.add_format({
            'font_size': 10, 'font_name': 'Arial',
            'bg_color': '#f8fafc', 'font_color': '#475569',
            'align': 'center', 'valign': 'vcenter'
        })
        
        # KPI Card format
        kpi_lbl_fmt = workbook.add_format({
            'font_size': 9, 'font_name': 'Arial', 'bold': True,
            'bg_color': '#f8fafc', 'font_color': '#64748b',
            'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#cbd5e1'
        })
        kpi_val_out_fmt = workbook.add_format({
            'font_size': 11, 'font_name': 'Arial', 'bold': True,
            'bg_color': '#f8fafc', 'font_color': '#1e88e5', 'num_format': f'"{sym} "#,##0.00',
            'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#cbd5e1'
        })
        kpi_val_in_fmt = workbook.add_format({
            'font_size': 11, 'font_name': 'Arial', 'bold': True,
            'bg_color': '#f8fafc', 'font_color': '#e53935', 'num_format': f'"{sym} "#,##0.00',
            'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#cbd5e1'
        })
        kpi_val_net_fmt = workbook.add_format({
            'font_size': 11, 'font_name': 'Arial', 'bold': True,
            'bg_color': '#f8fafc', 'font_color': '#2e7d32', 'num_format': f'"{sym} "#,##0.00',
            'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#cbd5e1'
        })
        kpi_val_tot_fmt = workbook.add_format({
            'font_size': 11, 'font_name': 'Arial', 'bold': True,
            'bg_color': '#f8fafc', 'font_color': '#0f172a', 'num_format': '#,##0',
            'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#cbd5e1'
        })

        section_hdr_sales_fmt = workbook.add_format({
            'bold': True, 'font_size': 11, 'font_name': 'Arial',
            'bg_color': '#1e3a8a', 'font_color': '#ffffff',
            'align': 'left', 'valign': 'vcenter',
            'border': 1, 'border_color': '#1e3a8a'
        })
        section_hdr_purch_fmt = workbook.add_format({
            'bold': True, 'font_size': 11, 'font_name': 'Arial',
            'bg_color': '#7f1d1d', 'font_color': '#ffffff',
            'align': 'left', 'valign': 'vcenter',
            'border': 1, 'border_color': '#7f1d1d'
        })
        tbl_hdr_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'font_name': 'Arial',
            'bg_color': '#e2e8f0', 'font_color': '#0f172a',
            'border': 1, 'border_color': '#cbd5e1', 'align': 'center', 'valign': 'vcenter'
        })
        cell_center_fmt = workbook.add_format({
            'font_size': 10, 'font_name': 'Arial',
            'border': 1, 'border_color': '#cbd5e1', 'align': 'center', 'valign': 'vcenter'
        })
        cell_desc_fmt = workbook.add_format({
            'font_size': 10, 'font_name': 'Arial',
            'border': 1, 'border_color': '#cbd5e1', 'align': 'left', 'valign': 'vcenter'
        })
        cell_num_fmt = workbook.add_format({
            'font_size': 10, 'font_name': 'Arial',
            'num_format': '#,##0.00', 'border': 1, 'border_color': '#cbd5e1', 'align': 'right', 'valign': 'vcenter'
        })
        total_lbl_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'font_name': 'Arial',
            'bg_color': '#f1f5f9', 'font_color': '#0f172a',
            'border': 1, 'border_color': '#cbd5e1', 'align': 'left', 'valign': 'vcenter'
        })
        total_num_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'font_name': 'Arial',
            'bg_color': '#f1f5f9', 'num_format': '#,##0.00', 'border': 1, 'border_color': '#cbd5e1', 'align': 'right', 'valign': 'vcenter'
        })

        # Title
        worksheet.set_row(0, 30)
        worksheet.merge_range(0, 0, 0, 6, '  VAT DETAILED SUMMARY REPORT', title_fmt)
        worksheet.set_row(1, 20)
        meta_text = f"Company: {company_str}  |  Period: {start_str} to {end_str}  |  Currency: {sym}"
        worksheet.merge_range(1, 0, 1, 6, meta_text, meta_fmt)

        # KPI Summary Cards (row 3 & 4)
        worksheet.set_row(3, 16)
        worksheet.set_row(4, 20)
        
        # 1. Output VAT (Sales)
        worksheet.write(3, 0, 'OUTPUT VAT (SALES)', kpi_lbl_fmt)
        worksheet.write(4, 0, total_output_vat, kpi_val_out_fmt)
        
        # 2. Input VAT (Bills)
        worksheet.write(3, 2, 'INPUT VAT (BILLS)', kpi_lbl_fmt)
        worksheet.write(4, 2, total_input_vat, kpi_val_in_fmt)
        
        # 3. Net VAT Payable
        worksheet.write(3, 4, 'NET VAT PAYABLE', kpi_lbl_fmt)
        worksheet.write(4, 4, net_vat_payable, kpi_val_net_fmt)
        
        # 4. Total Tax Lines
        worksheet.write(3, 6, 'TOTAL TAX LINES', kpi_lbl_fmt)
        worksheet.write(4, 6, total_count, kpi_val_tot_fmt)

        row = 6

        # Helper to write headers
        def write_headers(r, partner_hdr):
            worksheet.set_row(r, 24)
            worksheet.write(r, 0, 'Document', tbl_hdr_fmt)
            worksheet.write(r, 1, partner_hdr, tbl_hdr_fmt)
            worksheet.write(r, 2, 'Tax', tbl_hdr_fmt)
            worksheet.write(r, 3, 'Company', tbl_hdr_fmt)
            worksheet.write(r, 4, 'Date', tbl_hdr_fmt)
            worksheet.write(r, 5, f'Total Amount ({sym})', tbl_hdr_fmt)
            worksheet.write(r, 6, f'VAT Amount ({sym})', tbl_hdr_fmt)

        # Helper to write table rows
        def write_table_rows(start_row, records):
            curr_row = start_row
            sum_total = 0.0
            sum_vat = 0.0
            for rec in records:
                worksheet.set_row(curr_row, 20)
                worksheet.write(curr_row, 0, rec.get('move_name', '/'), cell_center_fmt)
                worksheet.write(curr_row, 1, rec.get('partner', '—'), cell_desc_fmt)
                worksheet.write(curr_row, 2, rec.get('tax_name', '—'), cell_center_fmt)
                worksheet.write(curr_row, 3, rec.get('company_name', '—'), cell_desc_fmt)
                worksheet.write(curr_row, 4, rec.get('invoice_date', ''), cell_center_fmt)
                worksheet.write(curr_row, 5, rec.get('total_amount', 0.0), cell_num_fmt)
                worksheet.write(curr_row, 6, rec.get('tax_amount', 0.0), cell_num_fmt)
                sum_total += rec.get('total_amount', 0.0)
                sum_vat += rec.get('tax_amount', 0.0)
                curr_row += 1
            
            # Total row
            worksheet.set_row(curr_row, 22)
            worksheet.write(curr_row, 0, 'Total', total_lbl_fmt)
            worksheet.write(curr_row, 1, '', total_lbl_fmt)
            worksheet.write(curr_row, 2, '', total_lbl_fmt)
            worksheet.write(curr_row, 3, '', total_lbl_fmt)
            worksheet.write(curr_row, 4, '', total_lbl_fmt)
            worksheet.write(curr_row, 5, sum_total, total_num_fmt)
            worksheet.write(curr_row, 6, sum_vat, total_num_fmt)
            return curr_row + 1

        # 1. Output VAT - Customer Invoices
        worksheet.set_row(row, 24)
        worksheet.merge_range(row, 0, row, 6, ' OUTPUT VAT — CUSTOMER INVOICES', section_hdr_sales_fmt)
        row += 1
        write_headers(row, 'Customer')
        row += 1
        if not out_records:
            worksheet.set_row(row, 20)
            worksheet.merge_range(row, 0, row, 6, 'No output VAT lines found.', cell_center_fmt)
            row += 1
        else:
            row = write_table_rows(row, out_records)

        row += 2

        # 2. Input VAT - Vendor Bills
        worksheet.set_row(row, 24)
        worksheet.merge_range(row, 0, row, 6, ' INPUT VAT — VENDOR BILLS', section_hdr_purch_fmt)
        row += 1
        write_headers(row, 'Vendor')
        row += 1
        if not in_records:
            worksheet.set_row(row, 20)
            worksheet.merge_range(row, 0, row, 6, 'No input VAT lines found.', cell_center_fmt)
            row += 1
        else:
            row = write_table_rows(row, in_records)

        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read()).decode('utf-8')
        filename = f"Tax_Detailed_{start_str}_to_{end_str}.xlsx"

        return {
            'filename': filename,
            'file_content': file_data,
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
                'amount_display': '{} {:,.2f}'.format(self._get_currency_symbol(company_currency), amt),
                'company_id':     move.company_id.id,
                'company_name':   move.company_id.name,
                'company_color':  co_color,
            })

        return {
            'records':      records,
            'total_count':  len(records),
            'total_amount': total_amount,
            'currency_sym': self._get_currency_symbol(company_currency),
            'companies':    [{'id': c.id, 'name': c.name, 'color': company_color_map.get(c.id, COMPANY_COLORS[0])} for c in companies],
            'date_range':   {'start': start_date.strftime('%Y-%m-%d') if start_date else 'All Time', 'end': end_date.strftime('%Y-%m-%d') if end_date else 'All Time'},
        }

    @api.model
    def get_analytix_pl_data(self, filter_name='this_month', date_from=None, date_to=None, compare_date_from=None, compare_date_to=None):
        """Return P&L (Profit & Loss) data with optional comparison period for dashboard modal preview."""
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
        sym = self._get_currency_symbol(company_currency)

        def build_pl_period(s_date, e_date):
            def fetch_section(account_types, negate=False):
                if not account_types:
                    return [], 0.0
                groups = self.env['account.move.line'].read_group(
                    domain=[
                        ('move_id.state', '=', 'posted'),
                        ('move_id.date', '>=', s_date),
                        ('move_id.date', '<=', e_date),
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

            income_accs,  income_total  = fetch_section(['income'],                negate=True)
            cogs_accs,    cogs_total    = fetch_section(['expense_direct_cost'],   negate=False)
            expense_accs, expense_total = fetch_section(['expense', 'expense_depreciation'], negate=False)
            oincome_accs, oincome_total = fetch_section(['income_other'],          negate=True)

            gross_profit          = round(income_total - cogs_total,            2)
            net_operating_income  = round(gross_profit - expense_total,         2)
            net_other_income      = round(oincome_total,                        2)
            net_income            = round(net_operating_income + net_other_income, 2)

            return {
                'period_label': '{} - {}'.format(s_date.strftime('%m/%d/%Y'), e_date.strftime('%m/%d/%Y')),
                'income':       {'accounts': income_accs,  'total': income_total},
                'cogs':         {'accounts': cogs_accs,    'total': cogs_total},
                'gross_profit': gross_profit,
                'expense':      {'accounts': expense_accs, 'total': expense_total},
                'net_operating_income': net_operating_income,
                'other_income': {'accounts': oincome_accs, 'total': oincome_total},
                'net_other_income':     net_other_income,
                'net_income':           net_income,
            }

        primary = build_pl_period(start_date, end_date)
        result = {
            'period_label': '{} – {}'.format(start_date.strftime('%d %b %Y'), end_date.strftime('%d %b %Y')),
            'period_from_iso': str(start_date),
            'period_to_iso': str(end_date),
            'year':         end_date.year,
            'currency_sym': sym,
            'company':      ', '.join(self.env.companies.mapped('name')),
        }
        result.update(primary)

        # Build comparison dataset if requested
        cmp_start = None
        cmp_end = None
        if compare_date_from and compare_date_to:
            try:
                cmp_start = datetime.strptime(str(compare_date_from), '%Y-%m-%d').date()
                cmp_end   = datetime.strptime(str(compare_date_to),   '%Y-%m-%d').date()
            except Exception:
                cmp_start = start_date - relativedelta(years=1)
                cmp_end   = end_date - relativedelta(years=1)
        elif compare_date_from:
            cmp_start = start_date - relativedelta(years=1)
            cmp_end   = end_date - relativedelta(years=1)

        if cmp_start and cmp_end:
            result['compare'] = build_pl_period(cmp_start, cmp_end)
            result['compare_from_iso'] = str(cmp_start)
            result['compare_to_iso']   = str(cmp_end)

        return result

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
        sym = self._get_currency_symbol(self.env.company.currency_id)

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
    def get_analytix_trial_balance_data(self, filter_name='this_month', date_from=None, date_to=None, target_moves='posted', hide_zero='hide', hierarchy_level='none'):
        """Return trial balance data: per-account debit/credit/balance grouped by account type."""
        self = self.sudo()
        today = date.today()

        # Parse date_from and date_to if provided
        parsed_from = None
        parsed_to = None
        if date_from:
            try:
                parsed_from = datetime.strptime(str(date_from)[:10], '%Y-%m-%d').date() if isinstance(date_from, str) else date_from
            except Exception:
                parsed_from = None
        if date_to:
            try:
                parsed_to = datetime.strptime(str(date_to)[:10], '%Y-%m-%d').date() if isinstance(date_to, str) else date_to
            except Exception:
                parsed_to = None

        if filter_name == 'custom' and parsed_from and parsed_to:
            start_date = parsed_from
            end_date = parsed_to
        elif parsed_from and parsed_to and filter_name not in ('this_month', 'last_month', 'this_quarter', 'last_3_months', 'this_year', 'last_year'):
            start_date = parsed_from
            end_date = parsed_to
        elif filter_name == 'this_month':
            start_date = today.replace(day=1)
            end_date = start_date + relativedelta(months=1, days=-1)
        elif filter_name == 'last_month':
            first_of_this_month = today.replace(day=1)
            end_date = first_of_this_month - relativedelta(days=1)
            start_date = end_date.replace(day=1)
        elif filter_name == 'this_quarter':
            q_month = ((today.month - 1) // 3) * 3 + 1
            start_date = today.replace(month=q_month, day=1)
            end_date = start_date + relativedelta(months=3, days=-1)
        elif filter_name == 'last_3_months':
            start_date = today.replace(day=1) - relativedelta(months=2)
            end_date = start_date + relativedelta(months=3, days=-1)
        elif filter_name == 'this_year':
            start_date = today.replace(month=1, day=1)
            end_date = today.replace(month=12, day=31)
        elif filter_name == 'last_year':
            start_date = today.replace(year=today.year - 1, month=1, day=1)
            end_date = today.replace(year=today.year - 1, month=12, day=31)
        elif parsed_from and parsed_to:
            start_date = parsed_from
            end_date = parsed_to
        else:
            start_date = today.replace(day=1)
            end_date = start_date + relativedelta(months=1, days=-1)

        company_ids = self.env.companies.ids or [self.env.company.id]
        company_currency = self.env.company.currency_id
        sym = self._get_currency_symbol(company_currency)

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

        TYPE_ORDER = {
            'asset':     1,
            'liability': 2,
            'equity':    3,
            'income':    4,
            'expense':   5,
        }

        TYPE_CFG = {
            'asset':     {'label': 'Assets',      'bg': '#e3f2fd', 'text': '#1565c0', 'dot': '#1e88e5', 'icon': 'fa-bank'},
            'liability': {'label': 'Liabilities', 'bg': '#fce4ec', 'text': '#c62828', 'dot': '#e53935', 'icon': 'fa-credit-card'},
            'equity':    {'label': 'Equities',    'bg': '#f3e5f5', 'text': '#6a1b9a', 'dot': '#8e24aa', 'icon': 'fa-pie-chart'},
            'income':    {'label': 'Income',      'bg': '#e8f5e9', 'text': '#2e7d32', 'dot': '#43a047', 'icon': 'fa-arrow-up'},
            'expense':   {'label': 'Expense',     'bg': '#fff3e0', 'text': '#e65100', 'dot': '#fb8c00', 'icon': 'fa-arrow-down'},
        }

        # Target move domain condition
        if target_moves == 'all':
            move_state_domain = [('move_id.state', '!=', 'cancel')]
        else:
            move_state_domain = [('move_id.state', '=', 'posted')]

        # Read initial balances (lines before start_date)
        init_domain = move_state_domain + [
            ('move_id.date', '<', start_date),
            ('company_id', 'in', company_ids),
        ]
        init_groups = self.env['account.move.line'].read_group(
            domain=init_domain,
            fields=['account_id', 'debit:sum', 'credit:sum', 'company_id'],
            groupby=['account_id', 'company_id'],
            lazy=False,
        )

        # Read period activity (lines from start_date to end_date)
        period_domain = move_state_domain + [
            ('move_id.date', '>=', start_date),
            ('move_id.date', '<=', end_date),
            ('company_id', 'in', company_ids),
        ]
        period_groups = self.env['account.move.line'].read_group(
            domain=period_domain,
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

        is_hide_zero = hide_zero in (True, 'hide', 'Hide')

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

            if is_hide_zero and init_bal == 0.0 and debit == 0.0 and credit == 0.0 and period_bal == 0.0 and ending_bal == 0.0:
                continue

            if hierarchy_level and hierarchy_level not in ('none', 'No limit', 'no_limit'):
                max_digits = {'level_1': 2, 'level_2': 4, 'level_3': 6}.get(hierarchy_level)
                if max_digits and len(acc_code) > max_digits:
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
                'type_seq':             TYPE_ORDER.get(type_group, 99),
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

        # Default sort by Main Type sequence: Assets (1), Liabilities (2), Equities (3), Income (4), Expense (5), then by Code
        records.sort(key=lambda r: (r.get('type_seq', 99), r['code'] or '', r['name'] or ''))

        last_type = None
        for r in records:
            if r.get('type_group') != last_type:
                r['is_first_of_group'] = True
                last_type = r.get('type_group')
            else:
                r['is_first_of_group'] = False

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
            'target_moves':   target_moves,
            'hide_zero':      hide_zero,
            'hierarchy_level': hierarchy_level,
            'filter_name':    filter_name,
        }
