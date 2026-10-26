# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _has_generated_qr_code(self):
        """
        Check whether the move has a generated QR code.
        Supports advanced_vat_invoice ('qr') as well as standard localization fields.
        """
        self.ensure_one()
        # 1. Check custom VAT / e-invoicing QR field (e.g. advanced_vat_invoice)
        if 'qr' in self._fields and bool(self.qr):
            return True

        # 2. Check standard or other localization QR code fields
        for field_name in ('l10n_sa_qr_code_str', 'qr_code_url', 'l10n_gcc_invoice_qr'):
            if field_name in self._fields and bool(getattr(self, field_name, False)):
                return True

        return False

    def _check_draftable_qr(self):
        """Raise ValidationError if a posted move has a generated QR code and user lacks permission."""
        current_user = self.env.user
        can_reset, reason = current_user._check_reset_invoice_qr_permission()
        if can_reset:
            return

        for move in self:
            if move.state == 'posted' and move._has_generated_qr_code():
                invoice_label = move.display_name or move.name or _("this document")
                msg = _(
                    "You cannot reset invoice '%(invoice_name)s' to draft because it has already been posted "
                    "and an official QR code has been generated.\n\n"
                    "According to e-invoicing and tax compliance regulations, modifying or resetting a finalized "
                    "invoice to draft is not permitted once the QR code is issued.\n\n"
                    "If you need to make corrections or cancel this invoice, please issue a Credit Note or Debit Note instead.",
                    invoice_name=invoice_label,
                )
                if reason == 'expired':
                    msg += _("\n\n(Note: Your permission to reset invoices to draft expired on %(until)s.)", until=current_user.reset_draft_valid_until)
                elif reason == 'future':
                    msg += _("\n\n(Note: Your permission to reset invoices to draft will only be active starting %(from_date)s.)", from_date=current_user.reset_draft_valid_from)
                elif reason == 'no_permission':
                    msg += _("\n\n(Note: Only users with 'Allow Reset to Draft' permission can reset this invoice.)")

                raise ValidationError(msg)

    def button_draft(self):
        """Override button_draft to restrict resetting posted invoices with QR code to draft."""
        self._check_draftable_qr()
        return super().button_draft()

    def write(self, vals):
        """Ensure programmatic state changes to 'draft' are also prevented when QR is present."""
        if vals.get('state') == 'draft':
            self._check_draftable_qr()
        return super().write(vals)
