# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMoveResetDraft(models.TransientModel):
    """
    Wizard to allow users to reset multiple posted/cancelled invoices or
    journal entries back to draft state in bulk from list/kanban views.
    """
    _name = 'account.move.reset.draft'
    _description = 'Reset Invoices to Draft Wizard'

    move_ids = fields.Many2many(
        'account.move',
        string='Selected Invoices / Entries',
        required=True,
    )
    total_count = fields.Integer(
        string='Total Selected',
        compute='_compute_counts',
    )
    posted_count = fields.Integer(
        string='Posted Invoices',
        compute='_compute_counts',
    )
    cancel_count = fields.Integer(
        string='Cancelled Invoices',
        compute='_compute_counts',
    )
    draft_count = fields.Integer(
        string='Already in Draft',
        compute='_compute_counts',
    )
    reconciled_count = fields.Integer(
        string='Reconciled / Paid Invoices',
        compute='_compute_counts',
    )
    unreconcile_payments = fields.Boolean(
        string='Unreconcile Payments',
        default=True,
        help='If checked, any reconciled payments will be cleanly detached from the invoices '
             'so the draft invoices can be edited or cancelled without reconciliation conflicts.'
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids', [])
        active_model = self.env.context.get('active_model')

        if active_model == 'account.move' and active_ids:
            moves = self.env['account.move'].browse(active_ids).exists()
            res['move_ids'] = [(6, 0, moves.ids)]
        elif self.env.context.get('default_move_ids'):
            res['move_ids'] = self.env.context.get('default_move_ids')

        return res

    @api.depends('move_ids')
    def _compute_counts(self):
        for wizard in self:
            wizard.total_count = len(wizard.move_ids)
            wizard.posted_count = len(wizard.move_ids.filtered(lambda m: m.state == 'posted'))
            wizard.cancel_count = len(wizard.move_ids.filtered(lambda m: m.state == 'cancel'))
            wizard.draft_count = len(wizard.move_ids.filtered(lambda m: m.state == 'draft'))
            wizard.reconciled_count = len(wizard.move_ids.filtered(
                lambda m: m.payment_state in ('in_payment', 'paid', 'partial')
            ))

    def action_reset_draft(self):
        """
        Executes bulk reset to draft on the selected moves.
        Uses savepoints to guarantee that any single locked or invalid move
        does not abort the entire batch.
        """
        self.ensure_one()
        moves_to_reset = self.move_ids.filtered(lambda m: m.state in ('posted', 'cancel'))

        if not moves_to_reset:
            raise UserError(_("None of the selected invoices/entries can be reset to draft. "
                              "All selected records are already in Draft state."))

        reset_count = 0
        failed_moves = []

        for move in moves_to_reset:
            try:
                with self.env.cr.savepoint():
                    # 1. Unreconcile payments if requested and move has reconciled lines
                    if self.unreconcile_payments and move.payment_state in ('in_payment', 'paid', 'partial'):
                        move.line_ids.remove_move_reconcile()

                    # 2. Call standard Odoo button_draft()
                    move.button_draft()

                    # 3. Post notification in the chatter
                    move.message_post(
                        body=_("Invoice reset to Draft via bulk action by %s.") % self.env.user.name,
                        message_type='notification'
                    )
                    reset_count += 1
            except Exception as exc:
                _logger.warning("Error resetting invoice %s (ID %s) to draft: %s", move.name or move.id, move.id, str(exc))
                failed_moves.append(f"• {move.display_name or move.name or f'ID {move.id}'}: {str(exc)}")

        # Prepare summary notification message
        if failed_moves and reset_count:
            message = _(
                "%(success_count)d invoice(s) reset to draft successfully.\n"
                "%(failed_count)d invoice(s) could not be reset:\n%(errors)s"
            ) % {
                'success_count': reset_count,
                'failed_count': len(failed_moves),
                'errors': '\n'.join(failed_moves)
            }
            notif_type = 'warning'
        elif failed_moves:
            message = _("Failed to reset selected invoice(s) to draft:\n%s") % '\n'.join(failed_moves)
            notif_type = 'danger'
        else:
            message = _("Successfully reset %(count)d invoice(s) to Draft state.") % {'count': reset_count}
            notif_type = 'success'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bulk Reset to Draft'),
                'message': message,
                'type': notif_type,
                'sticky': bool(failed_moves),
                'next': {
                    'type': 'ir.actions.act_window_close',
                },
            }
        }


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_bulk_reset_to_draft(self):
        """
        Direct entry point to open the bulk reset to draft wizard
        from the Action menu or code.
        """
        return {
            'name': _("Reset Invoices to Draft"),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.reset.draft',
            'view_mode': 'form',
            'target': 'new',
            'context': dict(self.env.context, active_ids=self.ids, active_model='account.move'),
        }
