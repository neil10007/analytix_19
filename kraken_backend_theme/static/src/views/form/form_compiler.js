/** @odoo-module **/

import { session } from "@web/session";
import { patch } from "@web/core/utils/patch";
import { append, createElement, setAttributes } from "@web/core/utils/xml";
import { FormCompiler } from "@web/views/form/form_compiler";

patch(FormCompiler.prototype, {
    compileHeader(node, params) {
        const res = super.compileHeader(node, params);
        const statusBarButtons = res.querySelector("StatusBarButtons");
        if (statusBarButtons) {
            statusBarButtons.setAttribute("t-if", "true");
        }
        return res;
    },

    compile(node, params) {
        const res = super.compile(node, params);

        const chatterContainerHookXml = res.querySelector(
            ".o_form_renderer > .o-mail-Form-chatter"
        );
        if (!chatterContainerHookXml) {
            return res;
        }

        setAttributes(chatterContainerHookXml, {
            "t-ref": "chatterContainer",
        });

        if (session.chatter_position === "bottom") {
            const formSheetBgXml = res.querySelector(".o_form_sheet_bg");
            if (!chatterContainerHookXml || !formSheetBgXml?.parentNode) {
                return res;
            }
            const webClientViewAttachmentViewHookXml = res.querySelector(
                ".o_attachment_preview"
            );
            const chatterContainerXml = chatterContainerHookXml.querySelector(
                "t[t-component='__comp__.mailComponents.Chatter']"
            );

            const sheetBgChatterContainerHookXml = chatterContainerHookXml.cloneNode(true);
            const sheetBgChatterContainerXml = sheetBgChatterContainerHookXml.querySelector(
                "t[t-component='__comp__.mailComponents.Chatter']"
            );

            sheetBgChatterContainerHookXml.classList.add("o-isInFormSheetBg", "w-auto");
            append(formSheetBgXml, sheetBgChatterContainerHookXml);

            setAttributes(sheetBgChatterContainerXml, {
                isInFormSheetBg: "true",
                isChatterAside: "false",
            });
            setAttributes(chatterContainerXml, {
                isInFormSheetBg: "true",
                isChatterAside: "false",
            });

            setAttributes(chatterContainerHookXml, {
                "t-if": "false",
            });

            if (webClientViewAttachmentViewHookXml) {
                setAttributes(webClientViewAttachmentViewHookXml, {
                    "t-if": "false",
                });
            }
        } else {
            setAttributes(chatterContainerHookXml, {
                "t-att-style": "__comp__.getChatterContainerStyle()",
                "t-att-class": "{ 'tt_chatter_collapsed': __comp__.chatterState.collapsed }",
            });

            const chatterContainerResizeHookXml = createElement("span");
            chatterContainerResizeHookXml.classList.add("tt_chatter_resize");
            setAttributes(chatterContainerResizeHookXml, {
                "t-on-mousedown.stop.prevent": "__comp__.onStartChatterResize.bind(__comp__)",
                "t-on-dblclick.stop.prevent": "__comp__.onDoubleClickChatterResize.bind(__comp__)",
            });

            append(chatterContainerHookXml, chatterContainerResizeHookXml);

            const chatterContainerCollapseButtonXml = createElement("button");
            chatterContainerCollapseButtonXml.classList.add("tt_chatter_collapse");
            setAttributes(chatterContainerCollapseButtonXml, {
                type: "button",
                "t-on-click.stop.prevent": "__comp__.toggleChatterCollapse.bind(__comp__)",
                "t-att-class": "{ 'is-collapsed': __comp__.chatterState.collapsed }",
                "t-att-aria-label": "__comp__.chatterState.collapsed ? 'Expand chatter' : 'Collapse chatter'",
                "t-att-title": "__comp__.chatterState.collapsed ? 'Expand chatter' : 'Collapse chatter'",
            });

            const chatterContainerCollapseIconXml = createElement("span");
            chatterContainerCollapseIconXml.classList.add("tt_chatter_collapse_icon");
            append(chatterContainerCollapseButtonXml, chatterContainerCollapseIconXml);
            append(chatterContainerHookXml, chatterContainerCollapseButtonXml);
        }
        return res;
    },
});