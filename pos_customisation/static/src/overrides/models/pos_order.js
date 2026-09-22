import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    generateQrcode() {
        if (this.config?.hide_receipt_header_qr || this.config_id?.hide_receipt_header_qr) {
            return false;
        }
        return super.generateQrcode(...arguments);
    },
});
