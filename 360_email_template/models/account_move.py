# -*- coding: utf-8 -*-
from io import BytesIO
import base64
from odoo import api, models, _
from odoo.exceptions import UserError

try:
    import qrcode
except ImportError:
    qrcode = None


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.depends('state')
    def generate_qrcode(self):
        """Override generate_qrcode to fix batch processing singleton error without modifying advanced_vat_invoice."""
        param = self.env['ir.config_parameter'].sudo()
        qr_code = param.get_param('advanced_vat_invoice.generate_qr')
        for rec in self:
            if rec.state == 'posted':
                if qrcode and base64:
                    if qr_code == 'automatically':
                        qr = qrcode.QRCode(
                            version=4,
                            error_correction=qrcode.constants.ERROR_CORRECT_L,
                            box_size=4,
                            border=1,
                        )
                        target = rec._origin if rec._origin else rec
                        if hasattr(target, 'qr_code_data'):
                            qr.add_data(target.qr_code_data())
                            qr.make(fit=True)
                            img = qr.make_image()
                            temp = BytesIO()
                            img.save(temp, format="PNG")
                            rec.qr = base64.b64encode(temp.getvalue())
                else:
                    raise UserError(
                        _('Necessary Requirements To Run This Operation Is Not Satisfied')
                    )

    def generate_qr_button(self):
        """Override generate_qr_button to fix manual QR generation batch safety."""
        param = self.env['ir.config_parameter'].sudo()
        qr_code = param.get_param('advanced_vat_invoice.generate_qr')
        for rec in self:
            if qrcode and base64:
                if qr_code == 'manually':
                    qr = qrcode.QRCode(
                        version=4,
                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                        box_size=4,
                        border=1,
                    )
                    target = rec._origin if rec._origin else rec
                    if hasattr(target, 'qr_code_data'):
                        qr.add_data(target.qr_code_data())
                        qr.make(fit=True)
                        img = qr.make_image()
                        temp = BytesIO()
                        img.save(temp, format="PNG")
                        rec.qr = base64.b64encode(temp.getvalue())
            else:
                raise UserError(
                    _('Necessary Requirements To Run This Operation Is Not Satisfied')
                )
