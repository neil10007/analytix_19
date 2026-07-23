# -*- coding: utf-8 -*-

from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _handle_debug(cls):
        """
        Intercept Odoo's debug mode handler. Strictly force debug mode to be
        disabled/cleared if the active user ID is not 2. This prevents any
        non-admin or normal admin from bypassing controls using ?debug=1 URL params.
        """
        super()._handle_debug()
        try:
            if request.session.debug and request.session.uid != 2:
                request.session.debug = ''
        except Exception:
            # Safe fallback if request/session is not fully initialized
            pass
