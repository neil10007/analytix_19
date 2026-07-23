from datetime import date
from urllib.parse import urlparse

from odoo import api, models
from odoo.modules.module import get_manifest
from odoo.tools.misc import format_date


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def get_kraken_dashboard_footer_data(self):
        user = self.env.user
        company = self.env.company.sudo()
        config = self.env["ir.config_parameter"].sudo()

        base_url = config.get_param("web.base.url", default="") or ""
        hostname = (urlparse(base_url).hostname or "").lower()
        db_name = self.env.cr.dbname
        fingerprint = f"{hostname} {db_name}".lower()
        environment = (config.get_param("kraken_backend_theme.environment", default="") or "").strip().lower()
        if environment not in {"production", "staging", "development"}:
            if any(token in fingerprint for token in ("stag", "stage", "uat", "preprod", "sandbox", "qa")):
                environment = "staging"
            elif any(token in fingerprint for token in ("dev", "test", "local", "demo")):
                environment = "development"
            else:
                environment = "production"
        environment_label = environment.capitalize()

        fiscal_period = format_date(self.env, date.today())
        if "fiscalyear_last_day" in company._fields and "fiscalyear_last_month" in company._fields:
            fiscal_dates = company.compute_fiscalyear_dates(date.today())
            fiscal_period = "{} - {}".format(
                format_date(self.env, fiscal_dates["date_from"]),
                format_date(self.env, fiscal_dates["date_to"]),
            )

        support_contact = (
            config.get_param("kraken_backend_theme.support_contact", default="")
            or company.partner_id.email
            or company.partner_id.phone
            or ""
        )
        build_version = config.get_param("kraken_backend_theme.build_version", default="") or ""

        theme_version = get_manifest("kraken_backend_theme").get("version", "")

        can_open_users = self.env["res.users"].check_access_rights("read", raise_exception=False)
        can_open_scheduled_actions = (
            self.env["ir.cron"].check_access_rights("read", raise_exception=False)
            and user._is_system()
        )
        can_open_settings = user._is_admin() or user._is_system()
        can_toggle_debug = user._is_internal()

        footer_data = {
            "company_name": company.name,
            "database_name": db_name,
            "user_name": user.name,
            "role_label": (
                "Administrator"
                if user._is_system()
                else "Access Rights"
                if user._is_admin()
                else "Internal User"
                if user._is_internal()
                else "Portal User"
            ),
            "environment": {
                "key": environment,
                "label": environment_label,
            },
            "fiscal_period": fiscal_period,
            "timezone": user.tz or "UTC",
            "locale": user.lang or "en_US",
            "odoo_version": self.env["ir.http"].session_info().get("server_version", "Odoo"),
            "theme_version": theme_version,
            "build_version": build_version,
            "support_contact": support_contact,
            "quick_links": {
                "settings": can_open_settings,
                "users": can_open_users,
                "scheduled_actions": can_open_scheduled_actions,
                "developer_mode": can_toggle_debug,
            },
            "system_status": {
                "background_jobs": None,
                "mail_queue": None,
                "integrations": None,
            },
        }

        if user._is_internal():
            footer_data["system_status"] = {
                "background_jobs": self.env["ir.cron"].sudo().search_count([("active", "=", True)]),
                "mail_queue": self.env["mail.mail"].sudo().search_count(
                    [("state", "in", ["outgoing", "exception"])]
                ),
                "integrations": self.env.registry.get("payment.provider")
                and self.env["payment.provider"].sudo().search_count([("state", "=", "enabled")])
                or None,
            }

        return footer_data
