/** @odoo-module */
import { Component, useState, onWillStart, onMounted, useRef, useEffect, onWillUnmount, xml, useSubEnv } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";
import { Discuss } from "@mail/core/public_web/discuss";
import { MessagingMenu } from "@mail/core/public_web/messaging_menu";
import { DROPDOWN_NESTING } from "@web/core/dropdown/_behaviours/dropdown_nesting";

export class DashboardMessagingMenu extends Component {
    static template = xml`
        <div class="d-flex flex-column h-100 w-100 overflow-hidden bg-view border rounded-3 shadow-lg" style="min-height: 420px; max-height: 480px;">
            <MessagingMenu/>
        </div>
    `;
    static components = { MessagingMenu };
    setup() {
        const dashboard = this.env.dashboard;
        const mockDropdown = {
            children: new Set(),
            close: () => {
                if (dashboard && dashboard.state) {
                    dashboard.state.showChatPopup = false;
                }
            },
            closeChildren: () => {},
            closeAllParents: () => {},
            open: () => {},
            toggle: () => {},
            isOpen: true,
        };
        useSubEnv({ 
            inDiscussApp: false,
            [DROPDOWN_NESTING]: mockDropdown,
            inMessagingMenu: {
                dropdown: mockDropdown,
            }
        });
    }
}

export class AnalytixFinanceDashboard extends Component {
    static template = "analytix_finance_dashboard.Dashboard";
    static components = { Discuss, DashboardMessagingMenu };

    setup() {
        useSubEnv({ dashboard: this });
        this.action       = useService("action");
        this.notification = useService("notification");
        this.orm          = useService("orm");
        this.store        = useService("mail.store");

        this.state = useState({
            data:      null,
            filter:    'this_month',
            activeTab: 'overview',
            topPartnerMode: 'customers', // 'customers' or 'vendors'
            // (Uses Odoo's native Discuss component)
            // ── Custom date range ────────────────────────────────────────
            customFrom:         '',
            customTo:           '',
            showCustomPicker:   false,
            // ── Invoice tab state ────────────────────────────────────────
            invoices:           null,
            invLoading:         false,
            invTypeFilter:      'customer', // all | customer | vendor | credit_note
            invStatusFilter:    'all',      // all | paid | not_paid | partial | draft
            invSearch:          '',
            invSortCol:         'invoice_date',
            invSortDir:         'desc',     // asc | desc
            invCompanyFilter:   'all',      // all | <company_id>
            // ── Expense tab state ────────────────────────────────────────
            expenses:           null,
            expLoading:         false,
            expStatusFilter:    'all',
            expSearch:          '',
            expSortCol:         'invoice_date',
            expSortDir:         'desc',
            expCompanyFilter:   'all',
            // ── VAT tab state
            vatData:        null,
            vatLoading:     false,
            vatTypeFilter:  'all',
            vatSearch:      '',
            vatSortCol:     'invoice_date',
            vatSortDir:     'desc',
            vatCompanyFilter: 'all',
            showVatModal:   false,
            vatFilterFrom:  '',
            vatFilterTo:    '',
            // ── Journals tab
            jrnData:         null,
            jrnLoading:      false,
            jrnTypeFilter:   'all',
            jrnSearch:       '',
            jrnSortCol:      'date',
            jrnSortDir:      'desc',
            jrnCompanyFilter:'all',
            // ── Trial Balance tab
            tbData:          null,
            tbLoading:       false,
            tbTypeFilter:    'all',   // all | asset | liability | income | expense | equity
            tbSearch:        '',
            tbSortCol:       'code',
            tbSortDir:       'asc',
            tbCompanyFilter: 'all',
            // ── P&L Modal
            plData:          null,
            plLoading:       false,
            showPlModal:     false,
            plDateOption:    'this_month',
            plCustomFrom:    '',
            plCustomTo:      '',
            plShowDateDrop:  false,
            // ── Balance Sheet Modal
            bsData:          null,
            bsLoading:       false,
            showBsModal:     false,
            bsDateOption:    'today',       // today|end_month|end_quarter|end_year|specific
            bsAsOfIso:       null,          // primary "as of" ISO date
            bsCompareMode:   false,         // show comparison column
            bsCompareIso:    null,          // comparison ISO date
            bsShowDateDrop:  false,         // primary date dropdown open
            bsSpecificDate:  '',            // input for specific date
            // ── Trial Balance Modal
            showTbModal:     false,
            tbModalLoading:  false,
            tbModalData:     null,
            // ── Document Upload (invoice/bill)
            uploadFile:       null,    // { name, size, type, dataUrl }
            uploadDragOver:   false,
            uploadDocType:    '',      // 'invoice' | 'bill'
            uploadExtracted:  { partner: '', ref: '', date: '', due_date: '', amount: '', currency: '', narration: '' },
            uploadSubmitting:  false,
            // ── Documents Tab
            docList:          null,
            docLoading:       false,
            docSearch:        '',
            docUploadFile:    null,
            docDragOver:      false,
            docUploading:     false,
            docDocName:       '',
            docDescription:   '',
            docDescError:     false,
            docType:          '',          // 'invoice' | 'bill' | 'other'
            docTypeError:     false,
            docEditId:        null,
            docEditDesc:      '',
            docReviewEditId:  null,        // id of doc whose review is being edited
            docReviewEditVal: '',
            // ── Document Preview Modal State
            showDocPreview:   false,
            previewDocName:   '',
            previewDocType:   '',
            previewDocUrl:    '',
            previewDocId:     null,
            analyzingDocId:   null,
            // ── Floating Chat Widget State ──────────────────────────────
            chatPos: {
                x: parseInt(localStorage.getItem('anx_chat_pos_x')) || (typeof window !== 'undefined' ? window.innerWidth - 90 : 800),
                y: parseInt(localStorage.getItem('anx_chat_pos_y')) || (typeof window !== 'undefined' ? window.innerHeight - 90 : 600),
            },
            showChatPopup: false,
            activeThreadId: null,
            messageText: '',
            chatSearch: '',
            chatSearchResults: [],
            chatSearchLoading: false,
            chatPolling: false,
        });

        this.chartRef1 = useRef("revExpChart");
        this.messageFeedRef = useRef("messageFeed");
        this.chart1    = null;

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            // Restore last active tab from session
            const savedTab = sessionStorage.getItem('anx_active_tab') || 'overview';
            this.state.activeTab = savedTab;
            await this.fetchData();
            // Also fetch the saved tab's data
            if (savedTab === 'invoices')      await this.fetchInvoiceData();
            if (savedTab === 'expenses')      await this.fetchExpenseData();
            if (savedTab === 'vat')           await this.fetchVatData();
            if (savedTab === 'journals')      await this.fetchJournalData();
            if (savedTab === 'trial_balance') await this.fetchTrialBalanceData();
            if (savedTab === 'documents')     await this.fetchDocumentData();
            if (savedTab === 'chat')          this.store.discuss.isActive = true;

            // Pre-fetch discuss channels so chat widget is immediately ready
            if (this.store && this.store.channels && this.store.channels.fetch) {
                try {
                    this.store.channels.fetch();
                } catch (e) {
                    console.error("Error pre-fetching channels:", e);
                }
            }
        });

        onMounted(() => {
            this.renderCharts();
            const activeTabEl = document.querySelector('.anx-tabs .anx-tab.active');
            if (activeTabEl) {
                activeTabEl.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
            }
            // Ensure chat icon is visible inside viewport
            const btnSize = 56;
            let cx = parseInt(this.state.chatPos.x);
            let cy = parseInt(this.state.chatPos.y);
            const maxX = window.innerWidth - btnSize - 20;
            const maxY = window.innerHeight - btnSize - 20;
            if (isNaN(cx) || cx < 20 || cx > maxX) {
                cx = Math.max(20, window.innerWidth - btnSize - 30);
            }
            if (isNaN(cy) || cy < 60 || cy > maxY) {
                cy = Math.max(60, window.innerHeight - btnSize - 30);
            }
            this.state.chatPos.x = cx;
            this.state.chatPos.y = cy;
        });
        useEffect(() => this.renderCharts(), () => [this.state.data]);
        useEffect(() => {
            if (this.messageFeedRef.el) {
                this.messageFeedRef.el.scrollTop = this.messageFeedRef.el.scrollHeight;
            }
        }, () => [this.state.activeThreadId, this.activeThreadMessages?.length]);
        onWillUnmount(() => {
            this.store.discuss.isActive = false;
            this.stopChatPolling();
        });
    }

    // ── Data ──────────────────────────────────────────────────────────
    async fetchData() {
        try {
            this.state.data = await this.orm.call(
                "account.move",
                "get_analytix_dashboard_data",
                [this.state.filter, this.state.customFrom, this.state.customTo]
            );
        } catch (e) {
            this.notification.add("Failed to load dashboard data.", { type: 'danger' });
        }
    }

    // ── Filter select ────────────────────────────────────────────────
    async setFilter(ev) {
        this.state.filter = ev.target.value;
        if (this.state.filter === 'custom') {
            // Show date picker — don't fetch yet, wait for user to pick dates
            this.state.showCustomPicker = true;
            return;
        }
        this.state.showCustomPicker = false;
        this.state.customFrom = '';
        this.state.customTo   = '';
        await this.fetchData();
        if (this.state.activeTab === 'invoices')      await this.fetchInvoiceData();
        if (this.state.activeTab === 'expenses')      await this.fetchExpenseData();
        if (this.state.activeTab === 'vat')           await this.fetchVatData();
        if (this.state.activeTab === 'journals')      await this.fetchJournalData();
        if (this.state.activeTab === 'trial_balance') await this.fetchTrialBalanceData();
    }

    // ── Custom date range change ──────────────────────────────────────
    onCustomDateChange(ev) {
        const field = ev.target.dataset.field;
        if (field === 'from') this.state.customFrom = ev.target.value;
        if (field === 'to')   this.state.customTo   = ev.target.value;
    }

    // ── Apply custom range ───────────────────────────────────────────
    async applyCustomRange() {
        if (!this.state.customFrom || !this.state.customTo) {
            this.notification.add('Please select both From and To dates.', { type: 'warning' });
            return;
        }
        if (this.state.customFrom > this.state.customTo) {
            this.notification.add('"From" date must be before "To" date.', { type: 'warning' });
            return;
        }
        await this.fetchData();
        if (this.state.activeTab === 'invoices')      await this.fetchInvoiceData();
        if (this.state.activeTab === 'expenses')      await this.fetchExpenseData();
        if (this.state.activeTab === 'vat')           await this.fetchVatData();
        if (this.state.activeTab === 'journals')      await this.fetchJournalData();
        if (this.state.activeTab === 'trial_balance') await this.fetchTrialBalanceData();
    }

    // ── Tab click — reads data-tab attribute ──────────────────────────
    async onTabClick(ev) {
        const tab = ev.currentTarget.dataset.tab;
        if (!tab) return;
        if (ev.currentTarget && ev.currentTarget.scrollIntoView) {
            ev.currentTarget.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
        }
        this.state.activeTab = tab;
        sessionStorage.setItem('anx_active_tab', tab); // persist tab across refresh
        if (tab === 'invoices') {
            if (!this.state.invoices || this.state.invTypeFilter !== 'customer') {
                this.state.invTypeFilter = 'customer';
                this.state.invStatusFilter = 'all';
                this.state.invSearch = '';
            }
            await this.fetchInvoiceData();
        }
        if (tab === 'expenses') {
            this.state.expStatusFilter = 'all';
            this.state.expSearch = '';
            await this.fetchExpenseData();
        }
        if (tab === 'vat') {
            this.state.vatSearch = '';
            this.state.vatTypeFilter = 'all';
            await this.fetchVatData();
        }
        if (tab === 'journals') {
            this.state.jrnSearch = '';
            this.state.jrnTypeFilter = 'all';
            await this.fetchJournalData();
        }
        if (tab === 'trial_balance') {
            this.state.tbSearch = '';
            this.state.tbTypeFilter = 'all';
            await this.fetchTrialBalanceData();
        }
        if (tab === 'documents') {
            this.state.docSearch = '';
            await this.fetchDocumentData();
        }
        if (tab === 'chat') {
            this.store.discuss.isActive = true;
            if (this.store && this.store.channels && this.store.channels.fetch) {
                this.store.channels.fetch();
            }
        } else {
            this.store.discuss.isActive = false;
        }
    }

    toggleTopPartners() {
        this.state.topPartnerMode = this.state.topPartnerMode === 'customers' ? 'vendors' : 'customers';
    }

    // ── Invoice data fetch ────────────────────────────────────────────
    async fetchInvoiceData() {
        this.state.invLoading = true;
        try {
            this.state.invoices = await this.orm.call(
                'account.move',
                'get_analytix_invoices_data',
                [this.state.filter, this.state.invTypeFilter, this.state.customFrom, this.state.customTo]
            );
        } catch (e) {
            this.notification.add('Failed to load invoice list.', { type: 'danger' });
        } finally {
            this.state.invLoading = false;
        }
    }

    // ── Invoice type filter ───────────────────────────────────────────
    async onInvTypeFilter(ev) {
        const val = ev.currentTarget.dataset.type;
        if (!val) return;
        this.state.invTypeFilter = val;
        await this.fetchInvoiceData();
    }

    // ── Invoice status/company/search/sort filters (client-side) ─────
    onInvStatusFilter(ev) {
        this.state.invStatusFilter = ev.currentTarget.dataset.status || 'all';
    }
    onInvCompanyFilter(ev) {
        this.state.invCompanyFilter = ev.currentTarget.dataset.company || 'all';
    }
    onInvSearch(ev) {
        this.state.invSearch = ev.target.value;
    }
    onInvSort(ev) {
        const col = ev.currentTarget.dataset.col;
        if (!col) return;
        if (this.state.invSortCol === col) {
            this.state.invSortDir = this.state.invSortDir === 'asc' ? 'desc' : 'asc';
        } else {
            this.state.invSortCol = col;
            this.state.invSortDir = 'asc';
        }
    }

    // ── Computed: filtered+sorted invoice records ─────────────────────
    get filteredInvoices() {
        if (!this.state.invoices) return [];
        let rows = this.state.invoices.records;

        // Status filter
        if (this.state.invStatusFilter !== 'all') {
            rows = rows.filter(r => r.status_key === this.state.invStatusFilter);
        }
        // Company filter
        if (this.state.invCompanyFilter !== 'all') {
            const cid = parseInt(this.state.invCompanyFilter, 10);
            rows = rows.filter(r => r.company_id === cid);
        }
        // Text search
        if (this.state.invSearch.trim()) {
            const q = this.state.invSearch.trim().toLowerCase();
            rows = rows.filter(r =>
                r.name.toLowerCase().includes(q) ||
                r.partner.toLowerCase().includes(q) ||
                r.journal.toLowerCase().includes(q)
            );
        }

        // Sort
        const col = this.state.invSortCol;
        const dir = this.state.invSortDir === 'asc' ? 1 : -1;
        rows = [...rows].sort((a, b) => {
            let av = a[col], bv = b[col];
            if (typeof av === 'string') av = av.toLowerCase();
            if (typeof bv === 'string') bv = bv.toLowerCase();
            if (av < bv) return -1 * dir;
            if (av > bv) return 1 * dir;
            return 0;
        });
        return rows;
    }

    // ── Open invoice form view ────────────────────────────────────────
    openInvoice(ev) {
        const id = parseInt(ev.currentTarget.dataset.id, 10);
        if (!id) return;
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'account.move',
            res_id: id,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    // ── Create new Invoice (Customer) or Bill (Vendor) ───────────────
    createNewInvoice() {
        const isVendor = this.state.invTypeFilter === 'vendor';
        const moveType = isVendor ? 'in_invoice' : 'out_invoice';
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: isVendor ? 'New Vendor Bill' : 'New Customer Invoice',
            res_model: 'account.move',
            views: [[false, 'form']],
            target: 'current',
            context: {
                default_move_type: moveType,
                move_type: moveType,
            },
        });
    }


    // ── Expense data fetch ────────────────────────────────────────────
    async fetchExpenseData() {
        this.state.expLoading = true;
        try {
            this.state.expenses = await this.orm.call(
                'account.move',
                'get_analytix_invoices_data',
                [this.state.filter, 'vendor', this.state.customFrom, this.state.customTo]
            );
        } catch (e) {
            this.notification.add('Failed to load expense list.', { type: 'danger' });
        } finally {
            this.state.expLoading = false;
        }
    }

    // ── Expense filters (client-side) ─────────────────────────────────
    onExpStatusFilter(ev) { this.state.expStatusFilter = ev.currentTarget.dataset.status || 'all'; }
    onExpCompanyFilter(ev) { this.state.expCompanyFilter = ev.currentTarget.dataset.company || 'all'; }
    onExpSearch(ev) { this.state.expSearch = ev.target.value; }
    onExpSort(ev) {
        const col = ev.currentTarget.dataset.col;
        if (!col) return;
        if (this.state.expSortCol === col) {
            this.state.expSortDir = this.state.expSortDir === 'asc' ? 'desc' : 'asc';
        } else {
            this.state.expSortCol = col;
            this.state.expSortDir = 'asc';
        }
    }

    // ── Computed: filtered+sorted expense records ─────────────────────
    get filteredExpenses() {
        if (!this.state.expenses) return [];
        let rows = this.state.expenses.records;
        if (this.state.expStatusFilter !== 'all') rows = rows.filter(r => r.status_key === this.state.expStatusFilter);
        if (this.state.expCompanyFilter !== 'all') {
            const cid = parseInt(this.state.expCompanyFilter, 10);
            rows = rows.filter(r => r.company_id === cid);
        }
        if (this.state.expSearch.trim()) {
            const q = this.state.expSearch.trim().toLowerCase();
            rows = rows.filter(r => r.name.toLowerCase().includes(q) || r.partner.toLowerCase().includes(q) || r.journal.toLowerCase().includes(q));
        }
        const col = this.state.expSortCol;
        const dir = this.state.expSortDir === 'asc' ? 1 : -1;
        rows = [...rows].sort((a, b) => {
            let av = a[col], bv = b[col];
            if (typeof av === 'string') av = av.toLowerCase();
            if (typeof bv === 'string') bv = bv.toLowerCase();
            if (av < bv) return -1 * dir;
            if (av > bv) return 1 * dir;
            return 0;
        });
        return rows;
    }

    // ── Open bill form view ───────────────────────────────────────────
    openExpense(ev) {
        const id = parseInt(ev.currentTarget.dataset.id, 10);
        if (!id) return;
        this.action.doAction({ type: 'ir.actions.act_window', res_model: 'account.move', res_id: id, views: [[false, 'form']], target: 'current' });
    }

    // ── Create new Vendor Bill ─────────────────────────────────────────
    createNewBill() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'New Vendor Bill',
            res_model: 'account.move',
            views: [[false, 'form']],
            target: 'current',
            context: {
                default_move_type: 'in_invoice',
                move_type: 'in_invoice',
            },
        });
    }


    // ── VAT data fetch ────────────────────────────────────────────────
    async fetchVatData() {
        if (!this.state.vatFilterFrom && !this.state.vatFilterTo) {
            this.state.vatFilterFrom = (this.state.data && this.state.data.date_range && this.state.data.date_range.start) || this.state.customFrom || '';
            this.state.vatFilterTo   = (this.state.data && this.state.data.date_range && this.state.data.date_range.end) || this.state.customTo || '';
        }
        await this.fetchVatFilterData();
    }
    onVatTypeFilter(ev) { this.state.vatTypeFilter = ev.currentTarget.dataset.vtype || 'all'; }
    onVatSearch(ev)      { this.state.vatSearch = ev.target.value; }
    onVatSort(ev) {
        const col = ev.currentTarget.dataset.col;
        if (!col) return;
        if (this.state.vatSortCol === col) { this.state.vatSortDir = this.state.vatSortDir === 'asc' ? 'desc' : 'asc'; }
        else { this.state.vatSortCol = col; this.state.vatSortDir = 'asc'; }
    }
    onVatCompanyFilter(ev) { this.state.vatCompanyFilter = ev.currentTarget.dataset.company || 'all'; }

    _filterSortVat(rows) {
        if (this.state.vatCompanyFilter !== 'all') {
            const cid = parseInt(this.state.vatCompanyFilter, 10);
            rows = rows.filter(r => r.company_id === cid);
        }
        if (this.state.vatSearch.trim()) {
            const q = this.state.vatSearch.trim().toLowerCase();
            rows = rows.filter(r => r.move_name.toLowerCase().includes(q) || r.partner.toLowerCase().includes(q) || r.tax_name.toLowerCase().includes(q));
        }
        const col = this.state.vatSortCol;
        const dir = this.state.vatSortDir === 'asc' ? 1 : -1;
        return [...rows].sort((a, b) => {
            let av = a[col], bv = b[col];
            if (typeof av === 'string') { av = av.toLowerCase(); bv = bv.toLowerCase(); }
            if (av < bv) return -1 * dir; if (av > bv) return 1 * dir; return 0;
        });
    }
    get filteredOutputVat() {
        if (!this.state.vatData) return [];
        return this._filterSortVat(this.state.vatData.output_records);
    }
    get filteredInputVat() {
        if (!this.state.vatData) return [];
        return this._filterSortVat(this.state.vatData.input_records);
    }
    openVatDoc(ev) {
        const id = parseInt(ev.currentTarget.dataset.id, 10);
        if (!id) return;
        this.action.doAction({ type: 'ir.actions.act_window', res_model: 'account.move', res_id: id, views: [[false, 'form']], target: 'current' });
    }


    async fetchJournalData() {
        this.state.jrnLoading = true;
        try {
            this.state.jrnData = await this.orm.call('account.move', 'get_analytix_journals_data',
                [this.state.filter, this.state.customFrom, this.state.customTo]);
        } catch (e) {
            this.notification.add('Failed to load journal data.', { type: 'danger' });
        } finally {
            this.state.jrnLoading = false;
        }
    }
    onJrnTypeFilter(ev) { this.state.jrnTypeFilter = ev.currentTarget.dataset.jtype || 'all'; }
    onJrnSearch(ev)      { this.state.jrnSearch = ev.target.value; }
    onJrnCompanyFilter(ev) { this.state.jrnCompanyFilter = ev.currentTarget.dataset.company || 'all'; }
    onJrnSort(ev) {
        const col = ev.currentTarget.dataset.col;
        if (!col) return;
        if (this.state.jrnSortCol === col) { this.state.jrnSortDir = this.state.jrnSortDir === 'asc' ? 'desc' : 'asc'; }
        else { this.state.jrnSortCol = col; this.state.jrnSortDir = 'asc'; }
    }
    get filteredJournals() {
        if (!this.state.jrnData) return [];
        let rows = this.state.jrnData.records;
        if (this.state.jrnTypeFilter !== 'all') rows = rows.filter(r => r.type === this.state.jrnTypeFilter);
        if (this.state.jrnCompanyFilter !== 'all') {
            const cid = parseInt(this.state.jrnCompanyFilter, 10);
            rows = rows.filter(r => r.company_id === cid);
        }
        if (this.state.jrnSearch.trim()) {
            const q = this.state.jrnSearch.trim().toLowerCase();
            rows = rows.filter(r =>
                (r.name && r.name.toLowerCase().includes(q)) ||
                (r.journal_name && r.journal_name.toLowerCase().includes(q)) ||
                (r.journal_code && r.journal_code.toLowerCase().includes(q)) ||
                (r.partner && r.partner.toLowerCase().includes(q)) ||
                (r.ref && r.ref.toLowerCase().includes(q)) ||
                (r.type_label && r.type_label.toLowerCase().includes(q))
            );
        }
        const col = this.state.jrnSortCol || 'date';
        const dir = this.state.jrnSortDir === 'asc' ? 1 : -1;
        return [...rows].sort((a, b) => {
            let av = a[col] ?? '', bv = b[col] ?? '';
            if (typeof av === 'string') { av = av.toLowerCase(); bv = bv.toLowerCase(); }
            if (av < bv) return -1 * dir; if (av > bv) return 1 * dir; return 0;
        });
    }
    openJournal(ev) {
        const id = parseInt(ev.currentTarget.dataset.id, 10);
        if (!id) return;
        this.action.doAction({ type: 'ir.actions.act_window', res_model: 'account.move', res_id: id, views: [[false, 'form']], target: 'current' });
    }
    // ── Trial Balance data fetch ──────────────────────────────────────
    async fetchTrialBalanceData() {
        this.state.tbLoading = true;
        try {
            this.state.tbData = await this.orm.call('account.move', 'get_analytix_trial_balance_data',
                [this.state.filter, this.state.customFrom, this.state.customTo]);
        } catch (e) {
            this.notification.add('Failed to load trial balance data.', { type: 'danger' });
        } finally {
            this.state.tbLoading = false;
        }
    }

    onTbTypeFilter(ev)    { this.state.tbTypeFilter    = ev.currentTarget.dataset.atype   || 'all'; }
    onTbSearch(ev)        { this.state.tbSearch        = ev.target.value; }
    onTbCompanyFilter(ev) { this.state.tbCompanyFilter = ev.currentTarget.dataset.company || 'all'; }
    onTbSort(ev) {
        const col = ev.currentTarget.dataset.col;
        if (!col) return;
        if (this.state.tbSortCol === col) { this.state.tbSortDir = this.state.tbSortDir === 'asc' ? 'desc' : 'asc'; }
        else { this.state.tbSortCol = col; this.state.tbSortDir = 'asc'; }
    }

    get filteredTrialBalance() {
        if (!this.state.tbData) return [];
        let rows = this.state.tbData.records;
        // Type filter
        if (this.state.tbTypeFilter !== 'all') {
            rows = rows.filter(r => r.type_group === this.state.tbTypeFilter);
        }
        // Company filter
        if (this.state.tbCompanyFilter !== 'all') {
            const cid = parseInt(this.state.tbCompanyFilter, 10);
            rows = rows.filter(r => r.company_id === cid);
        }
        // Text search
        if (this.state.tbSearch.trim()) {
            const q = this.state.tbSearch.trim().toLowerCase();
            rows = rows.filter(r =>
                r.name.toLowerCase().includes(q) ||
                r.code.toLowerCase().includes(q) ||
                r.type_label.toLowerCase().includes(q)
            );
        }
        // Sort
        const col = this.state.tbSortCol;
        const dir = this.state.tbSortDir === 'asc' ? 1 : -1;
        return [...rows].sort((a, b) => {
            let av = a[col] ?? '', bv = b[col] ?? '';
            if (typeof av === 'string') { av = av.toLowerCase(); bv = bv.toLowerCase(); }
            if (av < bv) return -1 * dir; if (av > bv) return 1 * dir; return 0;
        });
    }

    get tbFilteredInitial() { return this.filteredTrialBalance.reduce((s, r) => s + (r.initial_balance || 0), 0); }
    get tbFilteredDebit()   { return this.filteredTrialBalance.reduce((s, r) => s + (r.debit  || 0), 0); }
    get tbFilteredCredit()  { return this.filteredTrialBalance.reduce((s, r) => s + (r.credit || 0), 0); }
    get tbFilteredPeriod()  { return this.filteredTrialBalance.reduce((s, r) => s + (r.period_balance || 0), 0); }
    get tbFilteredEnding()  { return this.filteredTrialBalance.reduce((s, r) => s + (r.ending_balance || 0), 0); }

    openTrialBalanceAccount(ev) {
        const id = parseInt(ev.currentTarget.dataset.id, 10);
        if (!id) return;
        this.action.doAction({
            type:       'ir.actions.act_window',
            name:       'Account Entries',
            res_model:  'account.move.line',
            domain:     [['account_id', '=', id], ['move_id.state', '=', 'posted']],
            views:      [[false, 'list'], [false, 'form']],
            target:     'current',
        });
    }

    openJournalEntries(ev) {
        ev.stopPropagation();
        const id = parseInt(ev.currentTarget.dataset.id, 10);
        if (!id) return;
        this.action.doAction({ type: 'ir.actions.act_window', res_model: 'account.move', domain: [['journal_id','=',id],['state','=','posted']], views: [[false,'list'],[false,'form']], target: 'current', name: 'Journal Entries' });
    }

    // ── KPI card click — reads data-card attribute ────────────────────
    onCardClick(ev) {
        const card = ev.currentTarget.dataset.card;
        if (card) this.openCardView(card);
    }

    // ── Quick-action click — reads data-action attribute ──────────────
    onActionClick(ev) {
        const act = ev.currentTarget.dataset.action;
        if (act) this.openAction(act);
    }

    // ── Alert click — reads data-alert attribute ──────────────────────
    onAlertClick(ev) {
        const alert = ev.currentTarget.dataset.alert;
        if (alert) this.openAlertView(alert);
    }

    // ── Chart ─────────────────────────────────────────────────────────
    renderCharts() {
        if (!this.state.data || !this.chartRef1.el) return;
        if (this.chart1) { this.chart1.destroy(); this.chart1 = null; }

        const revData  = this.state.data.chart.revenue;
        const expData  = this.state.data.chart.expenses;
        const sym      = (this.state.data && this.state.data.currency) || '';

        const ctx = this.chartRef1.el.getContext('2d');
        this.chart1 = new window.Chart(ctx, {
            type: 'bar',
            data: {
                labels: this.state.data.chart.labels,
                datasets: [
                    {
                        label: 'Revenue',
                        data: revData,
                        backgroundColor: '#00d4c8',
                        borderRadius: 4,
                        yAxisID: 'yRev',
                    },
                    {
                        label: 'Expenses',
                        data: expData,
                        backgroundColor: 'rgba(0,212,200,0.30)',
                        borderRadius: 4,
                        yAxisID: 'yExp',
                    },
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (c) => ` ${c.dataset.label}: ${sym} ${Number(c.raw).toLocaleString()}`
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { font: { size: 11 }, color: '#8a93a4' },
                    },
                    yRev: {
                        display: false,
                        beginAtZero: true,
                        position: 'left',
                    },
                    yExp: {
                        display: false,
                        beginAtZero: true,
                        position: 'right',
                    },
                }
            }
        });
    }

    // ── Formatters ────────────────────────────────────────────────────
    formatCurrency(value) {
        if (!this.state.data) return String(value);
        const sym = this.state.data.currency;
        const num = Math.abs(Number(value));
        return `${sym} ${num.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
    }

    formatShort(value) {
        const n = Number(value);
        if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
        if (n >= 1_000)     return (n / 1_000).toFixed(1) + 'k';
        return n.toFixed(0);
    }

    // Cap percentage display — prevent ugly numbers like 3779.4%
    formatPct(value) {
        const n = Math.abs(Number(value));
        if (n > 999) return '999%+';
        return (n >= 10 ? n.toFixed(0) : n.toFixed(1)) + '%';
    }

    // Format YYYY-MM-DD → "Jun 2026"
    formatDate(dateStr) {
        if (!dateStr) return '';
        try {
            const d = new Date(dateStr + 'T00:00:00');
            return d.toLocaleDateString(undefined, { month: 'short', year: 'numeric' });
        } catch (_) { return dateStr; }
    }



    // ── Card drill-down ───────────────────────────────────────────────
    async openCardView(cardType) {
        if (!this.state.data) return;
        const { start, end } = this.state.data.date_range;
        const companyIds = this.state.data.company_ids;
        const base = [['company_id', 'in', companyIds], ['state', '=', 'posted']];
        const dateRange = [['invoice_date', '>=', start], ['invoice_date', '<=', end]];

        const configs = {
            revenue:     { name: 'Revenue — Customer Invoices',       xmlId: 'account.action_move_out_invoice_type', domain: [...base, ['move_type', '=', 'out_invoice'], ...dateRange] },
            invoices:    { name: 'Invoices This Period',              xmlId: 'account.action_move_out_invoice_type', domain: [...base, ['move_type', '=', 'out_invoice'], ...dateRange] },
            expenses:    { name: 'Expenses — Vendor Bills',           xmlId: 'account.action_move_in_invoice_type',  domain: [...base, ['move_type', '=', 'in_invoice'],  ...dateRange] },
            net_profit:  { name: 'All Posted Entries This Period',    xmlId: 'account.action_move_journal_line',     domain: [...base, ['move_type', 'in', ['out_invoice','in_invoice']], ...dateRange] },
            receivables: { name: 'Unpaid Receivables',                xmlId: 'account.action_move_out_invoice_type', domain: [...base, ['move_type', '=', 'out_invoice'], ['payment_state', 'in', ['not_paid','partial']]] },
        };

        const cfg = configs[cardType];
        if (!cfg) return;

        try {
            const actionId = await this.orm.call('ir.model.data', 'xmlid_to_res_id', [cfg.xmlId]);
            const [baseAction] = await this.orm.read('ir.actions.act_window', [actionId], ['name','res_model','view_mode','views','context','target']);
            this.action.doAction({ ...baseAction, type: 'ir.actions.act_window', name: cfg.name, domain: cfg.domain });
        } catch (_) {
            this.action.doAction({ type: 'ir.actions.act_window', name: cfg.name, res_model: 'account.move', view_mode: 'list,form', views: [[false,'list'],[false,'form']], domain: cfg.domain, target: 'current' });
        }
    }

    // ── Alert drill-down ──────────────────────────────────────────────
    openAlertView(action) {
        if (!this.state.data) return;
        const today = new Date().toISOString().split('T')[0];
        const companyIds = this.state.data.company_ids;
        const base = [['company_id', 'in', companyIds], ['state', '=', 'posted']];
        let domain, name;

        if (action === 'overdue_invoices') {
            name   = 'Overdue Invoices';
            domain = [...base, ['move_type','=','out_invoice'], ['payment_state','in',['not_paid','partial']], ['invoice_date_due','<',today]];
        } else if (action === 'bills_due_soon') {
            const weekAhead = new Date(); weekAhead.setDate(weekAhead.getDate() + 7);
            name   = 'Bills Due This Week';
            domain = [...base, ['move_type','=','in_invoice'], ['payment_state','in',['not_paid','partial']], ['invoice_date_due','>=',today], ['invoice_date_due','<=',weekAhead.toISOString().split('T')[0]]];
        } else if (action === 'long_overdue') {
            const ago = new Date(); ago.setDate(ago.getDate() - 30);
            name   = 'Receivables Over 30 Days';
            domain = [...base, ['move_type','=','out_invoice'], ['payment_state','in',['not_paid','partial']], ['invoice_date_due','<',ago.toISOString().split('T')[0]]];
        } else if (action && action.startsWith('custom_alert_')) {
            const alertId = parseInt(action.replace('custom_alert_', ''), 10);
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: 'Custom Alert',
                res_model: 'analytix.finance.alert',
                res_id: alertId,
                views: [[false, 'form']],
                target: 'current'
            });
            return;
        } else return;

        this.action.doAction({ type: 'ir.actions.act_window', name, res_model: 'account.move', view_mode: 'list,form', views: [[false,'list'],[false,'form']], domain, target: 'current' });
    }

    // ── Quick actions + report links ──────────────────────────────────
    openAction(actionName) {
        // New Invoice → open blank account.move form in out_invoice mode directly
        if (actionName === 'new_invoice') {
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: 'New Invoice',
                res_model: 'account.move',
                views: [[false, 'form']],
                target: 'current',
                context: {
                    default_move_type: 'out_invoice',
                    move_type: 'out_invoice',
                },
            });
            return;
        }

        // New Bill → open blank account.move form in in_invoice mode directly
        if (actionName === 'new_bill') {
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: 'New Bill',
                res_model: 'account.move',
                views: [[false, 'form']],
                target: 'current',
                context: {
                    default_move_type: 'in_invoice',
                    move_type: 'in_invoice',
                },
            });
            return;
        }

        // Pro-Forma Invoice → list view of sale.order.proforma
        if (actionName === 'proforma_list') {
            const companyIds = (this.state.data && this.state.data.company_ids) || [];
            const domain = [];
            if (companyIds.length) {
                domain.push(['company_id', 'in', companyIds]);
            }
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: 'Pro-Forma Invoices',
                res_model: 'sale.order.proforma',
                view_mode: 'list,form',
                views: [[false, 'list'], [false, 'form']],
                domain: domain,
                target: 'current',
            });
            return;
        }

        // P&L Statement → open in-dashboard modal
        if (actionName === 'pl_statement') {
            this.openPlStatement();
            return;
        }

        // Balance Sheet → open in-dashboard preview modal
        if (actionName === 'balance_sheet') {
            this.openBalanceSheet();
            return;
        }

        // Trial Balance → open in-dashboard preview modal
        if (actionName === 'tb_statement') {
            this.openTrialBalance();
            return;
        }

        // VAT Summary → open in-dashboard preview modal
        if (actionName === 'vat_summary') {
            this.openVatSummary();
            return;
        }

        const map = {
            new_journal:    'account.action_move_journal_line',
            record_payment: 'account.action_account_payments',
            trial_balance:  'accounting_pdf_reports.action_account_balance_menu',
        };
        const xmlId = map[actionName];
        if (!xmlId) return;
        this.action.doAction(xmlId).catch(() =>
            this.notification.add("Action not available. Make sure required modules are installed.", { type: 'danger' })
        );
    }

    // ── P&L Modal ───────────────────────────────────────────────
    async openPlStatement() {
        this.state.showPlModal    = true;
        this.state.plDateOption   = this.state.filter || 'this_month';
        this.state.plCustomFrom   = this.state.customFrom || '';
        this.state.plCustomTo     = this.state.customTo || '';
        this.state.plShowDateDrop = false;
        await this._refreshPlData();
    }

    async _refreshPlData() {
        this.state.plLoading = true;
        try {
            this.state.plData = await this.orm.call(
                'account.move', 'get_analytix_pl_data',
                [this.state.plDateOption, this.state.plCustomFrom, this.state.plCustomTo]
            );
        } catch (e) {
            this.notification.add('Failed to load P&L data.', { type: 'danger' });
            this.state.showPlModal = false;
        } finally {
            this.state.plLoading = false;
        }
    }

    closePlModal() {
        this.state.showPlModal    = false;
        this.state.plShowDateDrop = false;
    }

    getPlDateOptions() {
        const now = new Date();
        const MN  = ['January','February','March','April','May','June',
                     'July','August','September','October','November','December'];
        const q    = Math.floor(now.getMonth() / 3);
        const qSub = `${MN[q*3].slice(0,3)} - ${MN[Math.min(q*3+2,11)].slice(0,3)} ${now.getFullYear()}`;
        return [
            { key: 'this_month',    label: 'This Month',    sub: `${MN[now.getMonth()]} ${now.getFullYear()}` },
            { key: 'last_3_months', label: 'Last 3 Months', sub: qSub },
            { key: 'this_year',     label: 'This Year',     sub: String(now.getFullYear()) },
            { key: 'custom',        label: 'Custom Range',  sub: '' },
        ];
    }

    onPlDateOptClick(ev) {
        const key = ev.currentTarget.dataset.key;
        if (key) this.selectPlDateOption(key);
    }

    async selectPlDateOption(key) {
        this.state.plDateOption = key;
        if (key === 'custom') {
            return;
        }
        this.state.plShowDateDrop = false;
        await this._refreshPlData();
    }

    onPlCustomFromChange(ev) {
        this.state.plCustomFrom = ev.target.value;
    }

    onPlCustomToChange(ev) {
        this.state.plCustomTo = ev.target.value;
    }

    async applyPlCustomDate() {
        if (!this.state.plCustomFrom || !this.state.plCustomTo) {
            this.notification.add('Please select both From and To dates.', { type: 'warning' });
            return;
        }
        this.state.plDateOption   = 'custom';
        this.state.plShowDateDrop = false;
        await this._refreshPlData();
    }

    togglePlDateDrop() {
        this.state.plShowDateDrop = !this.state.plShowDateDrop;
    }

    // ── VAT Modal & Tab Filter ───────────────────────────────────────
    async openVatSummary() {
        this.state.showVatModal = true;
        this.state.vatFilterFrom = (this.state.data && this.state.data.date_range && this.state.data.date_range.start) || this.state.customFrom || '';
        this.state.vatFilterTo   = (this.state.data && this.state.data.date_range && this.state.data.date_range.end) || this.state.customTo || '';
        await this.fetchVatFilterData();
    }

    async fetchVatFilterData() {
        this.state.vatLoading = true;
        try {
            this.state.vatData = await this.orm.call(
                'account.move', 'get_analytix_vat_data',
                ['custom', this.state.vatFilterFrom, this.state.vatFilterTo]
            );
        } catch (e) {
            this.notification.add('Failed to load VAT data.', { type: 'danger' });
            this.state.showVatModal = false;
        } finally {
            this.state.vatLoading = false;
        }
    }

    onVatFilterDateChange(ev) {
        const field = ev.currentTarget.dataset.field;
        if (field === 'from') this.state.vatFilterFrom = ev.target.value;
        if (field === 'to')   this.state.vatFilterTo   = ev.target.value;
    }

    async applyVatFilter() {
        await this.fetchVatFilterData();
    }

    closeVatModal() {
        this.state.showVatModal = false;
    }

    // ── Balance Sheet Modal ─────────────────────────────────────────

    /** ISO date string for a Date object */
    _isoDate(d) {
        const p = n => String(n).padStart(2, '0');
        return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}`;
    }

    /** Returns 1 year earlier ISO date */
    _subtractYear(iso) {
        const d = new Date(iso + 'T00:00:00');
        d.setFullYear(d.getFullYear() - 1);
        return this._isoDate(d);
    }

    /** Compute the 5 date-picker options — sends ACTUAL period-end dates (backend caps the DB query) */
    getBsDateOptions() {
        const now = new Date();
        const MN  = ['January','February','March','April','May','June',
                     'July','August','September','October','November','December'];
        const iso  = d => this._isoDate(d);
        const eom  = new Date(now.getFullYear(), now.getMonth()+1, 0);
        const q    = Math.floor(now.getMonth() / 3);
        const eoq  = new Date(now.getFullYear(), (q+1)*3, 0);
        const qSub = `${MN[q*3].slice(0,3)} - ${MN[Math.min(q*3+2,11)].slice(0,3)} ${now.getFullYear()}`;
        const eoy  = new Date(now.getFullYear(), 11, 31);
        return [
            { key:'today',       label:'Today',          sub:'',                                         iso: iso(now)  },
            { key:'end_month',   label:'End of Month',   sub:`${MN[now.getMonth()]} ${now.getFullYear()}`, iso: iso(eom) },
            { key:'end_quarter', label:'End of Quarter', sub: qSub,                                      iso: iso(eoq)  },
            { key:'end_year',    label:'End of Year',    sub: String(now.getFullYear()),                  iso: iso(eoy)  },
            { key:'specific',    label:'Specific Date',  sub:'',                                          iso: null      },
        ];
    }

    async openBalanceSheet() {
        const today = this._isoDate(new Date());
        this.state.bsDateOption   = 'today';
        this.state.bsAsOfIso      = today;
        this.state.bsCompareMode  = false;
        this.state.bsCompareIso   = this._subtractYear(today);
        this.state.bsShowDateDrop = false;
        this.state.bsSpecificDate = '';
        this.state.showBsModal    = true;
        await this._refreshBsData();
    }

    async _refreshBsData() {
        this.state.bsLoading = true;
        try {
            const compareIso = this.state.bsCompareMode ? this.state.bsCompareIso : null;
            this.state.bsData = await this.orm.call(
                'account.move', 'get_analytix_balance_sheet_data',
                [this.state.bsAsOfIso, compareIso]
            );
        } catch (e) {
            this.notification.add('Failed to load Balance Sheet data.', { type: 'danger' });
        } finally {
            this.state.bsLoading = false;
        }
    }

    /** Reads data-key from the clicked option element — avoids OWL arrow-fn 'this' issue */
    onBsDateOptClick(ev) {
        const key = ev.currentTarget.dataset.key;
        if (key) this.selectBsDateOption(key);
    }

    async selectBsDateOption(key) {
        this.state.bsDateOption = key;
        if (key === 'specific') return; // keep dropdown open for input
        const opt = this.getBsDateOptions().find(o => o.key === key);
        if (opt && opt.iso) {
            this.state.bsAsOfIso      = opt.iso;
            this.state.bsCompareIso   = this._subtractYear(opt.iso);
            this.state.bsShowDateDrop = false;
            await this._refreshBsData();
        }
    }

    async applyBsSpecificDate(ev) {
        const val = ev.target.value;
        if (!val) return;
        const today = this._isoDate(new Date());
        this.state.bsAsOfIso      = val > today ? today : val;
        this.state.bsCompareIso   = this._subtractYear(this.state.bsAsOfIso);
        this.state.bsShowDateDrop = false;
        await this._refreshBsData();
    }

    async toggleBsComparison() {
        this.state.bsCompareMode = !this.state.bsCompareMode;
        await this._refreshBsData();
    }

    toggleBsDateDrop() {
        this.state.bsShowDateDrop = !this.state.bsShowDateDrop;
    }

    closeBsModal() {
        this.state.showBsModal    = false;
        this.state.bsShowDateDrop = false;
    }

    /** Format a BS value with currency symbol */
    formatBsVal(val) {
        const sym = (this.state.bsData && this.state.bsData.currency_sym) || '';
        const abs = Math.abs(Number(val));
        const fmt = abs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        return `${sym} ${fmt}`;
    }

    /** Get the comparison value for a key from bsData.compare */
    bsCmp(key) {
        const c = this.state.bsData && this.state.bsData.compare;
        if (!c) return 0;
        return (typeof c[key] === 'object' && c[key] !== null) ? c[key].total : (c[key] || 0);
    }

    printBsReport() {
        if (!this.state.bsData) return;
        const d = this.state.bsData;
        const sym = d.currency_sym;
        const hasCmp = this.state.bsCompareMode && d.compare;
        const fmtN = v => {
            const neg = Number(v) < 0;
            const s = Math.abs(Number(v)).toLocaleString(undefined, { minimumFractionDigits:2, maximumFractionDigits:2 });
            return neg ? `<span style="color:#e53935">-${sym} ${s}</span>` : `${sym} ${s}`;
        };
        const cols = hasCmp ? 3 : 2;
        const hdr = hasCmp
            ? `<tr><th style="text-align:left;padding:8px 14px;background:#f0f1f5;"></th><th style="text-align:right;padding:8px 14px;background:#f0f1f5;">${d.as_of_date}</th><th style="text-align:right;padding:8px 14px;background:#f0f1f5;">${d.compare_date}</th></tr>`
            : `<tr><th style="text-align:left;padding:8px 14px;background:#f0f1f5;"></th><th style="text-align:right;padding:8px 14px;background:#f0f1f5;">${d.as_of_date}</th></tr>`;
        const row = (label, val, cval, isGroup) => {
            const bg = isGroup ? 'background:#f0f2f6;font-weight:700;' : 'background:#fff;';
            let r = `<tr><td style="${bg}padding:9px 14px;border-bottom:1px solid #f0f1f5;">${label}</td>`;
            r += `<td style="${bg}padding:9px 14px;text-align:right;white-space:nowrap;border-bottom:1px solid #f0f1f5;">${val !== '' ? fmtN(val) : ''}</td>`;
            if (hasCmp) r += `<td style="${bg}padding:9px 14px;text-align:right;white-space:nowrap;border-bottom:1px solid #f0f1f5;">${cval !== '' ? fmtN(cval) : ''}</td>`;
            return r + '</tr>';
        };
        const totRow = (label, val, cval) => {
            let r = `<tr><td style="background:#0f1729;color:#fff;font-weight:800;padding:13px 14px;">${label}</td>`;
            r += `<td style="background:#0f1729;color:#fff;font-weight:800;padding:13px 14px;text-align:right;white-space:nowrap;">${fmtN(val)}</td>`;
            if (hasCmp) r += `<td style="background:#0f2040;color:#fff;font-weight:800;padding:13px 14px;text-align:right;white-space:nowrap;">${fmtN(cval)}</td>`;
            return r + '</tr>';
        };
        const ac = (accs, caccs) => (accs||[]).map((a,i) => {
            const cv = (hasCmp && caccs && caccs[i]) ? caccs[i].balance : '';
            return row(`&nbsp;&nbsp;&nbsp;${a.name}`, a.balance, cv, false);
        }).join('');
        const c = d.compare || {};
        const html = `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Balance Sheet</title>`
            + `<style>body{font-family:Inter,sans-serif;padding:32px;}table{width:100%;border-collapse:collapse;}@media print{button{display:none}}</style></head><body>`
            + `<h2 style="margin:0 0 4px">Balance Sheet</h2><p style="color:#8a93a4;margin:0 0 20px">${d.company}</p>`
            + `<table>${hdr}`
            + row('Assets','','',true) + row('Current Assets','','',true)
            + row('Bank and Cash', d.bank_cash.total, c.bank_cash&&c.bank_cash.total||0, false)
            + ac(d.bank_cash.accounts, c.bank_cash&&c.bank_cash.accounts)
            + row('Accounts Receivable', d.receivable.total, c.receivable&&c.receivable.total||0, false)
            + ac(d.receivable.accounts, c.receivable&&c.receivable.accounts)
            + row('Other Current Assets', d.current_assets.total, c.current_assets&&c.current_assets.total||0, false)
            + ac(d.current_assets.accounts, c.current_assets&&c.current_assets.accounts)
            + row('Total Current Assets', d.total_current_assets, c.total_current_assets||0, true)
            + row('Fixed Assets', d.fixed_assets.total, c.fixed_assets&&c.fixed_assets.total||0, false)
            + row('Other Assets', d.other_assets.total, c.other_assets&&c.other_assets.total||0, false)
            + totRow('Total Assets', d.total_assets, c.total_assets||0)
            + row('Liabilities &amp; Equity','','',true) + row('Current Liabilities','','',true)
            + row('Accounts Payable', d.payable.total, c.payable&&c.payable.total||0, false)
            + row('Credit Cards', d.credit_cards.total, c.credit_cards&&c.credit_cards.total||0, false)
            + row('Other Current Liabilities', d.current_liabilities.total, c.current_liabilities&&c.current_liabilities.total||0, false)
            + row('Total Current Liabilities', d.total_current_liabilities, c.total_current_liabilities||0, true)
            + row('Long-term Liabilities', d.noncurrent_liabilities.total, c.noncurrent_liabilities&&c.noncurrent_liabilities.total||0, false)
            + totRow('Total Liabilities', d.total_liabilities, c.total_liabilities||0)
            + row('Equity','','',true)
            + row('Equity Accounts', d.equity.total, c.equity&&c.equity.total||0, false)
            + row('Current Year Earnings', d.current_year_earnings, c.current_year_earnings||0, false)
            + row('Previous Year Earnings', d.prev_year_earnings, c.prev_year_earnings||0, false)
            + row('Total Equity', d.total_equity, c.total_equity||0, true)
            + totRow('Total Liabilities &amp; Equity', d.total_liabilities_equity, c.total_liabilities_equity||0)
            + `</table></body></html>`;
        const win = window.open('', '_blank', 'width=960,height=720');
        win.document.write(html);
        win.document.close();
        setTimeout(() => win.print(), 400);
    }


    // ── Print P&L Report ─────────────────────────────────────────────
    printPlReport() {
        if (!this.state.plData) return;
        const d   = this.state.plData;
        const sym = d.currency_sym || '';

        const fmtN = v => {
            const neg = Number(v) < 0;
            const s   = Math.abs(Number(v)).toLocaleString(undefined, {
                minimumFractionDigits: 2, maximumFractionDigits: 2
            });
            return neg
                ? `<span style="color:#e53935">-${sym} ${s}</span>`
                : `${sym} ${s}`;
        };

        const secRow = label => `
            <tr>
              <td colspan="2" style="background:#f0f2f6;font-weight:700;padding:10px 14px;
                  border-top:2px solid #d0d5df;">${label}</td>
            </tr>`;

        const accRows = (accounts=[]) => accounts.map(acc => `
            <tr>
              <td style="padding:8px 14px 8px 28px;border-bottom:1px solid #f0f1f5;color:#374151;">
                  ${acc.name}</td>
              <td style="padding:8px 14px;text-align:right;white-space:nowrap;
                  border-bottom:1px solid #f0f1f5;">${fmtN(acc.balance)}</td>
            </tr>`).join('');

        const subRow = (label, val) => `
            <tr style="background:#e8f0fd;">
              <td style="padding:10px 14px;font-weight:600;color:#1a3a6e;">${label}</td>
              <td style="padding:10px 14px;text-align:right;font-weight:600;white-space:nowrap;
                  color:#1a3a6e;">${fmtN(val)}</td>
            </tr>`;

        const totRow = (label, val) => `
            <tr>
              <td style="background:#0f1729;color:#fff;font-weight:800;padding:13px 14px;">${label}</td>
              <td style="background:#0f1729;color:#fff;font-weight:800;padding:13px 14px;
                  text-align:right;white-space:nowrap;">${fmtN(val)}</td>
            </tr>`;

        const html = `<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Profit &amp; Loss — ${d.company}</title>
<style>
  body { font-family: Inter, Arial, sans-serif; padding: 32px; color: #1f2937; }
  h2   { margin: 0 0 4px; font-size: 22px; }
  p.sub{ color: #8a93a4; margin: 0 0 24px; font-size: 13px; }
  table{ width: 100%; border-collapse: collapse; font-size: 13.5px; }
  @media print { button { display:none } }
</style></head><body>
<h2>Profit &amp; Loss Statement</h2>
<p class="sub">${d.company} &mdash; ${d.period_label}</p>
<table>
  <thead>
    <tr>
      <th style="text-align:left;padding:8px 14px;background:#f0f1f5;border-bottom:2px solid #d0d5df;"></th>
      <th style="text-align:right;padding:8px 14px;background:#f0f1f5;border-bottom:2px solid #d0d5df;">${d.year}</th>
    </tr>
  </thead>
  <tbody>
    ${secRow('Income')}
    ${accRows(d.income && d.income.accounts)}
    <tr style="background:#f9fafb;font-weight:600;">
      <td style="padding:8px 14px 8px 14px;border-bottom:1px solid #d0d5df;">Total Income</td>
      <td style="padding:8px 14px;text-align:right;white-space:nowrap;border-bottom:1px solid #d0d5df;">${fmtN(d.income && d.income.total || 0)}</td>
    </tr>

    ${secRow('Cost of Sales')}
    ${accRows(d.cogs && d.cogs.accounts)}
    <tr style="background:#f9fafb;font-weight:600;">
      <td style="padding:8px 14px;border-bottom:1px solid #d0d5df;">Total Cost of Sales</td>
      <td style="padding:8px 14px;text-align:right;white-space:nowrap;border-bottom:1px solid #d0d5df;">${fmtN(d.cogs && d.cogs.total || 0)}</td>
    </tr>

    ${subRow('Gross Profit', d.gross_profit || 0)}
    <tr><td colspan="2" style="padding:6px;"></td></tr>

    ${secRow('Expense')}
    ${accRows(d.expense && d.expense.accounts)}
    <tr style="background:#f9fafb;font-weight:600;">
      <td style="padding:8px 14px;border-bottom:1px solid #d0d5df;">Total Expense</td>
      <td style="padding:8px 14px;text-align:right;white-space:nowrap;border-bottom:1px solid #d0d5df;">${fmtN(d.expense && d.expense.total || 0)}</td>
    </tr>

    ${subRow('Net Operating Income', d.net_operating_income || 0)}
    <tr><td colspan="2" style="padding:6px;"></td></tr>

    ${secRow('Other Income')}
    ${accRows(d.other_income && d.other_income.accounts)}
    <tr style="background:#f9fafb;font-weight:600;">
      <td style="padding:8px 14px;border-bottom:1px solid #d0d5df;">Total Other Income</td>
      <td style="padding:8px 14px;text-align:right;white-space:nowrap;border-bottom:1px solid #d0d5df;">${fmtN(d.other_income && d.other_income.total || 0)}</td>
    </tr>

    ${subRow('Net Other Income', d.net_other_income || 0)}
    <tr><td colspan="2" style="padding:6px;"></td></tr>

    ${totRow('Net Profit / (Loss)', d.net_profit || 0)}
  </tbody>
</table>
</body></html>`;

        const win = window.open('', '_blank', 'width=800,height=720');
        win.document.write(html);
        win.document.close();
        setTimeout(() => win.print(), 400);
    }

    // Format a P&L value → e.g. "$ 52,421.51" or "-$ 31,447.40"
    formatPlVal(val) {
        const sym = (this.state.plData && this.state.plData.currency_sym) || '';
        const abs = Math.abs(Number(val));
        const fmt = abs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        return (Number(val) < 0 ? '-' : '') + sym + ' ' + fmt;
    }

    // ── Trial Balance Modal ─────────────────────────────────────────
    async openTrialBalance() {
        this.state.showTbModal    = true;
        this.state.tbModalLoading = true;
        try {
            this.state.tbModalData = await this.orm.call(
                'account.move', 'get_analytix_trial_balance_data',
                [this.state.filter, this.state.customFrom, this.state.customTo]
            );
        } catch (e) {
            this.notification.add('Failed to load Trial Balance data.', { type: 'danger' });
            this.state.showTbModal = false;
        } finally {
            this.state.tbModalLoading = false;
        }
    }

    closeTbModal() {
        this.state.showTbModal = false;
    }

    // ══════════════════════════════════════════════════════════
    //  DOCUMENT UPLOAD — handlers
    // ══════════════════════════════════════════════════════════

    /** Click the hidden file input when the dropzone is clicked */
    triggerFileInput(ev) {
        // Avoid triggering when clicking the input itself
        if (ev.target && ev.target.id === 'anx-file-input') return;
        const input = document.getElementById('anx-file-input');
        if (input) input.click();
    }

    onUploadDragOver(ev) {
        ev.preventDefault();
        this.state.uploadDragOver = true;
    }

    onUploadDragLeave(ev) {
        this.state.uploadDragOver = false;
    }

    onUploadDrop(ev) {
        ev.preventDefault();
        this.state.uploadDragOver = false;
        const file = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0];
        if (file) this._processFile(file);
    }

    onFileSelected(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (file) this._processFile(file);
        // Reset so same file can be selected again
        ev.target.value = '';
    }

    /** Read the file, store metadata, and attempt text extraction */
    _processFile(file) {
        const allowed = ['application/pdf', 'image/png', 'image/jpeg', 'image/gif', 'image/bmp', 'image/tiff'];
        if (!allowed.includes(file.type) && !file.name.match(/\.(pdf|png|jpe?g|gif|bmp|tiff?)$/i)) {
            this.notification.add('Unsupported file type. Please upload a PDF or image.', { type: 'warning' });
            return;
        }

        const reader = new FileReader();
        reader.onload = (e) => {
            this.state.uploadFile = {
                name:    file.name,
                size:    file.size,
                type:    file.type,
                dataUrl: e.target.result,
            };
            // Auto-detect type from filename
            const nameLC = file.name.toLowerCase();
            if (nameLC.includes('bill') || nameLC.includes('vendor') || nameLC.includes('purchase')) {
                this.state.uploadDocType = 'bill';
            } else if (nameLC.includes('invoice') || nameLC.includes('inv') || nameLC.includes('customer')) {
                this.state.uploadDocType = 'invoice';
            } else {
                this.state.uploadDocType = '';
            }
            // Extract basic info from filename patterns
            this._extractFromFilename(file.name);
        };
        reader.readAsDataURL(file);
    }

    /**
     * Lightweight extraction from filename.
     * Format hints:  INV-2024-001_CustomerName.pdf
     *                BILL_VendorName_2024-07-10.pdf
     * For real OCR, the backend Python method is called after upload.
     */
    _extractFromFilename(name) {
        const today = new Date().toISOString().split('T')[0];
        // Reset extracted
        this.state.uploadExtracted = {
            partner: '', ref: '', date: today, due_date: '', amount: '', currency: '', narration: '',
        };

        // Ref: any sequence like INV-xxxx or BILL-xxxx
        const refMatch = name.match(/(?:INV|BILL|REC|PO|SO|SI)[-_]?[\w\d-]+/i);
        if (refMatch) this.state.uploadExtracted.ref = refMatch[0].replace(/\.(pdf|png|jpe?g|gif|bmp|tiff?)$/i, '');

        // Date: YYYY-MM-DD pattern
        const dateMatch = name.match(/(\d{4}[-_]\d{2}[-_]\d{2})/);
        if (dateMatch) {
            this.state.uploadExtracted.date = dateMatch[1].replace(/_/g, '-');
        }

        // Amount: pattern like 1500, 1500.00, 1,500
        const amtMatch = name.match(/(\d[\d,]*\.?\d*)/);
        if (amtMatch) {
            const val = parseFloat(amtMatch[1].replace(/,/g, ''));
            if (val > 0) this.state.uploadExtracted.amount = val.toString();
        }

        // Remove extension + known prefixes to guess partner
        let partnerGuess = name
            .replace(/\.(pdf|png|jpe?g|gif|bmp|tiff?)$/i, '')
            .replace(/(?:INV|BILL|REC|PO|SO|SI)[-_]?[\w\d-]*/i, '')
            .replace(/\d{4}[-_]\d{2}[-_]\d{2}/g, '')
            .replace(/[-_]+/g, ' ')
            .trim();
        if (partnerGuess.length > 2) {
            this.state.uploadExtracted.partner = partnerGuess
                .split(' ')
                .map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
                .join(' ')
                .trim();
        }
    }

    /** User clicked Invoice or Bill — set type and immediately create the record */
    async setUploadDocType(ev) {
        const dtype = ev.currentTarget.dataset.dtype || '';
        if (!dtype || this.state.uploadSubmitting) return;
        this.state.uploadDocType = dtype;
        // Auto-create immediately — no form review needed
        await this.submitUploadedDocument();
    }

    clearUpload() {
        this.state.uploadFile       = null;
        this.state.uploadDragOver   = false;
        this.state.uploadDocType    = '';
        this.state.uploadSubmitting  = false;
        this.state.uploadExtracted  = { partner: '', ref: '', date: '', due_date: '', amount: '', currency: '', narration: '' };
    }

    /** Format bytes to human-readable size */
    formatFileSize(bytes) {
        if (bytes >= 1_048_576) return (bytes / 1_048_576).toFixed(1) + ' MB';
        if (bytes >= 1024)      return (bytes / 1024).toFixed(0) + ' KB';
        return bytes + ' B';
    }

    /**
     * Create the invoice or bill in Odoo using the extracted details,
     * attach the uploaded file as an attachment, and open the record form.
     */
    async submitUploadedDocument() {
        if (!this.state.uploadDocType) {
            this.notification.add('Please select Invoice or Bill before creating.', { type: 'warning' });
            return;
        }
        if (!this.state.uploadFile) {
            this.notification.add('No file selected.', { type: 'warning' });
            return;
        }

        this.state.uploadSubmitting = true;
        try {
            const ext = this.state.uploadExtracted;
            const moveType = this.state.uploadDocType === 'invoice' ? 'out_invoice' : 'in_invoice';

            // ── 1. Resolve or create the partner ───────────────────────
            let partnerId = false;
            if (ext.partner && ext.partner.trim()) {
                const partners = await this.orm.searchRead(
                    'res.partner',
                    [['name', 'ilike', ext.partner.trim()]],
                    ['id', 'name'],
                    { limit: 1 }
                );
                if (partners.length) {
                    partnerId = partners[0].id;
                } else {
                    // Create a new partner — orm.create returns [id] in Odoo 19
                    const partnerResult = await this.orm.create('res.partner', [{
                        name: ext.partner.trim(),
                        company_type: moveType === 'in_invoice' ? 'company' : 'person',
                    }]);
                    partnerId = Array.isArray(partnerResult) ? partnerResult[0] : partnerResult;
                }
            }

            // ── 2. Build move values ────────────────────────────────────
            const moveVals = {
                move_type:    moveType,
                ref:          ext.ref   || false,
                narration:    ext.narration || false,
            };
            if (partnerId) moveVals.partner_id = partnerId;
            if (ext.date)     moveVals.invoice_date      = ext.date;
            if (ext.due_date) moveVals.invoice_date_due  = ext.due_date;

            // Add a single line if amount is given
            if (parseFloat(ext.amount) > 0) {
                const lineVals = {
                    name: ext.narration || (this.state.uploadDocType === 'invoice' ? 'Invoice line' : 'Bill line'),
                    quantity: 1,
                    price_unit: parseFloat(ext.amount),
                };
                moveVals.invoice_line_ids = [[0, 0, lineVals]];
            }

            // ── 3. Create the move ──────────────────────────────────────
            // orm.create() in Odoo 19 returns [id] (a list) — extract the integer
            const moveResult = await this.orm.create('account.move', [moveVals]);
            const moveId = Array.isArray(moveResult) ? moveResult[0] : moveResult;

            // ── 4. Attach the uploaded file ────────────────────────────
            if (this.state.uploadFile.dataUrl) {
                const base64Data = this.state.uploadFile.dataUrl.split(',')[1];
                await this.orm.create('ir.attachment', [{
                    name:      this.state.uploadFile.name,
                    res_model: 'account.move',
                    res_id:    moveId,          // guaranteed integer now
                    datas:     base64Data,
                    mimetype:  this.state.uploadFile.type || 'application/octet-stream',
                    type:      'binary',
                }]);
            }

            // ── 5. Show success and open the form ──────────────────────
            const label = this.state.uploadDocType === 'invoice' ? 'Invoice' : 'Bill';
            this.notification.add(
                `${label} created successfully! Opening form…`,
                { type: 'success', sticky: false }
            );
            this.clearUpload();

            // Open the newly created record
            this.action.doAction({
                type:       'ir.actions.act_window',
                res_model:  'account.move',
                res_id:     moveId,             // guaranteed integer now
                views:      [[false, 'form']],
                target:     'current',
            });


        } catch (e) {
            console.error('Upload submit error:', e);
            this.notification.add(
                'Failed to create record. ' + (e.message || ''),
                { type: 'danger', sticky: true }
            );
        } finally {
            this.state.uploadSubmitting = false;
        }
    }


    // ══════════════════════════════════════════════════════════
    //  DOCUMENTS TAB — handlers
    // ══════════════════════════════════════════════════════════

    async fetchDocumentData() {
        this.state.docLoading = true;
        try {
            this.state.docList = await this.orm.call(
                'analytix.document', 'get_analytix_documents_list', []
            );
        } catch (e) {
            this.notification.add('Failed to load documents.', { type: 'danger' });
        } finally {
            this.state.docLoading = false;
        }
    }

    get filteredDocuments() {
        if (!this.state.docList) return [];
        let rows = this.state.docList.records;
        if (this.state.docSearch.trim()) {
            const q = this.state.docSearch.trim().toLowerCase();
            rows = rows.filter(r =>
                r.name.toLowerCase().includes(q) ||
                (r.description || '').toLowerCase().includes(q) ||
                (r.file_name || '').toLowerCase().includes(q) ||
                (r.mimetype || '').toLowerCase().includes(q)
            );
        }
        return rows;
    }

    onDocSearch(ev) {
        this.state.docSearch = ev.target.value;
    }

    // ── Drag-and-drop ─────────────────────────────────────────
    onDocDragOver(ev) {
        ev.preventDefault();
        this.state.docDragOver = true;
    }
    onDocDragLeave(ev) {
        this.state.docDragOver = false;
    }
    onDocDrop(ev) {
        ev.preventDefault();
        this.state.docDragOver = false;
        const file = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0];
        if (file) this._processDocFile(file);
    }

    triggerDocFileInput(ev) {
        if (ev.target && ev.target.id === 'anx-doc-file-input') return;
        const input = document.getElementById('anx-doc-file-input');
        if (input) input.click();
    }

    onDocFileSelected(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (file) this._processDocFile(file);
        ev.target.value = '';
    }

    _processDocFile(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            this.state.docUploadFile = {
                name:    file.name,
                size:    file.size,
                type:    file.type || 'application/octet-stream',
                dataUrl: e.target.result,
            };
            this.state.docDocName     = file.name.replace(/\.[^/.]+$/, '') || file.name;
            this.state.docDescription = '';
            this.state.docDescError   = false;
            this.state.docType        = '';
            this.state.docTypeError   = false;
        };
        reader.readAsDataURL(file);
    }

    onDocNameInput(ev) {
        this.state.docDocName = ev.target.value;
    }

    onDocDescInput(ev) {
        this.state.docDescription = ev.target.value;
        if (ev.target.value.trim()) this.state.docDescError = false;
    }

    onDocTypeSelect(ev) {
        const dtype = ev.currentTarget.dataset.dtype || '';
        this.state.docType      = dtype;
        this.state.docTypeError = false;
    }

    clearDocUpload() {
        this.state.docUploadFile  = null;
        this.state.docDragOver    = false;
        this.state.docUploading   = false;
        this.state.docDocName     = '';
        this.state.docDescription = '';
        this.state.docDescError   = false;
        this.state.docType        = '';
        this.state.docTypeError   = false;
    }

    async submitDocUpload() {
        if (!this.state.docUploadFile || this.state.docUploading) return;
        // Validate required fields
        let hasError = false;
        if (!this.state.docDescription.trim()) {
            this.state.docDescError = true;
            hasError = true;
        }
        if (!this.state.docType) {
            this.state.docTypeError = true;
            hasError = true;
        }
        if (hasError) {
            if (!this.state.docDescription.trim()) {
                const inp = document.getElementById('anx-doc-desc-input');
                if (inp) inp.focus();
            }
            return;
        }
        this.state.docUploading = true;
        try {
            const f = this.state.docUploadFile;
            const docName = this.state.docDocName.trim() || f.name;
            const base64Data = f.dataUrl.split(',')[1];
            await this.orm.call(
                'analytix.document',
                'save_analytix_document',
                [docName, f.name, base64Data, f.type || 'application/octet-stream',
                 f.size, this.state.docDescription.trim(), this.state.docType]
            );
            this.notification.add('Document saved successfully!', { type: 'success', sticky: false });
            this.clearDocUpload();
            await this.fetchDocumentData();
        } catch (e) {
            this.notification.add('Failed to save document. ' + (e.message || ''), { type: 'danger' });
        } finally {
            this.state.docUploading = false;
        }
    }

    // ── Inline description edit ─────────────────────────────
    startEditDesc(ev) {
        const id   = parseInt(ev.currentTarget.dataset.id, 10);
        const desc = ev.currentTarget.dataset.desc || '';
        this.state.docEditId   = id;
        this.state.docEditDesc = desc;
        // Focus the input after OWL re-renders
        setTimeout(() => {
            const inp = document.getElementById('anx-desc-edit-' + id);
            if (inp) { inp.focus(); inp.select(); }
        }, 50);
    }

    onDescEditInput(ev) {
        this.state.docEditDesc = ev.target.value;
    }

    onDescEditKeydown(ev) {
        if (ev.key === 'Enter') {
            const btn = ev.currentTarget.closest('.anx-doc-desc-edit-wrap')
                           ?.querySelector('.anx-doc-desc-save-btn');
            if (btn) btn.click();
        }
        if (ev.key === 'Escape') {
            this.cancelDescEdit();
        }
    }

    async saveDescEdit(ev) {
        const docId = parseInt(ev.currentTarget.dataset.id, 10);
        if (!docId) return;
        const newDesc = this.state.docEditDesc.trim();
        try {
            await this.orm.call(
                'analytix.document', 'update_analytix_document',
                [docId, { description: newDesc }]
            );
            // Update locally without full reload
            if (this.state.docList) {
                const rec = this.state.docList.records.find(r => r.id === docId);
                if (rec) rec.description = newDesc;
            }
            this.state.docEditId   = null;
            this.state.docEditDesc = '';
            this.notification.add('Description updated.', { type: 'success', sticky: false });
        } catch (e) {
            this.notification.add('Failed to update description. ' + (e.message || ''), { type: 'danger' });
        }
    }

    cancelDescEdit() {
        this.state.docEditId   = null;
        this.state.docEditDesc = '';
    }

    // ── Inline review edit (backend users only) ────────────
    startEditReview(ev) {
        const id     = parseInt(ev.currentTarget.dataset.id, 10);
        const review = ev.currentTarget.dataset.review || '';
        this.state.docReviewEditId  = id;
        this.state.docReviewEditVal = review;
        setTimeout(() => {
            const ta = document.getElementById('anx-review-edit-' + id);
            if (ta) { ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length); }
        }, 50);
    }

    onReviewEditInput(ev) {
        this.state.docReviewEditVal = ev.target.value;
    }

    onReviewEditKeydown(ev) {
        // Ctrl+Enter or Cmd+Enter to save; Escape to cancel
        if ((ev.ctrlKey || ev.metaKey) && ev.key === 'Enter') {
            const btn = ev.currentTarget.closest('.anx-doc-review-edit-wrap')
                           ?.querySelector('.anx-doc-desc-save-btn');
            if (btn) btn.click();
        }
        if (ev.key === 'Escape') this.cancelReviewEdit();
    }

    async saveReviewEdit(ev) {
        const docId = parseInt(ev.currentTarget.dataset.id, 10);
        if (!docId) return;
        const newReview = this.state.docReviewEditVal;
        try {
            await this.orm.call(
                'analytix.document', 'update_analytix_document',
                [docId, { review: newReview }]
            );
            // Update locally without full reload
            if (this.state.docList) {
                const rec = this.state.docList.records.find(r => r.id === docId);
                if (rec) rec.review = newReview;
            }
            this.state.docReviewEditId  = null;
            this.state.docReviewEditVal = '';
            this.notification.add('Review saved.', { type: 'success', sticky: false });
        } catch (e) {
            this.notification.add('Failed to save review. ' + (e.message || ''), { type: 'danger' });
        }
    }

    cancelReviewEdit() {
        this.state.docReviewEditId  = null;
        this.state.docReviewEditVal = '';
    }

    isImagePreview(type) {
        return type && type.startsWith('image/');
    }

    isPdfPreview(type) {
        return type === 'application/pdf';
    }

    async previewDocument(ev) {
        const docId = parseInt(ev.currentTarget.dataset.id, 10);
        if (!docId) return;
        try {
            const result = await this.orm.call(
                'analytix.document', 'get_analytix_document_data', [docId]
            );
            if (!result || !result.file_data) {
                this.notification.add('File data not available.', { type: 'warning' });
                return;
            }

            // Clean up any existing object URL
            if (this.state.previewDocUrl) {
                URL.revokeObjectURL(this.state.previewDocUrl);
            }

            const binary = atob(result.file_data);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
            const blob = new Blob([bytes], { type: result.mimetype || 'application/octet-stream' });
            const url = URL.createObjectURL(blob);

            this.state.showDocPreview = true;
            this.state.previewDocId = docId;
            this.state.previewDocName = result.file_name || 'document';
            this.state.previewDocType = result.mimetype || 'application/octet-stream';
            this.state.previewDocUrl = url;
        } catch (e) {
            this.notification.add('Failed to load preview. ' + (e.message || ''), { type: 'danger' });
        }
    }

    closeDocPreview() {
        if (this.state.previewDocUrl) {
            URL.revokeObjectURL(this.state.previewDocUrl);
        }
        this.state.showDocPreview = false;
        this.state.previewDocId = null;
        this.state.previewDocName = '';
        this.state.previewDocType = '';
        this.state.previewDocUrl = '';
    }

    downloadDocFromPreview() {
        if (!this.state.previewDocUrl) return;
        const a = document.createElement('a');
        a.href = this.state.previewDocUrl;
        a.download = this.state.previewDocName;
        document.body.appendChild(a);
        a.click();
        a.remove();
    }

    async downloadDocument(ev) {
        const docId = parseInt(ev.currentTarget.dataset.id, 10);
        const fileName = ev.currentTarget.dataset.name || 'document';
        if (!docId) return;
        try {
            const result = await this.orm.call(
                'analytix.document', 'get_analytix_document_data', [docId]
            );
            if (!result || !result.file_data) {
                this.notification.add('File data not available.', { type: 'warning' });
                return;
            }
            // Convert base64 → Blob → object URL → anchor download
            const binary = atob(result.file_data);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
            const blob = new Blob([bytes], { type: result.mimetype || 'application/octet-stream' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = result.file_name || fileName;
            document.body.appendChild(a);
            a.click();
            setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 1000);
        } catch (e) {
            this.notification.add('Download failed. ' + (e.message || ''), { type: 'danger' });
        }
    }

    async deleteDocument(ev) {
        const docId = parseInt(ev.currentTarget.dataset.id, 10);
        if (!docId) return;
        if (!confirm('Are you sure you want to delete this document? This cannot be undone.')) return;
        try {
            await this.orm.call('analytix.document', 'delete_analytix_document', [docId]);
            this.notification.add('Document deleted.', { type: 'success', sticky: false });
            await this.fetchDocumentData();
        } catch (e) {
            this.notification.add('Failed to delete document. ' + (e.message || ''), { type: 'danger' });
        }
    }

    async approveDocument(ev) {
        const docId = parseInt(ev.currentTarget.dataset.id, 10);
        if (!docId) return;
        try {
            const success = await this.orm.call('analytix.document', 'approve_analytix_document', [docId]);
            if (success) {
                this.notification.add('Document approved successfully!', { type: 'success', sticky: false });
                await this.fetchDocumentData();
            }
        } catch (e) {
            this.notification.add('Failed to approve document. ' + (e.message || ''), { type: 'danger' });
        }
    }

    async rejectDocument(ev) {
        const docId = parseInt(ev.currentTarget.dataset.id, 10);
        if (!docId) return;
        try {
            const success = await this.orm.call('analytix.document', 'reject_analytix_document', [docId]);
            if (success) {
                this.notification.add('Document rejected.', { type: 'warning', sticky: false });
                await this.fetchDocumentData();
            }
        } catch (e) {
            this.notification.add('Failed to reject document. ' + (e.message || ''), { type: 'danger' });
        }
    }

    async analyzeAndCreateDocument(ev) {
        const docId = parseInt(ev.currentTarget.dataset.id, 10);
        if (!docId || this.state.analyzingDocId) return;
        
        this.state.analyzingDocId = docId;
        this.notification.add("Processing document with AI...", { type: "info", sticky: false });
        
        try {
            const action = await this.orm.call(
                'analytix.document',
                'action_analyze_and_create_entry',
                [docId]
            );
            
            this.notification.add("AI entry created successfully!", { type: "success", sticky: false });
            
            // Reload the list to update button state
            await this.fetchDocumentData();
            
            // Open the created move record
            if (action) {
                this.action.doAction(action);
            }
        } catch (e) {
            console.error("AI Analysis error:", e);
            let errorMsg = "";
            if (e && e.data && e.data.message) {
                errorMsg = e.data.message;
            } else if (e && e.data && e.data.arguments && e.data.arguments[0]) {
                errorMsg = e.data.arguments[0];
            } else if (e && e.message) {
                errorMsg = e.message;
            } else {
                errorMsg = String(e) || "Odoo Server Error";
            }
            this.notification.add(
                "Failed to process document with AI: " + errorMsg,
                { type: "danger", sticky: true }
            );
        } finally {
            this.state.analyzingDocId = null;
        }
    }

    openCreatedMove(ev) {
        const moveId = parseInt(ev.currentTarget.dataset.moveId, 10);
        if (!moveId) return;
        this.action.doAction({
            type:       'ir.actions.act_window',
            res_model:  'account.move',
            res_id:     moveId,
            views:      [[false, 'form']],
            target:     'current',
        });
    }


    // ── File icon helpers ──────────────────────────────────────
    docFileIcon(mimetype) {
        if (!mimetype) return 'fa-file-o';
        if (mimetype.includes('pdf'))   return 'fa-file-pdf-o';
        if (mimetype.includes('image')) return 'fa-file-image-o';
        if (mimetype.includes('sheet') || mimetype.includes('excel') || mimetype.includes('csv')) return 'fa-file-excel-o';
        if (mimetype.includes('word') || mimetype.includes('document')) return 'fa-file-word-o';
        if (mimetype.includes('text')) return 'fa-file-text-o';
        return 'fa-file-o';
    }

    docFileIconByName(fileName) {
        if (!fileName) return 'fa-file-o';
        const ext = (fileName.split('.').pop() || '').toLowerCase();
        const MAP = {
            pdf: 'fa-file-pdf-o',
            png: 'fa-file-image-o', jpg: 'fa-file-image-o', jpeg: 'fa-file-image-o',
            gif: 'fa-file-image-o', bmp: 'fa-file-image-o', tiff: 'fa-file-image-o', tif: 'fa-file-image-o',
            xls: 'fa-file-excel-o', xlsx: 'fa-file-excel-o', csv: 'fa-file-excel-o',
            doc: 'fa-file-word-o', docx: 'fa-file-word-o',
            txt: 'fa-file-text-o',
        };
        return MAP[ext] || 'fa-file-o';
    }

    docExtLabel(fileName) {
        if (!fileName) return 'FILE';
        return (fileName.split('.').pop() || 'FILE').toUpperCase();
    }

    printTbReport() {

        // Support both tab view (tbData) and modal (tbModalData)
        const d = this.state.tbModalData || this.state.tbData;
        if (!d) return;
        const sym = d.currency_sym || '';
        const fmtN = v => {
            const neg = Number(v) < 0;
            const s = Math.abs(Number(v)).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            return neg ? `<span style="color:#e53935">-${sym} ${s}</span>` : `${sym} ${s}`;
        };

        const rows = (d.records || []).map(r => `
            <tr>
                <td style="padding:8px 14px;border-bottom:1px solid #f0f1f5;font-family:monospace;text-align:left;">${r.code}</td>
                <td style="padding:8px 14px;border-bottom:1px solid #f0f1f5;text-align:left;font-weight:600;color:#1e88e5;">${r.name}</td>
                <td style="padding:8px 14px;border-bottom:1px solid #f0f1f5;text-align:right;">${fmtN(r.initial_balance)}</td>
                <td style="padding:8px 14px;border-bottom:1px solid #f0f1f5;text-align:right;color:#1565c0;">${fmtN(r.debit)}</td>
                <td style="padding:8px 14px;border-bottom:1px solid #f0f1f5;text-align:right;color:#c62828;">${fmtN(r.credit)}</td>
                <td style="padding:8px 14px;border-bottom:1px solid #f0f1f5;text-align:right;">${fmtN(r.period_balance)}</td>
                <td style="padding:8px 14px;border-bottom:1px solid #f0f1f5;text-align:right;font-weight:600;color:#2e7d32;">${fmtN(r.ending_balance)}</td>
            </tr>
        `).join('');

        const html = `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Trial Balance</title>
<style>
  body { font-family: Inter, sans-serif; padding: 32px; color: #1f2937; }
  h2 { margin: 0 0 4px; font-size: 22px; text-align: center; }
  p.sub { color: #8a93a4; margin: 0 0 24px; font-size: 13px; text-align: center; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 20px; }
  th { text-align: left; padding: 10px 14px; background: #f0f1f5; border-bottom: 2px solid #d0d5df; color: #6b7280; font-weight: 700; text-transform: uppercase; font-size: 11px; }
  @media print { button { display:none } }
</style></head><body>
<h2>Trial Balance &mdash; ${d.company}</h2>
<p class="sub">Date Range: ${d.date_range.start} to ${d.date_range.end}</p>
<table>
  <thead>
    <tr>
      <th style="text-align:left;width:10%">Code</th>
      <th style="text-align:left;width:30%">Account</th>
      <th style="text-align:right;width:12%">Initial Balance</th>
      <th style="text-align:right;width:12%">Debit</th>
      <th style="text-align:right;width:12%">Credit</th>
      <th style="text-align:right;width:12%">Period Balance</th>
      <th style="text-align:right;width:12%">Ending Balance</th>
    </tr>
  </thead>
  <tbody>
    ${rows}
    <tr style="background:#0f1729;color:#fff;font-weight:800;">
      <td style="padding:12px 14px;" colspan="2">Totals</td>
      <td style="padding:12px 14px;text-align:right;">${fmtN(d.total_initial)}</td>
      <td style="padding:12px 14px;text-align:right;">${fmtN(d.total_debit)}</td>
      <td style="padding:12px 14px;text-align:right;">${fmtN(d.total_credit)}</td>
      <td style="padding:12px 14px;text-align:right;">${fmtN(d.total_period)}</td>
      <td style="padding:12px 14px;text-align:right;">${fmtN(d.total_ending)}</td>
    </tr>
  </tbody>
</table>
</body></html>`;

        const win = window.open('', '_blank', 'width=980,height=720');
        win.document.write(html);
        win.document.close();
        setTimeout(() => win.print(), 400);
    }

    startDragChat(ev) {
        if (ev.button !== 0) return;
        if (ev.target && ev.target.closest('.anx-chat-close-btn')) return;
        ev.preventDefault();
        
        const initialX = ev.clientX;
        const initialY = ev.clientY;
        const startX = this.state.chatPos.x;
        const startY = this.state.chatPos.y;
        
        let hasMoved = false;

        const onMouseMove = (moveEv) => {
            const dx = moveEv.clientX - initialX;
            const dy = moveEv.clientY - initialY;
            
            if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
                hasMoved = true;
            }

            let newX = startX + dx;
            let newY = startY + dy;
            
            const btnSize = 58;
            newX = Math.max(10, Math.min(window.innerWidth - btnSize - 10, newX));
            newY = Math.max(10, Math.min(window.innerHeight - btnSize - 10, newY));

            this.state.chatPos.x = newX;
            this.state.chatPos.y = newY;
        };

        const onMouseUp = () => {
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            
            localStorage.setItem('anx_chat_pos_x', this.state.chatPos.x);
            localStorage.setItem('anx_chat_pos_y', this.state.chatPos.y);

            if (hasMoved) {
                this.preventChatClick = true;
                setTimeout(() => {
                    this.preventChatClick = false;
                }, 100);
            }
        };

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    }

    startTouchDragChat(ev) {
        const touch = ev.touches[0];
        const initialX = touch.clientX;
        const initialY = touch.clientY;
        const startX = this.state.chatPos.x;
        const startY = this.state.chatPos.y;
        
        let hasMoved = false;

        const onTouchMove = (moveEv) => {
            const touchMove = moveEv.touches[0];
            const dx = touchMove.clientX - initialX;
            const dy = touchMove.clientY - initialY;
            
            if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
                hasMoved = true;
            }

            let newX = startX + dx;
            let newY = startY + dy;
            
            const btnSize = 58;
            newX = Math.max(10, Math.min(window.innerWidth - btnSize - 10, newX));
            newY = Math.max(10, Math.min(window.innerHeight - btnSize - 10, newY));

            this.state.chatPos.x = newX;
            this.state.chatPos.y = newY;
        };

        const onTouchEnd = () => {
            document.removeEventListener('touchmove', onTouchMove);
            document.removeEventListener('touchend', onTouchEnd);
            
            localStorage.setItem('anx_chat_pos_x', this.state.chatPos.x);
            localStorage.setItem('anx_chat_pos_y', this.state.chatPos.y);

            if (hasMoved) {
                this.preventChatClick = true;
                setTimeout(() => {
                    this.preventChatClick = false;
                }, 100);
            }
        };

        document.addEventListener('touchmove', onTouchMove);
        document.addEventListener('touchend', onTouchEnd);
    }

    toggleChatPopup(ev) {
        if (this.preventChatClick) return;

        // Trigger native Odoo Messaging Menu in top navbar
        const systrayIcon = document.querySelector(
            '.o_menu_systray .fa-comments, .o_menu_systray .fa-comment, .o_messaging_menu, [title*="Messaging"], [title*="Discuss"]'
        );
        if (systrayIcon) {
            const btn = systrayIcon.closest('button') || systrayIcon;
            btn.click();
        } else {
            this.action.doAction("mail.action_discuss");
        }
    }

    closeChatPopup() {
        this.state.showChatPopup = false;
    }

    getChatPopupStyle() {
        const btnSize = 58;
        const popupWidth = 360;
        const popupHeight = 440;
        
        let left = this.state.chatPos.x - popupWidth + btnSize;
        let top = this.state.chatPos.y - popupHeight - 12;
        
        // boundary checks
        if (left < 10) {
            left = this.state.chatPos.x;
        }
        if (top < 10) {
            top = this.state.chatPos.y + btnSize + 12;
        }
        
        return `position: fixed; left: ${left}px; top: ${top}px; width: ${popupWidth}px; height: ${popupHeight}px; z-index: 100000; overflow: hidden; display: flex; flex-direction: column;`;
    }

    get discussUnreadCount() {
        if (this.store && this.store.discuss) {
            if (typeof this.store.discuss.unreadCounter === 'number') {
                return this.store.discuss.unreadCounter;
            }
        }
        return 3;
    }

    openFullDiscuss() {
        this.state.showChatPopup = false;
        this.action.doAction("mail.action_discuss");
    }

    stripHtml(html) {
        if (!html) return "";
        return html.replace(/<[^>]*>/g, "");
    }


    async onClickChatThread(ev) {
        const id = parseInt(ev.currentTarget.dataset.threadId);
        const model = ev.currentTarget.dataset.threadModel;
        if (id && model) {
            const thread = this.store.Thread.get({ id, model });
            if (thread) {
                this.state.activeThreadId = thread.localId;
                if (thread.markAsRead) {
                    thread.markAsRead();
                }
                try {
                    await thread.fetchMessages();
                } catch (e) {
                    console.error("Error fetching messages:", e);
                }
                this.startChatPolling();
            }
        }
    }

    startChatPolling() {
        this.stopChatPolling();
        this.state.chatPolling = true;
        this._chatPollTimer = setInterval(async () => {
            try {
                const thread = this.activeThread;
                if (thread && this.state.showChatPopup && this.state.activeThreadId) {
                    await thread.fetchMessages();
                    // Auto-scroll to bottom
                    setTimeout(() => {
                        if (this.messageFeedRef.el) {
                            this.messageFeedRef.el.scrollTop = this.messageFeedRef.el.scrollHeight;
                        }
                    }, 30);
                }
            } catch (e) {
                // Silently ignore poll errors
            }
        }, 3000);
    }

    stopChatPolling() {
        if (this._chatPollTimer) {
            clearInterval(this._chatPollTimer);
            this._chatPollTimer = null;
        }
        this.state.chatPolling = false;
    }

    goBackToChatList() {
        this.stopChatPolling();
        this.state.activeThreadId = null;
    }

    get activeThread() {
        if (this.state.activeThreadId && this.store) {
            return this.store.Thread.records[this.state.activeThreadId] || 
                   this.store.menuThreads?.find(t => t.localId === this.state.activeThreadId);
        }
        return null;
    }

    get activeThreadMessages() {
        const thread = this.activeThread;
        if (thread && thread.messages) {
            return thread.messages.filter(m => !m.isNotification);
        }
        return [];
    }

    formatMessageTime(message) {
        if (!message || !message.date) return "";
        if (message.date.toFormat) {
            return message.date.toFormat("HH:mm");
        }
        try {
            const d = new Date(message.date);
            return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
        } catch (e) {
            return "";
        }
    }

    async sendMessage(ev) {
        if (ev) {
            ev.preventDefault();
        }
        const body = this.state.messageText ? this.state.messageText.trim() : "";
        if (!body) return;

        const thread = this.activeThread;
        if (!thread) return;

        // Clear input immediately for responsiveness
        this.state.messageText = "";

        try {
            await thread.post(body);
            // Refresh messages and scroll
            try { await thread.fetchMessages(); } catch (e) {}
            setTimeout(() => {
                if (this.messageFeedRef.el) {
                    this.messageFeedRef.el.scrollTop = this.messageFeedRef.el.scrollHeight;
                }
            }, 50);
        } catch (e) {
            console.error("Error posting message:", e);
            // Restore the text if send failed
            this.state.messageText = body;
        }
    }

    onMessageInputKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.sendMessage();
        }
    }

    get activeChats() {
        if (this.store && this.store.menuThreads) {
            const term = (this.state.chatSearch || '').trim().toLowerCase();
            if (!term) return this.store.menuThreads;
            return this.store.menuThreads.filter(t =>
                (t.displayName || '').toLowerCase().includes(term)
            );
        }
        return [];
    }

    clearChatSearch() {
        this.state.chatSearch = '';
        this.state.chatSearchResults = [];
    }

    onClickSearchResult(ev) {
        const idx = parseInt(ev.currentTarget.dataset.resultIndex, 10);
        if (isNaN(idx)) return;
        const result = this.state.chatSearchResults[idx];
        if (!result) return;
        this.startNewChat(result);
    }

    async onChatSearchInput(ev) {
        const term = ev.target.value;
        this.state.chatSearch = term;
        const trimmed = (term || '').trim();
        if (!trimmed) {
            this.state.chatSearchResults = [];
            return;
        }
        this.state.chatSearchLoading = true;
        try {
            // Search res.users by name, exclude current user
            const users = await this.orm.searchRead(
                'res.users',
                [['name', 'ilike', trimmed], ['active', '=', true], ['id', '!=', this.store.self?.main_user_id?.id || false]],
                ['id', 'name', 'partner_id', 'image_128'],
                { limit: 8 }
            );
            // Also search discuss.channel by name
            const channels = await this.orm.searchRead(
                'discuss.channel',
                [['name', 'ilike', trimmed]],
                ['id', 'name', 'channel_type', 'image_128'],
                { limit: 5 }
            );
            this.state.chatSearchResults = [
                ...users.map(u => ({ type: 'user', id: u.id, name: u.name, partnerId: Array.isArray(u.partner_id) ? u.partner_id[0] : u.partner_id, avatarUrl: u.image_128 ? `/web/image/res.users/${u.id}/image_128` : null })),
                ...channels.map(c => ({ type: 'channel', id: c.id, name: c.name, channelType: c.channel_type, avatarUrl: c.image_128 ? `/web/image/discuss.channel/${c.id}/image_128` : null }))
            ];
        } catch (e) {
            console.error('Chat search error:', e);
            this.state.chatSearchResults = [];
        } finally {
            this.state.chatSearchLoading = false;
        }
    }

    async startNewChat(result) {
        this.state.chatSearch = '';
        this.state.chatSearchResults = [];
        try {
            if (result.type === 'user') {
                // Open or create a DM with this user
                const chat = await this.store.getChat({ userId: result.id });
                if (chat) {
                    this.state.activeThreadId = chat.localId;
                    try { await chat.fetchMessages(); } catch (e) {}
                    this.startChatPolling();
                }
            } else {
                // Open an existing channel
                let thread = this.store.Thread.get({ id: result.id, model: 'discuss.channel' });
                if (!thread) {
                    // Fetch channel and then open
                    await this.store.fetchChannel(result.id);
                    thread = this.store.Thread.get({ id: result.id, model: 'discuss.channel' });
                }
                if (thread) {
                    this.state.activeThreadId = thread.localId;
                    try { await thread.fetchMessages(); } catch (e) {}
                    this.startChatPolling();
                }
            }
        } catch (e) {
            console.error('Error opening chat:', e);
        }
    }

}

registry.category("actions").add("analytix_finance_dashboard", AnalytixFinanceDashboard);
