DEFAULT_FAVORITE_MENU_XMLIDS = [
    "kraken_backend_theme.menu_kraken_dashboard",
    "sale.sale_menu_root",
    "stock.menu_stock_root",
    "crm.crm_menu_root",
    "purchase.menu_purchase_root",
    "account.menu_finance",
    "project.menu_main_pm",
    "mrp.menu_mrp_root",
    "hr.menu_hr_root",
    "calendar.mail_menu_calendar",
    "contacts.menu_contacts",
]
DEFAULT_FAVORITE_LIMIT = 11

DEFAULT_FAVORITE_MENU_LABELS = [
    "dashboard",
    "sales",
    "inventory",
    "crm",
    "purchase",
    "accounting",
    "invoicing",
    "project",
    "manufacturing",
    "employees",
    "calendar",
    "contacts",
]


def _canonical_label(name):
    return "".join(character for character in (name or "").lower() if character.isalnum())


def _get_default_favorite_menus(env):
    menus = env["ir.ui.menu"]
    for xmlid in DEFAULT_FAVORITE_MENU_XMLIDS:
        menu = env.ref(xmlid, raise_if_not_found=False)
        if menu and menu not in menus:
            menus |= menu

    for label in DEFAULT_FAVORITE_MENU_LABELS:
        canonical_label = _canonical_label(label)
        menu = env["ir.ui.menu"].search([("name", "ilike", label)], limit=1)
        if menu and canonical_label in _canonical_label(menu.name) and menu not in menus:
            menus |= menu
    return menus[:DEFAULT_FAVORITE_LIMIT]


def _get_dashboard_action(env):
    return env.ref("spreadsheet_dashboard.ir_actions_dashboard_action", raise_if_not_found=False)


def post_init_hook(env):
    favorite_menus = _get_default_favorite_menus(env)
    if favorite_menus:
        users = env["res.users"].search([
            ("share", "=", False),
            ("kraken_favorites_initialized", "=", False),
        ])
        users.write({
            "kraken_favorite_menu_ids": [(6, 0, favorite_menus.ids)],
            "kraken_favorites_initialized": True,
        })

    dashboard_action = _get_dashboard_action(env)
    admin_user = env.ref("base.user_admin", raise_if_not_found=False)
    if dashboard_action and admin_user and not admin_user.action_id:
        admin_user.write({
            "action_id": dashboard_action.id,
            "kraken_home_action_set": True,
        })


def uninstall_hook(env):
    dashboard_action = _get_dashboard_action(env)
    if dashboard_action:
        legacy_admin = env.ref("base.user_admin", raise_if_not_found=False)
        users = env["res.users"].search([
            ("kraken_home_action_set", "=", True),
            ("action_id", "=", dashboard_action.id),
        ])
        if legacy_admin and legacy_admin.action_id == dashboard_action:
            users |= legacy_admin
        users.write({
            "action_id": False,
            "kraken_home_action_set": False,
        })

    env["ir.config_parameter"].sudo().search([
        ("key", "=like", "kraken_backend_theme.%"),
    ]).unlink()
