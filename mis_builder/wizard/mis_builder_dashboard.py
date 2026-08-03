# Copyright 2014 ACSONE SA/NV (<http://acsone.eu>)
# Copyright 2020 CorporateHub (https://corporatehub.eu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
# NOTE: The `board` module was removed in Odoo 17+.
# This wizard is kept as a stub and will simply close.

from odoo import api, fields, models


class AddMisReportInstanceDashboard(models.TransientModel):
    _name = "add.mis.report.instance.dashboard.wizard"
    _description = "MIS Report Add to Dashboard Wizard"

    name = fields.Char(required=True)

    @api.model
    def default_get(self, fields_list):
        res = {}
        if self.env.context.get("active_id", False):
            res = super().default_get(fields_list)
            res["name"] = (
                self.env["mis.report.instance"]
                .browse(self.env.context["active_id"])
                .name
            )
        return res

    def action_add_to_dashboard(self):
        """
        The 'board' module (and board.board model) was removed in Odoo 17+.
        This method is kept as a stub for backward compatibility.
        """
        return {"type": "ir.actions.act_window_close"}
