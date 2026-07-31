import { useSubEnv } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

patch(FormController.prototype, {
    setup() {
        super.setup();
        // Re-inject footer into arch
        if (this.footerArchInfo && !this.env.inDialog) {
            const footer = this.footerArchInfo.xmlDoc;

            // Add spacing class to footer buttons
            footer.querySelectorAll("button").forEach((btn) => {
                const cls = btn.getAttribute("class") || "";
                if (!cls.includes("me-")) {
                    btn.setAttribute("class", `${cls} me-2`.trim());
                }
            });

            this.archInfo.xmlDoc.append(footer);
            this.archInfo.arch = this.archInfo.xmlDoc.outerHTML;
        }
    },
});
