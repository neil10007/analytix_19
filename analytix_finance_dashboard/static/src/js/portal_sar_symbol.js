/** @odoo-module **/

(function () {
    // Inject font-face dynamically into head to ensure relative URL resolution
    if (!document.getElementById("sr_symbol_font_face_style")) {
        const styleNode = document.createElement("style");
        styleNode.id = "sr_symbol_font_face_style";
        styleNode.textContent = `
            @font-face {
                font-family: 'sr_symbol';
                src: url('/iwesabe_sar_currency_symbol/static/src/fonts/sr.eot');
                src: url('/iwesabe_sar_currency_symbol/static/src/fonts/sr.eot?#iefix') format('embedded-opentype'),
                     url('/iwesabe_sar_currency_symbol/static/src/fonts/sr.woff') format('woff'),
                     url('/iwesabe_sar_currency_symbol/static/src/fonts/sr.ttf') format('truetype'),
                     url('/iwesabe_sar_currency_symbol/static/src/fonts/sr.svg#sr_symbol') format('svg');
                font-weight: normal;
                font-style: normal;
                font-display: block;
            }
            .anx-sar-icon {
                font-family: 'sr_symbol' !important;
                display: inline-block;
                font-style: normal;
                font-weight: normal;
                line-height: 1;
                -webkit-font-smoothing: antialiased;
                -moz-osx-font-smoothing: grayscale;
            }
        `;
        (document.head || document.documentElement).appendChild(styleNode);
    }

    function processTextNode(textNode) {
        if (!textNode || !textNode.nodeValue) return;
        const val = textNode.nodeValue;
        if (!val.includes("\uE900") && !val.includes("")) return;

        const parent = textNode.parentNode;
        if (!parent || parent.nodeType !== Node.ELEMENT_NODE) return;
        if (parent.classList && parent.classList.contains("anx-sar-icon")) return;

        const tag = parent.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || tag === 'OPTION' || tag === 'SCRIPT' || tag === 'STYLE') return;

        // Wrap the currency symbol character in a dedicated span to isolate font-family from the numbers
        const wrapper = document.createElement("span");
        wrapper.className = "anx-sar-icon";
        wrapper.textContent = "\uE900";

        // Replace character in text node
        const parts = val.split(/[\uE900\uE900]/);
        if (parts.length > 1) {
            const fragment = document.createDocumentFragment();
            for (let i = 0; i < parts.length; i++) {
                if (parts[i]) {
                    fragment.appendChild(document.createTextNode(parts[i]));
                }
                if (i < parts.length - 1) {
                    fragment.appendChild(wrapper.cloneNode(true));
                }
            }
            parent.replaceChild(fragment, textNode);
        } else {
            // Fallback font assignment if split didn't catch literal character
            parent.style.fontFamily = "'sr_symbol', Inter, sans-serif";
        }
    }

    function scanElement(element) {
        if (!element) return;
        if (element.nodeType === Node.TEXT_NODE) {
            processTextNode(element);
            return;
        }
        if (element.nodeType !== Node.ELEMENT_NODE) return;

        const tag = element.tagName;
        if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'HEAD' || tag === 'LINK') return;

        const children = Array.from(element.childNodes);
        for (const child of children) {
            scanElement(child);
        }
    }

    function initScanner() {
        scanElement(document.body);

        const observer = new MutationObserver((mutations) => {
            observer.disconnect();
            try {
                for (const mutation of mutations) {
                    if (mutation.type === "childList") {
                        mutation.addedNodes.forEach((node) => scanElement(node));
                    } else if (mutation.type === "characterData") {
                        processTextNode(mutation.target);
                    }
                }
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
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initScanner);
    } else {
        initScanner();
    }
    setTimeout(initScanner, 500);
    setTimeout(initScanner, 1500);
})();
