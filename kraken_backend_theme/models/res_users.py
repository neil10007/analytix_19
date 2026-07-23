from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ["chatter_position"]

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ["chatter_position"]

    chatter_position = fields.Selection(
        selection=[
            ("side", "Side"),
            ("bottom", "Bottom"),
        ],
        string="Chatter Position",
        default="side",
        required=True,
    )
    kraken_favorite_menu_ids = fields.Many2many(
        "ir.ui.menu",
        "kraken_user_favorite_menu_rel",
        "user_id",
        "menu_id",
        string="Kraken Favorite Menus",
    )
    kraken_favorites_initialized = fields.Boolean(default=False)
    kraken_home_action_set = fields.Boolean(default=False)

    @api.model
    def kraken_toggle_favorite_menu(self, menu_id):
        menu_id = int(menu_id or 0)
        menu = self.env["ir.ui.menu"].browse(menu_id).exists()
        if not menu:
            return self.env.user.kraken_get_favorite_menu_ids()

        current_user = self.env.user.sudo()
        if menu in current_user.kraken_favorite_menu_ids:
            current_user.write({"kraken_favorite_menu_ids": [(3, menu.id)]})
        else:
            current_user.write({"kraken_favorite_menu_ids": [(4, menu.id)]})
        return current_user.kraken_get_favorite_menu_ids()

    def kraken_get_favorite_menu_ids(self):
        self.ensure_one()
        return self.kraken_favorite_menu_ids.ids
