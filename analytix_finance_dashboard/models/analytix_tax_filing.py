# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, date

class AnalytixTaxFiling(models.Model):
    _name = 'analytix.tax.filing'
    _description = 'Analytix Tax Return Filing'
    _order = 'date_to desc, id desc'

    name = fields.Char(string='Filing Reference', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string='Currency', readonly=True)

    date_from = fields.Date(string='Period From', required=True)
    date_to = fields.Date(string='Period To', required=True)
    filing_date = fields.Date(string='Filing Date', default=fields.Date.context_today)

    period_type = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly (3 Months)'),
        ('semi_annual', 'Semi-Annual (6 Months)'),
        ('yearly', 'Yearly / Annual'),
        ('custom', 'Custom Period'),
    ], string='Filing Frequency', default='quarterly', required=True)

    status = fields.Selection([
        ('filed', 'Filed & Locked'),
        ('unfiled', 'Reopened / Draft')
    ], string='Status', default='filed', required=True)

    total_sales = fields.Monetary(string='Sales Base Amount', currency_field='currency_id')
    total_purchases = fields.Monetary(string='Purchases Base Amount', currency_field='currency_id')
    output_vat = fields.Monetary(string='Output VAT (Sales)', currency_field='currency_id')
    input_vat = fields.Monetary(string='Input VAT (Purchases)', currency_field='currency_id')
    sales_adjustment = fields.Monetary(string='Output VAT Adjustment (Prior Unfiled)', currency_field='currency_id')
    purchase_adjustment = fields.Monetary(string='Input VAT Adjustment (Prior Unfiled)', currency_field='currency_id')
    net_vat = fields.Monetary(string='Net VAT Payable / (Due)', currency_field='currency_id')

    move_ids = fields.Many2many(
        'account.move',
        'analytix_tax_filing_move_rel',
        'filing_id',
        'move_id',
        string='Filed Invoices & Bills'
    )
    prior_move_ids = fields.Many2many(
        'account.move',
        'analytix_tax_filing_prior_move_rel',
        'filing_id',
        'move_id',
        string='Prior Period Adjustment Invoices'
    )

    current_count = fields.Integer(string='Current Invoices Count', compute='_compute_counts')
    prior_count = fields.Integer(string='Prior Adjustments Count', compute='_compute_counts')
    total_count = fields.Integer(string='Total Invoices & Bills', compute='_compute_counts')

    notes = fields.Text(string='Notes / Description')

    @api.depends('move_ids', 'prior_move_ids')
    def _compute_counts(self):
        for rec in self:
            rec.current_count = len(rec.move_ids)
            rec.prior_count = len(rec.prior_move_ids)
            rec.total_count = rec.current_count + rec.prior_count

    @api.model
    def classify_period_type(self, d_from, d_to):
        """Helper to determine filing frequency from date_from and date_to."""
        if not d_from or not d_to:
            return 'custom'
        if isinstance(d_from, str):
            d_from = datetime.strptime(d_from, '%Y-%m-%d').date()
        if isinstance(d_to, str):
            d_to = datetime.strptime(d_to, '%Y-%m-%d').date()
        days = (d_to - d_from).days + 1

        if 27 <= days <= 35:
            return 'monthly'
        elif 80 <= days <= 100:
            return 'quarterly'
        elif 170 <= days <= 195:
            return 'semi_annual'
        elif 355 <= days <= 370:
            return 'yearly'
        return 'custom'

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'name': _("Invoices & Bills — %s", self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.move_ids.ids)],
            'target': 'current',
        }

    def action_view_prior_adjustments(self):
        self.ensure_one()
        return {
            'name': _("Prior Adjustments — %s", self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.prior_move_ids.ids)],
            'target': 'current',
        }

    def action_reopen_filing(self):
        """Unfile / Reopen this tax return period."""
        self.ensure_one()
        has_manager = self.env.user.has_group('account.group_account_manager') or self.env.is_admin()
        if not has_manager:
            raise UserError(_("Only an Accounting Manager or Administrator can reopen tax filings."))

        date_from_str = self.date_from.strftime('%Y-%m-%d')
        date_to_str = self.date_to.strftime('%Y-%m-%d')
        res = self.env['account.move'].unfile_tax_period(date_from_str, date_to_str)
        self.write({'status': 'unfiled'})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Filing Reopened"),
                'message': res.get('message', _("Tax filing has been reopened.")),
                'sticky': False,
                'type': 'warning',
            }
        }
