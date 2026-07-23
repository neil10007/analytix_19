/** @odoo-module **/

const GRID_SELECTOR = ".kr_sp_dashboard_content .o-grid.o-two-columns";
const SCROLL_SELECTOR = ".kr_sp_dashboard_scroll";
const DASHBOARD_HEIGHT_VAR = "--kr-sp-dashboard-content-height";
const MIN_DASHBOARD_HEIGHT = 620;
const HEIGHT_PADDING = 48;

function routeGridWheelToDashboard(event) {
    const grid = event.target.closest?.(GRID_SELECTOR);
    if (!grid || !event.deltaY) {
        return;
    }

    const scroller = grid.closest(".kr_sp_action_shell")?.querySelector(SCROLL_SELECTOR);
    if (!scroller) {
        return;
    }

    event.preventDefault();
    event.stopImmediatePropagation();
    scroller.scrollTop += event.deltaY;
}

document.addEventListener("wheel", routeGridWheelToDashboard, { capture: true, passive: false });

function getDashboardContentHeight(grid) {
    const gridRect = grid.getBoundingClientRect();
    // Dashboard figures are absolutely positioned; measuring the canvas would feed back
    // into the height we write below and make the dashboard grow indefinitely.
    const measuredElements = grid.querySelectorAll(".o-figure-wrapper, .o-dashboard-clickable-cell");
    let maxBottom = 0;
    for (const element of measuredElements) {
        const rect = element.getBoundingClientRect();
        if (!rect.width && !rect.height) {
            continue;
        }
        maxBottom = Math.max(maxBottom, rect.bottom - gridRect.top);
    }
    return Math.max(MIN_DASHBOARD_HEIGHT, Math.ceil(maxBottom + HEIGHT_PADDING));
}

function updateDashboardHeight(grid) {
    try {
        const container = grid.closest(".o_spreadsheet_container");
        const height = getDashboardContentHeight(grid);
        const currentHeight = parseInt(grid.style.getPropertyValue(DASHBOARD_HEIGHT_VAR), 10);
        if (Number.isFinite(currentHeight) && Math.abs(currentHeight - height) < 4) {
            return;
        }
        const value = `${height}px`;
        if (grid.style.getPropertyValue(DASHBOARD_HEIGHT_VAR) === value) {
            return;
        }
        grid.style.setProperty(DASHBOARD_HEIGHT_VAR, value);
        container?.style.setProperty(DASHBOARD_HEIGHT_VAR, value);
    } catch {
        // The dashboard can be patched while o-spreadsheet is rebuilding its DOM.
    }
}

function updateAllDashboardHeights() {
    for (const grid of document.querySelectorAll(GRID_SELECTOR)) {
        updateDashboardHeight(grid);
    }
}

let dashboardHeightFrame = 0;
function scheduleDashboardHeightUpdate() {
    if (dashboardHeightFrame) {
        return;
    }
    dashboardHeightFrame = requestAnimationFrame(() => {
        dashboardHeightFrame = 0;
        updateAllDashboardHeights();
    });
}

function isDashboardMutation(mutation) {
    const target = mutation.target;
    if (!(target instanceof Element)) {
        return false;
    }
    if (target.closest(".kr_sp_dashboard_content")) {
        return true;
    }
    for (const node of mutation.addedNodes) {
        if (node instanceof Element && node.querySelector?.(".kr_sp_dashboard_content")) {
            return true;
        }
    }
    return false;
}

function onDashboardMutation(mutations) {
    if (mutations.some(isDashboardMutation)) {
        scheduleDashboardHeightUpdate();
    }
}

function startDashboardHeightUpdater() {
    if (!document.body) {
        document.addEventListener("DOMContentLoaded", startDashboardHeightUpdater, { once: true });
        return;
    }

    window.addEventListener("resize", scheduleDashboardHeightUpdate);
    new MutationObserver(onDashboardMutation).observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["class", "style"],
    });
    scheduleDashboardHeightUpdate();
}

startDashboardHeightUpdater();
