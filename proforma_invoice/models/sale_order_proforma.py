# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.tools import is_html_empty
from odoo.tools.mail import html_keep_url


class SaleOrderProforma(models.Model):
    _name = 'sale.order.proforma'
    _description = 'Proforma Invoice'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    # -------------------------------------------------------------------------
    # BASIC INFORMATION
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Sequence", required=True, copy=False, readonly=True,
        default=lambda self: _('New')
    )
    proforma_date = fields.Date(string="Date", default=fields.Date.context_today)
    user_id = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user)
    approved_user_id = fields.Many2one('res.users', 'Approved By', tracking=True)
    order_id = fields.Many2one('sale.order', string='SO Number', domain="[('partner_id', '=', partner_id)]")
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    partner_id = fields.Many2one(
        'res.partner', string="Customer", required=True
    )
    bank_partner_id = fields.Many2one('res.partner', related="company_id.partner_id", store=True)
    sales_amount_total = fields.Monetary(string="SO Total", related="order_id.amount_total", store=True, tracking=4)
    state = fields.Selection([
        ('draft', "Draft"),
        ('requested', "PI Requested"),
        ('approved', "PI Approved"),
        ('cancel', "Cancelled"),
    ], default='draft', string="Status", tracking=True)
    terms_type = fields.Selection(related='company_id.terms_type')

    # -------------------------------------------------------------------------
    # Currency
    # -------------------------------------------------------------------------

    currency_new_id = fields.Many2one(
        'res.currency', string="Base Currency",
        compute='_compute_currency_new_id', store=True, readonly=False, precompute=True
    )

    # -------------------------------------------------------------------------
    # AMOUNTS AND TAXES
    # -------------------------------------------------------------------------
    amount_total = fields.Monetary(string="Total", compute='_compute_amounts', store=True, tracking=4)
    amount_untaxed = fields.Monetary(string="Untaxed Amount", compute='_compute_amounts', store=True, tracking=5)
    amount_tax = fields.Monetary(string="Taxes", compute='_compute_amounts', store=True)
    tax_totals = fields.Binary(compute='_compute_tax_totals', exportable=False)

    # -------------------------------------------------------------------------
    # RELATIONS
    # -------------------------------------------------------------------------
    pricelist_id = fields.Many2one('product.pricelist', related='order_id.pricelist_id')
    currency_id = fields.Many2one('res.currency', related='currency_new_id', store=True)
    tax_country_id = fields.Many2one('res.country', related='order_id.tax_country_id')
    tax_calculation_rounding_method = fields.Selection(related='order_id.tax_calculation_rounding_method')

    proforma_line_ids = fields.One2many(
        'sale.order.proforma.line', 'proforma_id', string="Proforma Lines",
        copy=True
    )

    # -------------------------------------------------------------------------
    # BANK & COMPANY FIELDS
    # -------------------------------------------------------------------------
    bank_id = fields.Many2one('res.partner.bank', string="Bank Account", domain="[('id', 'in', company_bank_ids)]")
    company_bank_ids = fields.One2many(
        'res.partner.bank', compute='_compute_company_bank_ids', string="Company Banks",
        help="Technical field used to filter available bank accounts based on the company."
    )

    # -------------------------------------------------------------------------
    # INVOICES
    # -------------------------------------------------------------------------
    invoice_count = fields.Integer(string="Invoice Count", compute='_get_invoice_count', store=True)
    invoice_ids = fields.Many2many('account.move', compute='_get_invoice_count', store=True, copy=False)

    # -------------------------------------------------------------------------
    # TERMS & CONDITIONS
    # -------------------------------------------------------------------------
    note = fields.Html(
        string="Terms and conditions", compute='_compute_note',
        store=True, readonly=False, precompute=True
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends('order_id')
    def _compute_currency_new_id(self):
        for order in self:
            if order.order_id:
                order.currency_new_id = order.order_id.currency_id
            else:
                order.currency_new_id = order.company_id.currency_id or self.env.company.currency_id

    @api.depends('proforma_line_ids.invoice_lines')
    def _get_invoice_count(self):
        for order in self:
            invoices = order.proforma_line_ids.invoice_lines.mapped('move_id').filtered(
                lambda r: r.move_type in ('out_invoice', 'out_refund')
            )
            order.invoice_ids = invoices
            order.invoice_count = len(invoices)

    @api.depends('proforma_line_ids.price_subtotal', 'proforma_line_ids.price_tax', 'proforma_line_ids.price_total')
    def _compute_amounts(self):
        """Compute the total amounts of the Proforma."""
        AccountTax = self.env['account.tax']
        for order in self:
            order = order.with_company(order.company_id)
            lines = order.proforma_line_ids.filtered(lambda x: not x.display_type)

            base_lines = [line._prepare_base_line_for_taxes_computation() for line in lines]
            AccountTax._add_tax_details_in_base_lines(base_lines, order.company_id)
            AccountTax._round_base_lines_tax_details(base_lines, order.company_id)
            tax_totals = AccountTax._get_tax_totals_summary(
                base_lines=base_lines,
                currency=order.currency_id or order.company_id.currency_id,
                company=order.company_id,
            )

            order.amount_untaxed = tax_totals.get('base_amount_currency', 0.0)
            order.amount_tax = tax_totals.get('tax_amount_currency', 0.0)
            order.amount_total = tax_totals.get('total_amount_currency', 0.0)

    @api.depends('proforma_line_ids.price_subtotal', 'proforma_line_ids.price_tax', 'proforma_line_ids.price_total')
    def _compute_tax_totals(self):
        """Compute the tax totals binary dictionary for the UI."""
        AccountTax = self.env['account.tax']
        for order in self:
            order = order.with_company(order.company_id)
            lines = order.proforma_line_ids.filtered(lambda x: not x.display_type)

            base_lines = [line._prepare_base_line_for_taxes_computation() for line in lines]
            AccountTax._add_tax_details_in_base_lines(base_lines, order.company_id)
            AccountTax._round_base_lines_tax_details(base_lines, order.company_id)
            tax_totals = AccountTax._get_tax_totals_summary(
                base_lines=base_lines,
                currency=order.currency_id or order.company_id.currency_id,
                company=order.company_id,
            )

            order.tax_totals = tax_totals

    @api.depends('company_id')
    def _compute_company_bank_ids(self):
        for rec in self:
            rec.company_bank_ids = rec.company_id.bank_ids
            if rec.company_id.bank_ids and len(rec.company_id.bank_ids) == 1:
                rec.bank_id = rec.company_id.bank_ids[0]
            elif rec.bank_id not in rec.company_id.bank_ids:
                rec.bank_id = False

    @api.model
    def _get_note_url(self):
        return self.env.company.get_base_url()

    @api.depends('partner_id')
    def _compute_note(self):
        """Set Terms and Conditions automatically."""
        use_invoice_terms = self.env['ir.config_parameter'].sudo().get_param('account.use_invoice_terms')
        if not use_invoice_terms:
            return
        for order in self:
            order = order.with_company(order.company_id)
            if order.terms_type == 'html' and self.env.company.invoice_terms_html:
                baseurl = html_keep_url(order._get_note_url() + '/terms')
                order.note = _('Terms & Conditions: %s', baseurl)
            elif not is_html_empty(self.env.company.invoice_terms):
                if order.partner_id.lang:
                    order = order.with_context(lang=order.partner_id.lang)
                order.note = order.env.company.invoice_terms

    # -------------------------------------------------------------------------
    # BUTTON ACTIONS
    # -------------------------------------------------------------------------
    def action_pi_request(self):
        """Send notification to approvers when PI is requested."""
        self.state = 'requested'

        proforma_group = self.env.ref('proforma_invoice.group_sale_proforma_approver')
        approver = proforma_group.user_ids.filtered(lambda u: u.company_id == self.company_id and u.email)
        if not approver:
            return

        approver = approver[0]
        approver_email = approver.email or 'no-reply@example.com'
        approver_name = approver.name or 'Approver'

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        proforma_url = f"{base_url}/web#id={self.id}&model=sale.order.proforma&view_type=form"

        html_body = f'''
            <p>Dear {approver_name},</p>
            <p>
                A Sale Order Proforma <strong>{self.name}</strong> has been requested by
                <strong>{self.create_uid.name}</strong> for
                <strong>{self.partner_id.name or 'N/A'}</strong>.
            </p>
            <p>
                <a href="{proforma_url}"
                   style="background-color:#875A7B; padding:10px 16px; text-decoration:none; color:#fff; border-radius:5px;">
                   View Sale Order Proforma
                </a>
            </p>
            <p>Regards,<br/>{self.create_uid.name}</p>
        '''

        self.env['mail.mail'].sudo().create({
            'subject': _('Sale Order Proforma Requested for %s') % self.name,
            'body_html': html_body,
            'email_to': approver_email,
            'auto_delete': True,
            'email_from': self.env.user.email or 'no-reply@example.com',
        }).send()

    def action_pi_approve(self):
        """Approve the proforma and send notification."""
        self.ensure_one()  # ✅ Added: Ensures we're working with a single record
        # Set the approved user to the current user
        self.approved_user_id = self.env.user
        self.state = 'approved'

        # Get the approvers group and find the current approver's name
        proforma_group = self.env.ref('proforma_invoice.group_sale_proforma_approver')
        current_user = self.env.user

        # ✅ Check if current user is in the approver group
        is_approver = current_user in proforma_group.user_ids

        # ✅ Get approver name - either from current user or fallback
        if is_approver:
            approver_name = current_user.name or 'Approver'
            approver_email = current_user.email or 'erp@analytix.org'
        else:
            approver_name = 'Approver'
            approver_email = 'erp@analytix.org'

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        proforma_url = f"{base_url}/web#id={self.id}&model=sale.order.proforma&view_type=form"

        html_body = f'''
            <p>Dear {self.create_uid.name},</p>
            <p>
                Your Sale Order Proforma <strong>{self.name}</strong> has been approved by
                <strong>{approver_name}</strong> for
                <strong>{self.partner_id.name or 'N/A'}</strong>.
            </p>
            <p>
                <a href="{proforma_url}"
                   style="background-color:#875A7B; padding:10px 16px; text-decoration:none; color:#fff; border-radius:5px;">
                   View Sale Order Proforma
                </a>
            </p>
            <p>Regards,<br/>{approver_name}</p>
        '''

        self.env['mail.mail'].sudo().create({
            'subject': _('Sale Order Proforma Approved for %s') % self.name,
            'body_html': html_body,
            'email_to': self.create_uid.email or 'no-reply@example.com',
            'auto_delete': True,
            'email_from': approver_email,
        }).send()

    def action_cancel(self):
        self.state = 'cancel'

    def action_draft(self):
        self.state = 'draft'
        self.approved_user_id = False

    # -------------------------------------------------------------------------
    # INVOICE ACTIONS
    # -------------------------------------------------------------------------
    def _prepare_invoice_vals(self):
        """Prepare values for invoice creation from the proforma."""
        self.ensure_one()

        # Ensure currency_id is properly set
        if not self.currency_id:
            # Fallback to company currency if proforma currency is not set
            currency_id = self.company_id.currency_id.id
        else:
            currency_id = self.currency_id.id

        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': fields.Date.today(),
            'currency_id': currency_id,
            'company_id': self.company_id.id,
            'proforma_id': self.id,
            'invoice_origin': self.name,
            'invoice_line_ids': [],
        }

        for line in self.proforma_line_ids:
            line_vals = {
                'name': line.name or line.product_id.display_name,
                'product_id': line.product_id.id,
                'quantity': line.product_uom_qty,
                'price_unit': line.price_unit,
                'tax_ids': [(6, 0, line.tax_id.ids)],
                'currency_id': currency_id,
            }
            invoice_vals['invoice_line_ids'].append((0, 0, line_vals))

        return invoice_vals

    def action_create_invoice(self):
        self.ensure_one()
        invoice_vals = self._prepare_invoice_vals()
        invoice = self.env['account.move'].create(invoice_vals)

        # For each proforma line, find the corresponding invoice line
        for line in self.proforma_line_ids:
            # Find the invoice line for this product (should be only one)
            invoice_line = invoice.invoice_line_ids.filtered(
                lambda l: l.product_id == line.product_id
            )
            # Now invoice_line is a recordset, potentially multiple lines
            if invoice_line:
                # Ensure we get the correct line (usually first one if multiple)
                # Or use a more specific condition
                if len(invoice_line) > 1:
                    # If multiple lines found, try to match by description or sequence
                    invoice_line = invoice_line.filtered(
                        lambda l: l.name == line.name or l.sequence == line.sequence
                    )
                # Take the first matching line
                if invoice_line:
                    invoice_line = invoice_line[0]  # Get singleton
                    line.write({'invoice_lines': [(4, invoice_line.id)]})





    def action_view_invoice(self):
        return {
            'name': _('Invoices'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'domain': [('invoice_origin', '=', self.name)],
            'view_mode': 'list,form',
            'target': 'current',
        }

    # -------------------------------------------------------------------------
    # CREATE / OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.order.proforma') or _('New')
            if 'company_id' not in vals:
                vals['company_id'] = self.env.company.id
        return super().create(vals_list)
