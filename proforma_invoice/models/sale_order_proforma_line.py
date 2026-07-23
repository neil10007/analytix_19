# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SaleOrderProformaLine(models.Model):
    _name = 'sale.order.proforma.line'
    _description = "Proforma Line"
    _order = 'sequence, id'

    # -------------------------------------------------------------------------
    # BASIC INFORMATION
    # -------------------------------------------------------------------------
    name = fields.Text(string="Description", required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    display_type = fields.Selection([
        ('line_section', "Section"),
        ('line_note', "Note"),
    ], string="Display Type", default=False, help="Technical field for section/note lines.")

    company_id = fields.Many2one('res.company', string="Company", related='proforma_id.company_id', store=True)
    currency_id = fields.Many2one('res.currency', related='proforma_id.currency_id', store=True)
    proforma_id = fields.Many2one('sale.order.proforma', string="Proforma Reference", ondelete='cascade')

    # -------------------------------------------------------------------------
    # PRODUCT FIELDS
    # -------------------------------------------------------------------------
    product_id = fields.Many2one(
        'product.product', string="Product",
        domain="[('sale_ok', '=', True)]"
    )
    product_uom_qty = fields.Float(string="Quantity", default=1.0)
    product_uom = fields.Many2one(
        'uom.uom', string="Unit of Measure"
    )
    product_type = fields.Selection(related='product_id.type', store=True)
    price_unit = fields.Float(string="Unit Price")
    discount = fields.Float(string="Discount (%)", digits='Discount', default=0.0)

    # -------------------------------------------------------------------------
    # TAXES & ACCOUNTS
    # -------------------------------------------------------------------------
    tax_id = fields.Many2many(
        'account.tax', string="Taxes",
        domain="[('type_tax_use', '=', 'sale')]"
    )
    analytic_distribution = fields.Json(string="Analytic Distribution")
    analytic_precision = fields.Integer(
        string="Analytic Precision",
        store=False,
        default=lambda self: self.env['decimal.precision'].precision_get('Percentage Analytic'),
    )

    # -------------------------------------------------------------------------
    # AMOUNTS
    # -------------------------------------------------------------------------
    price_subtotal = fields.Monetary(string="Subtotal", compute='_compute_amount', store=True)
    price_tax = fields.Monetary(string="Tax Amount", compute='_compute_amount', store=True)
    price_total = fields.Monetary(string="Total", compute='_compute_amount', store=True)

    # -------------------------------------------------------------------------
    # INVOICE RELATION
    # -------------------------------------------------------------------------
    invoice_lines = fields.Many2many('account.move.line', string="Invoice Lines", copy=False)
    qty_invoiced = fields.Float(string="Invoiced Quantity", compute='_compute_qty_invoiced', store=True)

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends('price_unit', 'discount', 'product_uom_qty', 'tax_id', 'currency_id')
    def _compute_amount(self):
        """Compute amounts including taxes."""
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(
                price, line.currency_id, line.product_uom_qty, product=line.product_id
            )
            line.price_subtotal = taxes['total_excluded']
            line.price_total = taxes['total_included']
            line.price_tax = taxes['total_included'] - taxes['total_excluded']

    @api.depends('invoice_lines.move_id.state')
    def _compute_qty_invoiced(self):
        """Compute total quantity invoiced for this line."""
        for line in self:
            qty = 0.0
            for inv_line in line.invoice_lines.filtered(lambda l: l.move_id.state != 'cancel'):
                if inv_line.move_id.move_type == 'out_refund':
                    qty -= inv_line.quantity
                else:
                    qty += inv_line.quantity
            line.qty_invoiced = qty

    # -------------------------------------------------------------------------
    # ONCHANGE METHODS
    # -------------------------------------------------------------------------
    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Update fields automatically when selecting a product."""
        if not self.product_id:
            return

        product = self.product_id
        self.name = product.get_product_multiline_description_sale() or product.display_name
        self.product_uom = product.uom_id
        self.price_unit = product.lst_price

        if product.taxes_id:
            company = self.proforma_id.company_id or self.env.company
            self.tax_id = product.taxes_id.filtered(lambda t: t.company_id == company)


    # -------------------------------------------------------------------------
    # BUSINESS LOGIC HELPERS
    # -------------------------------------------------------------------------
    def _prepare_base_line_for_taxes_computation(self, **kwargs):
        """ Convert the current record to a dictionary in order to use the generic taxes computation method
        defined on account.tax.
        """
        self.ensure_one()
        company = self.proforma_id.company_id or self.env.company
        base_values = {
            'tax_ids': self.tax_id,
            'quantity': self.product_uom_qty,
            'partner_id': self.proforma_id.partner_id,
            'currency_id': self.proforma_id.currency_id or company.currency_id,
            'rate': 1.0,
            'name': self.name,
        }
        base_values.update(kwargs)
        return self.env['account.tax']._prepare_base_line_for_taxes_computation(self, **base_values)

    # -------------------------------------------------------------------------
    # DISPLAY NAME
    # -------------------------------------------------------------------------
    @api.depends('name', 'product_id', 'product_uom_qty', 'product_uom')
    def _compute_display_name(self):
        """Display product with quantity for clarity."""
        for line in self:
            name = line.name or line.product_id.display_name or ''
            if line.product_uom_qty and line.product_uom:
                name = f"{name} ({line.product_uom_qty:g} {line.product_uom.name})"
            line.display_name = name
