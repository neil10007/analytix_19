# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    product_arabic_name = fields.Char(string='Product Arabic Name')

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        if 'product_arabic_name' not in fields_list:
            fields_list.append('product_arabic_name')
        return fields_list


class ProductProduct(models.Model):
    _inherit = 'product.product'

    product_arabic_name = fields.Char(
        string='Product Arabic Name',
        related='product_tmpl_id.product_arabic_name',
        readonly=False,
    )

    @api.model
    def _load_pos_data_fields(self, config):
        fields_list = super()._load_pos_data_fields(config)
        if 'product_arabic_name' not in fields_list:
            fields_list.append('product_arabic_name')
        return fields_list
