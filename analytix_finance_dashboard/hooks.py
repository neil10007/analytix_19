# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def _set_dashboard_home_action(env):
    """
    Set the Analytix Finance Dashboard as the default home action
    for ALL existing internal users.
    """
    action = env.ref(
        'analytix_finance_dashboard.action_analytix_finance_dashboard',
        raise_if_not_found=False,
    )
    if not action:
        _logger.warning("Analytix dashboard action not found — skipping home action setup.")
        return

    # Set for all internal users (not portal/public)
    internal_users = env['res.users'].search([
        ('share', '=', False),
    ])
    if internal_users:
        internal_users.write({'action_id': action.id})
        _logger.info(
            "✅ Analytix: Set Finance Dashboard as home action for %d users.",
            len(internal_users),
        )


def post_init_hook(env):
    """Runs on first install."""
    _set_dashboard_home_action(env)


def post_migrate_hook(env):
    """Runs on every upgrade."""
    _set_dashboard_home_action(env)
