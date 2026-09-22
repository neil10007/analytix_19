# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    hide_receipt_header_qr = fields.Boolean(
        related='pos_config_id.hide_receipt_header_qr',
        readonly=False,
    )
