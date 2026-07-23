# -*- coding: utf-8 -*-

from odoo import models, fields, api, exceptions, _


class UserCreationLimitLog(models.Model):
    _name = 'user.creation.limit.log'
    _description = 'User Creation Limit Log'
    _order = 'create_date desc'

    user_id = fields.Many2one('res.users', string='Target User', required=True, ondelete='cascade')
    previous_limit = fields.Integer(string='Previous Limit', required=True)
    new_limit = fields.Integer(string='New Limit', required=True)
    change_amount = fields.Integer(string='Change Amount', required=True)
    reason = fields.Char(string='Reason', required=True)
    modified_by_id = fields.Many2one('res.users', string='Modified By', default=lambda self: self.env.user, required=True)


class UserCreationLimitWizard(models.TransientModel):
    _name = 'user.creation.limit.wizard'
    _description = 'Adjust User Creation Limit Wizard'

    user_id = fields.Many2one('res.users', string='User', readonly=True, required=True)
    current_limit = fields.Integer(string='Current Limit', readonly=True)
    change_amount = fields.Integer(string='Add to Count', default=1, required=True)
    reason = fields.Char(string='Reason/Notes', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super(UserCreationLimitWizard, self).default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id:
            user = self.env['res.users'].browse(active_id)
            res.update({
                'user_id': user.id,
                'current_limit': user.max_users_to_create,
            })
        return res

    def action_confirm(self):
        self.ensure_one()
        # Verify current user has Super Admin access (direct ID 2 check or group check)
        is_super = self.env['res.users']._is_current_user_super_admin()
        if not is_super and self.env.uid != 2:
            raise exceptions.AccessError(_("Only Super Admins can adjust user creation limits."))

        previous_limit = self.current_limit
        change = self.change_amount
        new_limit = previous_limit + change

        if new_limit < 0:
            raise exceptions.ValidationError(_("The new limit cannot be negative."))

        # Update the user limit
        self.user_id.write({'max_users_to_create': new_limit})

        # Create history log
        self.env['user.creation.limit.log'].create({
            'user_id': self.user_id.id,
            'previous_limit': previous_limit,
            'new_limit': new_limit,
            'change_amount': change,
            'reason': self.reason,
            'modified_by_id': self.env.user.id,
        })
        return {'type': 'ir.actions.act_window_close'}
