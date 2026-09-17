from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from .ai_gl_config import EXPENSE_BILLS_TYPES

class AccountMove(models.Model):
    _inherit = 'account.move'

    expense_bills_type = fields.Selection(
        selection=EXPENSE_BILLS_TYPES,
        string='AI Expense Type',
        help='Expense Category detected by AI Document Processor'
    )

    partner_street = fields.Char(
        string='Street',
        related='partner_id.street',
        readonly=False,
    )
    partner_street2 = fields.Char(
        string='Street 2',
        related='partner_id.street2',
        readonly=False,
    )
    partner_city = fields.Char(
        string='City',
        related='partner_id.city',
        readonly=False,
    )
    partner_state_id = fields.Many2one(
        'res.country.state',
        string='State',
        related='partner_id.state_id',
        readonly=False,
    )
    partner_zip = fields.Char(
        string='ZIP',
        related='partner_id.zip',
        readonly=False,
    )
    partner_country_id = fields.Many2one(
        'res.country',
        string='Country',
        related='partner_id.country_id',
        readonly=False,
    )
    partner_vat = fields.Char(
        string='Tax ID',
        related='partner_id.vat',
        readonly=False,
    )

    ai_validation_status = fields.Selection([
        ('matched', 'Fully Matched'),
        ('warning', 'Mismatch / Warning Detected'),
    ], string='AI Validation Status', default='matched')

    ai_validation_notes = fields.Html(
        string='AI Validation Details & Mismatches',
        help='Summarizes inventory, tax, and total mismatches detected during AI document parsing.',
        sanitize=False,
    )

    tax_filing_status = fields.Selection([
        ('unfiled', 'Unfiled'),
        ('filed', 'Filed & Locked')
    ], string='Tax Filing Status', default='unfiled', copy=False, index=True)
    tax_filing_date = fields.Date(string='Tax Filing Date', copy=False)
    tax_filing_period = fields.Char(string='Tax Filing Period', copy=False)
    tax_filing_id = fields.Many2one('analytix.tax.filing', string='Tax Filing Reference', copy=False, ondelete='set null')

    is_tax_locked = fields.Boolean(
        string='Is Tax Filed & Locked',
        compute='_compute_is_tax_locked',
        help='Indicates whether this invoice has been included in a filed and locked VAT return.'
    )

    @api.depends('tax_filing_status')
    def _compute_is_tax_locked(self):
        for move in self:
            move.is_tax_locked = (move.tax_filing_status == 'filed')

    @api.model
    def mark_tax_filed_and_locked(self, date_from, date_to, include_prior=False):
        """Mark tax return as filed & locked for the period [date_from, date_to].
        Includes regular period posted tax lines, plus any unfiled transactions from prior periods."""
        has_manager = self.env.user.has_group('account.group_account_manager') or self.env.is_admin()
        if not has_manager:
            raise UserError(_("Only an Accounting Manager or Administrator can mark tax returns as filed."))

        if not date_from or not date_to:
            raise UserError(_("Please specify valid start and end dates for the filing period."))

        try:
            d_from = datetime.strptime(date_from, '%Y-%m-%d').date() if isinstance(date_from, str) else date_from
            d_to = datetime.strptime(date_to, '%Y-%m-%d').date() if isinstance(date_to, str) else date_to
        except Exception as e:
            raise UserError(_("Invalid date format: %s") % str(e))

        company_ids = self.env.context.get('allowed_company_ids') or [self.env.company.id]
        company = self.env.company
        today = fields.Date.context_today(self)

        # Check for overlapping filed tax periods
        filing_model = self.env['analytix.tax.filing'].sudo()
        overlapping_filings = filing_model.search([
            ('company_id', 'in', company_ids),
            ('status', '=', 'filed'),
            ('date_from', '<=', d_to),
            ('date_to', '>=', d_from),
        ], order='date_from asc')

        exact_match = (
            len(overlapping_filings) == 1 and
            overlapping_filings[0].date_from == d_from and
            overlapping_filings[0].date_to == d_to
        )

        if overlapping_filings and not exact_match:
            conflict_msgs = []
            for f in overlapping_filings:
                if f.date_from == d_from and f.date_to == d_to:
                    continue
                month_name = f.date_from.strftime('%B %Y') if (f.date_from.month == f.date_to.month and f.date_from.year == f.date_to.year) else f"{f.date_from} to {f.date_to}"
                next_valid_date = f.date_to + relativedelta(days=1)
                conflict_msgs.append(
                    _("Tax filing has already been completed and locked for the period %(period)s (%(d_from)s to %(d_to)s).\n\n"
                      "You cannot file a tax return for a date range that overlaps with an already filed tax period. "
                      "Please adjust your date range to start after %(d_to)s (e.g. from %(next_date)s), or reopen / unlock the %(period)s tax filing first.") % {
                        'period': month_name,
                        'd_from': f.date_from,
                        'd_to': f.date_to,
                        'next_date': next_valid_date,
                    }
                )
            raise UserError("\n\n".join(conflict_msgs))

        # 1. Moves within current period (with invoice_date or date fallback)
        current_moves = self.sudo().search([
            ('company_id', 'in', company_ids),
            ('state', '=', 'posted'),
            ('move_type', 'in', ['out_invoice', 'out_refund', 'in_invoice', 'in_refund']),
            '|',
            '&', ('invoice_date', '!=', False),
                 '&', ('invoice_date', '>=', d_from),
                      ('invoice_date', '<=', d_to),
            '&', ('invoice_date', '=', False),
                 '&', ('date', '>=', d_from),
                      ('date', '<=', d_to),
        ])

        # 2. Unfiled moves from prior periods (e.g. February invoice entered late during April-June filing)
        prior_domain = [
            ('company_id', 'in', company_ids),
            ('state', '=', 'posted'),
            ('move_type', 'in', ['out_invoice', 'out_refund', 'in_invoice', 'in_refund']),
            '|',
            '&', ('invoice_date', '!=', False), ('invoice_date', '<', d_from),
            '&', ('invoice_date', '=', False), ('date', '<', d_from),
            '|', ('tax_filing_status', '=', 'unfiled'), ('tax_filing_status', '=', False)
        ]
        prior_moves = self.sudo().search(prior_domain) if include_prior else self.sudo().browse()

        existing_filing = overlapping_filings[0] if exact_match else filing_model.search([
            ('company_id', '=', company.id),
            ('date_from', '=', d_from),
            ('date_to', '=', d_to),
        ], limit=1)

        # Classify frequency and format name
        period_type = filing_model.classify_period_type(d_from, d_to)
        type_labels = {
            'monthly': _("Monthly"),
            'quarterly': _("Quarterly (3M)"),
            'semi_annual': _("Semi-Annual (6M)"),
            'yearly': _("Annual"),
            'custom': _("Custom"),
        }
        type_str = type_labels.get(period_type, _("VAT Return"))
        filing_title = f"{type_str} Filing ({d_from} to {d_to})"

        # Compute accurate VAT totals for this filing
        total_sales_base = 0.0
        output_vat = 0.0
        total_purch_base = 0.0
        input_vat = 0.0
        sales_adj = 0.0
        purch_adj = 0.0

        try:
            vat_summary = self.get_analytix_vat_data(filter_name='custom', date_from=str(d_from), date_to=str(d_to), include_prior=include_prior)
            sales_boxes = {b['box']: b for b in vat_summary.get('vat_return_sales', [])}
            purch_boxes = {b['box']: b for b in vat_summary.get('vat_return_purchases', [])}
            net_boxes   = {b['box']: b for b in vat_summary.get('vat_return_net', [])}

            total_sales_base = sales_boxes.get('6', {}).get('amount', 0.0)
            output_vat       = vat_summary.get('output_vat', 0.0)
            total_purch_base = purch_boxes.get('12', {}).get('amount', 0.0)
            input_vat        = vat_summary.get('input_vat', 0.0)
            sales_adj        = vat_summary.get('prior_sales_adj', 0.0) if include_prior else 0.0
            purch_adj        = vat_summary.get('prior_purch_adj', 0.0) if include_prior else 0.0
            net_vat          = vat_summary.get('net_vat', 0.0)
        except Exception:
            for m in current_moves:
                if m.move_type in ['out_invoice', 'out_refund']:
                    sign = -1 if m.move_type == 'out_refund' else 1
                    total_sales_base += m.amount_untaxed * sign
                    output_vat += m.amount_tax * sign
                elif m.move_type in ['in_invoice', 'in_refund']:
                    sign = -1 if m.move_type == 'in_refund' else 1
                    total_purch_base += m.amount_untaxed * sign
                    input_vat += m.amount_tax * sign
            if include_prior:
                for pm in prior_moves:
                    if pm.move_type in ['out_invoice', 'out_refund']:
                        sign = -1 if pm.move_type == 'out_refund' else 1
                        sales_adj += pm.amount_tax * sign
                    elif pm.move_type in ['in_invoice', 'in_refund']:
                        sign = -1 if pm.move_type == 'in_refund' else 1
                        purch_adj += pm.amount_tax * sign
                net_vat = (output_vat + sales_adj) - (input_vat + purch_adj)
            else:
                net_vat = output_vat - input_vat

        filing_vals = {
            'name': filing_title,
            'company_id': company.id,
            'date_from': d_from,
            'date_to': d_to,
            'filing_date': today,
            'period_type': period_type,
            'status': 'filed',
            'total_sales': total_sales_base,
            'total_purchases': total_purch_base,
            'output_vat': output_vat,
            'input_vat': input_vat,
            'sales_adjustment': sales_adj,
            'purchase_adjustment': purch_adj,
            'net_vat': net_vat,
            'move_ids': [(6, 0, current_moves.ids)],
            'prior_move_ids': [(6, 0, prior_moves.ids)],
        }

        if existing_filing:
            existing_filing.write(filing_vals)
            filing = existing_filing
        else:
            filing = filing_model.create(filing_vals)

        # Tag current period moves as filed
        period_str = f"{d_from} to {d_to}"
        if current_moves:
            current_moves.write({
                'tax_filing_status': 'filed',
                'tax_filing_date': today,
                'tax_filing_period': period_str,
                'tax_filing_id': filing.id,
            })

        # Tag prior adjustment moves as filed under this filing
        if prior_moves:
            prior_moves.write({
                'tax_filing_status': 'filed',
                'tax_filing_date': today,
                'tax_filing_period': f"{period_str} (Adjustment)",
                'tax_filing_id': filing.id,
            })

        total_affected = len(current_moves) + len(prior_moves)
        msg = _("Tax filing for %(period)s marked as Filed & Locked. %(cur)d current transactions and %(prior)d prior period adjustment(s) are now filed.",
                period=period_str, cur=len(current_moves), prior=len(prior_moves))

        return {
            'success': True,
            'filing_id': filing.id,
            'period': period_str,
            'current_count': len(current_moves),
            'prior_count': len(prior_moves),
            'total_count': total_affected,
            'message': msg,
        }

    @api.model
    def unfile_tax_period(self, date_from, date_to):
        """Unlock / Reopen a previously filed tax return period."""
        has_manager = self.env.user.has_group('account.group_account_manager') or self.env.is_admin()
        if not has_manager:
            raise UserError(_("Only an Accounting Manager or Administrator can unfile tax returns."))

        if not date_from or not date_to:
            raise UserError(_("Please specify valid start and end dates."))

        try:
            d_from = datetime.strptime(date_from, '%Y-%m-%d').date() if isinstance(date_from, str) else date_from
            d_to = datetime.strptime(date_to, '%Y-%m-%d').date() if isinstance(date_to, str) else date_to
        except Exception as e:
            raise UserError(_("Invalid date format: %s") % str(e))

        company_ids = self.env.context.get('allowed_company_ids') or [self.env.company.id]
        filing_model = self.env['analytix.tax.filing'].sudo()
        filings = filing_model.search([
            ('company_id', 'in', company_ids),
            ('date_from', '=', d_from),
            ('date_to', '=', d_to),
        ])

        total_unfiled = 0
        for f in filings:
            all_moves = f.move_ids | f.prior_move_ids
            total_unfiled += len(all_moves)
            all_moves.write({
                'tax_filing_status': 'unfiled',
                'tax_filing_date': False,
                'tax_filing_period': False,
                'tax_filing_id': False,
            })
            f.write({'status': 'unfiled'})

        return {
            'success': True,
            'unfiled_count': total_unfiled,
            'message': _("Tax filing for %(period)s has been reopened / unfiled. %(count)d transactions are now marked as Unfiled.",
                         period=f"{d_from} to {d_to}", count=total_unfiled)
        }


