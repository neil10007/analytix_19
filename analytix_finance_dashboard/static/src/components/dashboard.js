/** @odoo-module */
import { Component, useState, onWillStart, onMounted, useRef, useEffect, onWillUnmount, xml, useSubEnv, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";
import { Discuss } from "@mail/core/public_web/discuss";
import { MessagingMenu } from "@mail/core/public_web/messaging_menu";
import { DROPDOWN_NESTING } from "@web/core/dropdown/_behaviours/dropdown_nesting";
import { user } from "@web/core/user";

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
            analyzingDocIds:  {},  // { [docId]: true } — per-doc concurrent lock
            // ── Account Validation Dialog Modal State
            showAccountValidationModal: false,
            accountValData:             null,
            selectedValidationAccountId: '',
            lineAccountMap:             {},
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
            // ── Inventory Tab State
            invProducts:        null,
            invProductsLoading: false,
            invProductSearch:   '',
            invProductSortCol:  'name',
            invProductSortDir:  'asc',
            invCurrencySym:     '',
            // ── Batch Document Selection ──────────────────────────────────
            selectedDocIds:     {},   // { [docId]: true|false }
            batchAnalyzing:     false,
        });

        this.chartRef1 = useRef("revExpChart");
        this.messageFeedRef = useRef("messageFeed");
        this.chart1    = null;

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            // Restore filters (activeTab resets to 'overview', or restores the return tab if
            // user is coming back from a record opened inside the dashboard)
            this.restoreFilterState();
            await this.fetchData();
            // Pre-fetch data for whichever tab will be shown on load
            const tab = this.state.activeTab;
            if (tab === 'invoices')      await this.fetchInvoiceData();
            if (tab === 'expenses')      await this.fetchExpenseData();
            if (tab === 'vat')           await this.fetchVatData();
            if (tab === 'journals')      await this.fetchJournalData();
            if (tab === 'trial_balance') await this.fetchTrialBalanceData();
            if (tab === 'documents')     await this.fetchDocumentData();
            if (tab === 'inventory')     await this.fetchInventoryData();
            if (tab === 'chat')          this.store.discuss.isActive = true;

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
            if (!document.getElementById("anx-inter-font")) {
                const link = document.createElement("link");
                link.id = "anx-inter-font";
                link.rel = "stylesheet";
                link.href = "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap";
                document.head.appendChild(link);
            }
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

            this.updateUnreadCount();
            this._unreadPollTimer = setInterval(() => {
                this.updateUnreadCount();
            }, 5000);
        });
        useEffect(() => {
            if (this.state.activeTab === 'overview') {
                this.renderCharts();
            }
        }, () => [this.state.data, this.state.activeTab]);
        useEffect(() => {
            if (this.messageFeedRef.el) {
                this.messageFeedRef.el.scrollTop = this.messageFeedRef.el.scrollHeight;
            }
        }, () => [this.state.activeThreadId, this.activeThreadMessages?.length]);
        onWillUnmount(() => {
            if (this._unreadPollTimer) {
                clearInterval(this._unreadPollTimer);
                this._unreadPollTimer = null;
            }
            this.store.discuss.isActive = false;
            this.stopChatPolling();
        });
    }

    // ── Save / Restore Filter Persistence ────────────────────────────
    saveFilterState() {
        try {
            const filterState = {
                filter:           this.state.filter,
                customFrom:       this.state.customFrom,
                customTo:         this.state.customTo,
                showCustomPicker: this.state.showCustomPicker,
                // activeTab is intentionally NOT saved — dashboard always opens on Overview
                invTypeFilter:    this.state.invTypeFilter,
                invStatusFilter:  this.state.invStatusFilter,
                invCompanyFilter: this.state.invCompanyFilter,
                expStatusFilter:  this.state.expStatusFilter,
                expCompanyFilter: this.state.expCompanyFilter,
                vatTypeFilter:    this.state.vatTypeFilter,
                vatCompanyFilter: this.state.vatCompanyFilter,
                jrnTypeFilter:    this.state.jrnTypeFilter,
                jrnCompanyFilter: this.state.jrnCompanyFilter,
                tbTypeFilter:     this.state.tbTypeFilter,
                tbCompanyFilter:  this.state.tbCompanyFilter,
            };
            sessionStorage.setItem('anx_dashboard_filters', JSON.stringify(filterState));
            // Do NOT persist active tab — always reset to overview on re-entry
        } catch (e) {
            console.error("Failed to save filter state:", e);
        }
    }

    restoreFilterState() {
        try {
            const saved = sessionStorage.getItem('anx_dashboard_filters');
            if (saved) {
                const p = JSON.parse(saved);
                if (p.filter)           this.state.filter           = p.filter;
                if (p.customFrom !== undefined) this.state.customFrom = p.customFrom;
                if (p.customTo !== undefined)   this.state.customTo   = p.customTo;
                if (p.showCustomPicker !== undefined) this.state.showCustomPicker = p.showCustomPicker;
                // activeTab is intentionally NOT restored — always open on Overview
                if (p.invTypeFilter)    this.state.invTypeFilter    = p.invTypeFilter;
                if (p.invStatusFilter)  this.state.invStatusFilter  = p.invStatusFilter;
                if (p.invCompanyFilter) this.state.invCompanyFilter = p.invCompanyFilter;
                if (p.expStatusFilter)  this.state.expStatusFilter  = p.expStatusFilter;
                if (p.expCompanyFilter) this.state.expCompanyFilter = p.expCompanyFilter;
                if (p.vatTypeFilter)    this.state.vatTypeFilter    = p.vatTypeFilter;
                if (p.vatCompanyFilter) this.state.vatCompanyFilter = p.vatCompanyFilter;
                if (p.jrnTypeFilter)    this.state.jrnTypeFilter    = p.jrnTypeFilter;
                if (p.jrnCompanyFilter) this.state.jrnCompanyFilter = p.jrnCompanyFilter;
                if (p.tbTypeFilter)     this.state.tbTypeFilter     = p.tbTypeFilter;
                if (p.tbCompanyFilter)  this.state.tbCompanyFilter  = p.tbCompanyFilter;
            }
            // If user came back from a record opened INSIDE the dashboard, restore that tab.
            // Otherwise (navigating from a different module) always show Overview.
            const returnTab = sessionStorage.getItem('anx_return_tab');
            if (returnTab) {
                this.state.activeTab = returnTab;
                sessionStorage.removeItem('anx_return_tab');
            } else {
                this.state.activeTab = 'overview';
            }
            // Clean up any stale legacy tab keys
            sessionStorage.removeItem('anx_active_tab');
        } catch (e) {
            console.error("Failed to restore filter state:", e);
        }
    }

    // ── Save the current tab so Back button restores it ──────────────
    // Call this BEFORE any doAction that navigates away from within the dashboard.
    _saveReturnTab() {
        try {
            sessionStorage.setItem('anx_return_tab', this.state.activeTab);
        } catch (e) { /* ignore */ }
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
            if (!this.state.customFrom || !this.state.customTo) {
                const start = (this.state.data && this.state.data.date_range && this.state.data.date_range.start) || '';
                const end   = (this.state.data && this.state.data.date_range && this.state.data.date_range.end) || '';
                this.state.customFrom = start;
                this.state.customTo   = end;
            }
            this.state.showCustomPicker = true;
            this.saveFilterState();
            return;
        }
        this.state.showCustomPicker = false;
        this.state.customFrom = '';
        this.state.customTo   = '';
        this.state.vatFilterFrom = '';
        this.state.vatFilterTo   = '';
        this.saveFilterState();
        await this.fetchData();
        if (this.state.activeTab === 'invoices')      await this.fetchInvoiceData();
        if (this.state.activeTab === 'expenses')      await this.fetchExpenseData();
        if (this.state.activeTab === 'vat')           await this.fetchVatData();
        if (this.state.activeTab === 'journals')      await this.fetchJournalData();
        if (this.state.activeTab === 'trial_balance') await this.fetchTrialBalanceData();
        if (this.state.activeTab === 'documents')     await this.fetchDocumentData();
        if (this.state.activeTab === 'inventory')     await this.fetchInventoryData();
    }

    // ── Custom date range change ──────────────────────────────────────
    onCustomDateChange(ev) {
        const field = ev.target.dataset.field;
        if (field === 'from') this.state.customFrom = ev.target.value;
        if (field === 'to')   this.state.customTo   = ev.target.value;
        this.saveFilterState();
    }

    // ── Apply custom range ───────────────────────────────────────────
    async applyCustomRange() {
        const fromEl = document.querySelector('input.anx-custom-date-input[data-field="from"]');
        const toEl   = document.querySelector('input.anx-custom-date-input[data-field="to"]');
        if (fromEl && fromEl.value) this.state.customFrom = fromEl.value;
        if (toEl && toEl.value)     this.state.customTo   = toEl.value;

        if (!this.state.customFrom || !this.state.customTo) {
            this.notification.add('Please select both From and To dates.', { type: 'warning' });
            return;
        }
        if (this.state.customFrom > this.state.customTo) {
            this.notification.add('"From" date must be before "To" date.', { type: 'warning' });
            return;
        }
        this.state.vatFilterFrom = this.state.customFrom;
        this.state.vatFilterTo   = this.state.customTo;
        this.saveFilterState();
        await this.fetchData();
        if (this.state.activeTab === 'invoices')      await this.fetchInvoiceData();
        if (this.state.activeTab === 'expenses')      await this.fetchExpenseData();
        if (this.state.activeTab === 'vat')           await this.fetchVatData();
        if (this.state.activeTab === 'journals')      await this.fetchJournalData();
        if (this.state.activeTab === 'trial_balance') await this.fetchTrialBalanceData();
        if (this.state.activeTab === 'documents')     await this.fetchDocumentData();
        if (this.state.activeTab === 'inventory')     await this.fetchInventoryData();
    }

    // ── Tab click — reads data-tab attribute ──────────────────────────
    async onTabClick(ev) {
        const tab = ev.currentTarget.dataset.tab;
        if (!tab) return;
        if (ev.currentTarget && ev.currentTarget.scrollIntoView) {
            ev.currentTarget.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
        }
        this.state.activeTab = tab;
        this.saveFilterState();
        if (tab === 'overview') {
            this.renderCharts();
        }
        if (tab === 'invoices') {
            await this.fetchInvoiceData();
        }
        if (tab === 'expenses') {
            await this.fetchExpenseData();
        }
        if (tab === 'vat') {
            await this.fetchVatData();
        }
        if (tab === 'journals') {
            await this.fetchJournalData();
        }
        if (tab === 'trial_balance') {
            await this.fetchTrialBalanceData();
        }
        if (tab === 'documents') {
            await this.fetchDocumentData();
        }
        if (tab === 'inventory') {
            await this.fetchInventoryData();
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

    // ── Inventory data fetch ──────────────────────────────────────────
    async fetchInventoryData() {
        this.state.invProductsLoading = true;
        try {
            const data = await this.orm.call(
                'account.move',
                'get_analytix_inventory_data',
                []
            );
            this.state.invProducts = data.records;
            this.state.invCurrencySym = data.currency_sym;
        } catch (e) {
            console.error("Failed to load inventory data:", e);
            this.notification.add('Failed to load product list.', { type: 'danger' });
        } finally {
            this.state.invProductsLoading = false;
        }
    }

    // ── Inventory search / sort ───────────────────────────────────────
    onInvProductSearch(ev) { this.state.invProductSearch = ev.target.value; }
    onInvProductSort(ev) {
        const col = ev.currentTarget.dataset.col;
        if (!col) return;
        if (this.state.invProductSortCol === col) {
            this.state.invProductSortDir = this.state.invProductSortDir === 'asc' ? 'desc' : 'asc';
        } else {
            this.state.invProductSortCol = col;
            this.state.invProductSortDir = 'asc';
        }
    }

    get filteredProducts() {
        if (!this.state.invProducts) return [];
        let rows = this.state.invProducts;
        const q = this.state.invProductSearch.trim().toLowerCase();
        if (q) {
            rows = rows.filter(r =>
                (r.name || '').toLowerCase().includes(q) ||
                (r.default_code || '').toLowerCase().includes(q) ||
                (r.barcode || '').toLowerCase().includes(q) ||
                (r.categ_id && r.categ_id[1] && r.categ_id[1].toLowerCase().includes(q))
            );
        }
        const col = this.state.invProductSortCol;
        const dir = this.state.invProductSortDir === 'asc' ? 1 : -1;
        return [...rows].sort((a, b) => {
            let av = a[col] ?? '', bv = b[col] ?? '';
            if (Array.isArray(av)) av = av[1] || '';
            if (Array.isArray(bv)) bv = bv[1] || '';
            if (typeof av === 'string') { av = av.toLowerCase(); bv = (bv + '').toLowerCase(); }
            if (av < bv) return -1 * dir;
            if (av > bv) return 1 * dir;
            return 0;
        });
    }

    // ── Open product form view ────────────────────────────────────────
    openProduct(ev) {
        const id = parseInt(ev.currentTarget.dataset.id, 10);
        if (!id) return;
        this._saveReturnTab();
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'product.template',
            res_id: id,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    // ── Create new Product ────────────────────────────────────────────
    createNewProduct() {
        this._saveReturnTab();
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'New Product',
            res_model: 'product.template',
            views: [[false, 'form']],
            target: 'current',
        });
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
        this.saveFilterState();
        await this.fetchInvoiceData();
    }

    // ── Invoice status/company/search/sort filters (client-side) ─────
    onInvStatusFilter(ev) {
        this.state.invStatusFilter = ev.currentTarget.dataset.status || 'all';
        this.saveFilterState();
    }
    onInvCompanyFilter(ev) {
        this.state.invCompanyFilter = ev.currentTarget.dataset.company || 'all';
        this.saveFilterState();
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
        this._saveReturnTab(); // restore Invoices tab on Back
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
        this._saveReturnTab(); // restore Invoices tab on Back
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
    onExpStatusFilter(ev) { this.state.expStatusFilter = ev.currentTarget.dataset.status || 'all'; this.saveFilterState(); }
    onExpCompanyFilter(ev) { this.state.expCompanyFilter = ev.currentTarget.dataset.company || 'all'; this.saveFilterState(); }
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
        this._saveReturnTab(); // restore Expenses tab on Back
        this.action.doAction({ type: 'ir.actions.act_window', res_model: 'account.move', res_id: id, views: [[false, 'form']], target: 'current' });
    }

    // ── Create new Vendor Bill ─────────────────────────────────────────
    createNewBill() {
        this._saveReturnTab(); // restore Expenses tab on Back
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
        if (this.state.filter === 'custom' && this.state.customFrom && this.state.customTo) {
            this.state.vatFilterFrom = this.state.customFrom;
            this.state.vatFilterTo   = this.state.customTo;
        } else if (!this.state.vatFilterFrom || !this.state.vatFilterTo) {
            this.state.vatFilterFrom = (this.state.data && this.state.data.date_range && this.state.data.date_range.start) || '';
            this.state.vatFilterTo   = (this.state.data && this.state.data.date_range && this.state.data.date_range.end) || '';
        }
        await this.fetchVatFilterData();
    }
    onVatTypeFilter(ev) { this.state.vatTypeFilter = ev.currentTarget.dataset.vtype || 'all'; this.saveFilterState(); }
    onVatSearch(ev)      { this.state.vatSearch = ev.target.value; }
    onVatSort(ev) {
        const col = ev.currentTarget.dataset.col;
        if (!col) return;
        if (this.state.vatSortCol === col) { this.state.vatSortDir = this.state.vatSortDir === 'asc' ? 'desc' : 'asc'; }
        else { this.state.vatSortCol = col; this.state.vatSortDir = 'asc'; }
    }
    onVatCompanyFilter(ev) { this.state.vatCompanyFilter = ev.currentTarget.dataset.company || 'all'; this.saveFilterState(); }

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
        this._saveReturnTab(); // restore VAT tab on Back
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
    onJrnTypeFilter(ev) { this.state.jrnTypeFilter = ev.currentTarget.dataset.jtype || 'all'; this.saveFilterState(); }
    onJrnSearch(ev)      { this.state.jrnSearch = ev.target.value; }
    onJrnCompanyFilter(ev) { this.state.jrnCompanyFilter = ev.currentTarget.dataset.company || 'all'; this.saveFilterState(); }
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
        this._saveReturnTab(); // restore Journals tab on Back
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

    onTbTypeFilter(ev)    { this.state.tbTypeFilter    = ev.currentTarget.dataset.atype   || 'all'; this.saveFilterState(); }
    onTbSearch(ev)        { this.state.tbSearch        = ev.target.value; }
    onTbCompanyFilter(ev) { this.state.tbCompanyFilter = ev.currentTarget.dataset.company || 'all'; this.saveFilterState(); }
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
        this._saveReturnTab(); // restore Trial Balance tab on Back
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
        this._saveReturnTab(); // restore Journals tab on Back
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
        if (this.state.activeTab !== 'overview') return;
        setTimeout(async () => {
            if (this.state.activeTab !== 'overview') return;
            if (typeof window.Chart === 'undefined') {
                try {
                    await loadJS("/web/static/lib/Chart/Chart.js");
                } catch (e) {
                    console.error("Error loading Chart.js:", e);
                }
            }
            if (!this.state.data || !this.chartRef1.el) return;
            const canvas = this.chartRef1.el;
            if (!canvas || !canvas.isConnected) return;

            if (this.chart1) {
                try { this.chart1.destroy(); } catch (e) {}
                this.chart1 = null;
            }

            const revData = (this.state.data.chart && this.state.data.chart.revenue) || [];
            const expData = (this.state.data.chart && this.state.data.chart.expenses) || [];
            const labels  = (this.state.data.chart && this.state.data.chart.labels) || [];
            const sym     = (this.state.data && this.state.data.currency) || '';

            const ctx = canvas.getContext('2d');
            if (!ctx) return;

            this.chart1 = new window.Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
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
                    animation: { duration: 300 },
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
        }, 50);
    }

    getCurrencySymbol(codeOrSym) {
        if (!codeOrSym) return '';
        const clean = String(codeOrSym).trim();
        if (/^(SAR|SR|﷼|ر\.?س\.?|\uE900|)$/i.test(clean) || clean.includes('\uE900') || clean.includes('')) {
            return '\uE900';
        }
        return clean;
    }

    // ── Formatters ────────────────────────────────────────────────────
    formatCurrency(value) {
        if (!this.state.data) return String(value);
        const sym = this.getCurrencySymbol(this.state.data.currency);
        const num = Math.abs(Number(value));
        return `${sym} ${num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }

    formatShort(value) {
        const n = Number(value || 0);
        return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    formatExact(value) {
        const n = Number(value || 0);
        return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
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
        this.state.showPlModal       = true;
        this.state.plDateOption      = this.state.filter || 'this_month';
        this.state.plCustomFrom      = this.state.customFrom || '';
        this.state.plCustomTo        = this.state.customTo || '';
        this.state.plShowDateDrop    = false;
        this.state.plCompareMode     = false;
        this.state.plCompareFromIso  = '';
        this.state.plCompareToIso    = '';
        await this._refreshPlData();
    }

    async _refreshPlData() {
        this.state.plLoading = true;
        try {
            const cmpFrom = this.state.plCompareMode ? (this.state.plCompareFromIso || this._getPlDefaultCmpFrom()) : '';
            const cmpTo   = this.state.plCompareMode ? (this.state.plCompareToIso   || this._getPlDefaultCmpTo())   : '';
            this.state.plData = await this.orm.call(
                'account.move', 'get_analytix_pl_data',
                [this.state.plDateOption, this.state.plCustomFrom, this.state.plCustomTo, cmpFrom, cmpTo]
            );
            if (this.state.plCompareMode && this.state.plData) {
                if (!this.state.plCompareFromIso && this.state.plData.compare_from_iso) {
                    this.state.plCompareFromIso = this.state.plData.compare_from_iso;
                }
                if (!this.state.plCompareToIso && this.state.plData.compare_to_iso) {
                    this.state.plCompareToIso = this.state.plData.compare_to_iso;
                }
            }
        } catch (e) {
            this.notification.add('Failed to load P&L data.', { type: 'danger' });
            this.state.showPlModal = false;
        } finally {
            this.state.plLoading = false;
        }
    }

    _getPlDefaultCmpFrom() {
        if (this.state.plData && this.state.plData.period_from_iso) {
            const d = new Date(this.state.plData.period_from_iso);
            d.setFullYear(d.getFullYear() - 1);
            return this._isoDate(d);
        }
        const today = new Date();
        today.setFullYear(today.getFullYear() - 1);
        today.setDate(1);
        return this._isoDate(today);
    }

    _getPlDefaultCmpTo() {
        if (this.state.plData && this.state.plData.period_to_iso) {
            const d = new Date(this.state.plData.period_to_iso);
            d.setFullYear(d.getFullYear() - 1);
            return this._isoDate(d);
        }
        const today = new Date();
        today.setFullYear(today.getFullYear() - 1);
        return this._isoDate(today);
    }

    async togglePlComparison() {
        this.state.plCompareMode = !this.state.plCompareMode;
        if (this.state.plCompareMode) {
            this.state.plCompareFromIso = this._getPlDefaultCmpFrom();
            this.state.plCompareToIso   = this._getPlDefaultCmpTo();
        }
        await this._refreshPlData();
    }

    async onPlCompareFromChange(ev) {
        const val = ev.target.value;
        if (!val) return;
        this.state.plCompareFromIso = val;
        await this._refreshPlData();
    }

    async onPlCompareToChange(ev) {
        const val = ev.target.value;
        if (!val) return;
        this.state.plCompareToIso = val;
        await this._refreshPlData();
    }

    plChangePct(curr, comp) {
        const c = parseFloat(curr) || 0;
        const p = parseFloat(comp) || 0;
        if (p === 0) {
            if (c === 0) return 'n/a';
            return c > 0 ? '+100.0%' : '-100.0%';
        }
        const pct = ((c - p) / Math.abs(p)) * 100;
        const sign = pct > 0 ? '+' : '';
        return sign + pct.toFixed(1) + '%';
    }

    plChangeClass(curr, comp) {
        const c = parseFloat(curr) || 0;
        const p = parseFloat(comp) || 0;
        if (c === p) return 'anx-bs-pct-na';
        return c >= p ? 'anx-bs-pct-green' : 'anx-bs-pct-red';
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

    printVatReport() {
        if (!this.state.vatData) return;
        
        if (this.state.showVatModal) {
            const outputRows = this.filteredOutputVat;
            const inputRows = this.filteredInputVat;
            
            const totalOutputVat = outputRows.reduce((sum, r) => sum + (r.tax_amount || 0), 0);
            const totalInputVat = inputRows.reduce((sum, r) => sum + (r.tax_amount || 0), 0);
            const netVatPayable = totalOutputVat - totalInputVat;
            const totalLinesCount = outputRows.length + inputRows.length;
            
            const sym = this.state.vatData.currency_sym || '';
            const isSar = /^(SAR|SR|﷼|ر\.?س\.?|\uE900|)$/i.test(String(sym).trim()) || String(sym).includes('\uE900') || String(sym).includes('');
            const symSpan = isSar ? `<span class="anx-currency-sym" style="font-family:'sr_symbol', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif !important;">&#xe900;</span>` : `<span>${sym}</span>`;

            const fmtN = v => {
                const num = Number(v) || 0;
                const neg = num < 0;
                const s = Math.abs(num).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                return neg ? `<span style="color:#e53935">-${symSpan}${s}</span>` : `${symSpan}${s}`;
            };

            let companyName = user.activeCompany?.name || 'All Companies';
            if (this.state.vatData && this.state.vatData.companies && Array.isArray(this.state.vatData.companies)) {
                companyName = this.state.vatData.companies.map(c => c.name).join(', ');
            } else if (this.state.data && typeof this.state.data.companies === 'string') {
                companyName = this.state.data.companies;
            }

            const buildDetailedRows = (rows) => {
                if (!rows || rows.length === 0) {
                    return `<tr><td colspan="7" style="padding:16px;text-align:center;color:#64748b;">No data found.</td></tr>`;
                }
                return rows.map(r => `
                    <tr>
                        <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;text-align:center;font-weight:600;color:#0f172a;">${r.move_name}</td>
                        <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;">${r.partner}</td>
                        <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;text-align:center;"><span style="background:#f1f5f9;color:#475569;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;">${r.tax_name}</span></td>
                        <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;">${r.company_name}</td>
                        <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;text-align:center;color:#475569;">${r.invoice_date}</td>
                        <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;text-align:right;">${fmtN(r.total_amount)}</td>
                        <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;text-align:right;font-weight:600;">${fmtN(r.tax_amount)}</td>
                    </tr>
                `).join('');
            };

            const outTotalAmt = outputRows.reduce((sum, r) => sum + (r.total_amount || 0), 0);
            const inTotalAmt = inputRows.reduce((sum, r) => sum + (r.total_amount || 0), 0);

            const outRowsHtml = buildDetailedRows(outputRows);
            const inRowsHtml = buildDetailedRows(inputRows);

            const html = `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>VAT Detailed Summary Report</title>
<style>
  @font-face {
      font-family: "sr_symbol";
      src: url("/iwesabe_sar_currency_symbol/static/src/fonts/sr.ttf") format("truetype"),
           url("data:font/truetype;base64,AAEAAAALAIAAAwAwT1MvMg8SBTgAAAC8AAAAYGNtYXAXVtKIAAABHAAAAFRnYXNwAAAAEAAAAXAAAAAIZ2x5ZjrqSMoAAAF4AAAYDGhlYWQqn96bAAAZhAAAADZoaGVhB1YDxwAAGbwAAAAkaG10eA0oAAAAABngAAAAGGxvY2EMLgwGAAAZ+AAAAA5tYXhwAAkLQQAAGggAAAAgbmFtZZlKCfsAABooAAABhnBvc3QAAwAAAAAbsAAAACAAAwMNAZAABQAAApkCzAAAAI8CmQLMAAAB6wAzAQkAAAAAAAAAAAAAAAAAAAABEAAAAAAAAAAAAAAAAAAAAABAAADpAQPA/8AAQAPAAEAAAAABAAAAAAAAAAAAAAAgAAAAAAADAAAAAwAAABwAAQADAAAAHAADAAEAAAAcAAQAOAAAAAoACAACAAIAAQAg6QH//f//AAAAAAAg6QD//f//AAH/4xcEAAMAAQAAAAAAAAAAAAAAAQAB//8ADwABAAD/wAAAA8AAAgAANzkBAAAAAAEAAP/AAAADwAACAAA3OQEAAAAAAQAA/8AAAAPAAAIAADc5AQAAAAACAAD/wAOUA8AItQs+AAABDgEjDgEVIgYHFAYHDgExOAExMCIxMAYxDgExMCIVIgYxDgEHMAYxIgYxOAExMAYxDgExIgYxDgEHIgYHFCIxMCIVMAYHDgEHDgEHMAYxMAYVIgYPARUcATEiMCMwBgcqASMwBiMGIiMUIjEwBiMiBiMOASMGIgcwIiMwBjEwIiMwIgciBiMiBgcqATEwBiMGIjEwBiMiBiMwIjEiBiMUIiMiBiMiBiMwBiMwIhUqATEqAQciBjEqAQcwIiMiBiMwIjEiBiMqASMGIiMwIjEwIgcwIgcqATEOASMiBgciBiMwBiMiBiMwBiMGIjEGIiMiBgcwIjEUMCMUMDEUBjEOARUwFAccATEwBhUOATEwFDEUBhUOATEwBhUUBjEOAQcUBgcGFBUwBhUUBhUwFDEUBjEcATEGFDEcASMwFBUwFCMcATEUBjEcARUUBhUUBhUcARUGMjMwNjMyNjMyNjEyNjMyNjcwMjM+ATM6ATEwNjMyNjc6ATMyNjMyNjMyNjM+ATMyNjMyNjMwMjM+ATM6ATc6ATU6ATU6ATMyNjE6ATEwMjUyNjMyNjM6ATcwMjMwNhUwNjMwMjcyNjcyNjE6ATcyNjM6ATEwNjMwNjM+ATMyNjMyNjMyNjMyNjMyNjc6ATcwMjcyNjMwMjcwMjM2MjE2MjM+ATE6ATEyNjMwMjM3FRwBIzAGBzAGIw4BIyoBByoBMQYiIzAiIzAGIyIGBzAiMTAiIxQGIzAGIwYiMSIGMSoBIxQiMTAiByoBMSIGIyoBIzAGIyIGIyIGIyoBBzAiByoBByIGIyIGIyIGIyIGMSIGIwYiMTAGIyIGBw4BIwYiByoBIzAGMSIGMSIGIwYiMQYiIzAGIzAiMTAiFSoBIw4BIyoBIzAGMSIGByIGIwYiByIGIyIGByoBBzAiBw4BIw4BFTAUMQYUMTAGFRQGMTAGBzAUBxQGMRQGMTAGMTAGBw4BFQ4BBwYUBzAGMRwBBxwBMRQGFQ4BFRQGFRQGFRQGFTAUFRQGFQYUFRQGFRQWNzYyMzA2MzYyMTYyNzI2MzoBNzI2MzoBNTAyMzA2Mz4BMzA2MTI2Mz4BMTAyNzoBMzA2MzAyNz4BMzAyNzoBMTI0MzAyMzAyMTA2MzYyNzYyMTI2MzYyMzI2MzoBNToBMTI2MToBMTI2MToBMTI2Mz4BMzI2MzI2MzYyMzI2MzoBMTgBNzAyMz4BMzI2MzoBMTYyMzA2MzAyMzA2MzYyMTI2MTAyNzI2MzI2MzAyMzA2MzoBNzI2MzoBNzoBNzA2MzI2MTI2NzI2MzoBNzAyMTYyMTAyMzYyNzI2MzAyMzA2MzoBMTI2MzoBMT4BMzoBNzI2MzoBNzQ2NTA2NTA0MTA0MzQ2NTQ2MTQ2NTQ2MTI0MTA0NTI4MTwBMT4BNTA0MzA0MTA2NTQ2NTA0MzQ2MTA2NzwBNTI0NTQ2NTQ2NTQ2MTQ2NTA2NTwBMTA2NTwBNTY0MTAGIwGsAQMBAQMBCwICAQECAQEBAQEBAQEFAQIBAQEBAQEBAQEBAQIBAQECAgMYAQECAQEBAQIBAgEBBgEBAQEDAgIDAQEDAgIEAQEFAgMDAQIBAgEBAgEBBAIBAwMBAgEBAgEBAQEBAQEDAgIEAQEFAgMDAQIBAgEBAgEBBAIBAwMBAgQBAgMCAQIFAQECAgQCAQECAQEDAQMBAgEBAQEBAgUBAQECAQEBAQEBAQEBAQEBAQEBAQECAQEDBAcBAQUCAwQBAgICCwMDAgEEAQEBAQgDAQEBAQIBAQEBAgEBAQEBAQEBAQEBAQEBAQECAQEBAQIDAQEDAQECAgQCAQQCAgECBAEBAQcBAQQCAQEBAQYCAQIBAQQCAgQBAQMBAQIBAgEBBAIBAQEBAwECAgEBAQECAQECAQQBAQMBAQEBAgEBAQECAQMEAwIDAQMBAgMBAQEGAgMCAgUBAQIBAQIBAgMCAQMBAQQCAQMBBAIBAwECAQMBAgIBAgEDBAEBAQEBAQEBAQYCBAMCBQEBAgEBAgEBAQEBAgEBBAMCAQEFAwMCAgMBAQECAQIBAQECAQUBAQEBAgEBBAEBAQEBAgEDAQEDAQEDAQEDAQEDAQICAQMBBAICAQMEBAYHAwIDAQEBAQICBQEDAgEEAQEBAQECAgECAQIEAQEBAQIBBQQBBAIBBAEBAwECBAQBAQEEAwIGAQMDAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBBQMDAQMBAgMBAwIBAwEDBgIDAQECAgEDAQQGAQICBAIBBgIBAQEBAQEEAwIEAgICAQEBAQEBAgEBAwEBAwEEAwEBAQIBAQMBAQMBAQEBAQEBAQIBBAIEAwIBAgIBAwEDBgEBAgECAwEDAgIDAQIBAgMCBAYBAwEFAwIFAQMDCAECAQMCAQMBAgIBAgEBAgEBAgEBAwECBAECAwEBAwECAgEBAgEBAQECAQIJAQECAQIBAQMBAQMCAgMBBQICAQIBAgECBAECBAECAQMDAQEBAgEFAwIEAQEEAQEBAQECAQMGAwIBAgECAQEBAQEBAgEDAQEBAQEBAQEBAQEBAgEFAQEBAgEBAQEBAQMBAgEBAQEBAwEBAQEBAQEDAQEBAQICAwEBAQEBAQEBAQECAQIBAQMCAgQFAwECBAEBAQIBAQEBAQIBAQECAQICAQEDAQEBAQECAQEBAQEBAQEDAwECAQMCAQMBDQEBAQEBAQEBCwECBQEDAQEDAQMCAgQBAgEBAgEBBQIBAgECAQECAQMCAgUBAgIBAgEDAgQEAQEBAQMCAgMDAgIDAwIBBAEBBAICBAECBgEBAQEBAQECAQEBAgEBAQEBAQIBAgEBAgECAQEBAQEBAgEBAQECAQIBAQMCCgIBAgEBAQkBAgICBgIBAQEDAgIFAQEBAQIBAgEBAQIBAwEBAwECAwEBAQIBAQEBAQECAgQBAQIBAgIBAQEBAwEBAQEBAQEBAQIBAQEBAQEBAQECAQEBAQECAQO/AQIBAQEHAQEBAQEBAQEBAQEBAwECAQEBAQEBAQECAQEBAgEDGAIBAgEBAQEDAQLXa2sBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQIBAQEBAwEBAQIBAQEBAQIEAQEBAQEBAQEDAQEDAQIDAgEBAgMFAgEEAgIDAQEBAQIBAQEBAQIBAgEBAgEDAQIBCAEBAQEDAQIEAQICAQEBAQEBAQEBAQIBAQIBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQFGMRQBAQEBAQEBAQEBAQEBAQEBAQIBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQECAgEBAQEBAQIDAQEBAQIBAQQEAgIEAQEEBQEDAQMBAgEBAQEDAgEEAQEDAgEDAQEBAQICAQQCAgMBAQMCAwEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQECAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQIBAQEBAQEBAQEBAgEBAQEBBwEBAQEEAQEBAQEBAQEFAQECAQIBAgEBBAEBAQEBAQEBAQEBAQQCAgEDAwQBAgEBAgEBAQECAQEBBAEBBQIEFDAaJQEBAQEBAQEBAQEBAQEBAQEBAQMBH09uAwEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQECAQECAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQIBAQIBAQEBAgEBAQEBCwMCAgEBAQEBAQECAQMCAgUCAwQBAgUFAQIBBAQBAQICAQQCBAUBAQIBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBARsbNwEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQECAgMBAQEBAQUCAgEBAgEBAQQCAwMBAgEBAgEBAwEDCwUBAwEBAQEBAgEBBgIBAwECAQgJAQEBAQEBAQEBAQEBAQECAgEBAQEBAQEBAQEBAQEBAQEBAQIBAQEBAQEBAgEBAQEBAgEBAQHGZGIBAQEBAQEEAQEBAQEBAQEBAQEFAQEBAQECAQECAQECBAEFBgYDBQIBAQIBAQIBAQIBAgKkpQEBAQIBAQEBAQEBAQEBAQEBAQIB95VjAfy/AQEBAQEBAQEBAQEBAQEBAQEBAQQBAQEBAQEBAQEBAQEBAQEBAQEBAQIBAQECAQEBAQEBAQEBAgEBAQEBAQEBAQEBAgEBAQICAQEJAQEBAQEBAQEBAQEBAQEBAQEBAgEDAgMDAgEDAgEKBAECAQMCAgMBAgEDDgMCAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQIBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBBgEBAQEBAQEBAQEBAQIBAgEBAQEBAQEFAgIBAgEBAgEBAgQEAgEBAQEBAQIBAgYCAQIBBgIDAQECAgEBAwECCAEAAAEAAP/AAjIDwAAIAAABBzc+ATEwBgcCMAICAQEBAQNIAgIBAQEBAAABAAAAAAAAsksaaV8PPPUACwQAAAAAAOP2zQ8AAAAA4/bNDwAA/8ADlAPAAAAACAACAAAAAAAAAAEAAAPA/8AAAAQAAAAAAAOUAAEAAAAAAAAAAAAAAAAAAAAGBAAAAAAAAAAAAAAAAgAAAAOUAAADlAAAAAAAAAAKABQAHgvyDAYAAAABAAAABgs/AAIAAAAAAAIAAAAAAAAAAAAAAAAAAAAAAAAADgCuAAEAAAAAAAEABwAAAAEAAAAAAAIABwBgAAEAAAAAAAMABwA2AAEAAAAAAAQABwB1AAEAAAAAAAUACwAVAAEAAAAAAAYABwBLAAEAAAAAAAoAGgCKAAMAAQQJAAEADgAHAAMAAQQJAAIADgBnAAMAAQQJAAMADgA9AAMAAQQJAAQADgB8AAMAAQQJAAUAFgAgAAMAAQQJAAYADgBSAAMAAQQJAAoANACkaWNvbW9vbgBpAGMAbwBtAG8AbwBuVmVyc2lvbiAxLjAAVgBlAHIAcwBpAG8AbgAgADEALgAwaWNvbW9vbgBpAGMAbwBtAG8AbwBuUmVndWxhcgBSAGUAZwB1AGwAYQByaWNvbW9vbgBpAGMAbwBtAG8AbwBuRm9udCBnZW5lcmF0ZWQgYnkgSWNvTW9vbi4ARgBvAG4AdAAgAGcAZQBuAGUAcgBhAHQAZQBk ACAAYgB5 ACAASQBjAG8ATQBvAG8AbnAuAAAAAwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==") format("truetype");
      font-weight: normal; font-style: normal; unicode-range: U+E900;
  }
  .anx-currency-sym, .o_sar_symbol, .icon-sr, [class*="sr_symbol"] { font-family: 'sr_symbol', "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important; display: inline-block; }
  body { font-family: 'sr_symbol', Inter, Arial, sans-serif; padding: 32px; color: #1f2937; line-height: 1.5; }
  .hdr-box { text-align: center; border-bottom: 2px solid #e2e8f0; padding-bottom: 16px; margin-bottom: 24px; }
  h2 { margin: 0 0 4px; font-size: 24px; color: #0f172a; letter-spacing: -0.5px; }
  p.sub { color: #64748b; margin: 0; font-size: 13px; font-weight: 500; }
  .kpi-row { display: flex; gap: 16px; margin-bottom: 28px; justify-content: space-between; }
  .kpi-card { flex: 1; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; text-align: center; }
  .kpi-lbl { font-size: 11px; text-transform: uppercase; font-weight: 700; color: #64748b; margin-bottom: 4px; }
  .kpi-val { font-size: 18px; font-weight: 800; color: #0f172a; }
  .kpi-val.output { color: #1e88e5; }
  .kpi-val.input { color: #e53935; }
  .kpi-val.net { color: #2e7d32; }
  .sec-hdr { font-size: 14px; font-weight: 700; padding: 10px 14px; background: #1e3a8a; color: #fff; border-radius: 6px 6px 0 0; margin-top: 24px; display: flex; justify-content: space-between; align-items: center; }
  .sec-hdr.purchases { background: #7f1d1d; }
  table { width: 100%; border-collapse: collapse; font-size: 11.5px; margin-bottom: 24px; border: 1px solid #e2e8f0; }
  th { text-align: left; padding: 10px 12px; background: #f1f5f9; border-bottom: 2px solid #cbd5e1; color: #475569; font-weight: 700; text-transform: uppercase; font-size: 10px; }
  th.num-col { text-align: right; }
  th.center-col { text-align: center; }
  td { padding: 8px 12px; border-bottom: 1px solid #e2e8f0; }
  tr.tot-row { background: #f8fafc; font-weight: 700; }
  tr.tot-row td { padding: 10px 12px; border-top: 2px solid #cbd5e1; font-size: 12px; }
  @media print { button { display:none } body { padding: 15px; } }
</style></head><body>
<div class="hdr-box">
  <h2>VAT Detailed Report &mdash; ${companyName}</h2>
  <p class="sub">Date Range: ${this.state.vatFilterFrom || 'Beginning'} to ${this.state.vatFilterTo || 'Present'}</p>
</div>

<div class="kpi-row">
  <div class="kpi-card">
    <div class="kpi-lbl">Total Output VAT</div>
    <div class="kpi-val output">${fmtN(totalOutputVat)}</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-lbl">Total Input VAT</div>
    <div class="kpi-val input">${fmtN(totalInputVat)}</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-lbl">Net VAT Payable</div>
    <div class="kpi-val net">${fmtN(netVatPayable)}</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-lbl">Total Tax Lines</div>
    <div class="kpi-val">${totalLinesCount}</div>
  </div>
</div>

<div class="sec-hdr">
  <span>1. Output VAT &mdash; Customer Invoices</span>
</div>
<table>
  <thead>
    <tr>
      <th class="center-col" style="width:15%">Document</th>
      <th style="width:25%">Customer</th>
      <th class="center-col" style="width:12%">Tax</th>
      <th style="width:15%">Company</th>
      <th class="center-col" style="width:11%">Date</th>
      <th class="num-col" style="width:11%">Total Amount</th>
      <th class="num-col" style="width:11%">VAT Amount</th>
    </tr>
  </thead>
  <tbody>
    ${outRowsHtml}
    <tr class="tot-row">
      <td colspan="5" style="border-top: 2px solid #cbd5e1;">Total</td>
      <td style="text-align:right;border-top: 2px solid #cbd5e1;">${fmtN(outTotalAmt)}</td>
      <td style="text-align:right;border-top: 2px solid #cbd5e1;">${fmtN(totalOutputVat)}</td>
    </tr>
  </tbody>
</table>

<div class="sec-hdr purchases">
  <span>2. Input VAT &mdash; Vendor Bills</span>
</div>
<table>
  <thead>
    <tr>
      <th class="center-col" style="width:15%">Document</th>
      <th style="width:25%">Vendor</th>
      <th class="center-col" style="width:12%">Tax</th>
      <th style="width:15%">Company</th>
      <th class="center-col" style="width:11%">Date</th>
      <th class="num-col" style="width:11%">Total Amount</th>
      <th class="num-col" style="width:11%">VAT Amount</th>
    </tr>
  </thead>
  <tbody>
    ${inRowsHtml}
    <tr class="tot-row">
      <td colspan="5" style="border-top: 2px solid #cbd5e1;">Total</td>
      <td style="text-align:right;border-top: 2px solid #cbd5e1;">${fmtN(inTotalAmt)}</td>
      <td style="text-align:right;border-top: 2px solid #cbd5e1;">${fmtN(totalInputVat)}</td>
    </tr>
  </tbody>
</table>

</body></html>`;

            const win = window.open('', '_blank', 'width=1100,height=800');
            win.document.write(html);
            win.document.close();
            if (win.document.fonts && win.document.fonts.load) {
                win.document.fonts.load("12px sr_symbol", "\uE900").then(() => {
                    setTimeout(() => win.print(), 100);
                }).catch(() => {
                    setTimeout(() => win.print(), 400);
                });
            } else {
                setTimeout(() => win.print(), 400);
            }
            return;
        }

        const d = this.state.vatData;
        const sym = d.currency_sym || '';
        const isSar = /^(SAR|SR|﷼|ر\.?س\.?|\uE900|)$/i.test(String(sym).trim()) || String(sym).includes('\uE900') || String(sym).includes('');
        const symSpan = isSar ? `<span class="anx-currency-sym" style="font-family:'sr_symbol', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif !important;">&#xe900;</span>` : `<span>${sym}</span>`;

        const fmtN = v => {
            const num = Number(v) || 0;
            const neg = num < 0;
            const s = Math.abs(num).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            return neg ? `<span style="color:#e53935">-${symSpan}${s}</span>` : `${symSpan}${s}`;
        };

        let companyName = user.activeCompany?.name || 'All Companies';
        if (d && d.companies && Array.isArray(d.companies)) {
            companyName = d.companies.map(c => c.name).join(', ');
        } else if (this.state.data && typeof this.state.data.companies === 'string') {
            companyName = this.state.data.companies;
        }

        const buildRows = (boxes, totalBox) => {
            return (boxes || []).map(b => {
                const isTotal = b.box === totalBox || b.box === '13' || b.box === '14';
                const rowStyle = isTotal ? 'font-weight: 700; background-color: #f1f5f9;' : '';
                const numStyle = isTotal ? 'font-weight: 700; text-align: right;' : 'text-align: right;';
                const boxStyle = isTotal ? 'font-weight: 700; text-align: center;' : 'text-align: center; color: #4b5563;';
                
                const amtVal = (b.box === '13' || b.box === '14') ? '—' : fmtN(b.amount);
                const adjVal = (b.box === '13' || b.box === '14') ? '—' : fmtN(b.adjustment);
                
                return `
                    <tr style="${rowStyle}">
                        <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;${boxStyle}">${b.box}</td>
                        <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;font-weight:${isTotal?'700':'normal'};">${b.description}</td>
                        <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;${numStyle}">${amtVal}</td>
                        <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;${numStyle}">${adjVal}</td>
                        <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;${numStyle}">${fmtN(b.vat_amount)}</td>
                    </tr>
                `;
            }).join('');
        };

        const salesRows = buildRows(d.vat_return_sales, '6');
        const purchaseRows = buildRows(d.vat_return_purchases, '12');
        const netRows = buildRows(d.vat_return_net, '');

        const html = `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>VAT Return Summary</title>
<style>
  @font-face {
      font-family: "sr_symbol";
      src: url("/iwesabe_sar_currency_symbol/static/src/fonts/sr.ttf") format("truetype"),
           url("data:font/truetype;base64,AAEAAAALAIAAAwAwT1MvMg8SBTgAAAC8AAAAYGNtYXAXVtKIAAABHAAAAFRnYXNwAAAAEAAAAXAAAAAIZ2x5ZjrqSMoAAAF4AAAYDGhlYWQqn96bAAAZhAAAADZoaGVhB1YDxwAAGbwAAAAkaG10eA0oAAAAABngAAAAGGxvY2EMLgwGAAAZ+AAAAA5tYXhwAAkLQQAAGggAAAAgbmFtZZlKCfsAABooAAABhnBvc3QAAwAAAAAbsAAAACAAAwMNAZAABQAAApkCzAAAAI8CmQLMAAAB6wAzAQkAAAAAAAAAAAAAAAAAAAABEAAAAAAAAAAAAAAAAAAAAABAAADpAQPA/8AAQAPAAEAAAAABAAAAAAAAAAAAAAAgAAAAAAADAAAAAwAAABwAAQADAAAAHAADAAEAAAAcAAQAOAAAAAoACAACAAIAAQAg6QH//f//AAAAAAAg6QD//f//AAH/4xcEAAMAAQAAAAAAAAAAAAAAAQAB//8ADwABAAD/wAAAA8AAAgAANzkBAAAAAAEAAP/AAAADwAACAAA3OQEAAAAAAQAA/8AAAAPAAAIAADc5AQAAAAACAAD/wAOUA8AItQs+AAABDgEjDgEVIgYHFAYHDgExOAExMCIxMAYxDgExMCIVIgYxDgEHMAYxIgYxOAExMAYxDgExIgYxDgEHIgYHFCIxMCIVMAYHDgEHDgEHMAYxMAYVIgYPARUcATEiMCMwBgcqASMwBiMGIiMUIjEwBiMiBiMOASMGIgcwIiMwBjEwIiMwIgciBiMiBgcqATEwBiMGIjEwBiMiBiMwIjEiBiMUIiMiBiMiBiMwBiMwIhUqATEqAQciBjEqAQcwIiMiBiMwIjEiBiMqASMGIiMwIjEwIgcwIgcqATEOASMiBgciBiMwBiMiBiMwBiMGIjEGIiMiBgcwIjEUMCMUMDEUBjEOARUwFAccATEwBhUOATEwFDEUBhUOATEwBhUUBjEOAQcUBgcGFBUwBhUUBhUwFDEUBjEcATEGFDEcASMwFBUwFCMcATEUBjEcARUUBhUUBhUcARUGMjMwNjMyNjMyNjEyNjMyNjcwMjM+ATM6ATEwNjMyNjc6ATMyNjMyNjMyNjM+ATMyNjMyNjMwMjM+ATM6ATc6ATU6ATU6ATMyNjE6ATEwMjUyNjMyNjM6ATcwMjMwNhUwNjMwMjcyNjcyNjE6ATcyNjM6ATEwNjMwNjM+ATMyNjMyNjMyNjMyNjMyNjc6ATcwMjcyNjMwMjcwMjM2MjE2MjM+ATE6ATEyNjMwMjM3FRwBIzAGBzAGIw4BIyoBByoBMQYiIzAiIzAGIyIGBzAiMTAiIxQGIzAGIwYiMSIGMSoBIxQiMTAiByoBMSIGIyoBIzAGIyIGIyIGIyoBBzAiByoBByIGIyIGIyIGIyIGMSIGIwYiMTAGIyIGBw4BIwYiByoBIzAGMSIGMSIGIwYiMQYiIzAGIzAiMTAiFSoBIw4BIyoBIzAGMSIGByIGIwYiByIGIyIGByoBBzAiBw4BIw4BFTAUMQYUMTAGFRQGMTAGBzAUBxQGMRQGMTAGMTAGBw4BFQ4BBwYUBzAGMRwBBxwBMRQGFQ4BFRQGFRQGFRQGFTAUFRQGFQYUFRQGFRQWNzYyMzA2MzYyMTYyNzI2MzoBNzI2MzoBNTAyMzA2Mz4BMzA2MTI2Mz4BMTAyNzoBMzA2MzAyNz4BMzAyNzoBMTI0MzAyMzAyMTA2MzYyNzYyMTI2MzYyMzI2MzoBNToBMTI2MToBMTI2MToBMTI2Mz4BMzI2MzI2MzYyMzI2MzoBMTgBNzAyMz4BMzI2MzoBMTYyMzA2MzAyMzA2MzYyMTI2MTAyNzI2MzI2MzAyMzA2MzoBNzI2MzoBNzoBNzA2MzI2MTI2NzI2MzoBNzAyMTYyMTAyMzYyNzI2MzAyMzA2MzoBMTI2MzoBMT4BMzoBNzI2MzoBNzQ2NTA2NTA0MTA0MzQ2NTQ2MTQ2NTQ2MTI0MTA0NTI4MTwBMT4BNTA0MzA0MTA2NTQ2NTA0MzQ2MTA2NzwBNTI0NTQ2NTQ2NTQ2MTQ2NTA2NTwBMTA2NTwBNTY0MTAGIwGsAQMBAQMBCwICAQECAQEBAQEBAQEFAQIBAQEBAQEBAQEBAQIBAQECAgMYAQECAQEBAQIBAgEBBgEBAQEDAgIDAQEDAgIEAQEFAgMDAQIBAgEBAgEBBAIBAwMBAgEBAgEBAQEBAQEDAgIEAQEFAgMDAQIBAgEBAgEBBAIBAwMBAgQBAgMCAQIFAQECAgQCAQECAQEDAQMBAgEBAQEBAgUBAQECAQEBAQEBAQEBAQEBAQEBAQECAQEDBAcBAQUCAwQBAgICCwMDAgEEAQEBAQgDAQEBAQIBAQEBAgEBAQEBAQEBAQEBAQEBAQECAQEBAQIDAQEDAQECAgQCAQQCAgECBAEBAQcBAQQCAQEBAQYCAQIBAQQCAgQBAQMBAQIBAgEBBAIBAQEBAwECAgEBAQECAQECAQQBAQMBAQEBAgEBAQECAQMEAwIDAQMBAgMBAQEGAgMCAgUBAQIBAQIBAgMCAQMBAQQCAQMBBAIBAwECAQMBAgIBAgEDBAEBAQEBAQEBAQYCBAMCBQEBAgEBAgEBAQEBAgEBBAMCAQEFAwMCAgMBAQECAQIBAQECAQUBAQEBAgEBBAEBAQEBAgEDAQEDAQEDAQEDAQEDAQICAQMBBAICAQMEBAYHAwIDAQEBAQICBQEDAgEEAQEBAQECAgECAQIEAQEBAQIBBQQBBAIBBAEBAwECBAQBAQEEAwIGAQMDAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBBQMDAQMBAgMBAwIBAwEDBgIDAQECAgEDAQQGAQICBAIBBgIBAQEBAQEEAwIEAgICAQEBAQEBAgEBAwEBAwEEAwEBAQIBAQMBAQMBAQEBAQEBAQIBBAIEAwIBAgIBAwEDBgEBAgECAwEDAgIDAQIBAgMCBAYBAwEFAwIFAQMDCAECAQMCAQMBAgIBAgEBAgEBAgEBAwECBAECAwEBAwECAgEBAgEBAQECAQIJAQECAQIBAQMBAQMCAgMBBQICAQIBAgECBAECBAECAQMDAQEBAgEFAwIEAQEEAQEBAQECAQMGAwIBAgECAQEBAQEBAgEDAQEBAQEBAQEBAQEBAgEFAQEBAgEBAQEBAQMBAgEBAQEBAwEBAQEBAQEDAQEBAQICAwEBAQEBAQEBAQECAQIBAQMCAgQFAwECBAEBAQIBAQEBAQIBAQECAQICAQEDAQEBAQECAQEBAQEBAQEDAwECAQMCAQMBDQEBAQEBAQEBCwECBQEDAQEDAQMCAgQBAgEBAgEBBQIBAgECAQECAQMCAgUBAgIBAgEDAgQEAQEBAQMCAgMDAgIDAwIBBAEBBAICBAECBgEBAQEBAQECAQEBAgEBAQEBAQIBAgEBAgECAQEBAQEBAgEBAQECAQIBAQMCCgIBAgEBAQkBAgICBgIBAQEDAgIFAQEBAQIBAgEBAQIBAwEBAwECAwEBAQIBAQEBAQECAgQBAQIBAgIBAQEBAwEBAQEBAQEBAQIBAQEBAQEBAQECAQEBAQECAQO/AQIBAQEHAQEBAQEBAQEBAQEBAwECAQEBAQEBAQECAQEBAgEDGAIBAgEBAQEDAQLXa2sBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQIBAQEBAwEBAQIBAQEBAQIEAQEBAQEBAQEDAQEDAQIDAgEBAgMFAgEEAgIDAQEBAQIBAQEBAQIBAgEBAgEDAQIBCAEBAQEDAQIEAQICAQEBAQEBAQEBAQIBAQIBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQFGMRQBAQEBAQEBAQEBAQEBAQEBAQIBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQECAgEBAQEBAQIDAQEBAQIBAQQEAgIEAQEEBQEDAQMBAgEBAQEDAgEEAQEDAgEDAQEBAQICAQQCAgMBAQMCAwEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQECAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQIBAQEBAQEBAQEBAgEBAQEBBwEBAQEEAQEBAQEBAQEFAQECAQIBAgEBBAEBAQEBAQEBAQEBAQQCAgEDAwQBAgEBAgEBAQECAQEBBAEBBQIEFDAaJQEBAQEBAQEBAQEBAQEBAQEBAQMBH09uAwEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQECAQECAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQIBAQIBAQEBAgEBAQEBCwMCAgEBAQEBAQECAQMCAgUCAwQBAgUFAQIBBAQBAQICAQQCBAUBAQIBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBARsbNwEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQECAgMBAQEBAQUCAgEBAgEBAQQCAwMBAgEBAgEBAwEDCwUBAwEBAQEBAgEBBgIBAwECAQgJAQEBAQEBAQEBAQEBAQECAgEBAQEBAQEBAQEBAQEBAQEBAQIBAQEBAQEBAgEBAQEBAgEBAQHGZGIBAQEBAQEEAQEBAQEBAQEBAQEFAQEBAQECAQECAQECBAEFBgYDBQIBAQIBAQIBAQIBAgKkpQEBAQIBAQEBAQEBAQEBAQEBAQIB95VjAfy/AQEBAQEBAQEBAQEBAQEBAQEBAQQBAQEBAQEBAQEBAQEBAQEBAQEBAQIBAQECAQEBAQEBAQEBAgEBAQEBAQEBAQEBAgEBAQICAQEJAQEBAQEBAQEBAQEBAQEBAQEBAgEDAgMDAgEDAgEKBAECAQMCAgMBAgEDDgMCAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQIBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBBgEBAQEBAQEBAQEBAQIBAgEBAQEBAQEFAgIBAgEBAgEBAgQEAgEBAQEBAQIBAgYCAQIBBgIDAQECAgEBAwECCAEAAAEAAP/AAjIDwAAIAAABBzc+ATEwBgcCMAICAQEBAQNIAgIBAQEBAAABAAAAAAAAsksaaV8PPPUACwQAAAAAAOP2zQ8AAAAA4/bNDwAA/8ADlAPAAAAACAACAAAAAAAAAAEAAAPA/8AAAAQAAAAAAAOUAAEAAAAAAAAAAAAAAAAAAAAGBAAAAAAAAAAAAAAAAgAAAAOUAAADlAAAAAAAAAAKABQAHgvyDAYAAAABAAAABgs/AAIAAAAAAAIAAAAAAAAAAAAAAAAAAAAAAAAADgCuAAEAAAAAAAEABwAAAAEAAAAAAAIABwBgAAEAAAAAAAMABwA2AAEAAAAAAAQABwB1AAEAAAAAAAUACwAVAAEAAAAAAAYABwBLAAEAAAAAAAoAGgCKAAMAAQQJAAEADgAHAAMAAQQJAAIADgBnAAMAAQQJAAMADgA9AAMAAQQJAAQADgB8AAMAAQQJAAUAFgAgAAMAAQQJAAYADgBSAAMAAQQJAAoANACkaWNvbW9vbgBpAGMAbwBtAG8AbwBuVmVyc2lvbiAxLjAAVgBlAHIAcwBpAG8AbgAgADEALgAwaWNvbW9vbgBpAGMAbwBtAG8AbwBuUmVndWxhcgBSAGUAZwB1AGwAYQByaWNvbW9vbgBpAGMAbwBtAG8AbwBuRm9udCBnZW5lcmF0ZWQgYnkgSWNvTW9vbi4ARgBvAG4AdAAgAGcAZQBuAGUAcgBhAHQAZQBk ACAAYgB5 ACAASQBjAG8ATQBvAG8AbnAuAAAAAwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==") format("truetype");
      font-weight: normal; font-style: normal; unicode-range: U+E900;
  }
  .anx-currency-sym, .o_sar_symbol, .icon-sr, [class*="sr_symbol"] { font-family: 'sr_symbol', "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important; display: inline-block; }
  body { font-family: 'sr_symbol', Inter, Arial, sans-serif; padding: 32px; color: #1f2937; line-height: 1.5; }
  .hdr-box { text-align: center; border-bottom: 2px solid #e2e8f0; padding-bottom: 16px; margin-bottom: 24px; }
  h2 { margin: 0 0 4px; font-size: 24px; color: #0f172a; letter-spacing: -0.5px; }
  p.sub { color: #64748b; margin: 0; font-size: 13px; font-weight: 500; }
  .kpi-row { display: flex; gap: 16px; margin-bottom: 28px; justify-content: space-between; }
  .kpi-card { flex: 1; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; text-align: center; }
  .kpi-lbl { font-size: 11px; text-transform: uppercase; font-weight: 700; color: #64748b; margin-bottom: 4px; }
  .kpi-val { font-size: 18px; font-weight: 800; color: #0f172a; }
  .kpi-val.output { color: #1e88e5; }
  .kpi-val.input { color: #e53935; }
  .kpi-val.net { color: #2e7d32; }
  .sec-hdr { font-size: 14px; font-weight: 700; padding: 10px 14px; background: #1e3a8a; color: #fff; border-radius: 6px 6px 0 0; margin-top: 24px; display: flex; justify-content: space-between; align-items: center; }
  .sec-hdr.purchases { background: #7f1d1d; }
  .sec-hdr.net-due { background: #166534; }
  table { width: 100%; border-collapse: collapse; font-size: 12.5px; margin-bottom: 24px; border: 1px solid #e2e8f0; }
  th { text-align: left; padding: 10px 12px; background: #f1f5f9; border-bottom: 2px solid #cbd5e1; color: #475569; font-weight: 700; text-transform: uppercase; font-size: 10.5px; }
  th.num-col { text-align: right; }
  th.box-col { text-align: center; }
  tr.tot-row { background: #f8fafc; font-weight: 700; }
  tr.tot-row td { padding: 10px 12px; border-top: 2px solid #cbd5e1; font-size: 13px; }
  @media print { button { display:none } body { padding: 15px; } }
</style></head><body>
<div class="hdr-box">
  <h2>VAT Return Summary Report &mdash; ${companyName}</h2>
  <p class="sub">Date Range: ${this.state.vatFilterFrom || 'Beginning'} to ${this.state.vatFilterTo || 'Present'}</p>
</div>

<div class="kpi-row">
  <div class="kpi-card">
    <div class="kpi-lbl">Total Output VAT</div>
    <div class="kpi-val output">${fmtN(d.output_vat)}</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-lbl">Total Input VAT</div>
    <div class="kpi-val input">${fmtN(d.input_vat)}</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-lbl">Net VAT Payable</div>
    <div class="kpi-val net">${fmtN(d.net_vat)}</div>
  </div>
</div>

<div class="sec-hdr">
  <span>1. VAT on Sales</span>
</div>
<table>
  <thead>
    <tr>
      <th class="box-col" style="width:10%">Box #</th>
      <th style="width:45%">Description</th>
      <th class="num-col" style="width:15%">Amount (Base)</th>
      <th class="num-col" style="width:15%">Adjustment</th>
      <th class="num-col" style="width:15%">VAT Amount</th>
    </tr>
  </thead>
  <tbody>
    ${salesRows}
  </tbody>
</table>

<div class="sec-hdr purchases">
  <span>2. VAT on Purchases</span>
</div>
<table>
  <thead>
    <tr>
      <th class="box-col" style="width:10%">Box #</th>
      <th style="width:45%">Description</th>
      <th class="num-col" style="width:15%">Amount (Base)</th>
      <th class="num-col" style="width:15%">Adjustment</th>
      <th class="num-col" style="width:15%">VAT Amount</th>
    </tr>
  </thead>
  <tbody>
    ${purchaseRows}
  </tbody>
</table>

<div class="sec-hdr net-due">
  <span>3. Net VAT Due</span>
</div>
<table>
  <thead>
    <tr>
      <th class="box-col" style="width:10%">Box #</th>
      <th style="width:45%">Description</th>
      <th class="num-col" style="width:15%">Amount (Base)</th>
      <th class="num-col" style="width:15%">Adjustment</th>
      <th class="num-col" style="width:15%">VAT Amount</th>
    </tr>
  </thead>
  <tbody>
    ${netRows}
  </tbody>
</table>

</body></html>`;

        const win = window.open('', '_blank', 'width=1000,height=750');
        win.document.write(html);
        win.document.close();
        if (win.document.fonts && win.document.fonts.load) {
            win.document.fonts.load("12px sr_symbol", "\uE900").then(() => {
                setTimeout(() => win.print(), 100);
            }).catch(() => {
                setTimeout(() => win.print(), 400);
            });
        } else {
            setTimeout(() => win.print(), 400);
        }
    }

    async exportVatExcel() {
        if (!this.state.vatData) return;
        try {
            let res;
            if (this.state.showVatModal) {
                res = await this.orm.call(
                    'account.move',
                    'export_analytix_vat_detailed_xlsx',
                    [],
                    {
                        filter_name: 'custom',
                        date_from: this.state.vatFilterFrom || '',
                        date_to: this.state.vatFilterTo || '',
                        company_filter: this.state.vatCompanyFilter || 'all',
                        search_query: this.state.vatSearch || '',
                        sort_col: this.state.vatSortCol || '',
                        sort_dir: this.state.vatSortDir || 'asc'
                    }
                );
            } else {
                const filterName = this.state.selectedVatFilter || 'custom';
                const fromDate = this.state.vatFilterFrom || '';
                const toDate = this.state.vatFilterTo || '';

                res = await this.orm.call(
                    'account.move',
                    'export_analytix_vat_xlsx',
                    [filterName, fromDate, toDate]
                );
            }

            if (res && res.file_content) {
                const byteCharacters = atob(res.file_content);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }
                const byteArray = new Uint8Array(byteNumbers);
                const blob = new Blob([byteArray], {
                    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                });
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = res.filename || 'VAT_Summary.xlsx';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(url);
            } else {
                if (this.notification) {
                    this.notification.add('Could not generate Excel file.', { type: 'danger' });
                }
            }
        } catch (err) {
            console.error('Error exporting VAT XLSX:', err);
            if (this.notification) {
                this.notification.add('Error exporting VAT Excel report.', { type: 'danger' });
            }
        }
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
        if (key === 'specific') {
            if (!this.state.bsSpecificDate) {
                this.state.bsSpecificDate = this.state.bsAsOfIso || this._isoDate(new Date());
            }
            return;
        }
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
        this.state.bsSpecificDate = val;
        this.state.bsAsOfIso      = val;
        this.state.bsCompareIso   = this._subtractYear(val);
        this.state.bsShowDateDrop = false;
        await this._refreshBsData();
    }

    async onBsCompareDateChange(ev) {
        const val = ev.target.value;
        if (!val) return;
        this.state.bsCompareIso = val;
        await this._refreshBsData();
    }

    async toggleBsComparison() {
        this.state.bsCompareMode = !this.state.bsCompareMode;
        if (this.state.bsCompareMode && !this.state.bsCompareIso) {
            this.state.bsCompareIso = this._subtractYear(this.state.bsAsOfIso || this._isoDate(new Date()));
        }
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

    /** Get comparison balance for a specific account inside section */
    bsAccCmp(sectionKey, accId) {
        const c = this.state.bsData && this.state.bsData.compare;
        if (!c || !c[sectionKey] || !c[sectionKey].accounts) return 0;
        const acc = c[sectionKey].accounts.find(a => a.id === accId);
        return acc ? acc.balance : 0;
    }

    /** Calculate percentage change between current balance (c1) and comparison balance (c2) */
    bsChangePct(currVal, compVal) {
        const c1 = Number(currVal) || 0;
        const c2 = Number(compVal) || 0;
        if (c1 === 0 && c2 === 0) return 'n/a';
        if (c2 === 0) return c1 > 0 ? '+100.0%' : '-100.0%';
        const pct = ((c1 - c2) / Math.abs(c2)) * 100;
        const sign = pct > 0 ? '+' : '';
        return `${sign}${pct.toFixed(1)}%`;
    }

    /** Class for change percentage text styling */
    bsChangeClass(currVal, compVal) {
        const str = this.bsChangePct(currVal, compVal);
        if (str === 'n/a') return 'anx-bs-pct-na';
        return str.startsWith('-') ? 'anx-bs-pct-green' : 'anx-bs-pct-red';
    }

    printBsReport() {
        if (!this.state.bsData) return;
        const d = this.state.bsData;
        const sym = d.currency_sym || '';
        const hasCmp = this.state.bsCompareMode && d.compare;
        const isSar = /^(SAR|SR|﷼|ر\.?س\.?|\uE900|)$/i.test(String(sym).trim()) || String(sym).includes('\uE900') || String(sym).includes('');
        const symSpan = isSar ? `<span class="anx-currency-sym" style="font-family:'sr_symbol', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif !important;">&#xe900;</span>` : `<span>${sym}</span>`;
        const fmtN = v => {
            const neg = Number(v) < 0;
            const s = Math.abs(Number(v)).toLocaleString(undefined, { minimumFractionDigits:2, maximumFractionDigits:2 });
            return neg ? `<span style="color:#e53935">-${symSpan} ${s}</span>` : `${symSpan} ${s}`;
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
            + `<style>
  @font-face {
      font-family: "sr_symbol";
      src: url("/iwesabe_sar_currency_symbol/static/src/fonts/sr.ttf") format("truetype"),
           url("data:font/truetype;base64,AAEAAAALAIAAAwAwT1MvMg8SBTgAAAC8AAAAYGNtYXAXVtKIAAABHAAAAFRnYXNwAAAAEAAAAXAAAAAIZ2x5ZjrqSMoAAAF4AAAYDGhlYWQqn96bAAAZhAAAADZoaGVhB1YDxwAAGbwAAAAkaG10eA0oAAAAABngAAAAGGxvY2EMLgwGAAAZ+AAAAA5tYXhwAAkLQQAAGggAAAAgbmFtZZlKCfsAABooAAABhnBvc3QAAwAAAAAbsAAAACAAAwMNAZAABQAAApkCzAAAAI8CmQLMAAAB6wAzAQkAAAAAAAAAAAAAAAAAAAABEAAAAAAAAAAAAAAAAAAAAABAAADpAQPA/8AAQAPAAEAAAAABAAAAAAAAAAAAAAAgAAAAAAADAAAAAwAAABwAAQADAAAAHAADAAEAAAAcAAQAOAAAAAoACAACAAIAAQAg6QH//f//AAAAAAAg6QD//f//AAH/4xcEAAMAAQAAAAAAAAAAAAAAAQAB//8ADwABAAD/wAAAA8AAAgAANzkBAAAAAAEAAP/AAAADwAACAAA3OQEAAAAAAQAA/8AAAAPAAAIAADc5AQAAAAACAAD/wAOUA8AItQs+AAABDgEjDgEVIgYHFAYHDgExOAExMCIxMAYxDgExMCIVIgYxDgEHMAYxIgYxOAExMAYxDgExIgYxDgEHIgYHFCIxMCIVMAYHDgEHDgEHMAYxMAYVIgYPARUcATEiMCMwBgcqASMwBiMGIiMUIjEwBiMiBiMOASMGIgcwIiMwBjEwIiMwIgciBiMiBgcqATEwBiMGIjEwBiMiBiMwIjEiBiMUIiMiBiMiBiMwBiMwIhUqATEqAQciBjEqAQcwIiMiBiMwIjEiBiMqASMGIiMwIjEwIgcwIgcqATEOASMiBgciBiMwBiMiBiMwBiMGIjEGIiMiBgcwIjEUMCMUMDEUBjEOARUwFAccATEwBhUOATEwFDEUBhUOATEwBhUUBjEOAQcUBgcGFBUwBhUUBhUwFDEUBjEcATEGFDEcASMwFBUwFCMcATEUBjEcARUUBhUUBhUcARUGMjMwNjMyNjMyNjEyNjMyNjcwMjM+ATM6ATEwNjMyNjc6ATMyNjMyNjMyNjM+ATMyNjMyNjMwMjM+ATM6ATc6ATU6ATU6ATMyNjE6ATEwMjUyNjMyNjM6ATcwMjMwNhUwNjMwMjcyNjcyNjE6ATcyNjM6ATEwNjMwNjM+ATMyNjMyNjMyNjMyNjMyNjc6ATcwMjcyNjMwMjcwMjM2MjE2MjM+ATE6ATEyNjMwMjM3FRwBIzAGBzAGIw4BIyoBByoBMQYiIzAiIzAGIyIGBzAiMTAiIxQGIzAGIwYiMSIGMSoBIxQiMTAiByoBMSIGIyoBIzAGIyIGIyIGIyoBBzAiByoBByIGIyIGIyIGIyIGMSIGIwYiMTAGIyIGBw4BIwYiByoBIzAGMSIGMSIGIwYiMQYiIzAGIzAiMTAiFSoBIw4BIyoBIzAGMSIGByIGIwYiByIGIyIGByoBBzAiBw4BIw4BFTAUMQYUMTAGFRQGMTAGBzAUBxQGMRQGMTAGMTAGBw4BFQ4BBwYUBzAGMRwBBxwBMRQGFQ4BFRQGFRQGFRQGFTAUFRQGFQYUFRQGFRQWNzYyMzA2MzYyMTYyNzI2MzoBNzI2MzoBNTAyMzA2Mz4BMzA2MTI2Mz4BMTAyNzoBMzA2MzAyNz4BMzAyNzoBMTI0MzAyMzAyMTA2MzYyNzYyMTI2MzYyMzI2MzoBNToBMTI2MToBMTI2MToBMTI2Mz4BMzI2MzI2MzYyMzI2MzoBMTgBNzAyMz4BMzI2MzoBMTYyMzA2MzAyMzA2MzYyMTI2MTAyNzI2MzI2MzAyMTAyNzoBNzI2MzoBNzoBNzA2MzI2MTI2NzI2MzoBNzAyMTYyMTAyMzYyNzI2MzAyMzA2MzoBMTI2MzoBMT4BMzoBNzI2MzoBNzQ2NTA2NTA0MTA0MzQ2NTQ2MTQ2NTQ2MTI0MTA0NTI4MTwBMT4BNTA0MzA0MTA2NTQ2NTA0MzQ2MTA2NzwBNTI0NTQ2NTQ2NTQ2MTQ2NTA2NTwBMTA2NTwBNTY0MTAGIwGsAQMBAQMBCwICAQECAQEBAQEBAQEFAQIBAQEBAQEBAQEBAQIBAQECAgMYAQECAQEBAQIBAgEBBgEBAQEDAgIDAQEDAgIEAQEFAgMDAQIBAgEBAgEBBAIBAwMBAgEBAgEBAQEBAQEDAgIEAQEFAgMDAQIBAgEBAgEBBAIBAwMBAgQBAgMCAQIFAQECAgQCAQECAQEDAQMBAgEBAQEBAgUBAQECAQEBAQEBAQEBAQEBAQEBAQECAQEDBAcBAQUCAwQBAgICCwMDAgEEAQEBAQgDAQEBAQIBAQEBAgEBAQEBAQEBAQEBAQEBAQECAQEBAQIDAQEDAQECAgQCAQQCAgECBAEBAQcBAQQCAQEBAQYCAQIBAQQCAgQBAQMBAQIBAgEBBAIBAQEBAwECAgEBAQECAQECAQQBAQMBAQEBAgEBAQECAQMEAwIDAQMBAgMBAQEGAgMCAgUBAQIBAQIBAgMCAQMBAQQCAQMBBAIBAwECAQMBAgIBAgEDBAEBAQEBAQEBAQYCBAMCBQEBAgEBAgEBAQEBAgEBBAMCAQEFAwMCAgMBAQECAQIBAQECAQUBAQEBAgEBBAEBAQEBAgEDAQEDAQEDAQEDAQEDAQICAQMBBAICAQMEBAYHAwIDAQEBAQICBQEDAgEEAQEBAQECAgECAQIEAQEBAQIBBQQBBAIBBAEBAwECBAQBAQEEAwIGAQMDAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBBQMDAQMBAgMBAwIBAwEDBgIDAQECAgEDAQQGAQICBAIBBgIBAQEBAQEEAwIEAgICAQEBAQEBAgEBAwEBAwEEAwEBAQIBAQMBAQMBAQEBAQEBAQIBBAIEAwIBAgIBAwEDBgEBAgECAwEDAgIDAQIBAgMCBAYBAwEFAwIFAQMDCAECAQMCAQMBAgIBAgEBAgEBAgEBAwECBAECAwEBAwECAgEBAgEBAQECAQIJAQECAQIBAQMBAQMCAgMBBQICAQIBAgECBAECBAECAQMDAQEBAgEFAwIEAQEEAQEBAQECAQMGAwIBAgECAQEBAQEBAgEDAQEBAQEBAQEBAQEBAgEFAQEBAgEBAQEBAQMBAgEBAQEBAwEBAQEBAQEDAQEBAQICAwEBAQEBAQEBAQECAQIBAQMCAgQFAwECBAEBAQIBAQEBAQIBAQECAQICAQEDAQEBAQECAQEBAQEBAQEDAwECAQMCAQMBDQEBAQEBAQEBCwECBQEDAQEDAQMCAgQBAgEBAgEBBQIBAgECAQECAQMCAgUBAgIBAgEDAgQEAQEBAQMCAgMDAgIDAwIBBAEBBAICBAECBgEBAQEBAQECAQEBAgEBAQEBAQIBAgEBAgECAQEBAQEBAgEBAQECAQIBAQMCCgIBAgEBAQkBAgICBgIBAQEDAgIFAQEBAQIBAgEBAQIBAwEBAwECAwEBAQIBAQEBAQECAgQBAQIBAgIBAQEBAwEBAQEBAQEBAQIBAQEBAQEBAQECAQEBAQECAQO/AQIBAQEHAQEBAQEBAQEBAQEBAwECAQEBAQEBAQECAQEBAgEDGAIBAgEBAQEDAQLXa2sBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQIBAQEBAwEBAQIBAQEBAQIEAQEBAQEBAQEDAQEDAQIDAgEBAgMFAgEEAgIDAQEBAQIBAQEBAQIBAgEBAgEDAQIBCAEBAQEDAQIEAQICAQEBAQEBAQEBAQIBAQIBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQFGMRQBAQEBAQEBAQEBAQEBAQEBAQIBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQECAgEBAQEBAQIDAQEBAQIBAQQEAgIEAQEEBQEDAQMBAgEBAQEDAgEEAQEDAgEDAQEBAQICAQQCAgMBAQMCAwEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQECAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQIBAQEBAQEBAQEBAgEBAQEBBwEBAQEEAQEBAQEBAQEFAQECAQIBAgEBBAEBAQEBAQEBAQEBAQQCAgEDAwQBAgEBAgEBAQECAQEBBAEBBQIEFDAaJQEBAQEBAQEBAQEBAQEBAQEBAQMBH09uAwEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQECAQECAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQIBAQIBAQEBAgEBAQEBCwMCAgEBAQEBAQECAQMCAgUCAwQBAgUFAQIBBAQBAQICAQQCBAUBAQIBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBARsbNwEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQECAgMBAQEBAQUCAgEBAgEBAQQCAwMBAgEBAgEBAwEDCwUBAwEBAQEBAgEBBgIBAwECAQgJAQEBAQEBAQEBAQEBAQECAgEBAQEBAQEBAQEBAQEBAQEBAQIBAQEBAQEBAgEBAQEBAgEBAQHGZGIBAQEBAQEEAQEBAQEBAQEBAQEFAQEBAQECAQECAQECBAEFBgYDBQIBAQIBAQIBAQIBAgKkpQEBAQIBAQEBAQEBAQEBAQEBAQIB95VjAfy/AQEBAQEBAQEBAQEBAQEBAQEBAQQBAQEBAQEBAQEBAQEBAQEBAQEBAQIBAQECAQEBAQEBAQEBAgEBAQEBAQEBAQEBAgEBAQICAQEJAQEBAQEBAQEBAQEBAQEBAQEBAgEDAgMDAgEDAgEKBAECAQMCAgMBAgEDDgMCAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQIBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBBgEBAQEBAQEBAQEBAQIBAgEBAQEBAQEFAgIBAgEBAgEBAgQEAgEBAQEBAQIBAgYCAQIBBgIDAQECAgEBAwECCAEAAAEAAP/AAjIDwAAIAAABBzc+ATEwBgcCMAICAQEBAQNIAgIBAQEBAAABAAAAAAAAsksaaV8PPPUACwQAAAAAAOP2zQ8AAAAA4/bNDwAA/8ADlAPAAAAACAACAAAAAAAAAAEAAAPA/8AAAAQAAAAAAAOUAAEAAAAAAAAAAAAAAAAAAAAGBAAAAAAAAAAAAAAAAgAAAAOUAAADlAAAAAAAAAAKABQAHgvyDAYAAAABAAAABgs/AAIAAAAAAAIAAAAAAAAAAAAAAAAAAAAAAAAADgCuAAEAAAAAAAEABwAAAAEAAAAAAAIABwBgAAEAAAAAAAMABwA2AAEAAAAAAAQABwB1AAEAAAAAAAUACwAVAAEAAAAAAAYABwBLAAEAAAAAAAoAGgCKAAMAAQQJAAEADgAHAAMAAQQJAAIADgBnAAMAAQQJAAMADgA9AAMAAQQJAAQADgB8AAMAAQQJAAUAFgAgAAMAAQQJAAYADgBSAAMAAQQJAAoANACkaWNvbW9vbgBpAGMAbwBtAG8AbwBuVmVyc2lvbiAxLjAAVgBlAHIAcwBpAG8AbgAgADEALgAwaWNvbW9vbgBpAGMAbwBtAG8AbwBuUmVndWxhcgBSAGUAZwB1AGwAYQByaWNvbW9vbgBpAGMAbwBtAG8AbwBuRm9udCBnZW5lcmF0ZWQgYnkgSWNvTW9vbi4ARgBvAG4AdAAgAGcAZQBuAGUAcgBhAHQAZQBk ACAAYgB5 ACAASQBjAG8ATQBvAG8AbnAuAAAAAwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==") format("truetype");
      font-weight: normal; font-style: normal; unicode-range: U+E900;
  }
  .anx-currency-sym, .o_sar_symbol, .icon-sr, [class*="sr_symbol"] { font-family: 'sr_symbol', "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important; display: inline-block; }
  body{font-family:'sr_symbol',Inter,sans-serif;padding:32px;}table{width:100%;border-collapse:collapse;}@media print{button{display:none}}</style></head><body>`
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
        if (win.document.fonts && win.document.fonts.load) {
            win.document.fonts.load("12px sr_symbol", "\uE900").then(() => {
                setTimeout(() => win.print(), 100);
            }).catch(() => {
                setTimeout(() => win.print(), 400);
            });
        } else {
            setTimeout(() => win.print(), 400);
        }
    }


    // ── Print P&L Report ─────────────────────────────────────────────
    printPlReport() {
        if (!this.state.plData) return;
        const d   = this.state.plData;
        const sym = d.currency_sym || '';
        const isSar = /^(SAR|SR|﷼|ر\.?س\.?|\uE900|)$/i.test(String(sym).trim()) || String(sym).includes('\uE900') || String(sym).includes('');
        const symSpan = isSar ? `<span class="anx-currency-sym" style="font-family:'sr_symbol', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif !important;">&#xe900;</span>` : `<span>${sym}</span>`;

        const fmtN = v => {
            const neg = Number(v) < 0;
            const s   = Math.abs(Number(v)).toLocaleString(undefined, {
                minimumFractionDigits: 2, maximumFractionDigits: 2
            });
            return neg
                ? `<span style="color:#e53935">-${symSpan} ${s}</span>`
                : `${symSpan} ${s}`;
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
  @font-face {
      font-family: "sr_symbol";
      src: url("/iwesabe_sar_currency_symbol/static/src/fonts/sr.ttf") format("truetype"),
           url("data:font/truetype;base64,AAEAAAALAIAAAwAwT1MvMg8SBTgAAAC8AAAAYGNtYXAXVtKIAAABHAAAAFRnYXNwAAAAEAAAAXAAAAAIZ2x5ZjrqSMoAAAF4AAAYDGhlYWQqn96bAAAZhAAAADZoaGVhB1YDxwAAGbwAAAAkaG10eA0oAAAAABngAAAAGGxvY2EMLgwGAAAZ+AAAAA5tYXhwAAkLQQAAGggAAAAgbmFtZZlKCfsAABooAAABhnBvc3QAAwAAAAAbsAAAACAAAwMNAZAABQAAApkCzAAAAI8CmQLMAAAB6wAzAQkAAAAAAAAAAAAAAAAAAAABEAAAAAAAAAAAAAAAAAAAAABAAADpAQPA/8AAQAPAAEAAAAABAAAAAAAAAAAAAAAgAAAAAAADAAAAAwAAABwAAQADAAAAHAADAAEAAAAcAAQAOAAAAAoACAACAAIAAQAg6QH//f//AAAAAAAg6QD//f//AAH/4xcEAAMAAQAAAAAAAAAAAAAAAQAB//8ADwABAAD/wAAAA8AAAgAANzkBAAAAAAEAAP/AAAADwAACAAA3OQEAAAAAAQAA/8AAAAPAAAIAADc5AQAAAAACAAD/wAOUA8AItQs+AAABDgEjDgEVIgYHFAYHDgExOAExMCIxMAYxDgExMCIVIgYxDgEHMAYxIgYxOAExMAYxDgExIgYxDgEHIgYHFCIxMCIVMAYHDgEHDgEHMAYxMAYVIgYPARUcATEiMCMwBgcqASMwBiMGIiMUIjEwBiMiBiMOASMGIgcwIiMwBjEwIiMwIgciBiMiBgcqATEwBiMGIjEwBiMiBiMwIjEiBiMUIiMiBiMiBiMwBiMwIhUqATEqAQciBjEqAQcwIiMiBiMwIjEiBiMqASMGIiMwIjEwIgcwIgcqATEOASMiBgciBiMwBiMiBiMwBiMGIjEGIiMiBgcwIjEUMCMUMDEUBjEOARUwFAccATEwBhUOATEwFDEUBhUOATEwBhUUBjEOAQcUBgcGFBUwBhUUBhUwFDEUBjEcATEGFDEcASMwFBUwFCMcATEUBjEcARUUBhUUBhUcARUGMjMwNjMyNjMyNjEyNjMyNjcwMjM+ATM6ATEwNjMyNjc6ATMyNjMyNjMyNjM+ATMyNjMyNjMwMjM+ATM6ATc6ATU6ATU6ATMyNjE6ATEwMjUyNjMyNjM6ATcwMjMwNhUwNjMwMjcyNjcyNjE6ATcyNjM6ATEwNjMwNjM+ATMyNjMyNjMyNjMyNjMyNjc6ATcwMjcyNjMwMjcwMjM2MjE2MjM+ATE6ATEyNjMwMjM3FRwBIzAGBzAGIw4BIyoBByoBMQYiIzAiIzAGIyIGBzAiMTAiIxQGIzAGIwYiMSIGMSoBIxQiMTAiByoBMSIGIyoBIzAGIyIGIyIGIyoBBzAiByoBByIGIyIGIyIGIyIGMSIGIwYiMTAGIyIGBw4BIwYiByoBIzAGMSIGMSIGIwYiMQYiIzAGIzAiMTAiFSoBIw4BIyoBIzAGMSIGByIGIwYiByIGIyIGByoBBzAiBw4BIw4BFTAUMQYUMTAGFRQGMTAGBzAUBxQGMRQGMTAGMTAGBw4BFQ4BBwYUBzAGMRwBBxwBMRQGFQ4BFRQGFRQGFRQGFTAUFRQGFQYUFRQGFRQWNzYyMzA2MzYyMTYyNzI2MzoBNzI2MzoBNTAyMzA2Mz4BMzA2MTI2Mz4BMTAyNzoBMzA2MzAyNz4BMzAyNzoBMTI0MzAyMzAyMTA2MzYyNzYyMTI2MzYyMzI2MzoBNToBMTI2MToBMTI2MToBMTI2Mz4BMzI2MzI2MzYyMzI2MzoBMTgBNzAyMz4BMzI2MzoBMTYyMzA2MzAyMzA2MzYyMTI2MTAyNzI2MzI2MzAyMTAyNzoBNzI2MzoBNzoBNzA2MzI2MTI2NzI2MzoBNzAyMTYyMTAyMzYyNzI2MzAyMzA2MzoBMTI2MzoBMT4BMzoBNzI2MzoBNzQ2NTA2NTA0MTA0MzQ2NTQ2MTQ2NTQ2MTI0MTA0NTI4MTwBMT4BNTA0MzA0MTA2NTQ2NTA0MzQ2MTA2NzwBNTI0NTQ2NTQ2NTQ2MTQ2NTA2NTwBMTA2NTwBNTY0MTAGIwGsAQMBAQMBCwICAQECAQEBAQEBAQEFAQIBAQEBAQEBAQEBAQIBAQECAgMYAQECAQEBAQIBAgEBBgEBAQEDAgIDAQEDAgIEAQEFAgMDAQIBAgEBAgEBBAIBAwMBAgEBAgEBAQEBAQEDAgIEAQEFAgMDAQIBAgEBAgEBBAIBAwMBAgQBAgMCAQIFAQECAgQCAQECAQEDAQMBAgEBAQEBAgUBAQECAQEBAQEBAQEBAQEBAQEBAQECAQEDBAcBAQUCAwQBAgICCwMDAgEEAQEBAQgDAQEBAQIBAQEBAgEBAQEBAQEBAQEBAQEBAQECAQEBAQIDAQEDAQECAgQCAQQCAgECBAEBAQcBAQQCAQEBAQYCAQIBAQQCAgQBAQMBAQIBAgEBBAIBAQEBAwECAgEBAQECAQECAQQBAQMBAQEBAgEBAQECAQMEAwIDAQMBAgMBAQEGAgMCAgUBAQIBAQIBAgMCAQMBAQQCAQMBBAIBAwECAQMBAgIBAgEDBAEBAQEBAQEBAQYCBAMCBQEBAgEBAgEBAQEBAgEBBAMCAQEFAwMCAgMBAQECAQIBAQECAQUBAQEBAgEBBAEBAQEBAgEDAQEDAQEDAQEDAQEDAQICAQMBBAICAQMEBAYHAwIDAQEBAQICBQEDAgEEAQEBAQECAgECAQIEAQEBAQIBBQQBBAIBBAEBAwECBAQBAQEEAwIGAQMDAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBBQMDAQMBAgMBAwIBAwEDBgIDAQECAgEDAQQGAQICBAIBBgIBAQEBAQEEAwIEAgICAQEBAQEBAgEBAwEBAwEEAwEBAQIBAQMBAQMBAQEBAQEBAQIBBAIEAwIBAgIBAwEDBgEBAgECAwEDAgIDAQIBAgMCBAYBAwEFAwIFAQMDCAECAQMCAQMBAgIBAgEBAgEBAgEBAwECBAECAwEBAwECAgEBAgEBAQECAQIJAQECAQIBAQMBAQMCAgMBBQICAQIBAgECBAECBAECAQMDAQEBAgEFAwIEAQEEAQEBAQECAQMGAwIBAgECAQEBAQEBAgEDAQEBAQEBAQEBAQEBAgEFAQEBAgEBAQEBAQMBAgEBAQEBAwEBAQEBAQEDAQEBAQICAwEBAQEBAQEBAQECAQIBAQMCAgQFAwECBAEBAQIBAQEBAQIBAQECAQICAQEDAQEBAQECAQEBAQEBAQEDAwECAQMCAQMBDQEBAQEBAQEBCwECBQEDAQEDAQMCAgQBAgEBAgEBBQIBAgECAQECAQMCAgUBAgIBAgEDAgQEAQEBAQMCAgMDAgIDAwIBBAEBBAICBAECBgEBAQEBAQECAQEBAgEBAQEBAQIBAgEBAgECAQEBAQEBAgEBAQECAQIBAQMCCgIBAgEBAQkBAgICBgIBAQEDAgIFAQEBAQIBAgEBAQIBAwEBAwECAwEBAQIBAQEBAQECAgQBAQIBAgIBAQEBAwEBAQEBAQEBAQIBAQEBAQEBAQECAQEBAQECAQO/AQIBAQEHAQEBAQEBAQEBAQEBAwECAQEBAQEBAQECAQEBAgEDGAIBAgEBAQEDAQLXa2sBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQIBAQEBAwEBAQIBAQEBAQIEAQEBAQEBAQEDAQEDAQIDAgEBAgMFAgEEAgIDAQEBAQIBAQEBAQIBAgEBAgEDAQIBCAEBAQEDAQIEAQICAQEBAQEBAQEBAQIBAQIBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQFGMRQBAQEBAQEBAQEBAQEBAQEBAQIBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQECAgEBAQEBAQIDAQEBAQIBAQQEAgIEAQEEBQEDAQMBAgEBAQEDAgEEAQEDAgEDAQEBAQICAQQCAgMBAQMCAwEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQECAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQIBAQEBAQEBAQEBAgEBAQEBBwEBAQEEAQEBAQEBAQEFAQECAQIBAgEBBAEBAQEBAQEBAQEBAQQCAgEDAwQBAgEBAgEBAQECAQEBBAEBBQIEFDAaJQEBAQEBAQEBAQEBAQEBAQEBAQMBH09uAwEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQECAQECAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQIBAQIBAQEBAgEBAQEBCwMCAgEBAQEBAQECAQMCAgUCAwQBAgUFAQIBBAQBAQICAQQCBAUBAQIBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBARsbNwEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQECAgMBAQEBAQUCAgEBAgEBAQQCAwMBAgEBAgEBAwEDCwUBAwEBAQEBAgEBBgIBAwECAQgJAQEBAQEBAQEBAQEBAQECAgEBAQEBAQEBAQEBAQEBAQEBAQIBAQEBAQEBAgEBAQEBAgEBAQHGZGIBAQEBAQEEAQEBAQEBAQEBAQEFAQEBAQECAQECAQECBAEFBgYDBQIBAQIBAQIBAQIBAgKkpQEBAQIBAQEBAQEBAQEBAQEBAQIB95VjAfy/AQEBAQEBAQEBAQEBAQEBAQEBAQQBAQEBAQEBAQEBAQEBAQEBAQEBAQIBAQECAQEBAQEBAQEBAgEBAQEBAQEBAQEBAgEBAQICAQEJAQEBAQEBAQEBAQEBAQEBAQEBAgEDAgMDAgEDAgEKBAECAQMCAgMBAgEDDgMCAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQIBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBBgEBAQEBAQEBAQEBAQIBAgEBAQEBAQEFAgIBAgEBAgEBAgQEAgEBAQEBAQIBAgYCAQIBBgIDAQECAgEBAwECCAEAAAEAAP/AAjIDwAAIAAABBzc+ATEwBgcCMAICAQEBAQNIAgIBAQEBAAABAAAAAAAAsksaaV8PPPUACwQAAAAAAOP2zQ8AAAAA4/bNDwAA/8ADlAPAAAAACAACAAAAAAAAAAEAAAPA/8AAAAQAAAAAAAOUAAEAAAAAAAAAAAAAAAAAAAAGBAAAAAAAAAAAAAAAAgAAAAOUAAADlAAAAAAAAAAKABQAHgvyDAYAAAABAAAABgs/AAIAAAAAAAIAAAAAAAAAAAAAAAAAAAAAAAAADgCuAAEAAAAAAAEABwAAAAEAAAAAAAIABwBgAAEAAAAAAAMABwA2AAEAAAAAAAQABwB1AAEAAAAAAAUACwAVAAEAAAAAAAYABwBLAAEAAAAAAAoAGgCKAAMAAQQJAAEADgAHAAMAAQQJAAIADgBnAAMAAQQJAAMADgA9AAMAAQQJAAQADgB8AAMAAQQJAAUAFgAgAAMAAQQJAAYADgBSAAMAAQQJAAoANACkaWNvbW9vbgBpAGMAbwBtAG8AbwBuVmVyc2lvbiAxLjAAVgBlAHIAcwBpAG8AbgAgADEALgAwaWNvbW9vbgBpAGMAbwBtAG8AbwBuUmVndWxhcgBSAGUAZwB1AGwAYQByaWNvbW9vbgBpAGMAbwBtAG8AbwBuRm9udCBnZW5lcmF0ZWQgYnkgSWNvTW9vbi4ARgBvAG4AdAAgAGcAZQBuAGUAcgBhAHQAZQBk ACAAYgB5 ACAASQBjAG8ATQBvAG8AbnAuAAAAAwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==") format("truetype");
      font-weight: normal; font-style: normal; unicode-range: U+E900;
  }
  .anx-currency-sym, .o_sar_symbol, .icon-sr, [class*="sr_symbol"] { font-family: 'sr_symbol', "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important; display: inline-block; }
  body { font-family: 'sr_symbol', Inter, Arial, sans-serif; padding: 32px; color: #1f2937; }
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
        if (win.document.fonts && win.document.fonts.load) {
            win.document.fonts.load("12px sr_symbol", "\uE900").then(() => {
                setTimeout(() => win.print(), 100);
            }).catch(() => {
                setTimeout(() => win.print(), 400);
            });
        } else {
            setTimeout(() => win.print(), 400);
        }
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
        const MAX_SIZE = 5 * 1024 * 1024; // 5 MB
        if (file && file.size > MAX_SIZE) {
            this.notification.add('The document size is more than 5 MB', { type: 'danger' });
            return;
        }
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
            this.notification.add('Please select Sales Invoice, Purchase Bill, or Expense Bill before creating.', { type: 'warning' });
            return;
        }
        if (!this.state.uploadFile) {
            this.notification.add('No file selected.', { type: 'warning' });
            return;
        }

        this.state.uploadSubmitting = true;
        try {
            const ext = this.state.uploadExtracted;
            let moveType = 'in_invoice';
            if (this.state.uploadDocType === 'invoice') {
                moveType = 'out_invoice';
            } else if (this.state.uploadDocType === 'expense_bill') {
                moveType = 'entry';
            }

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
                        company_type: moveType === 'out_invoice' ? 'person' : 'company',
                    }]);
                    partnerId = Array.isArray(partnerResult) ? partnerResult[0] : partnerResult;
                }
            }

            // ── 2. Build move values ────────────────────────────────────
            const moveVals = {
                move_type:    moveType,
                ref:          ext.ref || false,
                narration:    ext.narration || false,
            };
            if (partnerId) moveVals.partner_id = partnerId;

            if (moveType === 'entry') {
                if (ext.date) moveVals.date = ext.date;
                if (parseFloat(ext.amount) > 0) {
                    const amt = parseFloat(ext.amount);
                    const debitLine = {
                        name: ext.narration || 'Expense Bill Line',
                        debit: amt,
                        credit: 0.0,
                    };
                    if (partnerId) debitLine.partner_id = partnerId;

                    const creditLine = {
                        name: ext.ref || ext.narration || 'Expense Bill',
                        debit: 0.0,
                        credit: amt,
                    };
                    if (partnerId) creditLine.partner_id = partnerId;

                    moveVals.line_ids = [[0, 0, debitLine], [0, 0, creditLine]];
                }
            } else {
                if (ext.date)     moveVals.invoice_date      = ext.date;
                if (ext.due_date) moveVals.invoice_date_due  = ext.due_date;
                if (parseFloat(ext.amount) > 0) {
                    const lineVals = {
                        name: ext.narration || (this.state.uploadDocType === 'invoice' ? 'Sales Invoice line' : 'Purchase Bill line'),
                        quantity: 1,
                        price_unit: parseFloat(ext.amount),
                    };
                    moveVals.invoice_line_ids = [[0, 0, lineVals]];
                }
            }

            // ── 3. Create the move ──────────────────────────────────────
            const moveResult = await this.orm.create('account.move', [moveVals]);
            const moveId = Array.isArray(moveResult) ? moveResult[0] : moveResult;

            // ── 4. Attach the uploaded file ────────────────────────────
            if (this.state.uploadFile.dataUrl) {
                const base64Data = this.state.uploadFile.dataUrl.split(',')[1];
                await this.orm.create('ir.attachment', [{
                    name:      this.state.uploadFile.name,
                    res_model: 'account.move',
                    res_id:    moveId,
                    datas:     base64Data,
                    mimetype:  this.state.uploadFile.type || 'application/octet-stream',
                    type:      'binary',
                }]);
            }

            // ── 5. Show success and open the form ──────────────────────
            const label = this.state.uploadDocType === 'invoice' ? 'Sales Invoice' : (this.state.uploadDocType === 'expense_bill' ? 'Expense Bill Entry' : 'Purchase Bill');
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
        const MAX_SIZE = 5 * 1024 * 1024; // 5 MB
        if (file && file.size > MAX_SIZE) {
            this.notification.add('The document size is more than 5 MB', { type: 'danger' });
            return;
        }
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
        const MAX_SIZE = 5 * 1024 * 1024; // 5 MB
        if (this.state.docUploadFile.size > MAX_SIZE) {
            this.notification.add('The document size is more than 5 MB', { type: 'danger' });
            return;
        }
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
        if ((ev.key === 'Enter' && !ev.shiftKey) || ((ev.ctrlKey || ev.metaKey) && ev.key === 'Enter')) {
            ev.preventDefault();
            const btn = ev.currentTarget.closest('.anx-doc-review-edit-wrap')
                           ?.querySelector('.anx-doc-review-save-btn');
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

    async analyzeAndCreateDocument(ev, overrideAccountId = null, targetDocId = null, overrideLineAccounts = null, overrideTaxAccountId = null) {
        const docId = targetDocId || (ev && ev.currentTarget ? parseInt(ev.currentTarget.dataset.id, 10) : null);
        if (!docId) return;

        // Per-doc lock: only block the same doc from being clicked twice
        if (this.state.analyzingDocIds && this.state.analyzingDocIds[docId]) return;

        if (!this.state.analyzingDocIds) this.state.analyzingDocIds = {};
        this.state.analyzingDocIds[docId] = true;

        // Keep legacy analyzingDocId for any template compatibility
        this.state.analyzingDocId = docId;

        this.notification.add(`Processing document #${docId} with AI…`, { type: "info", sticky: false });
        
        try {
            const kwargs = {};
            if (overrideLineAccounts) {
                kwargs.override_line_accounts = overrideLineAccounts;
            } else if (overrideAccountId) {
                kwargs.override_account_id = parseInt(overrideAccountId, 10);
            }
            if (overrideTaxAccountId) {
                kwargs.override_tax_account_id = parseInt(overrideTaxAccountId, 10);
            }

            const action = await this.orm.call(
                'analytix.document',
                'action_analyze_and_create_entry',
                [[docId]],
                kwargs
            );

            // Intercept requirement for account validation
            if (action && action.requires_account_selection) {
                this.state.accountValData = action;
                const defaultAccId = action.available_accounts && action.available_accounts.length ? String(action.available_accounts[0].id) : '';
                this.state.selectedValidationAccountId = defaultAccId;

                const taxAccs = action.available_tax_accounts || action.available_accounts || [];
                const matchedTaxAcc = taxAccs.find(a => (a.code && a.code.startsWith('131')) || (a.name && a.name.toLowerCase().includes('tax'))) || taxAccs[0];
                this.state.selectedTaxAccountId = matchedTaxAcc ? String(matchedTaxAcc.id) : defaultAccId;

                const map = {};
                (action.unconfigured_lines || []).forEach((line, idx) => {
                    const lineKey = line.index !== undefined ? line.index : idx;
                    map[lineKey] = defaultAccId;
                });
                this.state.lineAccountMap = map;
                this.state.showAccountValidationModal = true;
                return;
            }
            
            this.closeAccountValidationModal();
            this.notification.add(`AI entry created for document #${docId}!`, { type: "success", sticky: false });
            
            // Reload the list to update button state (non-blocking — other docs continue)
            this.fetchDocumentData();
            
            // Open the created move record
            if (action && action.type === 'ir.actions.act_window') {
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
                `AI failed for document #${docId}: ` + errorMsg,
                { type: "danger", sticky: true }
            );
        } finally {
            // Release only THIS doc's lock — other docs are unaffected
            if (this.state.analyzingDocIds) {
                this.state.analyzingDocIds[docId] = false;
            }
            this.state.analyzingDocId = null;
        }
    }

    onDocSelectOne(ev) {
        const docId = parseInt(ev.target.dataset.id, 10);
        if (!docId) return;
        if (!this.state.selectedDocIds) this.state.selectedDocIds = {};
        this.state.selectedDocIds[docId] = ev.target.checked;
    }

    onDocSelectAll(ev) {
        const checked = ev.target.checked;
        const newMap = {};
        (this.filteredDocuments || []).forEach(doc => {
            newMap[doc.id] = checked;
        });
        this.state.selectedDocIds = newMap;
    }

    async analyzeAndCreateBatch() {
        // Collect all selected (checked) doc IDs
        const selectedIds = Object.entries(this.state.selectedDocIds || {})
            .filter(([, checked]) => checked)
            .map(([id]) => parseInt(id, 10))
            .filter(Boolean);

        if (!selectedIds.length) {
            this.notification.add("Please select at least one document to batch process.", { type: "warning" });
            return;
        }

        if (this.state.batchAnalyzing) return;
        this.state.batchAnalyzing = true;

        this.notification.add(
            `Processing ${selectedIds.length} document(s) with AI — please wait...`,
            { type: "info", sticky: false }
        );

        try {
            const action = await this.orm.call(
                'analytix.document',
                'action_batch_analyze_and_create',
                [selectedIds],
                {}
            );

            await this.fetchDocumentData();

            // Uncheck all after processing
            this.state.selectedDocIds = {};

            const summary = action && action.context && action.context.batch_ai_summary;
            this.notification.add(
                summary || `AI batch processing complete! Entries created.`,
                { type: "success", sticky: true }
            );

            if (action && action.type === 'ir.actions.act_window') {
                this.action.doAction(action);
            }
        } catch (e) {
            console.error("Batch AI Analysis error:", e);
            let errorMsg = "";
            if (e && e.data && e.data.message) errorMsg = e.data.message;
            else if (e && e.data && e.data.arguments && e.data.arguments[0]) errorMsg = e.data.arguments[0];
            else if (e && e.message) errorMsg = e.message;
            else errorMsg = String(e) || "Odoo Server Error";
            this.notification.add(
                "Batch AI processing failed: " + errorMsg,
                { type: "danger", sticky: true }
            );
        } finally {
            this.state.batchAnalyzing = false;
        }
    }

    closeAccountValidationModal() {
        this.state.showAccountValidationModal = false;
        this.state.accountValData = null;
        this.state.selectedValidationAccountId = '';
        this.state.selectedTaxAccountId = '';
        this.state.lineAccountMap = {};
    }

    onLineAccountChange(lineIndex, ev) {
        if (!this.state.lineAccountMap) {
            this.state.lineAccountMap = {};
        }
        this.state.lineAccountMap[lineIndex] = ev.target.value;
    }

    onTaxAccountSelect(ev) {
        this.state.selectedTaxAccountId = ev.target.value;
    }

    applyGlobalAccountToAllLines(ev) {
        const val = ev.target.value;
        this.state.selectedValidationAccountId = val;
        if (this.state.lineAccountMap) {
            for (const key in this.state.lineAccountMap) {
                this.state.lineAccountMap[key] = val;
            }
        }
    }

    async confirmAccountValidationAndCreate() {
        const docId = this.state.accountValData ? this.state.accountValData.doc_id : null;
        if (!docId) return;

        const lineMap = this.state.lineAccountMap || {};
        const taxAccId = this.state.selectedTaxAccountId ? parseInt(this.state.selectedTaxAccountId, 10) : null;
        this.state.showAccountValidationModal = false;
        await this.analyzeAndCreateDocument(null, null, docId, lineMap, taxAccId);
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
        if (!this.state.tbData) return;
        const d = this.state.tbData;
        const sym = d.currency_sym || '';
        const isSar = /^(SAR|SR|﷼|ر\.?س\.?|\uE900|)$/i.test(String(sym).trim()) || String(sym).includes('\uE900') || String(sym).includes('');
        const symSpan = isSar ? `<span class="anx-currency-sym" style="font-family:'sr_symbol', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif !important;">&#xe900;</span>` : `<span>${sym}</span>`;

        const fmtN = v => {
            const num = Number(v) || 0;
            const neg = num < 0;
            const s = Math.abs(num).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            return neg ? `<span style="color:#e53935">-${symSpan} ${s}</span>` : `${symSpan} ${s}`;
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
  @font-face {
      font-family: "sr_symbol";
      src: url("/iwesabe_sar_currency_symbol/static/src/fonts/sr.ttf") format("truetype"),
           url("data:font/truetype;base64,AAEAAAALAIAAAwAwT1MvMg8SBTgAAAC8AAAAYGNtYXAXVtKIAAABHAAAAFRnYXNwAAAAEAAAAXAAAAAIZ2x5ZjrqSMoAAAF4AAAYDGhlYWQqn96bAAAZhAAAADZoaGVhB1YDxwAAGbwAAAAkaG10eA0oAAAAABngAAAAGGxvY2EMLgwGAAAZ+AAAAA5tYXhwAAkLQQAAGggAAAAgbmFtZZlKCfsAABooAAABhnBvc3QAAwAAAAAbsAAAACAAAwMNAZAABQAAApkCzAAAAI8CmQLMAAAB6wAzAQkAAAAAAAAAAAAAAAAAAAABEAAAAAAAAAAAAAAAAAAAAABAAADpAQPA/8AAQAPAAEAAAAABAAAAAAAAAAAAAAAgAAAAAAADAAAAAwAAABwAAQADAAAAHAADAAEAAAAcAAQAOAAAAAoACAACAAIAAQAg6QH//f//AAAAAAAg6QD//f//AAH/4xcEAAMAAQAAAAAAAAAAAAAAAQAB//8ADwABAAD/wAAAA8AAAgAANzkBAAAAAAEAAP/AAAADwAACAAA3OQEAAAAAAQAA/8AAAAPAAAIAADc5AQAAAAACAAD/wAOUA8AItQs+AAABDgEjDgEVIgYHFAYHDgExOAExMCIxMAYxDgExMCIVIgYxDgEHMAYxIgYxOAExMAYxDgExIgYxDgEHIgYHFCIxMCIVMAYHDgEHDgEHMAYxMAYVIgYPARUcATEiMCMwBgcqASMwBiMGIiMUIjEwBiMiBiMOASMGIgcwIiMwBjEwIiMwIgciBiMiBgcqATEwBiMGIjEwBiMiBiMwIjEiBiMUIiMiBiMiBiMwBiMwIhUqATEqAQciBjEqAQcwIiMiBiMwIjEiBiMqASMGIiMwIjEwIgcwIgcqATEOASMiBgciBiMwBiMiBiMwBiMGIjEGIiMiBgcwIjEUMCMUMDEUBjEOARUwFAccATEwBhUOATEwFDEUBhUOATEwBhUUBjEOAQcUBgcGFBUwBhUUBhUwFDEUBjEcATEGFDEcASMwFBUwFCMcATEUBjEcARUUBhUUBhUcARUGMjMwNjMyNjMyNjEyNjMyNjcwMjM+ATM6ATEwNjMyNjc6ATMyNjMyNjMyNjM+ATMyNjMyNjMwMjM+ATM6ATc6ATU6ATU6ATMyNjE6ATEwMjUyNjMyNjM6ATcwMjMwNhUwNjMwMjcyNjcyNjE6ATcyNjM6ATEwNjMwNjM+ATMyNjMyNjMyNjMyNjMyNjc6ATcwMjcyNjMwMjcwMjM2MjE2MjM+ATE6ATEyNjMwMjM3FRwBIzAGBzAGIw4BIyoBByoBMQYiIzAiIzAGIyIGBzAiMTAiIxQGIzAGIwYiMSIGMSoBIxQiMTAiByoBMSIGIyoBIzAGIyIGIyIGIyoBBzAiByoBByIGIyIGIyIGIyIGMSIGIwYiMTAGIyIGBw4BIwYiByoBIzAGMSIGMSIGIwYiMQYiIzAGIzAiMTAiFSoBIw4BIyoBIzAGMSIGByIGIwYiByIGIyIGByoBBzAiBw4BIw4BFTAUMQYUMTAGFRQGMTAGBzAUBxQGMRQGMTAGMTAGBw4BFQ4BBwYUBzAGMRwBBxwBMRQGFQ4BFRQGFRQGFRQGFTAUFRQGFQYUFRQGFRQWNzYyMzA2MzYyMTYyNzI2MzoBNzI2MzoBNTAyMzA2Mz4BMzA2MTI2Mz4BMTAyNzoBMzA2MzAyNz4BMzAyNzoBMTI0MzAyMzAyMTA2MzYyNzYyMTI2MzYyMzI2MzoBNToBMTI2MToBMTI2MToBMTI2Mz4BMzI2MzI2MzYyMzI2MzoBMTgBNzAyMz4BMzI2MzoBMTYyMzA2MzAyMzA2MzYyMTI2MTAyNzI2MzI2MzAyMTAyNzoBNzI2MzoBNzoBNzA2MzI2MTI2NzI2MzoBNzAyMTYyMTAyMzYyNzI2MzAyMzA2MzoBMTI2MzoBMT4BMzoBNzI2MzoBNzQ2NTA2NTA0MTA0MzQ2NTQ2MTQ2NTQ2MTI0MTA0NTI4MTwBMT4BNTA0MzA0MTA2NTQ2NTA0MzQ2MTA2NzwBNTI0NTQ2NTQ2NTQ2MTQ2NTA2NTwBMTA2NTwBNTY0MTAGIwGsAQMBAQMBCwICAQECAQEBAQEBAQEFAQIBAQEBAQEBAQEBAQIBAQECAgMYAQECAQEBAQIBAgEBBgEBAQEDAgIDAQEDAgIEAQEFAgMDAQIBAgEBAgEBBAIBAwMBAgEBAgEBAQEBAQEDAgIEAQEFAgMDAQIBAgEBAgEBBAIBAwMBAgQBAgMCAQIFAQECAgQCAQECAQEDAQMBAgEBAQEBAgUBAQECAQEBAQEBAQEBAQEBAQEBAQECAQEDBAcBAQUCAwQBAgICCwMDAgEEAQEBAQgDAQEBAQIBAQEBAgEBAQEBAQEBAQEBAQEBAQECAQEBAQIDAQEDAQECAgQCAQQCAgECBAEBAQcBAQQCAQEBAQYCAQIBAQQCAgQBAQMBAQIBAgEBBAIBAQEBAwECAgEBAQECAQECAQQBAQMBAQEBAgEBAQECAQMEAwIDAQMBAgMBAQEGAgMCAgUBAQIBAQIBAgMCAQMBAQQCAQMBBAIBAwECAQMBAgIBAgEDBAEBAQEBAQEBAQYCBAMCBQEBAgEBAgEBAQEBAgEBBAMCAQEFAwMCAgMBAQECAQIBAQECAQUBAQEBAgEBBAEBAQEBAgEDAQEDAQEDAQEDAQEDAQICAQMBBAICAQMEBAYHAwIDAQEBAQICBQEDAgEEAQEBAQECAgECAQIEAQEBAQIBBQQBBAIBBAEBAwECBAQBAQEEAwIGAQMDAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBBQMDAQMBAgMBAwIBAwEDBgIDAQECAgEDAQQGAQICBAIBBgIBAQEBAQEEAwIEAgICAQEBAQEBAgEBAwEBAwEEAwEBAQIBAQMBAQMBAQEBAQEBAQIBBAIEAwIBAgIBAwEDBgEBAgECAwEDAgIDAQIBAgMCBAYBAwEFAwIFAQMDCAECAQMCAQMBAgIBAgEBAgEBAgEBAwECBAECAwEBAwECAgEBAgEBAQECAQIJAQECAQIBAQMBAQMCAgMBBQICAQIBAgECBAECBAECAQMDAQEBAgEFAwIEAQEEAQEBAQECAQMGAwIBAgECAQEBAQEBAgEDAQEBAQEBAQEBAQEBAgEFAQEBAgEBAQEBAQMBAgEBAQEBAwEBAQEBAQEDAQEBAQICAwEBAQEBAQEBAQECAQIBAQMCAgQFAwECBAEBAQIBAQEBAQIBAQECAQICAQEDAQEBAQECAQEBAQEBAQEDAwECAQMCAQMBDQEBAQEBAQEBCwECBQEDAQEDAQMCAgQBAgEBAgEBBQIBAgECAQECAQMCAgUBAgIBAgEDAgQEAQEBAQMCAgMDAgIDAwIBBAEBBAICBAECBgEBAQEBAQECAQEBAgEBAQEBAQIBAgEBAgECAQEBAQEBAgEBAQECAQIBAQMCCgIBAgEBAQkBAgICBgIBAQEDAgIFAQEBAQIBAgEBAQIBAwEBAwECAwEBAQIBAQEBAQECAgQBAQIBAgIBAQEBAwEBAQEBAQEBAQIBAQEBAQEBAQECAQEBAQECAQO/AQIBAQEHAQEBAQEBAQEBAQEBAwECAQEBAQEBAQECAQEBAgEDGAIBAgEBAQEDAQLXa2sBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQIBAQEBAwEBAQIBAQEBAQIEAQEBAQEBAQEDAQEDAQIDAgEBAgMFAgEEAgIDAQEBAQIBAQEBAQIBAgEBAgEDAQIBCAEBAQEDAQIEAQICAQEBAQEBAQEBAQIBAQIBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQFGMRQBAQEBAQEBAQEBAQEBAQEBAQIBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQECAgEBAQEBAQIDAQEBAQIBAQQEAgIEAQEEBQEDAQMBAgEBAQEDAgEEAQEDAgEDAQEBAQICAQQCAgMBAQMCAwEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQECAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQIBAQEBAQEBAQEBAgEBAQEBBwEBAQEEAQEBAQEBAQEFAQECAQIBAgEBBAEBAQEBAQEBAQEBAQQCAgEDAwQBAgEBAgEBAQECAQEBBAEBBQIEFDAaJQEBAQEBAQEBAQEBAQEBAQEBAQMBH09uAwEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQECAQECAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQIBAQIBAQEBAgEBAQEBCwMCAgEBAQEBAQECAQMCAgUCAwQBAgUFAQIBBAQBAQICAQQCBAUBAQIBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBARsbNwEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAgEBAQEBAQEBAQECAgMBAQEBAQUCAgEBAgEBAQQCAwMBAgEBAgEBAwEDCwUBAwEBAQEBAgEBBgIBAwECAQgJAQEBAQEBAQEBAQEBAQECAgEBAQEBAQEBAQEBAQEBAQEBAQIBAQEBAQEBAgEBAQEBAgEBAQHGZGIBAQEBAQEEAQEBAQEBAQEBAQEFAQEBAQECAQECAQECBAEFBgYDBQIBAQIBAQIBAQIBAgKkpQEBAQIBAQEBAQEBAQEBAQEBAQIB95VjAfy/AQEBAQEBAQEBAQEBAQEBAQEBAQQBAQEBAQEBAQEBAQEBAQEBAQEBAQIBAQECAQEBAQEBAQEBAgEBAQEBAQEBAQEBAgEBAQICAQEJAQEBAQEBAQEBAQEBAQEBAQEBAgEDAgMDAgEDAgEKBAECAQMCAgMBAgEDDgMCAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQIBAQEBAgEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBBgEBAQEBAQEBAQEBAQIBAgEBAQEBAQEFAgIBAgEBAgEBAgQEAgEBAQEBAQIBAgYCAQIBBgIDAQECAgEBAwECCAEAAAEAAP/AAjIDwAAIAAABBzc+ATEwBgcCMAICAQEBAQNIAgIBAQEBAAABAAAAAAAAsksaaV8PPPUACwQAAAAAAOP2zQ8AAAAA4/bNDwAA/8ADlAPAAAAACAACAAAAAAAAAAEAAAPA/8AAAAQAAAAAAAOUAAEAAAAAAAAAAAAAAAAAAAAGBAAAAAAAAAAAAAAAAgAAAAOUAAADlAAAAAAAAAAKABQAHgvyDAYAAAABAAAABgs/AAIAAAAAAAIAAAAAAAAAAAAAAAAAAAAAAAAADgCuAAEAAAAAAAEABwAAAAEAAAAAAAIABwBgAAEAAAAAAAMABwA2AAEAAAAAAAQABwB1AAEAAAAAAAUACwAVAAEAAAAAAAYABwBLAAEAAAAAAAoAGgCKAAMAAQQJAAEADgAHAAMAAQQJAAIADgBnAAMAAQQJAAMADgA9AAMAAQQJAAQADgB8AAMAAQQJAAUAFgAgAAMAAQQJAAYADgBSAAMAAQQJAAoANACkaWNvbW9vbgBpAGMAbwBtAG8AbwBuVmVyc2lvbiAxLjAAVgBlAHIAcwBpAG8AbgAgADEALgAwaWNvbW9vbgBpAGMAbwBtAG8AbwBuUmVndWxhcgBSAGUAZwB1AGwAYQByaWNvbW9vbgBpAGMAbwBtAG8AbwBuRm9udCBnZW5lcmF0ZWQgYnkgSWNvTW9vbi4ARgBvAG4AdAAgAGcAZQBuAGUAcgBhAHQAZQBk ACAAYgB5 ACAASQBjAG8ATQBvAG8AbnAuAAAAAwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==") format("truetype");
      font-weight: normal; font-style: normal; unicode-range: U+E900;
  }
  .anx-currency-sym, .o_sar_symbol, .icon-sr, [class*="sr_symbol"] { font-family: 'sr_symbol', "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important; display: inline-block; }
  body { font-family: 'sr_symbol', Inter, sans-serif; padding: 32px; color: #1f2937; }
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
        if (win.document.fonts && win.document.fonts.load) {
            win.document.fonts.load("12px sr_symbol", "\uE900").then(() => {
                setTimeout(() => win.print(), 100);
            }).catch(() => {
                setTimeout(() => win.print(), 400);
            });
        } else {
            setTimeout(() => win.print(), 400);
        }
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

    async toggleChatPopup(ev) {
        if (this.preventChatClick) return;
        this.state.showChatPopup = !this.state.showChatPopup;
        if (this.state.showChatPopup) {
            try {
                if (this.store && this.store.fetchStoreData) {
                    await this.store.fetchStoreData("init_messaging");
                }
            } catch (e) {}
            if (this.state.activeThreadId) {
                const thread = this.activeThread;
                if (thread) {
                    try { await thread.fetchMessages(); } catch (e) {}
                }
            }
            this.startChatPolling();
        } else {
            this.stopChatPolling();
        }
    }

    closeChatPopup() {
        this.state.showChatPopup = false;
    }

    getChatPopupStyle() {
        const btnSize = 58;
        const popupWidth = 380;
        const popupHeight = 520;
        
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

    focusChatSearch() {
        this.clearChatSearch();
        setTimeout(() => {
            const inp = document.querySelector('.anx-chat-search-input');
            if (inp) inp.focus();
        }, 50);
    }

    async startVoiceCall(ev) {
        if (ev) ev.stopPropagation();
        const thread = this.activeThread;
        if (!thread) return;
        this.notification.add(`Starting voice call with ${thread.displayName || 'user'}...`, { type: "info", sticky: false });
        try {
            if (this.store && this.store.rtc) {
                await this.store.rtc.toggleCall({ thread, video: false });
            } else if (this.env.services && this.env.services['mail.rtc']) {
                await this.env.services['mail.rtc'].toggleCall({ thread, video: false });
            } else if (thread.startCall) {
                await thread.startCall({ video: false });
            } else {
                this.openFullDiscuss();
            }
        } catch (e) {
            console.error("Voice call error:", e);
            this.openFullDiscuss();
        }
    }

    async startVideoCall(ev) {
        if (ev) ev.stopPropagation();
        const thread = this.activeThread;
        if (!thread) return;
        this.notification.add(`Starting video call with ${thread.displayName || 'user'}...`, { type: "info", sticky: false });
        try {
            if (this.store && this.store.rtc) {
                await this.store.rtc.toggleCall({ thread, video: true });
            } else if (this.env.services && this.env.services['mail.rtc']) {
                await this.env.services['mail.rtc'].toggleCall({ thread, video: true });
            } else if (thread.startCall) {
                await thread.startCall({ video: true });
            } else {
                this.openFullDiscuss();
            }
        } catch (e) {
            console.error("Video call error:", e);
            this.openFullDiscuss();
        }
    }

    async onAttachFileToChat(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file || !this.activeThread) return;
        const thread = this.activeThread;
        const inputEl = ev.target;
        try {
            const reader = new FileReader();
            reader.onload = async () => {
                try {
                    const base64 = reader.result.split(',')[1];
                    const res = await this.orm.create('ir.attachment', [{
                        name: file.name,
                        datas: base64,
                        res_model: thread.model || 'discuss.channel',
                        res_id: thread.id,
                    }]);
                    const attachmentId = Array.isArray(res) ? res[0] : res;
                    if (attachmentId) {
                        const attObj = (this.store['ir.attachment'] && this.store['ir.attachment'].insert) 
                            ? this.store['ir.attachment'].insert({ id: attachmentId, name: file.name })
                            : { id: attachmentId, name: file.name };
                        await thread.post('', {
                            attachments: [attObj],
                        });
                        await this.loadThreadMessages(thread);
                        setTimeout(() => {
                            if (this.messageFeedRef && this.messageFeedRef.el) {
                                this.messageFeedRef.el.scrollTop = this.messageFeedRef.el.scrollHeight;
                            }
                        }, 50);
                    }
                } catch (e) {
                    console.error("Error creating attachment:", e);
                    this.notification.add("Failed to send attachment: " + (e.message || ''), { type: 'danger' });
                } finally {
                    if (inputEl) inputEl.value = "";
                }
            };
            reader.readAsDataURL(file);
        } catch (e) {
            console.error("Attachment reader error:", e);
            if (inputEl) inputEl.value = "";
            this.notification.add("Failed to send attachment: " + (e.message || ''), { type: 'danger' });
        }
    }

    async updateUnreadCount() {
        try {
            let total = 0;

            const threadsMap = new Map();
            const addThread = (t) => {
                if (t && t.id && !threadsMap.has(t.localId || `${t.model}_${t.id}`)) {
                    threadsMap.set(t.localId || `${t.model}_${t.id}`, t);
                }
            };

            if (this.store) {
                if (Array.isArray(this.store.menuThreads)) {
                    this.store.menuThreads.forEach(addThread);
                }
                if (Array.isArray(this.store.allChannels)) {
                    this.store.allChannels.forEach(addThread);
                }
                if (this.store.Thread && this.store.Thread.records) {
                    Object.values(this.store.Thread.records).forEach(addThread);
                }

                for (const thread of threadsMap.values()) {
                    const memberCount = thread.self_member_id ? (thread.self_member_id.message_unread_counter ?? thread.self_member_id.message_unread_counter_ui) : null;
                    if (typeof memberCount === 'number' && memberCount > 0) {
                        total += memberCount;
                    } else if (typeof thread.unreadCounter === 'number' && thread.unreadCounter > 0) {
                        total += thread.unreadCounter;
                    } else if (typeof thread.message_unread_counter === 'number' && thread.message_unread_counter > 0) {
                        total += thread.message_unread_counter;
                    } else if (thread.isUnread) {
                        total += 1;
                    }
                }

                if (this.store.discuss && typeof this.store.discuss.unreadCounter === 'number' && !isNaN(this.store.discuss.unreadCounter)) {
                    if (this.store.discuss.unreadCounter > total) {
                        total = this.store.discuss.unreadCounter;
                    }
                }
            }
            this.state.chatUnreadCount = total;
        } catch (e) {
            console.error("Error in updateUnreadCount:", e);
        }
    }

    get discussUnreadCount() {
        return this.state.chatUnreadCount || 0;
    }

    openFullDiscuss() {
        const thread = this.activeThread;
        this.state.showChatPopup = false;
        this.action.doAction(
            {
                type: "ir.actions.client",
                tag: "mail.action_discuss",
            },
            {
                additionalContext: thread && thread.id ? { active_id: thread.id } : {},
            }
        );
    }

    stripHtml(html) {
        if (!html) return "";
        return html.replace(/<[^>]*>/g, "");
    }

    async loadThreadMessages(thread) {
        if (!thread || !thread.id) return;
        if (!this.threadMessagesCache) {
            this.threadMessagesCache = {};
        }
        try {
            await thread.fetchMessages();
        } catch (e) {}
        try {
            const rawMsgs = await this.orm.searchRead(
                'mail.message',
                [['model', '=', 'discuss.channel'], ['res_id', '=', thread.id]],
                ['id', 'body', 'date', 'author_id', 'message_type', 'attachment_ids'],
                { order: 'id asc', limit: 200 }
            );
            if (rawMsgs && rawMsgs.length > 0) {
                const currentUserId = this.store.self?.main_user_id?.id || false;
                const currentPartnerId = this.store.self?.id || false;

                const allAttIds = [];
                rawMsgs.forEach(m => {
                    if (Array.isArray(m.attachment_ids) && m.attachment_ids.length > 0) {
                        allAttIds.push(...m.attachment_ids);
                    }
                });

                const attachmentsMap = new Map();
                if (allAttIds.length > 0) {
                    try {
                        const rawAtts = await this.orm.searchRead(
                            'ir.attachment',
                            [['id', 'in', allAttIds]],
                            ['id', 'name', 'mimetype', 'file_size']
                        );
                        rawAtts.forEach(att => {
                            attachmentsMap.set(att.id, att);
                        });
                    } catch (e) {}
                }

                const formatted = rawMsgs.map(m => {
                    const authorId = Array.isArray(m.author_id) ? m.author_id[0] : m.author_id;
                    const authorName = Array.isArray(m.author_id) ? m.author_id[1] : 'User';
                    const isSelf = (authorId === currentPartnerId) || (authorId === currentUserId);
                    const msgAtts = Array.isArray(m.attachment_ids)
                        ? m.attachment_ids.map(attId => attachmentsMap.get(attId)).filter(Boolean)
                        : [];

                    return {
                        id: m.id,
                        body: m.body,
                        date: m.date,
                        author: { id: authorId, name: authorName },
                        isSelfAuthored: isSelf,
                        message_type: m.message_type,
                        attachments: msgAtts,
                    };
                }).filter(m => m.message_type !== 'notification');

                this.threadMessagesCache[thread.id] = formatted;

                this.store.insert({
                    'mail.message': rawMsgs.map(m => ({
                        id: m.id,
                        body: m.body,
                        date: m.date,
                        author_id: Array.isArray(m.author_id) ? m.author_id[0] : m.author_id,
                        message_type: m.message_type,
                        thread: { id: thread.id, model: 'discuss.channel' },
                    }))
                });
            }
        } catch (e) {
            console.error("Error loading thread messages:", e);
        }
    }

    async openThread(thread) {
        if (!thread) return;
        this.state.activeThreadId = thread.localId;
        if (thread.markAsRead) {
            try { await thread.markAsRead(); } catch (e) {}
        }
        if (thread.self_member_id) {
            thread.self_member_id.message_unread_counter = 0;
            thread.self_member_id.message_unread_counter_ui = 0;
        }
        if (typeof thread.unreadCounter === 'number') {
            thread.unreadCounter = 0;
        }
        if (typeof thread.message_unread_counter === 'number') {
            thread.message_unread_counter = 0;
        }
        thread.isUnread = false;
        this.updateUnreadCount();
        await this.loadThreadMessages(thread);
        this.startChatPolling();
        setTimeout(() => {
            if (this.messageFeedRef && this.messageFeedRef.el) {
                this.messageFeedRef.el.scrollTop = this.messageFeedRef.el.scrollHeight;
            }
        }, 50);
    }

    async onClickChatThread(ev) {
        const id = parseInt(ev.currentTarget.dataset.threadId);
        const model = ev.currentTarget.dataset.threadModel || 'discuss.channel';
        if (id && model) {
            let thread = this.store.Thread.get({ id, model });
            if (!thread && this.store.menuThreads) {
                thread = this.store.menuThreads.find(t => t.id === id && (t.model || 'discuss.channel') === model);
            }
            if (thread) {
                await this.openThread(thread);
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
                    await this.loadThreadMessages(thread);
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
                   this.store.menuThreads?.find(t => t.localId === this.state.activeThreadId) ||
                   this.store.allChannels?.find(t => t.localId === this.state.activeThreadId);
        }
        return null;
    }

    isImageAttachment(att) {
        if (!att) return false;
        const name = (att.name || att.filename || att.displayName || '').toLowerCase();
        const type = (att.mimetype || '').toLowerCase();
        return type.startsWith('image/') || name.endsWith('.png') || name.endsWith('.jpg') || name.endsWith('.jpeg') || name.endsWith('.gif') || name.endsWith('.webp');
    }

    getAttIconClass(att) {
        if (!att) return 'fa-file-o text-muted';
        const name = (att.name || att.filename || att.displayName || '').toLowerCase();
        if (name.endsWith('.pdf')) return 'fa-file-pdf-o text-danger';
        if (name.endsWith('.doc') || name.endsWith('.docx')) return 'fa-file-word-o text-primary';
        if (name.endsWith('.xls') || name.endsWith('.xlsx')) return 'fa-file-excel-o text-success';
        if (name.endsWith('.zip') || name.endsWith('.rar')) return 'fa-file-archive-o text-warning';
        if (name.endsWith('.txt')) return 'fa-file-text-o text-info';
        return 'fa-file-o text-primary';
    }

    get activeThreadMessages() {
        const thread = this.activeThread;
        if (!thread || !thread.id) return [];

        const msgMap = new Map();

        const extractAtts = (m, existing) => {
            const rawList = [];
            if (existing && existing.attachments && existing.attachments.length) {
                rawList.push(...existing.attachments);
            }
            if (m) {
                if (Array.isArray(m.attachments) && m.attachments.length) {
                    rawList.push(...m.attachments);
                } else if (m.attachments && m.attachments.length) {
                    rawList.push(...Array.from(m.attachments));
                }
                if (Array.isArray(m.attachment_ids) && m.attachment_ids.length) {
                    rawList.push(...m.attachment_ids);
                }
            }
            const attMap = new Map();
            for (const item of rawList) {
                if (!item) continue;
                const id = typeof item === 'object' ? (item.id || item) : item;
                if (!id) continue;
                if (!attMap.has(id) || (typeof item === 'object' && item.name)) {
                    const name = typeof item === 'object' ? (item.name || item.filename || item.displayName || (`File_${id}`)) : `File_${id}`;
                    const mimetype = typeof item === 'object' ? (item.mimetype || '') : '';
                    attMap.set(id, { id, name, mimetype });
                }
            }
            return Array.from(attMap.values());
        };

        if (this.threadMessagesCache && this.threadMessagesCache[thread.id]) {
            for (const m of this.threadMessagesCache[thread.id]) {
                if (m && m.id) {
                    msgMap.set(m.id, {
                        ...m,
                        attachments: extractAtts(m, null)
                    });
                }
            }
        }

        if (thread.messages) {
            for (const m of thread.messages) {
                if (m && m.id) {
                    const existing = msgMap.get(m.id);
                    const mergedAtts = extractAtts(m, existing);
                    msgMap.set(m.id, {
                        ...(existing || {}),
                        ...m,
                        attachments: mergedAtts
                    });
                }
            }
        }

        if (this.store && this.store["mail.message"] && this.store["mail.message"].records) {
            for (const m of Object.values(this.store["mail.message"].records)) {
                if (m && m.id) {
                    const matchesThread = (m.thread && m.thread.eq && m.thread.eq(thread)) ||
                                          (m.model === thread.model && m.res_id === thread.id) ||
                                          (m.res_id === thread.id && (!m.model || m.model === 'discuss.channel'));
                    if (matchesThread) {
                        const existing = msgMap.get(m.id);
                        const mergedAtts = extractAtts(m, existing);
                        msgMap.set(m.id, {
                            ...(existing || {}),
                            ...m,
                            attachments: mergedAtts
                        });
                    }
                }
            }
        }

        let msgs = Array.from(msgMap.values());
        msgs = msgs.filter(m => !m.isNotification);
        msgs.sort((a, b) => (a.id || 0) - (b.id || 0));
        return msgs;
    }

    formatMessageTime(message) {
        if (!message || !message.date) return "";
        if (typeof message.date === 'string') {
            try {
                const parts = message.date.split(' ');
                if (parts.length > 1) {
                    const timeParts = parts[1].split(':');
                    return `${timeParts[0]}:${timeParts[1]}`;
                }
            } catch (e) {}
        }
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

    formatMessageBody(body) {
        if (!body) return "";
        let str = typeof body === 'string' ? body : String(body);
        if (str.includes('&lt;') || str.includes('&gt;')) {
            try {
                const doc = new DOMParser().parseFromString(str, 'text/html');
                str = doc.body.textContent || str;
            } catch (e) {
                const txt = document.createElement('textarea');
                txt.innerHTML = str;
                str = txt.value;
            }
        }
        str = str.replace(/^\s*<p[^>]*>/gi, '')
                 .replace(/<\/p>\s*$/gi, '')
                 .replace(/<p[^>]*>/gi, '<br/>')
                 .replace(/<\/p>/gi, '');
        str = str.replace(/^\s*<div[^>]*>/gi, '')
                 .replace(/<\/div>\s*$/gi, '')
                 .replace(/<div[^>]*>/gi, '<br/>')
                 .replace(/<\/div>/gi, '');

        return markup(str);
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
            await this.loadThreadMessages(thread);
            setTimeout(() => {
                if (this.messageFeedRef && this.messageFeedRef.el) {
                    this.messageFeedRef.el.scrollTop = this.messageFeedRef.el.scrollHeight;
                }
            }, 50);
        } catch (e) {
            console.error("Error posting message:", e);
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
        if (!this.store) return [];
        const threadsMap = new Map();
        if (this.store.menuThreads) {
            for (const t of this.store.menuThreads) {
                if (t && t.id) threadsMap.set(t.localId || `${t.model}_${t.id}`, t);
            }
        }
        if (this.store.Thread && this.store.Thread.records) {
            for (const t of Object.values(this.store.Thread.records)) {
                if (t && t.id && t.model === 'discuss.channel') {
                    threadsMap.set(t.localId || `${t.model}_${t.id}`, t);
                }
            }
        }
        let list = Array.from(threadsMap.values());
        const term = (this.state.chatSearch || '').trim().toLowerCase();
        if (term) {
            list = list.filter(t => (t.displayName || t.name || '').toLowerCase().includes(term));
        }
        return list;
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
                const chat = await this.store.getChat({ partnerId: result.partnerId, userId: result.id });
                if (chat) {
                    await this.openThread(chat);
                }
            } else {
                // Open an existing channel
                let thread = this.store.Thread.get({ id: result.id, model: 'discuss.channel' });
                if (!thread) {
                    await this.store.fetchChannel(result.id);
                    thread = this.store.Thread.get({ id: result.id, model: 'discuss.channel' });
                }
                if (thread) {
                    await this.openThread(thread);
                }
            }
        } catch (e) {
            console.error('Error opening chat:', e);
        }
    }

}

registry.category("actions").add("analytix_finance_dashboard", AnalytixFinanceDashboard);
