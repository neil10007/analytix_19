/** @odoo-module **/

import { browser } from "@web/core/browser/browser";
import { cookie } from "@web/core/browser/cookie";
import { router, routerBus } from "@web/core/browser/router";
import { user, userBus } from "@web/core/user";
import { imageUrl } from "@web/core/utils/urls";
import { mountComponent } from "@web/env";
import { session } from "@web/session";
import { UserMenu } from "@web/webclient/user_menu/user_menu";

const THEME_KEY = "kr_sp_theme_mode";
const COLOR_KEY = "kr_sp_color_theme";
const SIDEBAR_APP_LIMIT = 11;
const KRAKEN_THEME_VERSION = "19.0.1.0.0";
let cachedRootMenus = null;
let renderScheduled = false;
let currentTopSections = new Map();
let activeSubmenuState = null;
let boundEnvBus = null;
let boundRouteEvents = false;
let footerLastLoadedAt = 0;
let footerRefreshPromise = null;
let systrayMountRetryTimer = null;
let systrayMountRetryCount = 0;
let tabsRenderRetryTimer = null;
let tabsRenderRetryCount = 0;
let modalViewportGuardReady = false;
let modalViewportSnapshot = null;
let modalViewportNormalizeTimer = null;

function markDashboardReady(selector) {
    document.querySelectorAll(selector).forEach((element) => {
        element.dataset.krReady = "1";
    });
}

function formatCount(value) {
    return new Intl.NumberFormat("en-US").format(Number(value) || 0);
}

function pluralize(value, singular, plural = `${singular}s`) {
    return `${formatCount(value)} ${value === 1 ? singular : plural}`;
}

function getUserLocale() {
    return user?.lang || navigator.language || "en-US";
}

function formatTimestamp(date = new Date()) {
    return new Intl.DateTimeFormat(getUserLocale(), {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
    }).format(date);
}

function formatShortTime(date = new Date()) {
    return new Intl.DateTimeFormat(getUserLocale(), {
        hour: "numeric",
        minute: "2-digit",
    }).format(date);
}

function buildJsonRpcBody(model, method, args = [], kwargs = {}) {
    return {
        jsonrpc: "2.0",
        method: "call",
        params: { model, method, args, kwargs },
        id: Date.now() + Math.floor(Math.random() * 1000),
    };
}

async function callKw(model, method, args = [], kwargs = {}) {
    const response = await fetch(`/web/dataset/call_kw/${model}/${method}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify(buildJsonRpcBody(model, method, args, kwargs)),
    });
    const payload = await response.json();
    if (payload.error) {
        throw new Error(payload.error.message || "RPC error");
    }
    return payload.result;
}

const COLOR_PALETTES = {
    default: {
        primary: "#875A7B",
        primaryHover: "#6d4a64",
        primaryText: "#ffffff",
        accent: "#875A7B",
        accentSoft: "rgba(135,90,123,0.12)",
        tabActive: "#151a1f",
        tabActiveText: "#ffffff",
    },
    blue: {
        primary: "#1a6fd4",
        primaryHover: "#155bb0",
        primaryText: "#ffffff",
        accent: "#1a6fd4",
        accentSoft: "rgba(26,111,212,0.12)",
        tabActive: "#1a6fd4",
        tabActiveText: "#ffffff",
    },
    red: {
        primary: "#d42b1a",
        primaryHover: "#b02315",
        primaryText: "#ffffff",
        accent: "#d42b1a",
        accentSoft: "rgba(212,43,26,0.12)",
        tabActive: "#d42b1a",
        tabActiveText: "#ffffff",
    },
};

function buildColorOverrideCSS(palette) {
    const p = palette.primary;
    const ph = palette.primaryHover;
    const pt = palette.primaryText;
    const soft = palette.accentSoft;
    const tabBg = palette.tabActive;
    const tabTxt = palette.tabActiveText;

    // Generate a semi-transparent shadow color from the primary
    const shadowAlpha = `color-mix(in srgb, ${p} 25%, transparent)`;

    return `
/* ============================================================
   KRAKEN COLOR THEME OVERRIDE — injected at runtime
   ============================================================ */

/* -- CSS Variables ----------------------------------------- */
:root {
    --o-brand-primary: ${p} !important;
    --o-brand-secondary: ${ph} !important;
    --kr-color-primary: ${p} !important;
    --kr-color-primary-hover: ${ph} !important;
    --kr-color-tab-active: ${tabBg} !important;
    --kr-color-tab-active-text: ${tabTxt} !important;
    --link-color: ${p} !important;
    --bs-primary: ${p} !important;
    --bs-primary-rgb: ${p} !important;
    --bs-link-color: ${p} !important;
    --bs-link-hover-color: ${ph} !important;
}

/* -- Primary buttons --------------------------------------- */
.btn-primary,
.o_form_button_save,
.btn.btn-primary {
    background-color: ${p} !important;
    border-color: ${p} !important;
    color: ${pt} !important;
}
.btn-primary:hover,
.btn-primary:focus,
.btn-primary:active,
.btn-primary.active,
.show > .btn-primary.dropdown-toggle,
.btn.btn-primary:hover,
.btn.btn-primary:focus,
.btn.btn-primary:active {
    background-color: ${ph} !important;
    border-color: ${ph} !important;
    color: ${pt} !important;
}
.btn-primary:focus,
.btn-primary.focus,
.btn.btn-primary:focus {
    box-shadow: 0 0 0 0.2rem ${soft} !important;
}

/* -- Outline primary buttons ------------------------------- */
.btn-outline-primary {
    color: ${p} !important;
    border-color: ${p} !important;
    background-color: transparent !important;
}
.btn-outline-primary:hover,
.btn-outline-primary:active,
.btn-outline-primary.active {
    background-color: ${p} !important;
    border-color: ${p} !important;
    color: ${pt} !important;
}

/* -- Links ------------------------------------------------- */
a:not(.btn):not(.nav-link):not(.dropdown-item):not(.kr_sp_rail_btn):not(.o_menu_brand) {
    color: ${p} !important;
}
a:not(.btn):not(.nav-link):not(.dropdown-item):not(.kr_sp_rail_btn):hover {
    color: ${ph} !important;
}
.text-primary { color: ${p} !important; }
.text-o-color-1 { color: ${p} !important; }

/* -- Odoo top main navbar ---------------------------------- */
.o_main_navbar,
.o_web_client:not(.kr_sp_global_mode) .o_main_navbar {
    background-color: ${p} !important;
    border-bottom-color: ${ph} !important;
}

/* -- Odoo horizontal menu active tab (kraken topbar) ------- */
.kr_sp_tabs .is-active,
.kr_sp_tabs .is-active:hover {
    background: ${tabBg} !important;
    color: ${tabTxt} !important;
    box-shadow: 0 3px 8px ${soft} !important;
}

/* -- Active rail buttons ----------------------------------- */
.kr_sp_rail_group_top .kr_sp_rail_btn.is-active:not(.kr_sp_color_swatch) {
    background: ${tabBg} !important;
    color: ${tabTxt} !important;
}

/* -- Badges ------------------------------------------------ */
.badge.bg-primary,
.badge-primary,
.badge.text-bg-primary {
    background-color: ${p} !important;
    color: ${pt} !important;
}

/* -- Form control focus ------------------------------------ */
.form-control:focus,
.form-select:focus,
.o_input:focus,
input:focus,
textarea:focus,
select:focus {
    border-color: ${p} !important;
    outline-color: ${p} !important;
    box-shadow: 0 0 0 0.2rem ${soft} !important;
}

/* -- Checkboxes & radio ------------------------------------ */
.form-check-input:checked,
.o_checkbox input:checked + span,
.o_field_boolean .o_checkbox:checked {
    background-color: ${p} !important;
    border-color: ${p} !important;
}
.form-check-input:focus {
    border-color: ${p} !important;
    box-shadow: 0 0 0 0.2rem ${soft} !important;
}

/* -- Progress bars ---------------------------------------- */
.progress-bar,
.o_progressbar_value {
    background-color: ${p} !important;
}

/* -- Pagination ------------------------------------------- */
.page-item.active .page-link,
.page-link:focus {
    background-color: ${p} !important;
    border-color: ${p} !important;
    color: ${pt} !important;
}

/* -- Dropdown active items --------------------------------- */
.dropdown-item.active,
.dropdown-item:active {
    background-color: ${p} !important;
    color: ${pt} !important;
}

/* -- Nav tabs active --------------------------------------- */
.nav-tabs .nav-link.active,
.nav-tabs .nav-item.show .nav-link {
    color: ${p} !important;
    border-bottom-color: ${p} !important;
}
.nav-pills .nav-link.active,
.nav-pills .show > .nav-link {
    background-color: ${p} !important;
    color: ${pt} !important;
}

/* -- Odoo status bar (workflow buttons) ------------------- */
.o_statusbar_status .o_arrow_button.btn-primary,
.o_statusbar_status button.o_arrow_button:last-child {
    background-color: ${p} !important;
    border-color: ${ph} !important;
    color: ${pt} !important;
}

/* -- Odoo list view selection highlight ------------------- */
.o_data_row.o_row_handle:hover,
.o_list_record_selector .form-check-input:checked {
    accent-color: ${p} !important;
}

/* -- Odoo breadcrumb active -------------------------------- */
.o_breadcrumb .active,
.breadcrumb-item.active {
    color: ${p} !important;
}

/* -- Odoo kanban stage fold indicator --------------------- */
.o_kanban_group.o_column_folded .o_kanban_header_title {
    color: ${p} !important;
}

/* -- Alert / info banners --------------------------------- */
.alert-primary {
    background-color: ${soft} !important;
    border-color: ${p} !important;
    color: ${p} !important;
}

/* -- Switch / toggle -------------------------------------- */
.form-switch .form-check-input:checked {
    background-color: ${p} !important;
    border-color: ${p} !important;
}

/* -- Odoo activity colors --------------------------------- */
.o_mail_activity_action .btn-primary,
.o_activity_btn .btn-primary {
    background-color: ${p} !important;
    border-color: ${p} !important;
}

/* -- Odoo pivot / graph highlight ------------------------- */
.o_graph_renderer .o_graph_main,
.o_pivot .o_pivot_header.o_pivot_origin_field {
    color: ${p} !important;
}

/* -- Odoo search panel selected --------------------------- */
.o_search_panel_category_value.active > header,
.o_search_panel_filter_value .o_search_panel_label_title:has(+ .o_search_panel_filter_value_count) {
    color: ${p} !important;
}
.o_searchview_input_container .o_facet_values {
    background-color: ${p} !important;
    color: ${pt} !important;
}

/* -- Odoo form view "Edit" mode active fields ------------- */
.o_form_editable .o_field_widget:focus-within {
    --o-field-border-focus: ${p} !important;
}

/* -- Priority star ---------------------------------------- */
.o_priority .o_priority_star.fa-star {
    color: ${p} !important;
}

/* -- Scrollbars ------------------------------------------- */
::-webkit-scrollbar-thumb {
    background: ${p} !important;
}

/* -- Kraken Dashboard specific ---------------------------- */
.kr_sp_tabs .is-active {
    background: ${tabBg} !important;
    color: ${tabTxt} !important;
}

/* -- Odoo "o-color" system -------------------------------- */
.o_tag.o_tag_color_0,
.badge.o_tag_color_0 {
    background-color: ${p} !important;
    color: ${pt} !important;
}
`.trim();
}

function applyColorTheme(colorName) {
    const palette = COLOR_PALETTES[colorName] || COLOR_PALETTES.default;

    // Inject or update the dynamic style override block
    let styleEl = document.getElementById("kr_color_theme_override");
    if (!styleEl) {
        styleEl = document.createElement("style");
        styleEl.id = "kr_color_theme_override";
        document.head.appendChild(styleEl);
    }
    styleEl.textContent = buildColorOverrideCSS(palette);

    // Also set CSS variables on root for any variable-based consumers
    const root = document.documentElement;
    root.style.setProperty("--kr-color-primary", palette.primary);
    root.style.setProperty("--kr-color-primary-hover", palette.primaryHover);
    root.style.setProperty("--kr-color-primary-text", palette.primaryText);
    root.style.setProperty("--kr-color-accent", palette.accent);
    root.style.setProperty("--kr-color-accent-soft", palette.accentSoft);
    root.style.setProperty("--kr-color-tab-active", palette.tabActive);
    root.style.setProperty("--kr-color-tab-active-text", palette.tabActiveText);
    root.style.setProperty("--o-brand-primary", palette.primary);
    root.style.setProperty("--o-brand-secondary", palette.primaryHover);

    // Update swatch active states
    document.querySelectorAll(".kr_sp_rail_group_top .kr_sp_color_swatch").forEach((btn) => {
        if (btn.dataset.krColor) {
            btn.classList.toggle("is-active", btn.dataset.krColor === colorName);
        }
    });
}


function getColorTheme() {
    return browser.localStorage.getItem(COLOR_KEY) || "default";
}

function setColorTheme(colorName) {
    const validColors = Object.keys(COLOR_PALETTES);
    const next = validColors.includes(colorName) ? colorName : "default";
    browser.localStorage.setItem(COLOR_KEY, next);
    applyColorTheme(next);
}

function applyTheme(mode) {
    const body = document.body;
    if (!body) {
        return;
    }
    const isDark = mode === "dark";
    body.classList.toggle("kr_sp_theme_dark", isDark);
    document.querySelectorAll(".o_web_client").forEach((webClient) => {
        webClient.classList.toggle("kr_sp_theme_dark", isDark);
    });
    document.querySelectorAll(".kr_sp_action_shell").forEach((shell) => {
        shell.classList.toggle("kr_sp_theme_dark", isDark);
    });
    document.querySelectorAll(".kr_sp_global_shell").forEach((shell) => {
        shell.classList.toggle("kr_sp_theme_dark", isDark);
    });

    document.querySelectorAll(".kr_sp_rail_group_top .kr_sp_rail_btn").forEach((btn) => {
        const action = btn.dataset.krAction;
        const btnColor = btn.dataset.krColor;
        if (btnColor) {
            // Color palette buttons — handled by applyColorTheme, keep as-is
            return;
        }
        const isLightButton = action === "theme-light";
        const isDarkButton = action === "theme-dark";
        const active = (mode === "light" && isLightButton) || (isDark && isDarkButton);
        btn.classList.toggle("is-active", active);
    });
}

function getThemeMode() {
    const cookieMode = cookie.get("color_scheme");
    if (cookieMode === "dark" || cookieMode === "light") {
        return cookieMode;
    }
    const storedMode = browser.localStorage.getItem(THEME_KEY);
    return storedMode === "dark" ? "dark" : "light";
}

function setThemeMode(mode) {
    const nextMode = mode === "dark" ? "dark" : "light";
    const previousCookieMode = cookie.get("color_scheme");
    cookie.set("color_scheme", nextMode);
    browser.localStorage.setItem(THEME_KEY, nextMode);
    applyTheme(nextMode);
    if (previousCookieMode !== nextMode) {
        browser.location.reload();
    }
}

function refreshThemeScope() {
    applyTheme(getThemeMode());
}

function setActiveButton(button, selector) {
    const group = button.closest(selector);
    if (!group) {
        return;
    }
    group.querySelectorAll("button").forEach((item) => item.classList.remove("is-active"));
    button.classList.add("is-active");
}

function isDashboardActionToken(actionToken) {
    const token = String(actionToken || "");
    return (
        token === "dashboards" ||
        token === "action_spreadsheet_dashboard" ||
        token.includes("spreadsheet_dashboard") ||
        token.includes("ir_actions_dashboard_action")
    );
}

function getMenuChildren(menuService, menu) {
    if (!menu?.id) {
        return [];
    }
    return menuService?.getMenuAsTree?.(menu.id)?.childrenTree || menu.childrenTree || [];
}

function findDashboardApp(menuService) {
    const apps = typeof menuService?.getApps === "function" ? menuService.getApps() : [];
    return (
        apps
            .filter((menu) => isDashboardMenuLabel(menu?.name))
            .sort((first, second) => {
                const firstChildren = getMenuChildren(menuService, first).length;
                const secondChildren = getMenuChildren(menuService, second).length;
                if (firstChildren !== secondChildren) {
                    return secondChildren - firstChildren;
                }
                return normalizeMenuLabel(second.name).length - normalizeMenuLabel(first.name).length;
            })[0] || null
    );
}

function resolveCurrentAppForTabs(menuService) {
    const currentApp = menuService?.getCurrentApp?.();
    const { actionId, actionToken } = getCurrentActionContext();
    const routeMenuId = Number.parseInt(router?.current?.menu_id, 10);
    const routeMenu =
        Number.isFinite(routeMenuId) && routeMenuId > 0 ? menuService?.getMenu?.(routeMenuId) || null : null;
    const matchedActionMenu =
        actionId || actionToken
            ? menuService?.getAll?.().find((menu) => {
                  if (!menu) {
                      return false;
                  }
                  return (
                      (actionId && menu.actionID === actionId) ||
                      (actionToken && typeof actionToken === "string" && menu.actionPath === actionToken)
                  );
              }) || null
            : null;
    const isDashboardMenuRoute =
        isDashboardMenuLabel(routeMenu?.name) || isDashboardMenuLabel(matchedActionMenu?.name);
    const hasNonDashboardRouteMenu = routeMenu?.id && !isDashboardMenuLabel(routeMenu.name);
    const hasNonDashboardActionMenu = matchedActionMenu?.id && !isDashboardMenuLabel(matchedActionMenu.name);
    const hasExplicitRouteSignal = !!(routeMenu || matchedActionMenu || actionId || actionToken);
    const isDashboardRoute =
        (!hasNonDashboardRouteMenu && !hasNonDashboardActionMenu && isDashboardActionToken(actionToken)) ||
        isDashboardMenuRoute ||
        (!hasExplicitRouteSignal && isDashboardContext());

    if (hasNonDashboardRouteMenu) {
        const routeAppId = routeMenu.appID || routeMenu.id;
        return menuService?.getMenu?.(routeAppId) || routeMenu;
    }

    if (hasNonDashboardActionMenu) {
        const matchAppId = matchedActionMenu.appID || matchedActionMenu.id;
        return menuService?.getMenu?.(matchAppId) || matchedActionMenu;
    }

    if (isDashboardRoute || isDashboardMenuRoute) {
        const dashboardApp = findDashboardApp(menuService);
        if (dashboardApp?.id) {
            return dashboardApp;
        }
    }

    const routeAppId = routeMenu?.appID || routeMenu?.id;
    if (routeAppId) {
        return menuService?.getMenu?.(routeAppId) || routeMenu;
    }

    if (matchedActionMenu) {
        const matchAppId = matchedActionMenu.appID || matchedActionMenu.id;
        if (matchAppId) {
            return menuService?.getMenu?.(matchAppId) || matchedActionMenu;
        }
    }

    if (currentApp?.id && !isDashboardRoute) {
        return currentApp;
    }

    return currentApp?.id ? currentApp : null;
}

function getCurrentAppSections(menuService) {
    const currentApp = resolveCurrentAppForTabs(menuService);
    if (!currentApp?.id) {
        return [];
    }
    return getMenuChildren(menuService, currentApp);
}

function findMenuInTree(nodes, targetMenuId) {
    if (!targetMenuId) {
        return null;
    }
    for (const node of nodes || []) {
        if (!node) {
            continue;
        }
        if (node.id === targetMenuId) {
            return node;
        }
        const childMatch = findMenuInTree(node.childrenTree || [], targetMenuId);
        if (childMatch) {
            return childMatch;
        }
    }
    return null;
}

function resolveTopSectionById(menuService, menuIdValue) {
    const menuId = Number.parseInt(menuIdValue, 10);
    if (!Number.isFinite(menuId)) {
        return null;
    }

    const cachedSection = currentTopSections.get(String(menuId));
    if (cachedSection) {
        return cachedSection;
    }

    const sections = getCurrentAppSections(menuService);
    const section = findMenuInTree(sections, menuId);
    if (section?.id) {
        currentTopSections.set(String(section.id), section);
    }
    return section || null;
}

function getCurrentActionContext() {
    const route = router?.current || {};
    const actionService = getWebclientActionService();
    const actionStack = Array.isArray(route.actionStack) ? route.actionStack : [];
    const routeAction = actionStack.at(-1)?.action || route.action;
    const currentAction = routeAction || actionService?.currentController?.action?.id || null;
    const numericActionId = Number.parseInt(currentAction, 10);
    return {
        actionId: Number.isFinite(numericActionId) ? numericActionId : null,
        actionToken: currentAction || null,
    };
}

function resolveCurrentMenu(menuService) {
    if (!menuService?.getAll) {
        return null;
    }

    const routeMenuId = Number.parseInt(router?.current?.menu_id, 10);
    const routeMenu =
        Number.isFinite(routeMenuId) && routeMenuId > 0 ? menuService.getMenu(routeMenuId) || null : null;

    const { actionId, actionToken } = getCurrentActionContext();
    const storedAppId = Number.parseInt(window.sessionStorage.getItem("menu_id"), 10);
    if (actionId || actionToken) {
        const matches = menuService.getAll().filter((menu) => {
            if (!menu) {
                return false;
            }
            return (
                (actionId && menu.actionID === actionId) ||
                (actionToken && typeof actionToken === "string" && menu.actionPath === actionToken)
            );
        });
        if (matches.length) {
            const preferredAppId = routeMenu?.appID || routeMenu?.id || storedAppId;
            return matches.find((menu) => menu.appID === preferredAppId) || matches[0];
        }
    }

    if (routeMenu) {
        return routeMenu;
    }
    return Number.isFinite(storedAppId) && storedAppId > 0 ? menuService.getMenu(storedAppId) || null : null;
}

function menuTreeContains(menu, targetMenuId, targetActionId) {
    if (!menu) {
        return false;
    }
    if ((targetMenuId && menu.id === targetMenuId) || (targetActionId && menu.actionID === targetActionId)) {
        return true;
    }
    return (menu.childrenTree || []).some((child) =>
        menuTreeContains(child, targetMenuId, targetActionId)
    );
}

function findActiveTopSection(sections, currentMenu) {
    const { actionId } = getCurrentActionContext();
    return (
        sections.find((section) => menuTreeContains(section, currentMenu?.id || null, actionId)) ||
        sections[0] ||
        null
    );
}

function collectActionableDescendants(menu) {
    const items = [];
    const seen = new Set();

    const traverseMenuTree = (tree, callback, parents = []) => {
        if (!tree) {
            return;
        }
        callback(tree, parents);
        (tree.childrenTree || []).forEach((child) =>
            traverseMenuTree(child, callback, parents.concat([tree]))
        );
    };

    for (const root of menu?.childrenTree || []) {
        traverseMenuTree(root, (node, parents) => {
            if (!node?.id || !node.actionID || seen.has(node.id)) {
                return;
            }
            seen.add(node.id);
            const label = normalizeMenuLabel(node.name || "Menu");
            const normalizedParents = parents.map((parent) => normalizeMenuLabel(parent.name || "Menu"));
            const immediateParent = normalizedParents[normalizedParents.length - 1] || "";
            const resolvedGroup = immediateParent && immediateParent !== label ? immediateParent : null;
            items.push({
                actionID: node.actionID,
                id: node.id,
                key: `${node.id}-${node.actionID}`,
                group: resolvedGroup,
                label,
            });
        });
    }

    return items;
}

function closeSubmenuPopover() {
    if (!activeSubmenuState) {
        return;
    }
    const { button, popover, onPointerDown, onKeyDown, onWindowChange } = activeSubmenuState;
    window.removeEventListener("pointerdown", onPointerDown, true);
    window.removeEventListener("keydown", onKeyDown);
    window.removeEventListener("resize", onWindowChange);
    window.removeEventListener("scroll", onWindowChange, true);
    button?.classList.remove("is-open");
    button?.setAttribute("aria-expanded", "false");
    popover?.remove();
    activeSubmenuState = null;
}

function openSubmenuPopover(button, menuService, activeMenuId) {
    const menuIdValue = button?.dataset?.krMenuId;
    const section =
        currentTopSections.get(menuIdValue || "") || resolveTopSectionById(menuService, menuIdValue);
    const items = collectActionableDescendants(section);
    if (!items.length) {
        if (section?.actionID) {
            navigateToMenu(section.id, section.actionID);
        }
        return;
    }
    if (!button) {
        return;
    }
    if (activeSubmenuState?.button === button) {
        closeSubmenuPopover();
        return;
    }

    closeSubmenuPopover();
    button.classList.add("is-open");
    button.setAttribute("aria-expanded", "true");

    const popover = document.createElement("div");
    popover.className = "o_popover popover kr_sp_submenu_popover_wrap";
    popover.setAttribute("role", "menu");
    popover.innerHTML = '<div class="popover-body kr_sp_submenu_popover"></div>';
    const body = popover.querySelector(".popover-body");
    const ungroupedItems = [];
    const groups = new Map();
    for (const item of items) {
        if (!item.group) {
            ungroupedItems.push(item);
            continue;
        }
        if (!groups.has(item.group)) {
            groups.set(item.group, []);
        }
        groups.get(item.group).push(item);
    }

    const appendItemButton = (item) => {
        const itemButton = document.createElement("button");
        itemButton.type = "button";
        itemButton.className = "dropdown-item";
        if (activeMenuId === item.id) {
            itemButton.classList.add("active");
        }
        itemButton.textContent = item.label;
        itemButton.dataset.krAction = "open-menu";
        itemButton.dataset.krMenuId = String(item.id);
        itemButton.dataset.krActionId = String(item.actionID);
        itemButton.addEventListener("click", (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            closeSubmenuPopover();
            navigateToMenu(item.id, item.actionID);
        });
        body.appendChild(itemButton);
    };

    for (const item of ungroupedItems) {
        appendItemButton(item);
    }

    if (ungroupedItems.length && groups.size) {
        const divider = document.createElement("div");
        divider.className = "kr_sp_submenu_group_divider";
        body.appendChild(divider);
    }

    const groupEntries = Array.from(groups.entries());
    groupEntries.forEach(([groupLabel, groupItems], index) => {
        const header = document.createElement("div");
        header.className = "kr_sp_submenu_group_title";
        if (groupItems.some((item) => item.id === activeMenuId)) {
            header.classList.add("is-active");
        }
        header.textContent = groupLabel;
        body.appendChild(header);

        for (const item of groupItems) {
            appendItemButton(item);
        }

        if (index < groupEntries.length - 1) {
            const divider = document.createElement("div");
            divider.className = "kr_sp_submenu_group_divider";
            body.appendChild(divider);
        }
    });
    document.body.appendChild(popover);

    const positionPopover = () => {
        const rect = button.getBoundingClientRect();
        popover.style.position = "fixed";
        popover.style.top = `${rect.bottom + 8}px`;
        popover.style.left = `${Math.max(8, rect.left)}px`;
        popover.style.maxHeight = `calc(100vh - ${rect.bottom + 24}px)`;
        popover.style.zIndex = "2200";
    };

    const onPointerDown = (ev) => {
        if (!popover.contains(ev.target) && !button.contains(ev.target)) {
            closeSubmenuPopover();
        }
    };
    const onKeyDown = (ev) => {
        if (ev.key === "Escape") {
            closeSubmenuPopover();
        }
    };
    const onWindowChange = (ev) => {
        if (ev && ev.target && (popover.contains(ev.target) || ev.target === popover)) {
            return;
        }
        closeSubmenuPopover();
    };

    positionPopover();
    window.addEventListener("pointerdown", onPointerDown, true);
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("resize", onWindowChange);
    window.addEventListener("scroll", onWindowChange, true);

    activeSubmenuState = {
        button,
        popover,
        onPointerDown,
        onKeyDown,
        onWindowChange,
    };
}

function scrollToTarget(id) {
    if (!id) {
        return;
    }
    const target = document.getElementById(id);
    if (!target) {
        return;
    }
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    target.classList.add("kr_sp_target_flash");
    window.setTimeout(() => target.classList.remove("kr_sp_target_flash"), 700);
}

function getWebclientMenuService() {
    const wowlRoot = window.odoo?.__WOWL_DEBUG__?.root;
    return wowlRoot?.menuService || wowlRoot?.env?.services?.menu || null;
}

function getWebclientCommandService() {
    return window.odoo?.__WOWL_DEBUG__?.root?.env?.services?.command || null;
}

function getWebclientActionService() {
    return window.odoo?.__WOWL_DEBUG__?.root?.env?.services?.action || null;
}

function getWebclientBus() {
    return window.odoo?.__WOWL_DEBUG__?.root?.env?.bus || null;
}

function hasVisibleModal() {
    return Array.from(document.querySelectorAll(".modal.show, .modal.d-block")).some((modal) => {
        const style = window.getComputedStyle(modal);
        return style.display !== "none" && style.visibility !== "hidden" && modal.getClientRects().length > 0;
    });
}

function getKrakenViewportElements() {
    return [
        document.documentElement,
        document.body,
        document.querySelector(".o_web_client"),
        document.querySelector(".o_web_client > .o_action_manager"),
        document.querySelector(".o_web_client > .o_action_manager > .o_action"),
        document.querySelector(".o_web_client > .o_action_manager > .o_action > .o_content"),
    ].filter(Boolean);
}

function captureModalViewportState() {
    const body = document.body;
    if (!body?.classList.contains("kr_sp_global_mode") || modalViewportSnapshot) {
        return;
    }
    modalViewportSnapshot = {
        windowX: window.scrollX || 0,
        windowY: window.scrollY || 0,
        elements: getKrakenViewportElements().map((element) => ({
            element,
            scrollLeft: element.scrollLeft || 0,
            scrollTop: element.scrollTop || 0,
        })),
    };
}

function clearModalCompensationStyles() {
    for (const element of getKrakenViewportElements()) {
        element.style.removeProperty("padding-right");
        element.style.removeProperty("padding-left");
        element.style.removeProperty("margin-right");
        element.style.removeProperty("margin-left");
    }
    document.body.style.removeProperty("overflow");
    document.body.style.removeProperty("position");
    document.body.style.removeProperty("top");
    document.body.style.removeProperty("left");
    document.body.style.removeProperty("right");
}

function normalizeModalViewportState() {
    const body = document.body;
    if (!body?.classList.contains("kr_sp_global_mode") || hasVisibleModal()) {
        return;
    }

    body.classList.remove("modal-open");
    clearModalCompensationStyles();

    if (modalViewportSnapshot) {
        for (const item of modalViewportSnapshot.elements) {
            if (item.element.isConnected) {
                item.element.scrollLeft = item.scrollLeft;
                item.element.scrollTop = item.scrollTop;
            }
        }
        window.scrollTo(modalViewportSnapshot.windowX, modalViewportSnapshot.windowY);
    }
    modalViewportSnapshot = null;
    renderAllTopbars();
    mountScrollers();
}

function setupModalViewportGuard() {
    if (modalViewportGuardReady || !document.body) {
        return;
    }
    modalViewportGuardReady = true;

    const scheduleCapture = () => {
        window.setTimeout(captureModalViewportState, 0);
    };
    const scheduleNormalize = () => {
        if (modalViewportNormalizeTimer) {
            window.clearTimeout(modalViewportNormalizeTimer);
        }
        window.setTimeout(normalizeModalViewportState, 0);
        modalViewportNormalizeTimer = window.setTimeout(() => {
            modalViewportNormalizeTimer = null;
            normalizeModalViewportState();
        }, 220);
    };

    document.addEventListener("show.bs.modal", scheduleCapture, true);
    document.addEventListener("shown.bs.modal", scheduleCapture, true);
    document.addEventListener("hide.bs.modal", scheduleNormalize, true);
    document.addEventListener("hidden.bs.modal", scheduleNormalize, true);
    new MutationObserver(() => {
        if (document.body.classList.contains("modal-open")) {
            captureModalViewportState();
        } else if (modalViewportSnapshot) {
            scheduleNormalize();
        }
    }).observe(document.body, {
        attributes: true,
        attributeFilter: ["class", "style"],
    });
}

function isDashboardContext() {
    return !!document.querySelector(".kr_sp_action_shell");
}

function isPendingDashboardNavigation() {
    const path = window.location.pathname.replace(/\/+$/, "") || "/";
    if (path === "/dashboard" || path.startsWith("/dashboard/")) {
        return true;
    }
    if (
        path === "/odoo/dashboard" ||
        path === "/odoo/dashboards" ||
        path.startsWith("/odoo/dashboard/") ||
        path.startsWith("/odoo/dashboards/")
    ) {
        return true;
    }

    const menuService = getWebclientMenuService();
    const routeMenuId = Number.parseInt(router?.current?.menu_id, 10);
    const routeMenu =
        Number.isFinite(routeMenuId) && routeMenuId > 0 ? menuService?.getMenu?.(routeMenuId) || null : null;
    if (routeMenu?.id) {
        return isDashboardMenuLabel(routeMenu.name);
    }

    const { actionId, actionToken } = getCurrentActionContext();
    if (isDashboardActionToken(actionToken)) {
        return true;
    }
    if ((actionId || actionToken) && menuService?.getAll) {
        const matchedActionMenu =
            menuService.getAll().find((menu) => {
                if (!menu) {
                    return false;
                }
                return (
                    (actionId && menu.actionID === actionId) ||
                    (actionToken && typeof actionToken === "string" && menu.actionPath === actionToken)
                );
            }) || null;
        return isDashboardMenuLabel(matchedActionMenu?.name);
    }

    return false;
}

function getSelectedCompanyName() {
    if (user?.activeCompany?.name) {
        return user.activeCompany.name;
    }
    if (user?.defaultCompany?.name) {
        return user.defaultCompany.name;
    }
    if (Array.isArray(user?.allowedCompanies) && user.allowedCompanies[0]?.name) {
        return user.allowedCompanies[0].name;
    }

    const sessionCompanyInfo = window.odoo?.__session_info__?.user_companies;
    if (sessionCompanyInfo && sessionCompanyInfo.allowed_companies) {
        const currentCompanyId = sessionCompanyInfo.current_company;
        const currentCompany = sessionCompanyInfo.allowed_companies[String(currentCompanyId)];
        if (currentCompany?.name) {
            return currentCompany.name;
        }
    }

    const companyService = window.odoo?.__WOWL_DEBUG__?.root?.env?.services?.company;
    return companyService?.currentCompany?.name || "";
}

function getSelectedCompanyId() {
    if (user?.activeCompany?.id) {
        return user.activeCompany.id;
    }
    if (user?.defaultCompany?.id) {
        return user.defaultCompany.id;
    }
    if (Array.isArray(user?.allowedCompanies) && user.allowedCompanies[0]?.id) {
        return user.allowedCompanies[0].id;
    }

    const sessionCompanyInfo = window.odoo?.__session_info__?.user_companies;
    if (sessionCompanyInfo?.current_company) {
        return sessionCompanyInfo.current_company;
    }

    const companyService = window.odoo?.__WOWL_DEBUG__?.root?.env?.services?.company;
    return companyService?.currentCompany?.id || null;
}

function getSelectedCompanyLogoSrc() {
    const companyId = getSelectedCompanyId();
    if (!companyId) {
        return "/web/binary/company_logo";
    }
    return `/web/image?model=res.company&field=logo&id=${companyId}`;
}

function shouldShowPendingActionSkeleton(actionManager) {
    if (isDashboardContext() || !isPendingDashboardNavigation()) {
        return false;
    }
    const currentAction = actionManager?.querySelector(":scope > .o_action");
    if (!currentAction) {
        return true;
    }
    if (currentAction.querySelector(".o_content, .o_control_panel, .o_renderer, .o_view_controller")) {
        return false;
    }
    return !currentAction.textContent.trim();
}

function syncPendingActionSkeleton() {
    const actionManager = document.querySelector(".o_web_client > .o_action_manager");
    if (!actionManager) {
        return;
    }

    const existing = document.getElementById("kr_sp_pending_action_skeleton");
    if (!shouldShowPendingActionSkeleton(actionManager)) {
        existing?.remove();
        return;
    }
    if (existing) {
        return;
    }

    const skeleton = document.createElement("section");
    skeleton.id = "kr_sp_pending_action_skeleton";
    skeleton.className = "kr_sp_pending_action_skeleton";
    skeleton.setAttribute("aria-hidden", "true");
    skeleton.innerHTML = `
        <div class="kr_sp_pending_header"></div>
        <div class="kr_sp_pending_grid">
            <article></article>
            <article></article>
            <article></article>
        </div>
        <div class="kr_sp_pending_grid is-bottom">
            <article></article>
            <article></article>
            <article></article>
        </div>
    `;
    actionManager.appendChild(skeleton);
}

function getUserAvatarSrc() {
    if (user?.partnerId) {
        return imageUrl("res.partner", user.partnerId, "avatar_128", {
            unique: user.writeDate,
        });
    }
    if (user?.userId) {
        return `/web/image?model=res.users&field=avatar_128&id=${user.userId}`;
    }
    return "/web/static/img/user_menu_avatar.png";
}

function getUserDisplayName() {
    return user?.name || "User";
}

function isDebugMode() {
    return !!window.odoo?.__WOWL_DEBUG__?.root?.env?.debug;
}

function getUserRoleLabel() {
    if (user?.isSystem) {
        return "Administrator";
    }
    if (user?.isAdmin) {
        return "Access Rights";
    }
    if (user?.isInternalUser) {
        return "Internal User";
    }
    return "Portal User";
}

function getUserMetaLabel() {
    return isDebugMode() ? session.db || "" : getUserRoleLabel();
}

function inferEnvironment() {
    const fingerprint = `${window.location.hostname} ${session.db || ""}`.toLowerCase();
    if (/(stag|stage|uat|preprod|sandbox|qa)/.test(fingerprint)) {
        return { label: "Staging", className: "is-staging" };
    }
    if (/(dev|test|local|demo)/.test(fingerprint)) {
        return { label: "Development", className: "is-development" };
    }
    return { label: "Production", className: "is-production" };
}

function getFiscalPeriodLabel() {
    const now = new Date();
    const quarter = Math.floor(now.getMonth() / 3) + 1;
    const dateLabel = new Intl.DateTimeFormat(getUserLocale(), {
        year: "numeric",
        month: "short",
        day: "numeric",
    }).format(now);
    return `Q${quarter} ${now.getFullYear()} • ${dateLabel}`;
}

function getShortcutHint() {
    const platform = navigator.platform || "";
    return /Mac|iPhone|iPad|iPod/i.test(platform) ? "Cmd+K search" : "Ctrl+K search";
}

function logThemeError(context, error) {
    console.error(`[kraken_backend_theme] ${context}`, error);
}

function runSafely(context, callback) {
    try {
        const result = callback();
        if (result && typeof result.then === "function") {
            return result.catch((error) => {
                logThemeError(context, error);
                return null;
            });
        }
        return result;
    } catch (error) {
        logThemeError(context, error);
        return null;
    }
}

function getLocaleTimeZoneLabel() {
    const locale = getUserLocale();
    const timeZone = user?.tz || Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
    return `${timeZone} / ${locale}`;
}

function setTextContent(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value;
    }
}

function setElementHidden(id, hidden) {
    const element = document.getElementById(id);
    if (element) {
        element.hidden = !!hidden;
    }
}

function setActionVisibility(action, visible) {
    document.querySelectorAll(`.kr_sp_footer_action[data-kr-action="${action}"]`).forEach((element) => {
        element.hidden = !visible;
    });
}

function setEnvironmentBadge(environment = inferEnvironment()) {
    const badge = document.getElementById("kr_sp_footer_env_badge");
    if (!badge) {
        return;
    }
    badge.textContent = environment.label || "Production";
    badge.classList.remove("is-production", "is-staging", "is-development");
    badge.classList.add(
        environment.className || `is-${(environment.key || "production").toLowerCase()}`
    );
}

function collectDashboardFilters() {
    const activeNodes = Array.from(
        document.querySelectorAll(
            ".o_spreadsheet_dashboard_search_panel .o_search_panel_category_value.active, " +
                ".o_spreadsheet_dashboard_search_panel .o_search_panel_filter_value.active"
        )
    );
    const labels = activeNodes
        .map((node) => (node.textContent || "").trim().replace(/\s+/g, " "))
        .filter(Boolean);

    if (!labels.length) {
        return "No filters applied";
    }
    if (labels.length <= 3) {
        return labels.join(" / ");
    }
    return `${labels.slice(0, 3).join(" / ")} +${labels.length - 3}`;
}

function collectDashboardScope() {
    const filters = collectDashboardFilters();
    if (filters !== "No filters applied") {
        return `Filtered view • ${filters}`;
    }
    const companyName = getSelectedCompanyName();
    return companyName ? `${companyName} • all dashboard records` : "All dashboard records";
}

function syncDashboardFooterContext() {
    if (!isDashboardContext()) {
        return;
    }
    const companyName = getSelectedCompanyName() || "Current Company";
    const dbName = session.db || "database";
    const userName = getUserDisplayName();
    const roleLabel = getUserRoleLabel();

    setEnvironmentBadge();
    setTextContent("kr_sp_footer_company_db", `${companyName} / ${dbName}`);
    setTextContent("kr_sp_footer_user_role", `${userName} / ${roleLabel}`);
    setTextContent("kr_sp_footer_period", getFiscalPeriodLabel());
    setTextContent("kr_sp_footer_scope", collectDashboardScope());
    setTextContent("kr_sp_footer_filters", collectDashboardFilters());
    setTextContent("kr_sp_footer_shortcut", getShortcutHint());
    setTextContent("kr_sp_footer_locale", getLocaleTimeZoneLabel());
    setTextContent("kr_sp_footer_odoo_version", session.server_version || "Odoo 19");
    setTextContent("kr_sp_footer_theme_version", KRAKEN_THEME_VERSION);
    setTextContent(
        "kr_sp_footer_debug_link",
        isDebugMode() ? "Developer Mode On" : "Developer Mode"
    );
}

function syncCompanyBrandName() {
    const companyName = getSelectedCompanyName();
    if (!companyName) {
        return;
    }
    document.querySelectorAll(".kr_sp_brand_name").forEach((element) => {
        element.textContent = companyName;
    });
}

function syncCompanyBrandLogo() {
    const logoSrc = getSelectedCompanyLogoSrc();
    document.querySelectorAll(".kr_sp_brand_logo").forEach((element) => {
        element.src = logoSrc;
    });
}

function syncProfileDetails() {
    const userName = getUserDisplayName();
    const metaLabel = getUserMetaLabel();
    const avatarSrc = getUserAvatarSrc();
    const debugMode = isDebugMode();

    document.querySelectorAll(".kr_sp_user_name").forEach((element) => {
        element.textContent = userName;
    });
    document.querySelectorAll(".kr_sp_user_meta").forEach((element) => {
        element.classList.toggle("is-db-badge", debugMode);
        if (debugMode) {
            element.innerHTML = `<i class="fa fa-database" aria-hidden="true"></i><span>${metaLabel}</span>`;
        } else {
            element.textContent = metaLabel;
        }
    });
    document.querySelectorAll(".kr_sp_user_avatar").forEach((element) => {
        element.src = avatarSrc;
        element.alt = userName;
    });
}

async function countModelRecords(model, domain = []) {
    try {
        return await callKw(model, "search_count", [domain]);
    } catch (error) {
        if (model !== "helpdesk.ticket" || !String(error?.message || error).includes("404")) {
            logThemeError(`failed to count ${model}`, error);
        }
        return null;
    }
}

function formatOptionalCount(value) {
    return Number.isFinite(value) ? formatCount(value) : "Unavailable";
}

function getActivityStatusLabel(dateDeadline) {
    if (!dateDeadline) {
        return "Pending";
    }
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const target = new Date(`${dateDeadline}T00:00:00`);
    if (Number.isNaN(target.getTime())) {
        return "Pending";
    }
    return target < today ? "Overdue" : "Open";
}

function formatActivityDate(dateDeadline) {
    if (!dateDeadline) {
        return "-";
    }
    const target = new Date(`${dateDeadline}T00:00:00`);
    if (Number.isNaN(target.getTime())) {
        return dateDeadline;
    }
    return new Intl.DateTimeFormat(getUserLocale(), {
        year: "numeric",
        month: "short",
        day: "numeric",
    }).format(target);
}

function getLocalDateString(date = new Date()) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

function renderRecentActivitiesTable(activities = []) {
    const tableBody = document.getElementById("kr_sp_recent_table_body");
    if (!tableBody) {
        return;
    }

    tableBody.replaceChildren();
    if (!activities.length) {
        const row = document.createElement("tr");
        ["No recent activities found", "-", "-", "-"].forEach((value) => {
            const cell = document.createElement("td");
            cell.textContent = value;
            row.appendChild(cell);
        });
        tableBody.appendChild(row);
        return;
    }

    activities.forEach((activity) => {
        const row = document.createElement("tr");
        row.dataset.krAction = "open-dashboard-activity-row";
        row.dataset.krModel = activity.res_model || "mail.activity";
        row.dataset.krResId = activity.res_id ? String(activity.res_id) : "";
        row.dataset.krActivityId = activity.id ? String(activity.id) : "";
        row.setAttribute("role", "button");
        row.tabIndex = 0;
        [
            activity.summary || "Activity",
            activity.res_model || "-",
            getActivityStatusLabel(activity.date_deadline),
            formatActivityDate(activity.date_deadline),
        ].forEach((value) => {
            const cell = document.createElement("td");
            cell.textContent = value;
            row.appendChild(cell);
        });
        tableBody.appendChild(row);
    });
}

function setDashboardChartBarHeights(values = []) {
    const finiteValues = values.map((value) => (Number.isFinite(value) ? value : 0));
    if (!finiteValues.length) {
        return;
    }
    const maxValue = Math.max(...finiteValues, 1);
    document.querySelectorAll(".kr_sp_chart_bars span").forEach((bar, index) => {
        const value = finiteValues[index] || 0;
        bar.style.setProperty("--p", `${Math.max(18, Math.round((value / maxValue) * 128))}px`);
    });
}

async function refreshDashboardOverview(force = false) {
    const overview = document.getElementById("kr_sp_overview");
    if (!overview) {
        return;
    }

    const companyName = getSelectedCompanyName() || "Current Company";
    const userName = getUserDisplayName();
    setTextContent("kr_sp_overview_user", userName);
    setTextContent("kr_sp_overview_scope", `${companyName} live operational snapshot.`);

    if (overview.dataset.krOverviewLoaded === "1" && !force) {
        markDashboardReady(".kr_sp_pending_live");
        return;
    }
    overview.dataset.krOverviewLoaded = "1";
    overview.dataset.krOverviewRefreshing = "1";
    document.querySelectorAll('[data-kr-action="refresh-dashboard-overview"]').forEach((button) => {
        button.disabled = true;
    });

    try {
    const todayDate = getLocalDateString();
    const overdueActivityDomain = [["date_deadline", "<", todayDate]];
    const todayActivityDomain = [["date_deadline", "=", todayDate]];
    const salesOrderDomain = [["state", "in", ["sale", "done"]]];
    const invoiceDomain = [["move_type", "in", ["out_invoice", "out_refund"]]];
    const quotationDomain = [["state", "in", ["draft", "sent"]]];
    const unpaidInvoiceDomain = [
        ["move_type", "=", "out_invoice"],
        ["state", "=", "posted"],
        ["payment_state", "in", ["not_paid", "partial"]],
    ];
    const crmLeadDomain = [
        ["type", "=", "lead"],
        ["active", "=", true],
    ];
    const openTicketDomain = [["stage_id.fold", "=", false]];

    const [
        partners,
        usersCount,
        activitiesCount,
        attachments,
        companies,
        customers,
        vendors,
        overdueActivities,
        todayActivities,
        salesOrders,
        invoices,
        crmLeads,
        quotations,
        unpaidInvoices,
        helpdeskTickets,
        activities,
    ] = await Promise.all([
        countModelRecords("res.partner"),
        countModelRecords("res.users", [["share", "=", false]]),
        countModelRecords("mail.activity"),
        countModelRecords("ir.attachment"),
        countModelRecords("res.partner", [["is_company", "=", true]]),
        countModelRecords("res.partner", [["customer_rank", ">", 0]]),
        countModelRecords("res.partner", [["supplier_rank", ">", 0]]),
        countModelRecords("mail.activity", overdueActivityDomain),
        countModelRecords("mail.activity", todayActivityDomain),
        countModelRecords("sale.order", salesOrderDomain),
        countModelRecords("account.move", invoiceDomain),
        countModelRecords("crm.lead", crmLeadDomain),
        countModelRecords("sale.order", quotationDomain),
        countModelRecords("account.move", unpaidInvoiceDomain),
        countModelRecords("helpdesk.ticket", openTicketDomain),
        callKw("mail.activity", "search_read", [[]], {
            fields: ["id", "summary", "res_model", "res_id", "date_deadline"],
            limit: 5,
            order: "date_deadline asc",
        }).catch((error) => {
            logThemeError("failed to load recent activities", error);
            return [];
        }),
    ]);
    const counts = [partners, usersCount, activitiesCount, attachments].filter(Number.isFinite);
    const totalRecords = counts.reduce((total, count) => total + count, 0);

    setTextContent("kr_sp_overview_total", counts.length ? formatCount(totalRecords) : "Unavailable");
    setTextContent(
        "kr_sp_overview_total_note",
        counts.length
            ? "Across core operational records"
            : "Live counts are unavailable for this user"
    );
    const urgentActivities =
        (Number.isFinite(overdueActivities) ? overdueActivities : 0) +
        (Number.isFinite(todayActivities) ? todayActivities : 0);
    const activityProgress =
        Number.isFinite(activitiesCount) && activitiesCount
            ? Math.min(100, Math.round((urgentActivities / activitiesCount) * 100))
            : 0;
    const progressFill = document.getElementById("kr_sp_progress_fill");
    if (progressFill) {
        progressFill.style.setProperty("--kr-progress", `${Math.max(activityProgress, urgentActivities ? 8 : 0)}%`);
    }
    const nextDueDate = activities.find((activity) => activity.date_deadline)?.date_deadline;

    setTextContent("kr_sp_metric_value_1", formatOptionalCount(overdueActivities));
    setTextContent("kr_sp_metric_value_2", formatOptionalCount(todayActivities));
    setTextContent("kr_sp_metric_value_3", formatOptionalCount(salesOrders));
    setTextContent("kr_sp_metric_value_4", formatOptionalCount(invoices));
    setTextContent("kr_sp_wallet_companies", formatOptionalCount(companies));
    setTextContent("kr_sp_wallet_customers", formatOptionalCount(customers));
    setTextContent("kr_sp_wallet_vendors", formatOptionalCount(vendors));
    setTextContent("kr_sp_live_leads", formatOptionalCount(crmLeads));
    setTextContent("kr_sp_live_quotations", formatOptionalCount(quotations));
    setTextContent("kr_sp_live_unpaid_invoices", formatOptionalCount(unpaidInvoices));
    setTextContent("kr_sp_live_tickets", formatOptionalCount(helpdeskTickets));
    setTextContent("kr_sp_chart_customers", formatOptionalCount(customers));
    setTextContent("kr_sp_chart_vendors", formatOptionalCount(vendors));
    setTextContent("kr_sp_chart_sales_orders", formatOptionalCount(salesOrders));
    setTextContent("kr_sp_chart_invoices", formatOptionalCount(invoices));
    setTextContent("kr_sp_progress_current", `${formatOptionalCount(urgentActivities)} urgent activities`);
    setTextContent("kr_sp_progress_total", Number.isFinite(activitiesCount) ? `${formatCount(activitiesCount)} open activities` : "Live records");
    setTextContent("kr_sp_progress_share", Number.isFinite(activitiesCount) ? `${activityProgress}% urgent` : "-");
    setTextContent("kr_sp_progress_today", formatOptionalCount(todayActivities));
    setTextContent("kr_sp_progress_due", nextDueDate ? formatActivityDate(nextDueDate) : "None");
    setTextContent("kr_sp_activity_status", activities.length ? "Live" : "Empty");
    setDashboardChartBarHeights([customers, vendors, salesOrders, invoices]);
    renderRecentActivitiesTable(activities);
    setTextContent("kr_sp_overview_updated", `Updated ${formatShortTime()}`);
    markDashboardReady(".kr_sp_pending_live");
    } finally {
    delete overview.dataset.krOverviewRefreshing;
    document.querySelectorAll('[data-kr-action="refresh-dashboard-overview"]').forEach((button) => {
        button.disabled = false;
    });
    }
}

async function refreshDashboardFooterData(force = false) {
    if (!isDashboardContext()) {
        return;
    }

    syncDashboardFooterContext();

    if (!force && Date.now() - footerLastLoadedAt < 30000) {
        return footerRefreshPromise;
    }
    if (footerRefreshPromise) {
        return footerRefreshPromise;
    }

    footerRefreshPromise = callKw("res.users", "get_kraken_dashboard_footer_data")
        .then((footerData) => {
            const nowLabel = formatTimestamp(new Date());
            const environment = footerData.environment || inferEnvironment();
            const supportContact = footerData.support_contact || "";
            const buildVersion = footerData.build_version || "";
            const quickLinks = footerData.quick_links || {};
            const status = footerData.system_status || {};
            const hasSystemStatus = Object.values(status).some((value) => value !== null && value !== undefined);

            setEnvironmentBadge({
                key: environment.key || environment.label?.toLowerCase() || "production",
                label: environment.label || "Production",
                className: `is-${(environment.key || "production").toLowerCase()}`,
            });
            setTextContent(
                "kr_sp_footer_company_db",
                `${footerData.company_name || getSelectedCompanyName() || "Current Company"} / ${footerData.database_name || session.db || "database"}`
            );
            setTextContent(
                "kr_sp_footer_user_role",
                `${footerData.user_name || getUserDisplayName()} / ${footerData.role_label || getUserRoleLabel()}`
            );
            setTextContent("kr_sp_footer_period", footerData.fiscal_period || getFiscalPeriodLabel());
            setTextContent("kr_sp_footer_scope", collectDashboardScope());
            setTextContent("kr_sp_footer_filters", collectDashboardFilters());
            setTextContent("kr_sp_footer_shortcut", getShortcutHint());
            setTextContent(
                "kr_sp_footer_locale",
                `${footerData.timezone || user?.tz || "UTC"} / ${footerData.locale || getUserLocale()}`
            );
            setTextContent("kr_sp_footer_odoo_version", footerData.odoo_version || session.server_version || "Odoo");
            setTextContent("kr_sp_footer_theme_version", footerData.theme_version || KRAKEN_THEME_VERSION);
            setTextContent("kr_sp_footer_last_refresh", nowLabel);
            setTextContent(
                "kr_sp_footer_debug_link",
                isDebugMode() ? "Developer Mode On" : "Developer Mode"
            );

            if (supportContact) {
                setTextContent("kr_sp_footer_support", supportContact);
            }
            if (buildVersion) {
                setTextContent("kr_sp_footer_build_version", buildVersion);
            }

            setElementHidden("kr_sp_footer_support_row", !supportContact);
            setElementHidden("kr_sp_footer_build_row", !buildVersion);

            setActionVisibility("open-settings", !!quickLinks.settings);
            setActionVisibility("open-users", !!quickLinks.users);
            setActionVisibility("open-scheduled-actions", !!quickLinks.scheduled_actions);
            setActionVisibility("toggle-debug", !!quickLinks.developer_mode);
            setElementHidden(
                "kr_sp_footer_actions",
                !Array.from(document.querySelectorAll("#kr_sp_footer_actions .kr_sp_footer_action")).some(
                    (element) => !element.hidden
                )
            );

            setElementHidden("kr_sp_footer_status_section", !hasSystemStatus);
            if (hasSystemStatus) {
                setTextContent(
                    "kr_sp_footer_jobs",
                    status.background_jobs === null || status.background_jobs === undefined
                        ? "Unavailable"
                        : `${pluralize(status.background_jobs, "job")} active`
                );
                setTextContent(
                    "kr_sp_footer_mail_queue",
                    status.mail_queue === null || status.mail_queue === undefined
                        ? "Unavailable"
                        : `${pluralize(status.mail_queue, "message")} queued`
                );
                setTextContent(
                    "kr_sp_footer_integrations",
                    status.integrations === null || status.integrations === undefined
                        ? "Not configured"
                        : `${pluralize(status.integrations, "integration")} enabled`
                );
            }
            footerLastLoadedAt = Date.now();
        })
        .finally(() => {
            footerRefreshPromise = null;
        });

    return footerRefreshPromise;
}

async function mountUserMenu() {
    const mountHosts = Array.from(document.querySelectorAll(".kr_sp_profile_menu_mount"));
    if (!mountHosts.length) {
        return;
    }
    const env = window.odoo?.__WOWL_DEBUG__?.root?.env;
    if (!env) {
        return;
    }

    const mounts = mountHosts
        .filter((host) => !host.dataset.krMounted)
        .map(async (host) => {
            host.dataset.krMounted = "1";
            try {
                await mountComponent(UserMenu, host, { env });
                host.querySelector(".o_user_menu")?.classList.add("kr_sp_profile_menu");
            } catch {
                host.dataset.krMounted = "";
            }
        });

    await Promise.all(mounts);
}

function buildTabsElement(menuService) {
    const currentApp = resolveCurrentAppForTabs(menuService);
    const sections = getMenuChildren(menuService, currentApp).slice(0, 10);
    const currentMenu = resolveCurrentMenu(menuService);
    const activeSection = findActiveTopSection(sections, currentMenu);
    currentTopSections = new Map(sections.map((section) => [String(section.id), section]));

    const tabs = document.createElement("div");
    tabs.className = "kr_sp_tabs";
    const signatureParts = [`app:${currentApp?.id || 0}`];

    if (!sections.length) {
        tabs.dataset.krTabsSignature = "empty";
        return tabs;
    }

    for (const section of sections) {
        const button = document.createElement("button");
        const label = normalizeMenuLabel(section.name || "Section");
        const descendants = collectActionableDescendants(section);
        const hasChildren = descendants.length > 0;
        signatureParts.push(
            `${section.id}:${section.actionID || 0}:${hasChildren ? 1 : 0}:${descendants.length}`
        );
        button.type = "button";
        button.className = "kr_sp_submenu_btn";
        button.textContent = label;
        button.dataset.krMenuId = String(section.id);
        if (section.actionID) {
            button.dataset.krActionId = String(section.actionID);
        }
        if (hasChildren) {
            button.classList.add("has-children");
            button.dataset.krAction = "open-submenu-popover";
            button.addEventListener("click", (ev) => {
                ev.preventDefault();
                ev.stopPropagation();
                const currentMenu = resolveCurrentMenu(menuService);
                openSubmenuPopover(button, menuService, currentMenu?.id || null);
            });
        } else if (section.actionID) {
            button.dataset.krAction = "open-menu";
            button.addEventListener("click", (ev) => {
                ev.preventDefault();
                ev.stopPropagation();
                closeSubmenuPopover();
                navigateToMenu(section.id, section.actionID);
            });
        } else {
            button.dataset.krAction = "open-apps";
            button.addEventListener("click", (ev) => {
                ev.preventDefault();
                ev.stopPropagation();
                closeSubmenuPopover();
                openAppsPage();
            });
        }
        if (activeSection?.id === section.id) {
            button.classList.add("is-active");
        }
        tabs.appendChild(button);
    }

    signatureParts.push(`active:${activeSection?.id || 0}`);
    tabs.dataset.krTabsSignature = signatureParts.join("|");

    return tabs;
}

function renderTabsInViewport(viewport, menuService) {
    if (!viewport) {
        return false;
    }
    const nextTabs = buildTabsElement(menuService);
    const currentTabs = viewport.querySelector(":scope > .kr_sp_tabs");
    if (nextTabs.dataset.krTabsSignature === "empty") {
        scheduleTabsRender();
        if (!currentTabs) {
            viewport.replaceChildren(nextTabs);
        }
        return false;
    }
    if (!currentTabs) {
        viewport.replaceChildren(nextTabs);
        return true;
    }
    if (currentTabs.dataset.krTabsSignature === nextTabs.dataset.krTabsSignature) {
        return true;
    }
    closeSubmenuPopover();
    currentTabs.replaceChildren(...nextTabs.childNodes);
    currentTabs.dataset.krTabsSignature = nextTabs.dataset.krTabsSignature || "";
    return true;
}

function openSearchPalette() {
    const commandService = getWebclientCommandService();
    if (commandService?.openMainPalette) {
        commandService.openMainPalette();
        return;
    }
    window.dispatchEvent(
        new KeyboardEvent("keydown", {
            key: "k",
            ctrlKey: true,
            bubbles: true,
        })
    );
}

function buildTopbarMarkup(context = "global") {
    const companyLogoSrc = getSelectedCompanyLogoSrc();
    const avatarSrc = getUserAvatarSrc();
    const modifier = context === "dashboard" ? "kr_sp_topbar--dashboard" : "kr_sp_topbar--global";

    return `
        <section class="kr_sp_topbar ${modifier} kr_sp_pending_shell" id="kr_sp_topbar">
            <div class="kr_sp_brand_section">
                <img src="${companyLogoSrc}" alt="Company" class="kr_sp_brand_logo"/>
                <span class="kr_sp_brand_name"></span>
            </div>
            <div class="kr_sp_tabs_cluster">
                <button type="button" class="kr_sp_tabs_scroll is-left" title="Scroll left" aria-label="Scroll left">
                    <i class="fa fa-angle-left"></i>
                </button>
                <div class="kr_sp_tabs_section">
                    <div class="kr_sp_tabs_viewport"></div>
                </div>
                <button type="button" class="kr_sp_tabs_scroll is-right" title="Scroll right" aria-label="Scroll right">
                    <i class="fa fa-angle-right"></i>
                </button>
            </div>
            <div class="kr_sp_right_section">
                <div class="kr_sp_topbar_icons">
                    <button type="button" class="kr_sp_search_btn" data-kr-action="open-search" title="Search menus (Ctrl+K)"><i class="fa fa-search"></i></button>
                    <div class="kr_sp_systray_mount"></div>
                </div>
                <div class="kr_sp_profile">
                    <img src="${avatarSrc}" alt="User" class="kr_sp_user_avatar"/>
                    <div class="kr_sp_user_text">
                        <span class="kr_sp_user_name"></span>
                        <small class="kr_sp_user_meta"></small>
                    </div>
                    <i class="fa fa-angle-down"></i>
                    <div class="kr_sp_profile_menu_mount"></div>
                </div>
            </div>
        </section>
    `;
}

function renderTopbarMount(mount) {
    if (!mount) {
        return;
    }
    const context = mount.dataset.krTopbarContext || "global";
    if (mount.dataset.krTopbarRendered === context && mount.querySelector(".kr_sp_topbar")) {
        return;
    }
    mount.dataset.krTopbarRendered = context;
    mount.innerHTML = buildTopbarMarkup(context);
    const topbar = mount.querySelector(".kr_sp_topbar");
    if (topbar) {
        topbar.dataset.krReady = "1";
    }
    const brandName = mount.querySelector(".kr_sp_brand_name");
    if (brandName) {
        brandName.textContent = getSelectedCompanyName();
    }
    const userName = mount.querySelector(".kr_sp_user_name");
    if (userName) {
        userName.textContent = getUserDisplayName();
    }
    const userMeta = mount.querySelector(".kr_sp_user_meta");
    if (userMeta) {
        userMeta.textContent = getUserMetaLabel();
    }
}

function renderAllTopbars() {
    const mounts = document.querySelectorAll(".kr_sp_topbar_mount");
    if (mounts.length) {
        systrayMountRetryCount = 0;
        tabsRenderRetryCount = 0;
    }
    mounts.forEach(renderTopbarMount);
}

function scheduleSystemTrayMount() {
    if (systrayMountRetryTimer || systrayMountRetryCount >= 8) {
        return;
    }
    systrayMountRetryCount += 1;
    systrayMountRetryTimer = window.setTimeout(() => {
        systrayMountRetryTimer = null;
        mountSystemTray();
    }, Math.min(900, 80 * systrayMountRetryCount));
}

function mountSystemTray() {
    const mountHosts = Array.from(document.querySelectorAll(".kr_sp_systray_mount"));
    if (!mountHosts.length) {
        scheduleSystemTrayMount();
        return;
    }

    const dashboardHost = mountHosts.find((host) => host.closest(".kr_sp_topbar--dashboard"));
    const globalHost = mountHosts.find((host) => host.closest(".kr_sp_topbar--global"));
    const activeHost = dashboardHost || globalHost || mountHosts[0];
    const systray =
        document.querySelector(".kr_sp_systray_menu") ||
        document.querySelector(".o_main_navbar .o_menu_systray") ||
        document.querySelector(".o_menu_systray");
    if (!activeHost || !systray) {
        scheduleSystemTrayMount();
        return;
    }

    if (systray.parentElement !== activeHost) {
        activeHost.appendChild(systray);
    }
    systray.classList.add("kr_sp_systray_menu");
    systrayMountRetryCount = 0;
}

function renderGlobalShell() {
    const body = document.body;
    if (!body) {
        return;
    }

    const webClient = document.querySelector(".o_web_client");
    const actionManager = webClient?.querySelector(":scope > .o_action_manager");
    if (!webClient || !actionManager) {
        return;
    }

    const enableGlobalMode = () => {
        body.classList.add("kr_sp_global_mode");
        webClient.classList.add("kr_sp_global_mode");
    };

    const existing = document.getElementById("kr_sp_global_shell");
    if (existing) {
        if (existing.parentElement !== webClient || existing.nextElementSibling !== actionManager) {
            webClient.insertBefore(existing, actionManager);
        }
        enableGlobalMode();
        renderAllTopbars();
        syncPendingActionSkeleton();
        return;
    }

    const shell = document.createElement("section");
    shell.id = "kr_sp_global_shell";
    shell.className = "kr_sp_global_shell";
    shell.innerHTML = `
        <div class="kr_sp_topbar_mount" data-kr-topbar-context="global"></div>
        <div class="kr_sp_rail_group kr_sp_rail_group_top">
            <button type="button" class="kr_sp_rail_btn is-active" data-kr-action="theme-light" title="Light mode"><i class="fa fa-sun-o"></i></button>
            <button type="button" class="kr_sp_rail_btn" data-kr-action="theme-dark" title="Dark mode"><i class="fa fa-moon-o"></i></button>
        </div>
        <div class="kr_sp_rail_group kr_sp_rail_group_main">
            <button type="button" class="kr_sp_rail_btn is-active" data-kr-action="workspace-modal" title="Workspace"><i class="fa fa-th-large"></i></button>
            <div id="kr_sp_rail_apps" class="kr_sp_rail_apps"></div>
        </div>
        <div class="kr_sp_rail_group kr_sp_rail_group_bottom">
            <button type="button" class="kr_sp_rail_btn" data-kr-action="open-apps" title="Apps"><i class="fa fa-th-large"></i></button>
            <button type="button" class="kr_sp_rail_btn" data-kr-action="open-settings" title="Settings"><i class="fa fa-cog"></i></button>
            <button type="button" class="kr_sp_rail_btn" data-kr-action="go-home" title="Logout"><i class="fa fa-sign-out"></i></button>
        </div>
        <div id="kr_sp_workspace_modal" class="kr_sp_workspace_modal" aria-hidden="true" role="dialog" aria-modal="true" aria-label="Apps">
            <div class="kr_sp_workspace_inner">
                <div class="kr_sp_workspace_topbar">
                    <div class="kr_sp_workspace_topbar_left">
                        <span class="kr_sp_workspace_title"><i class="fa fa-th-large"></i> Apps</span>
                    </div>
                    <div class="kr_sp_workspace_topbar_center">
                        <div class="kr_sp_workspace_search_wrap">
                            <i class="fa fa-search kr_sp_workspace_search_icon"></i>
                            <input
                                id="kr_sp_workspace_search"
                                type="text"
                                class="kr_sp_workspace_search_input"
                                placeholder="Search apps..."
                                autocomplete="off"
                                spellcheck="false"
                            />
                            <button type="button" class="kr_sp_workspace_search_clear" id="kr_sp_workspace_search_clear" title="Clear search" style="display:none">
                                <i class="fa fa-times-circle"></i>
                            </button>
                        </div>
                    </div>
                    <div class="kr_sp_workspace_topbar_right">
                        <button type="button" class="kr_sp_workspace_close" data-kr-action="workspace-close" title="Close">
                            <i class="fa fa-times"></i>
                        </button>
                    </div>
                </div>
                <div class="kr_sp_workspace_body">
                    <div id="kr_sp_workspace_grid" class="kr_sp_workspace_grid"></div>
                    <div id="kr_sp_workspace_no_results" class="kr_sp_workspace_no_results" style="display:none">
                        <i class="fa fa-search"></i>
                        <span>No apps found</span>
                    </div>
                </div>
            </div>
        </div>
    `;
    webClient.insertBefore(shell, actionManager);
    enableGlobalMode();
    renderAllTopbars();
    syncPendingActionSkeleton();
}

async function loadRootMenus() {
    if (cachedRootMenus) {
        return cachedRootMenus;
    }

    const menuService = getWebclientMenuService();
    if (menuService?.getApps) {
        const apps = menuService
            .getApps()
            .filter((menu) => menu && menu.id && menu.name)
            .map((menu) => ({
                id: menu.id,
                name: menu.name,
                actionID: menu.actionID,
                webIcon: menu.webIcon,
                webIconData: menu.webIconData,
            }));
        if (apps.length) {
            cachedRootMenus = apps;
            return cachedRootMenus;
        }
    }

    let payload = null;
    if (window.odoo?.loadMenusPromise) {
        payload = await window.odoo.loadMenusPromise;
    } else {
        const response = await fetch("/web/webclient/load_menus", {
            method: "GET",
            credentials: "same-origin",
            cache: "no-store",
        });
        payload = await response.json();
    }
    const root = payload?.root || {};
    const rootChildren = Array.isArray(root.children) ? root.children : [];
    let seenDashboardMenu = false;
    cachedRootMenus = rootChildren
        .map((menuId) => payload?.[menuId])
        .filter((menu) => menu && menu.id && menu.name)
        .map((menu) => ({
            id: menu.id,
            name: menu.name,
            actionID: menu.actionID,
            webIcon: menu.webIcon,
            webIconData: menu.webIconData,
        }))
        .filter((menu) => {
            const label = normalizeMenuLabel(menu.name).toLowerCase();
            if (label === "dashboard" || label === "dashboards") {
                if (seenDashboardMenu) {
                    return false;
                }
                seenDashboardMenu = true;
            }
            return true;
        });
    return cachedRootMenus;
}

function menuInitial(name) {
    if (!name) {
        return "A";
    }
    const normalizedName = name.replace(/[\uE000-\uF8FF]/g, "").trim();
    const token = (normalizedName.split(/\s+/)[0] || "A").slice(0, 1);
    return token.toUpperCase();
}

function isDashboardMenuLabel(name) {
    const canonical = normalizeMenuLabel(name).toLowerCase().replace(/[^a-z0-9]/g, "");
    return canonical === "dashboard" || canonical === "dashboards";
}

function isReservedRailMenuLabel(name) {
    const canonical = normalizeMenuLabel(name).toLowerCase().replace(/[^a-z0-9]/g, "");
    return canonical === "apps" || canonical === "settings";
}

function getFavoriteMenuIds() {
    return Array.isArray(session?.kraken_favorite_menu_ids)
        ? session.kraken_favorite_menu_ids.map((menuId) => String(menuId))
        : [];
}

function setFavoriteMenuIds(menuIds) {
    const normalizedIds = [...new Set(menuIds.map((menuId) => String(menuId)).filter(Boolean))];
    session.kraken_favorite_menu_ids = normalizedIds.map((menuId) => Number(menuId)).filter(Number.isFinite);
    return normalizedIds;
}

function isFavoriteMenu(menuId) {
    return getFavoriteMenuIds().includes(String(menuId));
}

async function toggleFavoriteMenu(menuId) {
    const normalizedMenuId = String(menuId || "");
    if (!normalizedMenuId) {
        return getFavoriteMenuIds();
    }
    const menuIds = await callKw("res.users", "kraken_toggle_favorite_menu", [Number(normalizedMenuId)]);
    return setFavoriteMenuIds(menuIds || []);
}

function pruneDuplicateDashboardItems(root) {
    if (!root) {
        return;
    }
    root.querySelectorAll("button").forEach((button) => {
        const canonical = normalizeMenuLabel(button.textContent).toLowerCase().replace(/[^a-z0-9]/g, "");
        if (canonical === "dashboards") {
            button.remove();
        }
    });
}

function normalizeMenuLabel(name) {
    const cleaned = (name || "").replace(/[\uE000-\uF8FF]/g, "").trim();
    if (cleaned === "Kraken Dashboard") {
        return "Dashboard";
    }
    return cleaned || "Dashboard";
}

function menuIconSrc(menu) {
    if (menu?.webIconData) {
        const value = String(menu.webIconData).trim();
        if (value.startsWith("data:image")) {
            return value;
        }
        if (value.startsWith("/") || value.startsWith("http://") || value.startsWith("https://")) {
            return value;
        }
        return `data:image/png;base64,${value}`;
    }
    if (menu?.webIcon && menu.webIcon.includes(",")) {
        return `/${menu.webIcon.replace(",", "/")}`;
    }
    return null;
}

function navigateToMenu(menuId, actionId) {
    if (!menuId) {
        return;
    }
    closeWorkspaceModal();
    const menuService = getWebclientMenuService();
    if (menuService?.selectMenu) {
        try {
            menuService.selectMenu(Number(menuId));
            return;
        } catch (error) {
            logThemeError("menu navigation via selectMenu failed", error);
        }
    }

    const hash = new URLSearchParams();
    hash.set("menu_id", String(menuId));
    if (actionId) {
        hash.set("action", String(actionId));
    }
    window.location.assign(`/odoo/web#${hash.toString()}`);
}

function renderAllTabs() {
    const menuService = getWebclientMenuService();
    if (!menuService) {
        scheduleTabsRender();
        return;
    }
    const viewports = document.querySelectorAll(".kr_sp_tabs_viewport");
    if (!viewports.length) {
        scheduleTabsRender();
        return;
    }
    const renderedAnyTabs = Array.from(viewports).some((viewport) =>
        renderTabsInViewport(viewport, menuService)
    );
    if (renderedAnyTabs) {
        tabsRenderRetryCount = 0;
    } else {
        scheduleTabsRender();
    }
}

function scheduleTabsRender() {
    if (tabsRenderRetryTimer || tabsRenderRetryCount >= 8) {
        return;
    }
    tabsRenderRetryCount += 1;
    tabsRenderRetryTimer = window.setTimeout(() => {
        tabsRenderRetryTimer = null;
        renderAllTabs();
        mountScrollers();
    }, Math.min(900, 80 * tabsRenderRetryCount));
}

function renderWorkspaceGrid(menus) {
    const grid = document.getElementById("kr_sp_workspace_grid");
    if (!grid) {
        return;
    }
    grid.innerHTML = "";

    let seenDashboardMenu = false;
    for (const menu of menus) {
        if (isDashboardMenuLabel(menu.name)) {
            if (seenDashboardMenu) {
                continue;
            }
            seenDashboardMenu = true;
        }

        const card = document.createElement("div");
        card.className = "kr_sp_workspace_item";
        card.setAttribute("role", "button");
        card.tabIndex = 0;
        const label = normalizeMenuLabel(menu.name);
        const iconSrc = menuIconSrc(menu);
        const isReservedRailMenu = isReservedRailMenuLabel(menu.name);
        const favorite = isFavoriteMenu(menu.id);
        const iconWrap = document.createElement("div");
        iconWrap.className = "kr_sp_workspace_icon_wrap";
        const icon = document.createElement("span");
        icon.className = "kr_sp_workspace_icon";
        if (iconSrc) {
            const image = document.createElement("img");
            image.src = iconSrc;
            image.alt = "";
            icon.appendChild(image);
        } else {
            icon.textContent = menuInitial(label);
        }
        iconWrap.appendChild(icon);
        const labelElement = document.createElement("span");
        labelElement.className = "kr_sp_workspace_label";
        labelElement.textContent = label;
        card.appendChild(iconWrap);
        card.appendChild(labelElement);
        if (!isReservedRailMenu) {
            const favoriteButton = document.createElement("button");
            favoriteButton.type = "button";
            favoriteButton.className = `kr_sp_workspace_favorite${favorite ? " is-active" : ""}`;
            favoriteButton.title = favorite ? "Remove from favorites" : "Add to favorites";
            favoriteButton.dataset.krAction = "toggle-favorite-menu";
            favoriteButton.dataset.krMenuId = String(menu.id);
            favoriteButton.setAttribute("aria-pressed", favorite ? "true" : "false");
            favoriteButton.innerHTML = `<i class="fa ${favorite ? "fa-star" : "fa-star-o"}"></i>`;
            card.appendChild(favoriteButton);
        }

        card.addEventListener("click", (ev) => {
            if (ev.target.closest(".kr_sp_workspace_favorite")) {
                return;
            }
            navigateToMenu(menu.id, menu.actionID);
        });
        card.addEventListener("keydown", (ev) => {
            if (ev.target.closest(".kr_sp_workspace_favorite")) {
                return;
            }
            if (ev.key === "Enter" || ev.key === " ") {
                ev.preventDefault();
                navigateToMenu(menu.id, menu.actionID);
            }
        });
        grid.appendChild(card);
    }

    pruneDuplicateDashboardItems(grid);
}

let workspaceModalEscHandler = null;

function filterWorkspaceGrid(query) {
    const grid = document.getElementById("kr_sp_workspace_grid");
    const noResults = document.getElementById("kr_sp_workspace_no_results");
    const clearBtn = document.getElementById("kr_sp_workspace_search_clear");
    if (!grid) {
        return;
    }
    const normalizedQuery = (query || "").trim().toLowerCase();
    let visibleCount = 0;
    grid.querySelectorAll(".kr_sp_workspace_item").forEach((item) => {
        const label = item.querySelector(".kr_sp_workspace_label")?.textContent?.trim().toLowerCase() || "";
        const matches = !normalizedQuery || label.includes(normalizedQuery);
        item.style.display = matches ? "" : "none";
        if (matches) {
            visibleCount++;
        }
    });
    if (noResults) {
        noResults.style.display = normalizedQuery && visibleCount === 0 ? "flex" : "none";
    }
    if (clearBtn) {
        clearBtn.style.display = normalizedQuery ? "" : "none";
    }
}

function setupWorkspaceSearch() {
    const input = document.getElementById("kr_sp_workspace_search");
    const clearBtn = document.getElementById("kr_sp_workspace_search_clear");
    if (!input || input.dataset.krSearchReady) {
        return;
    }
    input.dataset.krSearchReady = "1";
    input.addEventListener("input", () => {
        filterWorkspaceGrid(input.value);
    });
    input.addEventListener("keydown", (ev) => {
        if (ev.key === "Escape") {
            if (input.value) {
                ev.stopPropagation();
                input.value = "";
                filterWorkspaceGrid("");
            }
        }
    });
    if (clearBtn) {
        clearBtn.addEventListener("click", () => {
            input.value = "";
            filterWorkspaceGrid("");
            input.focus();
        });
    }
}

function openWorkspaceModal() {
    const modal = document.getElementById("kr_sp_workspace_modal");
    if (!modal) {
        return;
    }
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");

    // Reset search
    const input = document.getElementById("kr_sp_workspace_search");
    if (input) {
        input.value = "";
        filterWorkspaceGrid("");
        setupWorkspaceSearch();
        window.setTimeout(() => input.focus(), 80);
    }

    if (workspaceModalEscHandler) {
        window.removeEventListener("keydown", workspaceModalEscHandler);
    }
    workspaceModalEscHandler = (ev) => {
        if (ev.key === "Escape") {
            const searchInput = document.getElementById("kr_sp_workspace_search");
            if (searchInput?.value) {
                return; // let the input's own ESC handler clear it first
            }
            closeWorkspaceModal();
        }
    };
    window.addEventListener("keydown", workspaceModalEscHandler);
}

function closeWorkspaceModal() {
    const modal = document.getElementById("kr_sp_workspace_modal");
    if (!modal) {
        return;
    }
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");

    // Clear search on close
    const input = document.getElementById("kr_sp_workspace_search");
    if (input) {
        input.value = "";
        filterWorkspaceGrid("");
    }

    if (workspaceModalEscHandler) {
        window.removeEventListener("keydown", workspaceModalEscHandler);
        workspaceModalEscHandler = null;
    }
}

function getSidebarMenus(menus) {
    const visibleMenus = menus.filter((menu) => !isReservedRailMenuLabel(menu.name));
    const dashboardMenu = visibleMenus.find((menu) => isDashboardMenuLabel(menu.name)) || null;
    const favoriteMenuIds = getFavoriteMenuIds();
    const favoriteMenus = favoriteMenuIds
        .map((favoriteId) => visibleMenus.find((menu) => String(menu.id) === favoriteId))
        .filter(Boolean)
        .filter((menu) => !isDashboardMenuLabel(menu.name));
    return (dashboardMenu ? [dashboardMenu, ...favoriteMenus] : favoriteMenus)
        .slice(0, SIDEBAR_APP_LIMIT);
}

async function buildSidebarApps({ force = false } = {}) {
    const containers = Array.from(document.querySelectorAll(".kr_sp_rail_apps"));
    if (!containers.length) {
        return;
    }

    const pendingContainers = force ? containers : containers.filter((container) => !container.dataset.krReady);
    if (!pendingContainers.length) {
        if (cachedRootMenus) {
            renderWorkspaceGrid(cachedRootMenus);
        }
        return;
    }

    try {
        const menus = await loadRootMenus();
        const sidebarMenus = getSidebarMenus(menus);
        pendingContainers.forEach((container) => {
            container.innerHTML = "";
        });

        for (const menu of sidebarMenus) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "kr_sp_rail_btn";
            const label = normalizeMenuLabel(menu.name);
            button.title = label;
            button.dataset.krAction = "open-menu";
            button.dataset.krMenuId = String(menu.id);
            button.dataset.krActionId = menu.actionID ? String(menu.actionID) : "";
            const iconSrc = menuIconSrc(menu);
            if (isDashboardMenuLabel(menu.name)) {
                button.innerHTML = '<i class="fa fa-dashboard"></i>';
            } else if (iconSrc) {
                button.innerHTML = `<span class="kr_sp_app_icon"><img src="${iconSrc}" alt=""/></span>`;
            } else {
                button.innerHTML = `<span class="kr_sp_app_initial">${menuInitial(label)}</span>`;
            }
            pendingContainers.forEach((container) => {
                container.appendChild(button.cloneNode(true));
            });
        }

        renderWorkspaceGrid(menus);
        pendingContainers.forEach((container) => {
            container.dataset.krReady = "1";
        });
    } catch {
        pendingContainers.forEach((container) => {
            container.dataset.krReady = "";
        });
    }
}

function openBackendList({ name, model, domain = [], views = [[false, "list"], [false, "form"]] }) {
    const actionService = getWebclientActionService();
    if (!actionService?.doAction) {
        return;
    }
    actionService.doAction({
        type: "ir.actions.act_window",
        name,
        res_model: model,
        domain,
        views,
        target: "current",
    });
}

function openBackendRecord({ name, model, resId }) {
    const actionService = getWebclientActionService();
    if (!actionService?.doAction || !model || !Number.isFinite(resId)) {
        return;
    }
    actionService.doAction({
        type: "ir.actions.act_window",
        name: name || "Record",
        res_model: model,
        res_id: resId,
        views: [[false, "form"]],
        target: "current",
    });
}

function openAppsPage() {
    window.location.assign("/odoo/apps");
}

function toggleDeveloperMode() {
    const url = new URL(window.location.href);
    if (isDebugMode()) {
        url.searchParams.delete("debug");
    } else {
        url.searchParams.set("debug", "1");
    }
    window.location.assign(url.toString());
}

function setupControlButtons() {
    const root = document.body;
    if (!root || root.dataset.krControlsReady) {
        return;
    }
    root.dataset.krControlsReady = "1";

    applyTheme(getThemeMode());

    root.addEventListener("click", (ev) => {
        const button = ev.target.closest("button, [data-kr-action], [data-kr-scroll]");
        if (!button) {
            return;
        }

        try {
            const scrollTarget = button.dataset.krScroll;
            if (scrollTarget) {
                ev.preventDefault();
                scrollToTarget(scrollTarget);
            }

            if (button.classList.contains("kr_sp_rail_btn") && button.closest(".kr_sp_rail_group_main")) {
                setActiveButton(button, ".kr_sp_rail_group_main");
            }

            const action = button.dataset.krAction;
            if (action === "theme-light") {
                ev.preventDefault();
                setThemeMode("light");
            }

            if (action === "theme-dark") {
                ev.preventDefault();
                setThemeMode("dark");
            }

            if (action === "theme-color") {
                ev.preventDefault();
                const colorName = button.dataset.krColor || "default";
                setColorTheme(colorName);
            }

            if (action === "workspace-modal") {
                ev.preventDefault();
                openWorkspaceModal();
            }

            if (action === "workspace-close") {
                ev.preventDefault();
                closeWorkspaceModal();
            }

            if (action === "toggle-favorite-menu") {
                ev.preventDefault();
                ev.stopPropagation();
                const menuId = Number.parseInt(button.dataset.krMenuId, 10);
                if (Number.isFinite(menuId)) {
                    toggleFavoriteMenu(menuId)
                        .then(() => {
                            if (cachedRootMenus) {
                                renderWorkspaceGrid(cachedRootMenus);
                            }
                            buildSidebarApps({ force: true });
                        })
                        .catch((error) => logThemeError("favorite menu toggle failed", error));
                }
            }

            if (action === "open-menu") {
                ev.preventDefault();
                const menuId = Number.parseInt(button.dataset.krMenuId, 10);
                const actionId = Number.parseInt(button.dataset.krActionId, 10);
                if (Number.isFinite(menuId)) {
                    closeSubmenuPopover();
                    navigateToMenu(menuId, Number.isFinite(actionId) ? actionId : null);
                }
            }

            if (action === "open-submenu-popover") {
                ev.preventDefault();
                const menuService = getWebclientMenuService();
                const currentMenu = resolveCurrentMenu(menuService);
                openSubmenuPopover(button, menuService, currentMenu?.id || null);
            }

            if (action === "go-home") {
                ev.preventDefault();
                closeSubmenuPopover();
                window.location.assign("/web/session/logout?redirect=/web/login");
            }

            if (action === "open-dashboard") {
                ev.preventDefault();
                closeSubmenuPopover();
                window.location.assign("/odoo/web#action=spreadsheet_dashboard.ir_actions_dashboard_action");
            }

            if (action === "open-apps") {
                ev.preventDefault();
                closeSubmenuPopover();
                openAppsPage();
            }

            if (action === "open-settings") {
                ev.preventDefault();
                closeSubmenuPopover();
                window.location.assign("/odoo/settings");
            }

            if (action === "open-users") {
                ev.preventDefault();
                closeSubmenuPopover();
                openBackendList({ name: "Users", model: "res.users" });
            }

            if (action === "open-partners") {
                ev.preventDefault();
                closeSubmenuPopover();
                openBackendList({ name: "Partners", model: "res.partner" });
            }

            if (action === "open-activities") {
                ev.preventDefault();
                closeSubmenuPopover();
                openBackendList({ name: "Activities", model: "mail.activity" });
            }

            if (action === "open-attachments") {
                ev.preventDefault();
                closeSubmenuPopover();
                openBackendList({ name: "Attachments", model: "ir.attachment" });
            }

            if (action === "refresh-dashboard-overview") {
                ev.preventDefault();
                closeSubmenuPopover();
                refreshDashboardOverview(true).catch((error) =>
                    logThemeError("manual dashboard overview refresh failed", error)
                );
            }

            if (action === "open-customers") {
                ev.preventDefault();
                closeSubmenuPopover();
                openBackendList({
                    name: "Customers",
                    model: "res.partner",
                    domain: [["customer_rank", ">", 0]],
                });
            }

            if (action === "open-vendors") {
                ev.preventDefault();
                closeSubmenuPopover();
                openBackendList({
                    name: "Vendors",
                    model: "res.partner",
                    domain: [["supplier_rank", ">", 0]],
                });
            }

            if (action === "open-dashboard-activity-row") {
                ev.preventDefault();
                closeSubmenuPopover();
                const resId = Number.parseInt(button.dataset.krResId, 10);
                const activityId = Number.parseInt(button.dataset.krActivityId, 10);
                if (button.dataset.krModel && Number.isFinite(resId)) {
                    openBackendRecord({
                        name: button.textContent?.trim() || "Activity Record",
                        model: button.dataset.krModel,
                        resId,
                    });
                } else if (Number.isFinite(activityId)) {
                    openBackendRecord({
                        name: "Activity",
                        model: "mail.activity",
                        resId: activityId,
                    });
                }
            }

            if (action === "open-overdue-activities") {
                ev.preventDefault();
                closeSubmenuPopover();
                openBackendList({
                    name: "Overdue Activities",
                    model: "mail.activity",
                    domain: [["date_deadline", "<", getLocalDateString()]],
                });
            }

            if (action === "open-today-activities") {
                ev.preventDefault();
                closeSubmenuPopover();
                openBackendList({
                    name: "Activities Due Today",
                    model: "mail.activity",
                    domain: [["date_deadline", "=", getLocalDateString()]],
                });
            }

            if (action === "open-sales-orders") {
                ev.preventDefault();
                closeSubmenuPopover();
                openBackendList({
                    name: "Sales Orders",
                    model: "sale.order",
                    domain: [["state", "in", ["sale", "done"]]],
                });
            }

            if (action === "open-invoices") {
                ev.preventDefault();
                closeSubmenuPopover();
                openBackendList({
                    name: "Customer Invoices",
                    model: "account.move",
                    domain: [["move_type", "in", ["out_invoice", "out_refund"]]],
                });
            }

            if (action === "open-crm-leads") {
                ev.preventDefault();
                closeSubmenuPopover();
                openBackendList({
                    name: "CRM Leads",
                    model: "crm.lead",
                    domain: [["type", "=", "lead"], ["active", "=", true]],
                });
            }

            if (action === "open-quotations") {
                ev.preventDefault();
                closeSubmenuPopover();
                openBackendList({
                    name: "Quotations",
                    model: "sale.order",
                    domain: [["state", "in", ["draft", "sent"]]],
                });
            }

            if (action === "open-unpaid-invoices") {
                ev.preventDefault();
                closeSubmenuPopover();
                openBackendList({
                    name: "Unpaid Invoices",
                    model: "account.move",
                    domain: [
                        ["move_type", "=", "out_invoice"],
                        ["state", "=", "posted"],
                        ["payment_state", "in", ["not_paid", "partial"]],
                    ],
                });
            }

            if (action === "open-helpdesk-tickets") {
                ev.preventDefault();
                closeSubmenuPopover();
                openBackendList({
                    name: "Open Tickets",
                    model: "helpdesk.ticket",
                    domain: [["stage_id.fold", "=", false]],
                });
            }

            if (action === "open-scheduled-actions") {
                ev.preventDefault();
                closeSubmenuPopover();
                openBackendList({ name: "Scheduled Actions", model: "ir.cron" });
            }

            if (action === "toggle-debug") {
                ev.preventDefault();
                closeSubmenuPopover();
                toggleDeveloperMode();
            }

            if (action === "open-search") {
                ev.preventDefault();
                closeSubmenuPopover();
                openSearchPalette();
            }
        } catch (error) {
            logThemeError("control button handler failed", error);
        }
    });

    root.addEventListener("click", (ev) => {
        if (ev.target.closest(".kr_sp_workspace_backdrop")) {
            closeWorkspaceModal();
        }
    });

    root.addEventListener("keydown", (ev) => {
        const keyboardControl = ev.target.closest?.("[data-kr-action][role='button'], [data-kr-scroll][role='button']");
        if (keyboardControl && (ev.key === "Enter" || ev.key === " ")) {
            ev.preventDefault();
            keyboardControl.click();
            return;
        }

        if (ev.key === "Escape") {
            closeWorkspaceModal();
            closeSubmenuPopover();
        }
    });

    const companyBus = userBus;
    companyBus.addEventListener("ACTIVE_COMPANIES_CHANGED", () => {
        window.setTimeout(() => {
            syncCompanyBrandName();
            syncCompanyBrandLogo();
            syncDashboardFooterContext();
            refreshDashboardFooterData(true);
            mountSystemTray();
        }, 0);
    });
}

function setupTabsScroller(cluster) {
    if (!cluster || cluster.dataset.krScrollerReady) {
        return;
    }

    const section = cluster.querySelector(".kr_sp_tabs_section");
    if (!section) {
        return;
    }
    const viewport = section.querySelector(".kr_sp_tabs_viewport");
    const tabs = section.querySelector(".kr_sp_tabs");
    const leftButton = cluster.querySelector(".kr_sp_tabs_scroll.is-left");
    const rightButton = cluster.querySelector(".kr_sp_tabs_scroll.is-right");
    if (!viewport || !tabs || !leftButton || !rightButton) {
        return;
    }

    cluster.dataset.krScrollerReady = "1";

    const getIsMaxed = () => {
        const maxWidth = Number.parseFloat(getComputedStyle(section).maxWidth);
        if (!Number.isFinite(maxWidth) || maxWidth <= 0) {
            return false;
        }
        const currentWidth = Math.max(section.clientWidth, section.offsetWidth);
        return currentWidth >= maxWidth - 2;
    };

    const updateState = () => {
        const maxOffset = Math.max(0, tabs.scrollWidth - viewport.clientWidth);
        const isOverflowing = maxOffset > 2;
        const isMaxed = getIsMaxed();
        const showButtons = isOverflowing && isMaxed;
        cluster.classList.toggle("is-overflowing", isOverflowing);
        cluster.classList.toggle("is-maxed", isMaxed);

        if (!showButtons) {
            tabs.scrollLeft = 0;
        }

        leftButton.disabled = !showButtons || tabs.scrollLeft <= 1;
        rightButton.disabled = !showButtons || tabs.scrollLeft >= maxOffset - 1;
    };

    const scrollTabs = (direction) => {
        const step = Math.max(80, Math.round(viewport.clientWidth * 0.65));
        tabs.scrollBy({
            left: direction * step,
            behavior: "smooth",
        });
    };

    leftButton.addEventListener("click", () => scrollTabs(-1));
    rightButton.addEventListener("click", () => scrollTabs(1));
    tabs.addEventListener("scroll", updateState, { passive: true });

    const resizeObserver = new ResizeObserver(updateState);
    resizeObserver.observe(viewport);
    resizeObserver.observe(tabs);

    const mutationObserver = new MutationObserver(updateState);
    mutationObserver.observe(tabs, { childList: true, subtree: true, attributes: true });

    updateState();
}

function mountScrollers() {
    document.querySelectorAll(".kr_sp_tabs_cluster").forEach(setupTabsScroller);
}

function bindNavigationRefresh(scheduleRunFeatures) {
    if (!boundRouteEvents) {
        routerBus.addEventListener("ROUTE_CHANGE", () => {
            closeSubmenuPopover();
            scheduleRunFeatures();
        });
        boundRouteEvents = true;
    }

    const envBus = getWebclientBus();
    if (envBus && envBus !== boundEnvBus) {
        if (boundEnvBus) {
            boundEnvBus.removeEventListener("MENUS:APP-CHANGED", scheduleRunFeatures);
            boundEnvBus.removeEventListener("ACTION_MANAGER:UI-UPDATED", scheduleRunFeatures);
        }
        boundEnvBus = envBus;
        boundEnvBus.addEventListener("MENUS:APP-CHANGED", scheduleRunFeatures);
        boundEnvBus.addEventListener("ACTION_MANAGER:UI-UPDATED", scheduleRunFeatures);
    }
}

function start() {
    if (!document.body) {
        return;
    }
    const runFeatures = () => {
        renderScheduled = false;
        runSafely("bind navigation refresh", () => bindNavigationRefresh(scheduleRunFeatures));
        runSafely("render global shell", renderGlobalShell);
        runSafely("setup modal viewport guard", setupModalViewportGuard);
        runSafely("normalize modal viewport state", normalizeModalViewportState);
        runSafely("render shared topbars", renderAllTopbars);
        runSafely("sync pending action skeleton", syncPendingActionSkeleton);
        runSafely("render tabs", renderAllTabs);
        runSafely("sync company brand name", syncCompanyBrandName);
        runSafely("sync company brand logo", syncCompanyBrandLogo);
        runSafely("sync profile details", syncProfileDetails);
        runSafely("refresh dashboard overview", refreshDashboardOverview);
        runSafely("sync dashboard footer context", syncDashboardFooterContext);
        runSafely("mount system tray", mountSystemTray);
        runSafely("mount user menu", mountUserMenu);
        runSafely("mount scrollers", mountScrollers);
        runSafely("setup control buttons", setupControlButtons);
        runSafely("refresh theme scope", refreshThemeScope);
        runSafely("apply color theme", () => applyColorTheme(getColorTheme()));
        runSafely("mark dashboard ready", () => markDashboardReady(".kr_sp_pending_shell"));
        runSafely("refresh dashboard footer data", refreshDashboardFooterData);
        runSafely("build sidebar apps", buildSidebarApps);
    };

    const scheduleRunFeatures = () => {
        if (renderScheduled) {
            return;
        }
        renderScheduled = true;
        window.requestAnimationFrame(runFeatures);
    };

    const actionManager = document.querySelector(".o_web_client > .o_action_manager") || document.body;
    const rootObserver = new MutationObserver(scheduleRunFeatures);
    try {
        rootObserver.observe(actionManager, { childList: true, subtree: false });
    } catch (error) {
        logThemeError("failed to observe action manager", error);
    }
    runSafely("initial scrollers mount", mountScrollers);
    runSafely("initial feature run", runFeatures);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
} else {
    start();
}
