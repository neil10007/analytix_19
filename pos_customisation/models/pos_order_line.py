# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    product_arabic_name = fields.Char(
        string='Product Arabic Name',
        related='product_id.product_arabic_name',
        readonly=True,
    )

    @api.model
    def _load_pos_data_fields(self, config):
        fields_list = super()._load_pos_data_fields(config)
        if 'product_arabic_name' not in fields_list:
            fields_list.append('product_arabic_name')
        return fields_list
