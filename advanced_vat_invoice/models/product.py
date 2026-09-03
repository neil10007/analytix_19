# -*- coding: utf-8 -*-
from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    product_arabic_name = fields.Char(string='Product Arabic Name')


class ProductProduct(models.Model):
    _inherit = 'product.product'

    product_arabic_name = fields.Char(
        string='Product Arabic Name',
        related='product_tmpl_id.product_arabic_name',
        readonly=False,
        store=True,
    )
