/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";

function processTextNode(textNode) {
    const val = textNode.nodeValue;
    if (!val || (!val.includes("\uE900") && !val.includes(""))) {
        return;
    }

    const parent = textNode.parentNode;
    if (!parent || parent.nodeType !== Node.ELEMENT_NODE) {
        return;
    }

    // Safely apply the font-family directly to the parent node.
    // This entirely avoids altering the DOM tree structure (like inserting <span>),
    // which prevents conflicts with Odoo's OWL Virtual DOM reconciliation in wizards and draft views.
    if (parent.style.fontFamily !== "'sr_symbol'") {
        parent.style.setProperty("font-family", "'sr_symbol'", "important");
    }
}

function processNode(node) {
    if (!node) return;
    
    if (node.nodeType === Node.TEXT_NODE) {
        processTextNode(node);
    } else if (node.nodeType === Node.ELEMENT_NODE) {
        const tagName = node.tagName;

        // Skip non-visual and metadata tags entirely
        if (tagName === 'SCRIPT' || tagName === 'STYLE' || tagName === 'HEAD' || tagName === 'LINK' || tagName === 'META') {
            return;
        }

        // Apply font-family styling if matching target classes
        if (
            node.classList.contains("o_sar_symbol") ||
            node.classList.contains("anx-currency-sym") ||
            node.classList.contains("icon-sr") ||
            (node.className && typeof node.className === "string" && node.className.includes("sr_symbol"))
        ) {
            if (node.style.fontFamily !== "'sr_symbol'") {
                node.style.setProperty("font-family", "'sr_symbol'", "important");
            }
        }

        // Recursively process child nodes
        const children = Array.from(node.childNodes);
        for (const child of children) {
            processNode(child);
        }
    }
}

patch(WebClient.prototype, {
    setup() {
        super.setup();

        // Run initial scan once DOM is ready or after brief delay
        setTimeout(() => {
            processNode(document.body);
        }, 300);

        const observer = new MutationObserver((mutations) => {
            // Disconnect to avoid loops when we modify inline styles
            observer.disconnect();
            try {
                for (const mutation of mutations) {
                    if (mutation.type === "childList") {
                        mutation.addedNodes.forEach((node) => {
                            processNode(node);
                        });
                    } else if (mutation.type === "characterData") {
                        processTextNode(mutation.target);
                    }
                }
            } catch (err) {
                console.error("Error in SAR symbol process:", err);
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




