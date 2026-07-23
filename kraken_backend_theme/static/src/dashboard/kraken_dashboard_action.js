/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { Component, onWillStart, useState } from "@odoo/owl";

function formatCount(value) {
    return new Intl.NumberFormat("en-US").format(Number(value) || 0);
}

export class KrakenDashboardAction extends Component {
    static template = "kraken_backend_theme.KrakenDashboardAction";
    static props = { ...standardActionServiceProps };
    static displayName = _t("Dashboard");

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");

        this.state = useState({
            loading: true,
            greeting: _t("Good morning"),
            userName: "",
            partnerCount: 0,
            userCount: 0,
            activityCount: 0,
            attachmentCount: 0,
            activityRows: [],
        });

        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }

    get safeRows() {
        return this.state.activityRows;
    }

    formatCount(value) {
        return formatCount(value);
    }

    async loadDashboardData() {
        this.state.userName = user.name || _t("User");

        try {
            const [partnerCount, userCount, activityCount, attachmentCount, rows] = await Promise.all([
                this.orm.searchCount("res.partner", []),
                this.orm.searchCount("res.users", []),
                this.orm.searchCount("mail.activity", []),
                this.orm.searchCount("ir.attachment", []),
                this.orm.searchRead(
                    "mail.activity",
                    [],
                    ["summary", "date_deadline", "res_model", "state"],
                    { limit: 5, order: "date_deadline desc, id desc" }
                ),
            ]);

            this.state.partnerCount = partnerCount;
            this.state.userCount = userCount;
            this.state.activityCount = activityCount;
            this.state.attachmentCount = attachmentCount;

            this.state.activityRows = rows.map((row, index) => ({
                ref: `ACT_${String(index + 1).padStart(6, "0")}`,
                label: row.summary || row.res_model || _t("Activity"),
                status: row.state === "done" ? "Completed" : (index % 2 ? "Pending" : "In Progress"),
                date: row.date_deadline || _t("No deadline"),
            }));
        } catch {
            this.state.activityRows = [];
        } finally {
            this.state.loading = false;
        }
    }

    openApps() {
        this.actionService.doAction({ type: "ir.actions.client", tag: "home" });
    }

    openActivities() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: _t("Activities"),
            res_model: "mail.activity",
            views: [[false, "list"], [false, "form"]],
        });
    }
}

registry.category("actions").add("kraken_backend_theme.dashboard", KrakenDashboardAction);
