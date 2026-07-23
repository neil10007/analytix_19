/** @odoo-module **/

import { router } from "@web/core/browser/router";

const originalStateToUrl = router.stateToUrl.bind(router);
const originalUrlToState = router.urlToState.bind(router);

function isSpreadsheetDashboardState(state) {
    const activeAction = state?.actionStack?.at?.(-1)?.action || state?.action;
    return activeAction === "dashboards" || activeAction === "action_spreadsheet_dashboard";
}

router.stateToUrl = function stateToUrl(state) {
    if (!isSpreadsheetDashboardState(state)) {
        return originalStateToUrl(state);
    }

    const url = new URL(originalStateToUrl(state), window.location.origin);
    url.pathname = "/dashboard";
    url.searchParams.delete("dashboard_id");
    return `${url.pathname}${url.search}${url.hash}`;
};

router.urlToState = function urlToState(urlObj) {
    if (!urlObj?.pathname?.startsWith("/dashboard") && !urlObj?.pathname?.startsWith("/odoo/dashboard")) {
        return originalUrlToState(urlObj);
    }

    const canonicalUrl = new URL(urlObj.href);
    canonicalUrl.pathname = "/odoo/dashboards";
    canonicalUrl.searchParams.delete("dashboard_id");
    return originalUrlToState(canonicalUrl);
};
