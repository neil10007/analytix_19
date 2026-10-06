# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import UserError


class AccountAccountReconcile(models.Model):
    _inherit = "account.account.reconcile"

    def reconcile(self):
        self.ensure_one()
        counterparts = (self.reconcile_data_info or {}).get("counterparts", [])
        if not counterparts:
            raise UserError(
                _("Nothing to reconcile!\n\nPlease select the matching entries you want to reconcile from the list below before clicking Reconcile.")
            )

        lines = self.env["account.move.line"].browse(counterparts)
        if not lines:
            raise UserError(
                _("No valid journal entries found to reconcile.")
            )

        if len(lines) < 2 and abs(sum(lines.mapped("amount_residual"))) > 0.0001:
            raise UserError(
                _("A single entry with an open balance cannot be reconciled on its own.\n\nPlease select matching debit and credit entries.")
            )

        try:
            lines.reconcile()
        except UserError:
            raise
        except Exception as e:
            raise UserError(
                _("Reconciliation Failed:\n%s") % str(e)
            )

        # Remove temporary user counterparts data
        data_record = self.env["account.account.reconcile.data"].search(
            [("user_id", "=", self.env.user.id), ("reconcile_id", "=", self.id)]
        )
        data_record.unlink()

        # Count remaining open records to celebrate if all are finished!
        remaining = self.search_count([("is_reconciled", "=", False), ("id", "!=", self.id)])
        if remaining == 0:
            msg = _("Congratulations! All items have been reconciled.")
        else:
            msg = _("Well done! That's %s entries reconciled.") % len(lines)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Reconciled"),
                "message": msg,
                "type": "success",
                "sticky": False,
            },
            "effect": {
                "fadeout": "slow",
                "message": msg,
                "type": "rainbow_man",
            },
        }

    def clean_reconcile(self):
        super().clean_reconcile()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Selection Cleared"),
                "message": _("All selected counterpart lines have been removed."),
                "type": "info",
                "sticky": False,
            },
        }
