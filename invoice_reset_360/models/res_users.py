# -*- coding: utf-8 -*-
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    allow_invoice_reset_draft = fields.Boolean(
        string="Allow Reset to Draft (QR Invoices)",
        help="Grants this user permission to reset posted invoices with generated QR codes back to draft.",
    )
    reset_draft_valid_from = fields.Datetime(
        string="Reset Permission Valid From",
        help="Start date and time from which the user is allowed to reset invoices to draft. Leave blank for no start restriction.",
    )
    reset_draft_valid_until = fields.Datetime(
        string="Reset Permission Valid Until",
        help="End date and time until which the user is allowed to reset invoices to draft. Leave blank for permanent permission.",
    )

    def _check_reset_invoice_qr_permission(self):
        """
        Check if the user has permission to reset invoices with QR codes to draft.
        Returns: (can_reset: bool, reason: str)
        """
        self.ensure_one()
        if self._is_superuser():
            return True, 'superuser'

        has_permission = (
            self.allow_invoice_reset_draft
            or self.has_group('invoice_reset_360.group_allow_invoice_reset_draft')
        )
        if not has_permission:
            return False, 'no_permission'

        now = fields.Datetime.now()
        if self.reset_draft_valid_from and now < self.reset_draft_valid_from:
            return False, 'future'
        if self.reset_draft_valid_until and now > self.reset_draft_valid_until:
            return False, 'expired'

        return True, 'authorized'

    def _can_reset_invoice_with_qr(self):
        """Convenience method returning True if authorized."""
        can_reset, _ = self._check_reset_invoice_qr_permission()
        return can_reset
