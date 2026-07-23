/** @odoo-module **/

import { components } from "@odoo/o-spreadsheet";
import { cookie } from "@web/core/browser/cookie";
import { patch } from "@web/core/utils/patch";
import { DashboardLoader } from "@spreadsheet_dashboard/bundle/dashboard_action/dashboard_loader_service";

const DARK_BG = "#0b0f16";
const DARK_PANEL = "#111827";
const DARK_BORDER = "rgba(71, 85, 105, 0.34)";
const DARK_GRID = "rgba(51, 65, 85, 0.24)";
const DARK_TEXT = "#d1d5db";
const DARK_MUTED = "#9ca3af";
const DARK_TEAL = "#48c7ce";
const DARK_CARD = "#111827";
const DARK_CARD_BORDER = "#243244";
const DARK_DATA_BAR_COLOR = 0x2b6f9f;
const DARK_TABLE_STYLE_ID = "krakenDarkDashboard";
const DARK_TABLE_STYLE = {
    category: "dark",
    templateName: "dark",
    displayName: "Kraken Dark Dashboard",
    primaryColor: DARK_TEAL,
    wholeTable: {
        style: { fillColor: DARK_BG, textColor: DARK_TEXT },
        border: {
            top: { color: DARK_CARD_BORDER, style: "thin" },
            bottom: { color: DARK_CARD_BORDER, style: "thin" },
            horizontal: { color: DARK_CARD_BORDER, style: "thin" },
            vertical: { color: DARK_CARD_BORDER, style: "thin" },
        },
    },
    headerRow: {
        style: { fillColor: DARK_CARD, textColor: DARK_TEXT, bold: true },
        border: { bottom: { color: DARK_CARD_BORDER, style: "thin" } },
    },
    firstRowStripe: { style: { fillColor: "#0f172a", textColor: DARK_TEXT } },
    secondRowStripe: { style: { fillColor: DARK_BG, textColor: DARK_TEXT } },
};

function isDarkMode() {
    return (
        cookie.get("color_scheme") === "dark" ||
        document.body?.classList.contains("kr_sp_theme_dark") ||
        document.querySelector(".o_web_client")?.classList.contains("kr_sp_theme_dark")
    );
}

function forcePlainChartTextColor(value, depth = 0) {
    if (!value || typeof value !== "object") {
        return;
    }
    if (depth > 8 || Object.isFrozen(value) || !Object.isExtensible(value)) {
        return;
    }
    if ("color" in value && typeof value.color === "string") {
        value.color = DARK_TEXT;
    }
    if ("fontColor" in value && typeof value.fontColor === "string") {
        value.fontColor = DARK_TEXT;
    }
    for (const child of Object.values(value)) {
        if (child && typeof child === "object" && child.constructor === Object) {
            forcePlainChartTextColor(child, depth + 1);
        }
    }
}

function darkenScale(scale) {
    if (!scale) {
        return;
    }
    scale.border = { ...(scale.border || {}), color: DARK_BORDER };
    scale.grid = { ...(scale.grid || {}), color: DARK_GRID, tickColor: DARK_GRID };
    scale.ticks = { ...(scale.ticks || {}), color: DARK_TEXT };
    scale.title = { ...(scale.title || {}), color: DARK_MUTED };
    scale.pointLabels = { ...(scale.pointLabels || {}), color: DARK_TEXT };
    scale.angleLines = { ...(scale.angleLines || {}), color: DARK_GRID };
}

function applyDarkChartRuntime(chartRuntime) {
    if (!isDarkMode() || !chartRuntime?.chartJsConfig) {
        return chartRuntime;
    }

    const config = chartRuntime.chartJsConfig;
    if (config.type === "choropleth") {
        chartRuntime.background = DARK_BG;
        config.options = {
            ...(config.options || {}),
            backgroundColor: DARK_BG,
            animation: false,
            animations: false,
            transitions: {
                active: { animation: false },
                resize: { animation: false },
                show: { animations: false },
                hide: { animations: false },
            },
        };
        return chartRuntime;
    }

    chartRuntime.background = DARK_BG;

    const options = (config.options ||= {});
    const plugins = (options.plugins ||= {});

    options.color = DARK_TEXT;
    options.backgroundColor = DARK_BG;
    options.borderColor = DARK_BORDER;

    plugins.title = { ...(plugins.title || {}), color: DARK_TEXT };
    plugins.subtitle = { ...(plugins.subtitle || {}), color: DARK_MUTED };
    plugins.legend = {
        ...(plugins.legend || {}),
        labels: { ...(plugins.legend?.labels || {}), color: DARK_TEXT },
        title: { ...(plugins.legend?.title || {}), color: DARK_TEXT },
    };
    plugins.tooltip = {
        ...(plugins.tooltip || {}),
        backgroundColor: DARK_PANEL,
        borderColor: DARK_BORDER,
        borderWidth: 1,
        bodyColor: DARK_TEXT,
        titleColor: "#f8fafc",
        footerColor: DARK_MUTED,
    };

    for (const scale of Object.values(options.scales || {})) {
        darkenScale(scale);
    }

    forcePlainChartTextColor({
        title: plugins.title,
        subtitle: plugins.subtitle,
        legend: plugins.legend,
        tooltip: plugins.tooltip,
    });

    return chartRuntime;
}

function getColumnName(index) {
    let name = "";
    let value = index + 1;
    while (value > 0) {
        const remainder = (value - 1) % 26;
        name = String.fromCharCode(65 + remainder) + name;
        value = Math.floor((value - remainder) / 26);
    }
    return name;
}

function parseRange(range) {
    const match = /^([A-Z]+)(\d+):([A-Z]+)(\d+)$/.exec(range || "");
    if (!match) {
        return null;
    }
    return {
        startCol: match[1],
        startRow: Number(match[2]),
        endCol: match[3],
        endRow: Number(match[4]),
    };
}

function isLightColor(color) {
    if (!color || typeof color !== "string" || !color.startsWith("#")) {
        return false;
    }
    const hex = color.slice(1);
    if (![3, 6].includes(hex.length)) {
        return false;
    }
    const fullHex =
        hex.length === 3
            ? hex
                  .split("")
                  .map((part) => part + part)
                  .join("")
            : hex;
    const r = parseInt(fullHex.slice(0, 2), 16);
    const g = parseInt(fullHex.slice(2, 4), 16);
    const b = parseInt(fullHex.slice(4, 6), 16);
    return (r * 299 + g * 587 + b * 114) / 1000 > 170;
}

function isDarkTextColor(color) {
    if (!color || typeof color !== "string" || !color.startsWith("#")) {
        return false;
    }
    const hex = color.slice(1);
    if (![3, 6].includes(hex.length)) {
        return false;
    }
    const fullHex =
        hex.length === 3
            ? hex
                  .split("")
                  .map((part) => part + part)
                  .join("")
            : hex;
    const r = parseInt(fullHex.slice(0, 2), 16);
    const g = parseInt(fullHex.slice(2, 4), 16);
    const b = parseInt(fullHex.slice(4, 6), 16);
    return (r * 299 + g * 587 + b * 114) / 1000 < 115;
}

function nextStyleId(styles) {
    const numericIds = Object.keys(styles)
        .map((id) => Number(id))
        .filter((id) => Number.isFinite(id));
    return String(Math.max(0, ...numericIds) + 1);
}

function darkenStyle(style) {
    if (!style || typeof style !== "object") {
        return;
    }
    if (isDarkTextColor(style.textColor)) {
        style.textColor = DARK_TEXT;
    }
    if (style.textColor && style.textColor.toLowerCase() === "#01666b") {
        style.textColor = DARK_TEAL;
    }
    if (isLightColor(style.fillColor)) {
        style.fillColor = DARK_CARD;
    }
    if (!style.fillColor) {
        style.fillColor = DARK_BG;
    }
}

function darkenFigureData(data) {
    if (!data || typeof data !== "object") {
        return;
    }
    if (!data.background || isLightColor(data.background)) {
        data.background = DARK_BG;
    }
    if (!data.backgroundColor || isLightColor(data.backgroundColor)) {
        data.backgroundColor = DARK_BG;
    }
    if (data.title?.color && isDarkTextColor(data.title.color)) {
        data.title.color = DARK_TEXT;
    }
    if (data.baselineDescr?.color && isDarkTextColor(data.baselineDescr.color)) {
        data.baselineDescr.color = DARK_MUTED;
    }
    if (data.type === "scorecard") {
        data.background = DARK_CARD;
        data.borderColor = DARK_CARD_BORDER;
        data.fontColor = DARK_TEXT;
    }
    if (data.headerDesign) {
        data.headerDesign = {
            ...data.headerDesign,
            fillColor: DARK_CARD,
            color: DARK_TEXT,
            textColor: DARK_TEXT,
        };
    }
    if (data.valuesDesign) {
        data.valuesDesign = {
            ...data.valuesDesign,
            color: DARK_TEXT,
            textColor: DARK_TEXT,
        };
    }
    for (const chartDefinition of Object.values(data.chartDefinitions || {})) {
        darkenFigureData(chartDefinition);
    }
    forcePlainChartTextColor({
        title: data.title,
        baselineDescr: data.baselineDescr,
        headerDesign: data.headerDesign,
        valuesDesign: data.valuesDesign,
        legendPosition: data.legendPosition,
    });
}

function darkenConditionalFormats(conditionalFormats = []) {
    for (const conditionalFormat of conditionalFormats) {
        const rule = conditionalFormat?.rule;
        if (rule?.type === "DataBarRule") {
            rule.color = DARK_DATA_BAR_COLOR;
        }
    }
}

function applyDarkDashboardSnapshot(snapshot) {
    if (!isDarkMode() || !snapshot?.sheets || !snapshot?.styles) {
        return snapshot;
    }

    for (const style of Object.values(snapshot.styles)) {
        darkenStyle(style);
    }

    const baseStyleId = nextStyleId(snapshot.styles);
    snapshot.styles[baseStyleId] = {
        fillColor: DARK_BG,
        textColor: DARK_TEXT,
        verticalAlign: "middle",
    };
    const headerStyleId = nextStyleId(snapshot.styles);
    snapshot.styles[headerStyleId] = {
        fillColor: DARK_CARD,
        textColor: DARK_TEXT,
        bold: true,
        verticalAlign: "middle",
    };
    const tableBodyStyleId = nextStyleId(snapshot.styles);
    snapshot.styles[tableBodyStyleId] = {
        fillColor: DARK_BG,
        textColor: DARK_TEXT,
        verticalAlign: "middle",
    };

    snapshot.customTableStyles = {
        ...(snapshot.customTableStyles || {}),
        [DARK_TABLE_STYLE_ID]: DARK_TABLE_STYLE,
    };

    for (const border of Object.values(snapshot.borders || {})) {
        for (const side of Object.values(border || {})) {
            if (side && typeof side === "object" && (side.style || side.color)) {
                side.color = DARK_CARD_BORDER;
            }
        }
    }

    for (const sheet of snapshot.sheets) {
        const colCount = Math.max(sheet.colNumber || 26, 26);
        const rowCount = Math.max(sheet.rowNumber || 100, 120);
        const fullRange = `A1:${getColumnName(colCount - 1)}${rowCount}`;
        sheet.styles = { [fullRange]: baseStyleId, ...(sheet.styles || {}) };
        sheet.areGridLinesVisible = false;
        darkenConditionalFormats(sheet.conditionalFormats);

        for (const table of sheet.tables || []) {
            table.config = {
                ...(table.config || {}),
                styleId: DARK_TABLE_STYLE_ID,
            };
            const parsedRange = parseRange(table.range);
            if (parsedRange) {
                const { startCol, startRow, endCol, endRow } = parsedRange;
                const headerRows = Math.max(table.config.numberOfHeaders || 1, 1);
                const headerEndRow = Math.min(startRow + headerRows - 1, endRow);
                sheet.styles[`${startCol}${startRow}:${endCol}${headerEndRow}`] = headerStyleId;
                if (headerEndRow < endRow) {
                    sheet.styles[`${startCol}${headerEndRow + 1}:${endCol}${endRow}`] =
                        tableBodyStyleId;
                }
            }
        }

        for (const figure of sheet.figures || []) {
            darkenFigureData(figure.data);
        }
    }

    return snapshot;
}

patch(components.ChartJsComponent.prototype, {
    createChart(chartRuntime) {
        super.createChart(applyDarkChartRuntime(chartRuntime));
    },

    updateChartJs(chartRuntime) {
        super.updateChartJs(applyDarkChartRuntime(chartRuntime));
    },
});

patch(components.ChartDashboardMenu.prototype, {
    get backgroundColor() {
        if (isDarkMode()) {
            return `background-color: ${DARK_BG}`;
        }
        return super.backgroundColor;
    },
});

patch(DashboardLoader.prototype, {
    _createSpreadsheetModel(snapshot, revisions = [], currency, translationNamespace) {
        return super._createSpreadsheetModel(
            applyDarkDashboardSnapshot(snapshot),
            revisions,
            currency,
            translationNamespace
        );
    },
});
