# -*- coding: utf-8 -*-
from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    hide_receipt_header_qr = fields.Boolean(
        string="Hide Header QR Code (Below Logo)",
        default=True,
        help="If checked, the QR code right below the company logo will be hidden on POS receipts.",
    )
