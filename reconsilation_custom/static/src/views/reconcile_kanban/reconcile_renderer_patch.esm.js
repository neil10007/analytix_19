import { patch } from "@web/core/utils/patch";
import { ReconcileRenderer } from "@account_reconcile_oca/views/reconcile_kanban/reconcile_renderer.esm";
import { useState } from "@odoo/owl";

patch(ReconcileRenderer.prototype, {
    setup() {
        super.setup();
        if (!this.treeState) {
            this.treeState = useState({
                expandedAccounts: {},
            });
        }
    },

    get isAccountReconcile() {
        return this.env.parentController?.props?.resModel === "account.account.reconcile";
    },

    get groupedAccounts() {
        if (!this.isAccountReconcile) {
            return [];
        }
        const accountsMap = new Map();
        const records = this.props.list?.records || [];

        for (const record of records) {
            const accountField = record.data.account_id;
            const accountId = Array.isArray(accountField)
                ? accountField[0]
                : (accountField?.id || accountField || 0);
            const accountName = Array.isArray(accountField)
                ? accountField[1]
                : (accountField?.display_name || record.data.name || "Unknown Account");

            if (!accountsMap.has(accountId)) {
                accountsMap.set(accountId, {
                    id: accountId,
                    name: accountName,
                    records: [],
                    partners: [],
                    hasPartners: false,
                    hasSelectedRecord: false,
                });
            }

            const group = accountsMap.get(accountId);
            group.records.push(record);

            const partnerField = record.data.partner_id;
            const partnerId = Array.isArray(partnerField)
                ? partnerField[0]
                : (partnerField?.id || null);
            const partnerName = Array.isArray(partnerField)
                ? partnerField[1]
                : (partnerField?.display_name || null);
            const isSelected = this.props.selectedRecordId === record.resId;

            if (isSelected) {
                group.hasSelectedRecord = true;
            }
            if (partnerId) {
                group.hasPartners = true;
            }

            group.partners.push({
                id: record.resId,
                partnerId: partnerId,
                partnerName: partnerName || (group.records.length > 1 ? `Item #${group.records.length}` : "General / No Partner"),
                record: record,
                isSelected: isSelected,
            });
        }

        return Array.from(accountsMap.values());
    },

    isAccountExpanded(acc) {
        if (this.treeState && this.treeState.expandedAccounts[acc.id] !== undefined) {
            return this.treeState.expandedAccounts[acc.id];
        }
        if (acc.hasSelectedRecord || this.groupedAccounts.length === 1) {
            return true;
        }
        return false;
    },

    toggleAccount(acc, ev) {
        if (ev) {
            ev.stopPropagation();
        }
        const current = this.isAccountExpanded(acc);
        if (this.treeState) {
            this.treeState.expandedAccounts[acc.id] = !current;
        }
    },

    async onAccountClick(acc) {
        if (acc.hasPartners || acc.partners.length > 1) {
            const isExp = this.isAccountExpanded(acc);
            if (this.treeState) {
                this.treeState.expandedAccounts[acc.id] = !isExp;
            }
            if (!isExp && !acc.hasSelectedRecord && acc.partners.length > 0) {
                await this.onSelectPartner(acc.partners[0].record);
            }
        } else if (acc.partners.length === 1) {
            await this.onSelectPartner(acc.partners[0].record);
        }
    },

    async onSelectPartner(record) {
        if (this.props.openRecord) {
            await this.props.openRecord(record);
        }
    },
});

import { ReconcileFormController } from "@account_reconcile_oca/views/reconcile_form/reconcile_form_controller.esm";
import { useService } from "@web/core/utils/hooks";

patch(ReconcileFormController.prototype, {
    setup() {
        super.setup(...arguments);
        this.notification = useService("notification");
    },
    beforeExecuteActionButton(clickParams) {
        if (clickParams.name === "reconcile") {
            const counterparts = this.model.root.data.reconcile_data_info?.counterparts || [];
            if (counterparts.length === 0) {
                this.notification.add(
                    "Please select the matching entries you want to reconcile from the table below.",
                    {
                        title: "Nothing to Reconcile",
                        type: "warning",
                        sticky: false,
                    }
                );
                return false;
            }
        }
        return super.beforeExecuteActionButton ? super.beforeExecuteActionButton(clickParams) : true;
    },
});

