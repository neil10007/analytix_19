# -*- coding: utf-8 -*-

from odoo import models, fields, api, exceptions, _
import logging

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    """
    Extends res.users with a Super Admin flag.

    Behaviour:
      - Super Admin  : sees and can manage ALL users including other super admins.
                       Full access to every menu / developer mode.
      - Normal Admin : can create and manage regular users ONLY.
                       Super admin accounts are completely hidden from them.
                       Developer mode is blocked.
      - Regular User : standard access only.
    """
    _inherit = 'res.users'

    is_super_admin = fields.Boolean(
        string='Super Admin',
        default=False,
        copy=False,
        help="Super Admin accounts are hidden from Normal Admins and regular users.",
    )

    max_users_to_create = fields.Integer(
        string='Max Users to Create',
        default=0,
        help="Maximum number of users this user is allowed to create. 0 means they cannot create any users.",
    )

    creation_limit_log_ids = fields.One2many(
        'user.creation.limit.log',
        'user_id',
        string='Creation Limit Logs'
    )

    # ------------------------------------------------------------------
    # Core helper – MUST use raw SQL to avoid infinite recursion.
    # ------------------------------------------------------------------

    @api.model
    def _is_current_user_super_admin(self):
        """Return True if the currently logged-in user is a Super Admin (raw SQL)."""
        uid = self.env.uid
        if not uid:
            return False
        self.env.cr.execute(
            "SELECT is_super_admin FROM res_users WHERE id = %s LIMIT 1",
            (uid,)
        )
        row = self.env.cr.fetchone()
        return bool(row and row[0])

    def _get_super_admin_domain(self):
        """
        When the current user is NOT a super admin, add a filter that
        hides all super-admin accounts from search results.
        """
        if self.env.su:
            return []
        if not self._is_current_user_super_admin():
            return [('is_super_admin', '=', False)]
        return []

    # ------------------------------------------------------------------
    # ORM search overrides
    # ------------------------------------------------------------------

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        extra = self._get_super_admin_domain()
        if extra:
            domain = list(domain) + extra
        return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)

    @api.model
    def search_count(self, domain, limit=None):
        extra = self._get_super_admin_domain()
        if extra:
            domain = list(domain) + extra
        return super().search_count(domain, limit=limit)

    # ------------------------------------------------------------------
    # Create / Write / Unlink guards
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self._is_current_user_super_admin():
            for vals in vals_list:
                if vals.get('is_super_admin'):
                    raise exceptions.AccessError(
                        _("You do not have permission to create Super Admin accounts.")
                    )

            # Limit user creation count
            current_user = self.env.user
            created_count = self.search_count([('create_uid', '=', current_user.id)])
            to_create_count = len(vals_list)

            if created_count + to_create_count > current_user.max_users_to_create:
                raise exceptions.AccessError(
                    _("You have reached your limit of creating users. Allowed: %d, Created: %d, Attempting: %d. Please contact the Super Admin to increase your limit.")
                    % (current_user.max_users_to_create, created_count, to_create_count)
                )

        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and not self._is_current_user_super_admin():
            if any(u.is_super_admin for u in self):
                raise exceptions.AccessError(
                    _("You do not have permission to modify Super Admin accounts.")
                )
            if vals.get('is_super_admin'):
                raise exceptions.AccessError(
                    _("You do not have permission to grant Super Admin privileges.")
                )
        return super().write(vals)

    def unlink(self):
        if not self.env.su and not self._is_current_user_super_admin():
            if any(u.is_super_admin for u in self):
                raise exceptions.AccessError(
                    _("You do not have permission to delete Super Admin accounts.")
                )
        return super().unlink()

    # ------------------------------------------------------------------
    # Inject is_super_admin into the browser session
    # ------------------------------------------------------------------

    def _get_session_token_fields(self):
        return super()._get_session_token_fields() | {'is_super_admin'}

    @api.model
    def session_info(self):
        result = super().session_info()
        result['is_super_admin'] = self._is_current_user_super_admin()
        result['can_activate_developer_mode'] = (self.env.uid == 2)
        return result

    # ------------------------------------------------------------------
    # Developer mode checks
    # ------------------------------------------------------------------

    @api.model
    def _can_activate_developer_mode(self):
        return self.env.uid == 2

    def action_check_developer_mode_access(self):
        self.ensure_one()
        if self.env.uid != 2:
            raise exceptions.AccessError(
                _("Developer mode can only be activated by the main administrator (ID 2).")
            )
        return True

    # ------------------------------------------------------------------
    # User Creation Limits action buttons
    # ------------------------------------------------------------------

    def action_open_creation_limit_wizard(self):
        self.ensure_one()
        return {
            'name': _('Adjust User Creation Limit'),
            'type': 'ir.actions.act_window',
            'res_model': 'user.creation.limit.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_id': self.id,
            }
        }

    def action_view_creation_limit_history(self):
        self.ensure_one()
        return {
            'name': _('Limit Change History: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'user.creation.limit.log',
            'view_mode': 'list',
            'domain': [('user_id', '=', self.id)],
            'context': {'default_user_id': self.id},
        }

    # ------------------------------------------------------------------
    # Display name
    # ------------------------------------------------------------------

    def _compute_display_name(self):
        super()._compute_display_name()
        if self._is_current_user_super_admin():
            for user in self:
                if user.is_super_admin:
                    user.display_name = f"⭐ {user.display_name}"

    # ------------------------------------------------------------------
    # Auto-bootstrap hooks on registry load
    # ------------------------------------------------------------------

    @api.model
    def _register_hook(self):
        """
        Runs when the registry is loaded. Automatically ensures the main admin
        user (base.user_admin) and root system user (base.user_root) are
        flagged as Super Admin, bypassing XML loading limits.
        """
        super()._register_hook()
        try:
            admin_user = self.env.ref('base.user_admin', raise_if_not_found=False)
            if admin_user and not admin_user.is_super_admin:
                self.env.cr.execute(
                    "UPDATE res_users SET is_super_admin = True WHERE id = %s",
                    (admin_user.id,)
                )
                self.env.cr.commit()

            root_user = self.env.ref('base.user_root', raise_if_not_found=False)
            if root_user and not root_user.is_super_admin:
                self.env.cr.execute(
                    "UPDATE res_users SET is_super_admin = True WHERE id = %s",
                    (root_user.id,)
                )
                self.env.cr.commit()
        except Exception as e:
            _logger.warning("Failed to auto-bootstrap Super Admin status: %s", e)

