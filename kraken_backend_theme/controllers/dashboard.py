# -*- coding: utf-8 -*-

from odoo import http
from odoo.addons.web.controllers.home import Home as WebHome


class Home(WebHome):
    @http.route(
        ["/dashboard", "/dashboard/<path:subpath>"],
        type="http",
        auth="none",
        readonly=WebHome._web_client_readonly,
    )
    def dashboard(self, s_action=None, subpath=None, **kw):
        return super().web_client(s_action=s_action, **kw)
