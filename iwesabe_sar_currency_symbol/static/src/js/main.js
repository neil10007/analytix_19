/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";

function ensureSarFontOnTextNode(textNode) {
    if (!textNode || !textNode.nodeValue) return;
    const val = textNode.nodeValue;
    if (!val.includes("\uE900") && !val.includes("")) {
        return;
    }

    const parent = textNode.parentNode;
    if (!parent || parent.nodeType !== Node.ELEMENT_NODE) return;

    // Ensure 'sr_symbol' font family is included at the front of the stack
    const currentFont = parent.style ? parent.style.fontFamily : "";
    if (!currentFont || !currentFont.includes("sr_symbol")) {
        const newFont = currentFont ? `'sr_symbol', ${currentFont}` : `'sr_symbol', Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
        parent.style.setProperty("font-family", newFont, "important");
    }
}

function processNode(node) {
    if (!node) return;
    
    if (node.nodeType === Node.TEXT_NODE) {
        ensureSarFontOnTextNode(node);
    } else if (node.nodeType === Node.ELEMENT_NODE) {
        const tagName = node.tagName;
        if (tagName === 'SCRIPT' || tagName === 'STYLE' || tagName === 'HEAD' || tagName === 'LINK' || tagName === 'META') {
            return;
        }

        if (node.childNodes && node.childNodes.length > 0) {
            for (let i = 0; i < node.childNodes.length; i++) {
                processNode(node.childNodes[i]);
            }
        }
    }
}

patch(WebClient.prototype, {
    setup() {
        super.setup();

        setTimeout(() => {
            processNode(document.body);
        }, 300);

        const observer = new MutationObserver((mutations) => {
            observer.disconnect();
            try {
                for (const mutation of mutations) {
                    if (mutation.type === "childList") {
                        mutation.addedNodes.forEach((node) => {
                            processNode(node);
                        });
                    } else if (mutation.type === "characterData") {
                        ensureSarFontOnTextNode(mutation.target);
                    }
                }
            } catch (err) {
                console.error("Error in SAR symbol observer:", err);
            } finally {
                observer.observe(document.body, {
                    childList: true,
                    subtree: true,
                    characterData: true,
                });
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true,
            characterData: true,
        });
    },
});
