/** @odoo-module **/

import { ButtonBox } from "@web/views/form/button_box/button_box";
import { patch } from "@web/core/utils/patch";
import { onWillRender } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

patch(ButtonBox.prototype, {
    setup() {
        super.setup();
        const ui = useService("ui");

        onWillRender(() => {
            const MAX_VISIBLE_BUTTONS_BY_SIZE = [2, 2, 3, 7, 4, 5, 8];
            const maxVisibleButtons = MAX_VISIBLE_BUTTONS_BY_SIZE[ui.size] ?? 8;

            const allVisibleButtons = Object.entries(this.props.slots)
                .filter(([_, slot]) => this.isSlotVisible(slot))
                .map(([slotName]) => slotName);

            if (allVisibleButtons.length <= maxVisibleButtons) {
                this.visibleButtons = allVisibleButtons;
                this.additionalButtons = [];
                this.isFull = allVisibleButtons.length === maxVisibleButtons;
            } else {
                const splitIndex = Math.max(maxVisibleButtons - 1, 0);
                this.visibleButtons = allVisibleButtons.slice(0, splitIndex);
                this.additionalButtons = allVisibleButtons.slice(splitIndex);
                this.isFull = true;
            }
        });
    }
});