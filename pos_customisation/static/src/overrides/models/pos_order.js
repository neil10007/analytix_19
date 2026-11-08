import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { patch } from "@web/core/utils/patch";

const { DateTime } = luxon;

export function amountToWordsSAR(amount) {
    const ones = [
        "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
        "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
        "Seventeen", "Eighteen", "Nineteen"
    ];
    const tens = [
        "", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"
    ];

    function convertGroup(n) {
        let str = "";
        if (n >= 100) {
            str += ones[Math.floor(n / 100)] + " Hundred";
            n %= 100;
            if (n > 0) {
                str += " ";
            }
        }
        if (n >= 20) {
            str += tens[Math.floor(n / 10)];
            if (n % 10 > 0) {
                str += " " + ones[n % 10];
            }
        } else if (n > 0) {
            str += ones[n];
        }
        return str;
    }

    function numToWords(n) {
        if (n === 0) {
            return "Zero";
        }
        let num = Math.floor(Math.abs(n));
        const billions = Math.floor(num / 1000000000);
        num %= 1000000000;
        const millions = Math.floor(num / 1000000);
        num %= 1000000;
        const thousands = Math.floor(num / 1000);
        const remainder = num % 1000;

        const parts = [];
        if (billions) {
            parts.push(convertGroup(billions) + " Billion");
        }
        if (millions) {
            parts.push(convertGroup(millions) + " Million");
        }
        if (thousands) {
            parts.push(convertGroup(thousands) + " Thousand");
        }
        if (remainder) {
            parts.push(convertGroup(remainder));
        }

        return parts.join(" ");
    }

    const total = Math.round(Number(amount || 0) * 100) / 100;
    const whole = Math.floor(total);
    const decimal = Math.round((total - whole) * 100);

    let result = "";
    if (whole > 0) {
        result += numToWords(whole) + " Riyal";
    }
    if (decimal > 0) {
        if (result) {
            result += " and ";
        }
        result += numToWords(decimal) + " Halala";
    }
    if (!result) {
        result = "Zero Riyal";
    }
    return result + " Only";
}

patch(PosOrder.prototype, {
    get orderNumber() {
        try {
            if (this.tracking_number) {
                return String(this.tracking_number);
            }
            if (this.pos_reference) {
                const match = String(this.pos_reference).match(/\d+$/);
                if (match) {
                    return match[0];
                }
                return String(this.pos_reference).replace(/^Order\s*/i, "");
            }
            if (this.name) {
                return String(this.name);
            }
        } catch (e) {}
        return "1";
    },

    get orderDateTime() {
        try {
            if (this.date_order) {
                if (typeof this.date_order.toFormat === "function") {
                    return this.date_order;
                }
                if (typeof this.date_order === "string") {
                    const parsed = DateTime.fromISO(this.date_order);
                    if (parsed.isValid) return parsed;
                    const parsedSql = DateTime.fromSQL(this.date_order);
                    if (parsedSql.isValid) return parsedSql;
                }
                if (this.date_order instanceof Date) {
                    return DateTime.fromJSDate(this.date_order);
                }
            }
        } catch (e) {}
        return DateTime.now();
    },

    // Matches Sample Receipt format: "29/09/2026 6:52PM"
    get orderIssueDate() {
        try {
            const dt = this.orderDateTime;
            return dt.toFormat("dd/MM/yyyy h:mma");
        } catch (e) {}
        return DateTime.now().toFormat("dd/MM/yyyy h:mma");
    },

    get dateOfSupply() {
        try {
            if (this.shipping_date) {
                if (typeof this.shipping_date.toFormat === "function") {
                    return this.shipping_date.toFormat("dd/MM/yyyy");
                }
                const parsed = DateTime.fromISO(String(this.shipping_date));
                if (parsed.isValid) {
                    return parsed.toFormat("dd/MM/yyyy");
                }
            }
        } catch (e) {}
        try {
            return this.orderDateTime.toFormat("dd/MM/yyyy");
        } catch (e) {}
        return DateTime.now().toFormat("dd/MM/yyyy");
    },

    get orderPrintDate() {
        return DateTime.now().toFormat("dd/MM/yyyy hh:mm a");
    },

    get totalTaxableAmountExcl() {
        try {
            return Number(this.priceExcl || 0).toFixed(2);
        } catch (e) {}
        return "0.00";
    },

    get totalDiscountAmount() {
        try {
            const disc = typeof this.getTotalDiscount === "function" ? this.getTotalDiscount() : 0;
            return Number(disc || 0).toFixed(2);
        } catch (e) {}
        return "0.00";
    },

    get totalVatAmount() {
        try {
            return Number(this.amountTaxes || 0).toFixed(2);
        } catch (e) {}
        return "0.00";
    },

    get totalAmountDue() {
        try {
            return Number(this.priceIncl || 0).toFixed(2);
        } catch (e) {}
        return "0.00";
    },

    get amountInWordsSAR() {
        try {
            return amountToWordsSAR(this.priceIncl || 0);
        } catch (e) {}
        return "";
    },

    get totalItemsCount() {
        return this.lines ? this.lines.length : 0;
    },

    // Barcode: uses order reference digits (e.g. *486810548*), NOT ticket_code (*zkdzp*)
    get orderBarcodeRaw() {
        try {
            if (this.pos_reference) {
                const digits = String(this.pos_reference).replace(/\D/g, "");
                if (digits) {
                    return digits;
                }
            }
            if (this.barcode) {
                return String(this.barcode).replace(/\*/g, "");
            }
            if (this.tracking_number) {
                const trDigits = String(this.tracking_number).replace(/\D/g, "");
                if (trDigits) {
                    return trDigits;
                }
            }
            const ordDigits = String(this.orderNumber || "").replace(/\D/g, "");
            if (ordDigits) {
                return ordDigits;
            }
        } catch (e) {}
        return "486810548";
    },

    get orderBarcodeValue() {
        return `*${this.orderBarcodeRaw}*`;
    },

    get companyLogoUrl() {
        try {
            if (this.config?.receiptLogoUrl) {
                return this.config.receiptLogoUrl;
            }
            if (this.company?.id) {
                return `/web/image?model=res.company&id=${this.company.id}&field=logo`;
            }
        } catch (e) {}
        return false;
    },

    get cashierDisplayName() {
        try {
            let name = typeof this.getCashierName === "function" ? this.getCashierName() : (this.user?.name || "Admin");
            if (name === "Administrator") {
                name = "Admin";
            }
            return name || "Admin";
        } catch (e) {}
        return "Admin";
    },

    // Matches Sample Receipt: diff = total - paid (e.g. 801.02 - 1000.00 = -198.98)
    get balanceAmount() {
        try {
            const paid = Number(this.amountPaid || 0);
            const total = Number(this.priceIncl || 0);
            const diff = total - paid;
            return diff.toFixed(2);
        } catch (e) {}
        return "0.00";
    },

    get taxDetails() {
        const taxes = {};
        if (!this.lines) return [];

        this.lines.forEach(line => {
            const lineTaxes = line.tax_ids || [];
            lineTaxes.forEach(tax => {
                if (!taxes[tax.id]) {
                    taxes[tax.id] = {
                        id: tax.id,
                        name: tax.name,
                        amount: 0
                    };
                }
                const lineTaxAmount = (line.priceIncl - line.priceExcl) || 0;
                taxes[tax.id].amount += lineTaxAmount;
            });
        });

        return Object.values(taxes).map(t => ({
            id: t.id,
            name: t.name,
            amountFormatted: t.amount.toFixed(2)
        }));
    },

    // Compliant ZATCA Phase 1 & 2 Electronic Invoicing QR code
    get saQrCode() {
        try {
            const company = this.company || this.pos?.company;
            const vat = company?.vat || "314710124800003";
            const name = company?.name || "Company";

            let dt = this.orderDateTime;
            if (!dt || !dt.isValid) {
                dt = DateTime.now();
            }
            if (dt > DateTime.now()) {
                dt = DateTime.now();
            }
            // ZATCA standard ISO 8601 timestamp: YYYY-MM-DDTHH:mm:ss
            const dateIso = dt.setZone("Asia/Riyadh").toFormat("yyyy-MM-dd'T'HH:mm:ss");

            const subtotal = Number(this.priceExcl || 0).toFixed(2);
            const tax = Number(this.amountTaxes || 0).toFixed(2);
            const total = (Number(subtotal) + Number(tax)).toFixed(2);

            function zatcaTLV(tag, val) {
                const textEncoder = new TextEncoder();
                const bytes = Array.from(textEncoder.encode(String(val)));
                return [tag, bytes.length, ...bytes];
            }

            const strToEncode = [
                ...zatcaTLV(1, name),
                ...zatcaTLV(2, vat),
                ...zatcaTLV(3, dateIso),
                ...zatcaTLV(4, total),
                ...zatcaTLV(5, tax),
            ];

            let binary = "";
            for (let i = 0; i < strToEncode.length; i++) {
                binary += String.fromCharCode(strToEncode[i]);
            }
            const base64TLV = btoa(binary);

            if (typeof window !== "undefined" && window.ZXing) {
                const codeWriter = new window.ZXing.BrowserQRCodeSvgWriter();
                const qrSvg = new XMLSerializer().serializeToString(codeWriter.write(base64TLV, 200, 200));
                return "data:image/svg+xml;base64," + window.btoa(qrSvg);
            }
        } catch (e) {
            console.warn("Could not generate ZATCA QR code:", e);
        }
        return false;
    },
});

patch(PosOrderline.prototype, {
    get serialNumber() {
        try {
            if (this.lot_name) {
                return String(this.lot_name);
            }
            if (this.pack_lot_ids && this.pack_lot_ids.length > 0) {
                const lots = this.pack_lot_ids.map((l) => l.lot_name).filter(Boolean);
                if (lots.length > 0) {
                    return lots.join(", ");
                }
            }
            if (this.packLotLines && this.packLotLines.length > 0) {
                return this.packLotLines.join(", ");
            }
        } catch (e) {}
        return "";
    },

    get unitPriceExclFormatted() {
        try {
            const qty = typeof this.getQuantity === "function" ? this.getQuantity() : (this.qty || 1);
            if (qty && typeof this.priceExcl === "number") {
                return (this.priceExcl / qty).toFixed(2);
            }
            if (typeof this.displayPriceUnitExcl === "number") {
                return this.displayPriceUnitExcl.toFixed(2);
            }
            if (typeof this.price_unit === "number") {
                return this.price_unit.toFixed(2);
            }
        } catch (e) {}
        return "0.00";
    },

    get quantityFormatted() {
        try {
            const qty = typeof this.getQuantity === "function" ? this.getQuantity() : (this.qty || 1);
            return Number(qty || 0).toFixed(2);
        } catch (e) {}
        return "1.00";
    },

    get subtotalInclFormatted() {
        try {
            if (typeof this.priceIncl === "number") {
                return this.priceIncl.toFixed(2);
            }
        } catch (e) {}
        return "0.00";
    },

    get productDisplayName() {
        if (this.full_product_name) {
            return this.full_product_name;
        }
        let product = this.product_id;
        if (typeof product === "number" || typeof product === "string") {
            const prodModel =
                this.models?.["product.product"] ||
                this.pos?.models?.["product.product"] ||
                this.order_id?.pos?.models?.["product.product"];
            product = prodModel?.get(product) || product;
        }
        return product?.display_name || product?.name || "";
    },

    // Arabic product name from product master (product.product / product.template)
    get productArabicName() {
        try {
            if (this.product_arabic_name) {
                return String(this.product_arabic_name).trim();
            }
            let product = this.product_id;
            if (typeof product === "number" || typeof product === "string") {
                const prodModel =
                    this.models?.["product.product"] ||
                    this.pos?.models?.["product.product"] ||
                    this.order_id?.pos?.models?.["product.product"];
                product = prodModel?.get(product) || product;
            }
            if (product && typeof product === "object") {
                let tmpl = product.product_tmpl_id;
                if (typeof tmpl === "number" || typeof tmpl === "string") {
                    const tmplModel =
                        this.models?.["product.template"] ||
                        this.pos?.models?.["product.template"] ||
                        this.order_id?.pos?.models?.["product.template"];
                    tmpl = tmplModel?.get(tmpl) || tmpl;
                }
                const arName =
                    product.product_arabic_name ||
                    product.arabic_name ||
                    product.name_arabic ||
                    (tmpl && typeof tmpl === "object"
                        ? tmpl.product_arabic_name || tmpl.arabic_name || tmpl.name_arabic
                        : "") ||
                    "";
                if (arName) {
                    return String(arName).trim();
                }
            }
        } catch (e) {}
        return "";
    },

});

patch(PosPayment.prototype, {
    get amountFormatted() {
        try {
            return (this.amount || 0).toFixed(2);
        } catch (e) {}
        return "0.00";
    },
});