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


def _disable_spreadsheet_dashboard_menus(env):
    """
    Permanently disable spreadsheet dashboard menus.
    """
    menu_xml_ids = [
        'spreadsheet_dashboard.spreadsheet_dashboard_menu_dashboard',
        'spreadsheet_dashboard.spreadsheet_dashboard_menu_configuration_dashboards',
        'spreadsheet_dashboard.spreadsheet_dashboard_menu_root',
    ]
    for xml_id in menu_xml_ids:
        menu = env.ref(xml_id, raise_if_not_found=False)
        if menu:
            menu.write({'active': False})
            _logger.info("✅ Disabled menu: %s", xml_id)


def _ensure_accounting_dashboard_menu(env):
    """
    Ensure the Analytix Dashboard menu under Accounting is active and linked
    to action_analytix_finance_dashboard_accounting.
    """
    menu = env.ref(
        'analytix_finance_dashboard.menu_analytix_finance_dashboard_accounting',
        raise_if_not_found=False,
    )
    action = env.ref(
        'analytix_finance_dashboard.action_analytix_finance_dashboard_accounting',
        raise_if_not_found=False,
    )
    if menu:
        vals = {'active': True}
        if action:
            vals['action'] = f'ir.actions.client,{action.id}'
        menu.write(vals)
        _logger.info("✅ Analytix: Enabled Accounting Dashboard menu (%s)", menu.id)


def _ensure_ai_gl_configs_all_companies(env):
    """
    Ensure AI GL Configuration records exist for every company in the system.
    """
    companies = env['res.company'].sudo().search([])
    ai_config_obj = env['ai.gl.config'].sudo()
    for company in companies:
        ai_config_obj._create_default_configs_for_company(company.id)
    _logger.info("✅ Analytix: Verified AI GL Configurations for %d companies.", len(companies))


def _sync_super_admin_ai_config(env):
    """
    Sync OpenRouter API key and model from the Super Admin user to system parameters
    so all users can immediately use them.
    """
    User = env['res.users'].sudo()
    super_group = env.ref('analytix_finance_dashboard.group_groq_super_admin', raise_if_not_found=False)

    super_admin = False
    if super_group:
        super_admin = User.search([
            ('group_ids', 'in', super_group.id),
            ('open_router_key', '!=', False),
        ], limit=1)
    if not super_admin:
        user_admin = env.ref('base.user_admin', raise_if_not_found=False)
        if user_admin and user_admin.sudo().open_router_key:
            super_admin = user_admin.sudo()
    if not super_admin:
        user_2 = User.browse(2)
        if user_2.exists() and user_2.open_router_key:
            super_admin = user_2

    if super_admin and super_admin.open_router_key:
        param = env['ir.config_parameter'].sudo()
        param.set_param('analytix.open_router_key', super_admin.open_router_key.strip())
        eff_model = False
        if hasattr(super_admin, 'get_effective_openrouter_model'):
            eff_model = super_admin.get_effective_openrouter_model()
        else:
            eff_model = getattr(super_admin, 'openrouter_model', False)
        eff_model = eff_model or 'google/gemini-2.5-flash'
        param.set_param('analytix.openrouter_model', eff_model)
        _logger.info("✅ Analytix: Synced OpenRouter AI configuration from Super Admin (%s) to system parameters.", super_admin.login)


def post_init_hook(env):
    """Runs on first install."""
    _set_dashboard_home_action(env)
    _disable_spreadsheet_dashboard_menus(env)
    _ensure_accounting_dashboard_menu(env)
    _ensure_ai_gl_configs_all_companies(env)
    _sync_super_admin_ai_config(env)


def post_migrate_hook(env):
    """Runs on every upgrade."""
    _set_dashboard_home_action(env)
    _disable_spreadsheet_dashboard_menus(env)
    _ensure_accounting_dashboard_menu(env)
    _ensure_ai_gl_configs_all_companies(env)
    _sync_super_admin_ai_config(env)

