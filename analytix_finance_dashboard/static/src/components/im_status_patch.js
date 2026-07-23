/** @odoo-module */
/**
 * Patch for Odoo 19 bug: im_status_service crashes with
 * "can't access property 'res.partner', store is undefined"
 *
 * ROOT CAUSE (addons/mail/static/src/core/common/im_status_service.js line 44-45):
 *   const store = env.services["mail.store"];
 *   const partner = store["res.partner"].get(partner_id);  ← crashes if store not ready
 *
 * FIX: Replace the bus subscription handler with a null-safe version.
 *
 * This uses the registry to overwrite the service BEFORE it is started,
 * so the fixed version runs instead of the broken one.
 */

import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";

export const AWAY_DELAY = 30 * 60 * 1000; // 30 minutes

// Replace the broken im_status service with a null-safe version
registry.category("services").remove("im_status");
registry.category("services").add("im_status", {
    dependencies: ["bus_service", "presence"],

    start(env, { bus_service, presence }) {
        let lastSentInactivity;
        let becomeAwayTimeout;

        const updateBusPresence = () => {
            lastSentInactivity = presence.getInactivityPeriod();
            startAwayTimeout();
            bus_service.send("update_presence", { inactivity_period: lastSentInactivity });
        };

        const startAwayTimeout = () => {
            clearTimeout(becomeAwayTimeout);
            const awayTime = AWAY_DELAY - presence.getInactivityPeriod();
            if (awayTime > 0) {
                becomeAwayTimeout = browser.setTimeout(() => updateBusPresence(), awayTime);
            }
        };

        bus_service.addEventListener("BUS:CONNECT", () => updateBusPresence(), { once: true });

        bus_service.subscribe(
            "bus.bus/im_status_updated",
            async ({ presence_status, im_status, partner_id, guest_id, debounce = true }) => {
                // ── NULL GUARD: skip if mail.store is not yet initialized ──────
                const store = env.services["mail.store"];
                if (!store) {
                    return; // store not ready yet — message will be resent
                }
                // ─────────────────────────────────────────────────────────────
                const partner = store["res.partner"]?.get(partner_id);
                const guest   = store["mail.guest"]?.get(guest_id);
                if (!partner && !guest) {
                    return; // unknown persona — ignore
                }
                if (debounce) {
                    partner?.debouncedSetImStatus(im_status);
                    guest?.debouncedSetImStatus(im_status);
                } else {
                    partner?.updateImStatus(im_status);
                    guest?.updateImStatus(im_status);
                }
                if (partner?.eq(store.self_partner) || guest?.eq(store.self_guest)) {
                    const isOnline = presence.getInactivityPeriod() < AWAY_DELAY;
                    if ((presence_status === "away" && isOnline) || presence_status === "offline") {
                        updateBusPresence();
                    }
                }
            }
        );

        presence.bus.addEventListener("presence", () => {
            if (!lastSentInactivity || lastSentInactivity >= AWAY_DELAY) {
                updateBusPresence();
            }
            startAwayTimeout();
        });

        return { updateBusPresence };
    },
});
