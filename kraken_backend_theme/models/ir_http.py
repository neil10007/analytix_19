from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def color_scheme(self):
        return "dark" if request.httprequest.cookies.get("color_scheme") == "dark" else "light"

    def session_info(self):
        result = super().session_info()
        result["chatter_position"] = self.env.user.chatter_position
        result["kraken_favorite_menu_ids"] = self.env.user.kraken_get_favorite_menu_ids()
        return result
