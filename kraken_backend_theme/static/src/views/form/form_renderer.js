/** @odoo-module **/

import { useRef, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { patch } from "@web/core/utils/patch";
import { FormRenderer } from "@web/views/form/form_renderer";

const CHATTER_DEFAULT_WIDTH = 420;
const CHATTER_COLLAPSED_WIDTH = 0;
const CHATTER_WIDTH_STORAGE_KEY = "kraken_backend_theme_chatter.width";
const CHATTER_COLLAPSED_STORAGE_KEY = "kraken_backend_theme_chatter.collapsed";

patch(FormRenderer.prototype, {
    setup() {
        super.setup();
        let storedWidth = CHATTER_DEFAULT_WIDTH;
        try {
            const parsedWidth = parseInt(browser.localStorage.getItem(CHATTER_WIDTH_STORAGE_KEY), 10);
            if (Number.isFinite(parsedWidth) && parsedWidth > 0) {
                storedWidth = parsedWidth;
            }
        } catch {
            storedWidth = CHATTER_DEFAULT_WIDTH;
        }

        let storedCollapsed = false;
        try {
            storedCollapsed = browser.localStorage.getItem(CHATTER_COLLAPSED_STORAGE_KEY) === "1";
        } catch {
            storedCollapsed = false;
        }

        this.chatterState = useState({
            width: storedWidth,
            collapsed: storedCollapsed,
        });
        this.chatterContainer = useRef("chatterContainer");
    },

    getChatterContainerStyle() {
        const width = this.chatterState.collapsed
            ? CHATTER_COLLAPSED_WIDTH
            : this.chatterState.width || CHATTER_DEFAULT_WIDTH;
        return `width: ${width}px;`;
    },

    toggleChatterCollapse() {
        this.chatterState.collapsed = !this.chatterState.collapsed;
        try {
            browser.localStorage.setItem(
                CHATTER_COLLAPSED_STORAGE_KEY,
                this.chatterState.collapsed ? "1" : "0"
            );
        } catch {
            // ignore storage errors
        }
    },

    onStartChatterResize(ev) {
        if (ev.button !== 0 || this.chatterState.collapsed) {
            return;
        }
        const initialX = ev.pageX;
        const chatterElement = this.chatterContainer.el;
        const initialWidth = chatterElement.offsetWidth;
        const resizeStoppingEvents = ["keydown", "mousedown", "mouseup"];

        const resizePanel = (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            const newWidth = Math.min(
                Math.max(320, initialWidth - (ev.pageX - initialX)),
                Math.max(chatterElement.parentElement.offsetWidth - 300, 320)
            );
            try {
                browser.localStorage.setItem(CHATTER_WIDTH_STORAGE_KEY, newWidth);
            } catch {
                // ignore storage errors
            }
            this.chatterState.width = newWidth;
        };

        const stopResize = (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            if (ev.type === "mousedown" && ev.button === 0) {
                return;
            }
            document.removeEventListener("mousemove", resizePanel, true);
            resizeStoppingEvents.forEach((stoppingEvent) => {
                document.removeEventListener(stoppingEvent, stopResize, true);
            });
            document.activeElement.blur();
        };

        document.addEventListener("mousemove", resizePanel, true);
        resizeStoppingEvents.forEach((stoppingEvent) => {
            document.addEventListener(stoppingEvent, stopResize, true);
        });
    },

    onDoubleClickChatterResize() {
        try {
            browser.localStorage.setItem(CHATTER_WIDTH_STORAGE_KEY, CHATTER_DEFAULT_WIDTH);
        } catch {
            // ignore storage errors
        }
        this.chatterState.width = CHATTER_DEFAULT_WIDTH;
    },
});