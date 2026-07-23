/** @odoo-module **/

import { registry } from "@web/core/registry";
import { session } from "@web/session";

function canActivateDevMode() {
    return Boolean(session.can_activate_developer_mode);
}

// 1. Strip ?debug= from URL for non-developer-mode users on page load
(function blockDebugUrlOnLoad() {
    if (canActivateDevMode()) return;

    const url = new URL(window.location.href);
    if (url.searchParams.has("debug")) {
        url.searchParams.delete("debug");
        window.history.replaceState({}, document.title, url.toString());
        console.warn("[AccessRights] Developer mode is restricted to the main administrator. Debug param removed.");
    }
})();

// 2. System tray / debug menu – hide debug entries
const debugMenuRegistry = registry.category("debug");

class DevModeGuardService {
    static serviceName = "dev_mode_guard";

    constructor(env) {
        this.env = env;
        this._patchDebugMenu();
    }

    _patchDebugMenu() {
        if (canActivateDevMode()) return;

        const keysToRemove = [];
        for (const [key] of debugMenuRegistry.getEntries()) {
            if (
                key.includes("debug") ||
                key.includes("developer") ||
                key === "activate_debug_mode" ||
                key === "deactivate_debug_mode"
            ) {
                keysToRemove.push(key);
            }
        }

        for (const key of keysToRemove) {
            try {
                debugMenuRegistry.remove(key);
            } catch {
                // Ignore
            }
        }
    }
}

registry.category("services").add("dev_mode_guard", {
    start(env) {
        return new DevModeGuardService(env);
    },
});

// 3. Inject CSS to hide developer links
if (!canActivateDevMode()) {
    const style = document.createElement("style");
    style.setAttribute("data-module", "acces_right_users");
    style.textContent = `
        .o_debug_manager .dropdown-item[data-action="activate_debug_mode"],
        .o_debug_manager .dropdown-item[data-action="deactivate_debug_mode"],
        .o_debug_manager,
        [data-toggle-debug],
        .o_debug_mode_switcher {
            display: none !important;
        }
        .o_setting_box[id*="developer"] {
            display: none !important;
        }
        .o_menu_sections .o_nav_entry[data-menu-xmlid*="base_setup.menu_action_general_configuration"]
            + * [data-menu-xmlid*="base.menu_action_ui_view"] {
            display: none !important;
        }
    `;
    document.head.appendChild(style);
}

// 4. Sanitize history states
if (!canActivateDevMode()) {
    const _pushState = history.pushState.bind(history);
    const _replaceState = history.replaceState.bind(history);

    function sanitizeDebugUrl(url) {
        if (!url) return url;
        try {
            const u = new URL(url, window.location.origin);
            if (u.searchParams.has("debug")) {
                u.searchParams.delete("debug");
                return u.toString();
            }
        } catch {
            return String(url).replace(/[?&]debug=[^&]*/g, "").replace(/[?&]$/, "");
        }
        return url;
    }

    history.pushState = function (state, title, url) {
        return _pushState(state, title, sanitizeDebugUrl(url));
    };

    history.replaceState = function (state, title, url) {
        return _replaceState(state, title, sanitizeDebugUrl(url));
    };
}
