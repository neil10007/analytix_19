/** @odoo-module **/
import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

export class AccountingCustomDashboard extends Component {
    static template = "accounting_19_dashboard.DashboardMain";
    static props = {};

    setup() {
        this.actionService = useService("action");
        this.state = useState({
            loading: true,
            company: "",
            currency: "",
            today: new Date().toLocaleDateString("en-GB", {
                weekday: "long", year: "numeric", month: "long", day: "numeric",
            }),
            total_receivable: 0,
            overdue_receivable: 0,
            total_payable: 0,
            overdue_payable: 0,
            total_bank: 0,
            bank_accounts: [],
            revenue_this_month: 0,
            revenue_last_month: 0,
            revenue_change: 0,
            expense_this_month: 0,
            expense_tax_mtd: 0,
            gross_profit: 0,
            net_profit: 0,
            unpaid_invoices: 0,
            unpaid_bills: 0,
            monthly_chart: [],
            recent_invoices: [],
            recent_bills: [],
            showBills: false,
            balance_sheet: {
                assets:      { current: [], non_current: [], total_current: 0, total_non_current: 0, total: 0 },
                liabilities: { current: [], non_current: [], total_current: 0, total_non_current: 0, total: 0 },
                equity:      { items: [], total: 0 },
            },
            bsActiveSection: 'assets',
        });

        this._chartInstance = null;
        this._animFrames = [];
        this._canvas = null;
        this._animCtx = null;
        this._particles = [];
        this._animRunning = false;

        onMounted(() => {
            this._loadGoogleFonts();
            this.loadData();
            this._startParticles();
        });

        onWillUnmount(() => {
            this._animRunning = false;
            this._animFrames.forEach(cancelAnimationFrame);
            if (this._chartInstance) {
                this._chartInstance.destroy();
                this._chartInstance = null;
            }
        });
    }

    // ── Toggle invoice/bill table ───────────────────────────────────────────
    showInvoicesTab() { this.state.showBills = false; }
    showBillsTab()    { this.state.showBills = true;  }

    // ── Google Fonts ───────────────────────────────────────────────────────
    _loadGoogleFonts() {
        if (document.getElementById("acc_dash_inter_font")) return;
        const link = document.createElement("link");
        link.id = "acc_dash_inter_font";
        link.rel = "stylesheet";
        link.href = "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600&display=swap";
        document.head.appendChild(link);
    }

    // ── Particle Canvas ────────────────────────────────────────────────────
    _startParticles() {
        const canvas = document.getElementById("acc_particle_canvas");
        if (!canvas) return;
        this._canvas = canvas;
        this._animCtx = canvas.getContext("2d");
        this._resizeCanvas();
        this._initParticles();
        this._animRunning = true;
        this._animateParticles();

        window.addEventListener("resize", () => this._resizeCanvas());
    }

    _resizeCanvas() {
        if (!this._canvas) return;
        const root = this._canvas.parentElement;
        this._canvas.width  = root.offsetWidth;
        this._canvas.height = root.scrollHeight || root.offsetHeight;
    }

    _initParticles() {
        this._particles = [];
        const count = 55;
        for (let i = 0; i < count; i++) {
            this._particles.push({
                x: Math.random() * (this._canvas ? this._canvas.width : 1200),
                y: Math.random() * (this._canvas ? this._canvas.height : 800),
                r: Math.random() * 1.8 + 0.4,
                dx: (Math.random() - 0.5) * 0.35,
                dy: (Math.random() - 0.5) * 0.35,
                alpha: Math.random() * 0.4 + 0.1,
                color: Math.random() > 0.5 ? "99,202,183" : Math.random() > 0.5 ? "79,156,243" : "167,139,250",
            });
        }
    }

    _animateParticles() {
        if (!this._animRunning || !this._animCtx || !this._canvas) return;
        const ctx = this._animCtx;
        const W = this._canvas.width;
        const H = this._canvas.height;

        ctx.clearRect(0, 0, W, H);

        // Draw connections
        for (let i = 0; i < this._particles.length; i++) {
            for (let j = i + 1; j < this._particles.length; j++) {
                const dx = this._particles[i].x - this._particles[j].x;
                const dy = this._particles[i].y - this._particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 130) {
                    const alpha = (1 - dist / 130) * 0.12;
                    ctx.beginPath();
                    ctx.strokeStyle = `rgba(99,202,183,${alpha})`;
                    ctx.lineWidth = 0.5;
                    ctx.moveTo(this._particles[i].x, this._particles[i].y);
                    ctx.lineTo(this._particles[j].x, this._particles[j].y);
                    ctx.stroke();
                }
            }
        }

        // Draw particles
        this._particles.forEach((p) => {
            p.x += p.dx;
            p.y += p.dy;
            if (p.x < 0 || p.x > W) p.dx *= -1;
            if (p.y < 0 || p.y > H) p.dy *= -1;

            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${p.color},${p.alpha})`;
            ctx.fill();
        });

        const frame = requestAnimationFrame(() => this._animateParticles());
        this._animFrames.push(frame);
    }

    // ── Animated Number Counter ────────────────────────────────────────────
    _animateCounter(elementId, targetValue, duration = 1200, prefix = "") {
        const el = document.getElementById(elementId);
        if (!el) return;
        const start = performance.now();
        const startVal = 0;

        const step = (now) => {
            const elapsed = now - start;
            const progress = Math.min(elapsed / duration, 1);
            // Ease-out cubic
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = startVal + (targetValue - startVal) * eased;

            el.textContent = prefix + Number(current).toLocaleString("en-US", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            });

            if (progress < 1) {
                const frame = requestAnimationFrame(step);
                this._animFrames.push(frame);
            }
        };
        requestAnimationFrame(step);
    }

    _animateCountInt(elementId, targetValue, duration = 900) {
        const el = document.getElementById(elementId);
        if (!el) return;
        const start = performance.now();
        const step = (now) => {
            const elapsed = now - start;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            el.textContent = Math.round(targetValue * eased);
            if (progress < 1) {
                const frame = requestAnimationFrame(step);
                this._animFrames.push(frame);
            }
        };
        requestAnimationFrame(step);
    }

    // ── Navigation handlers ───────────────────────────────────────────────
    openReceivables() {
        // Opens Chart of Accounts filtered by Receivable type (like screenshot)
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: 'Chart of Accounts – Receivable',
            res_model: 'account.account',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: [['account_type', '=', 'asset_receivable']],
            context: { search_default_account_type: 'asset_receivable' },
        });
    }

    openPayables() {
        // Opens Chart of Accounts filtered by Payable type
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: 'Chart of Accounts – Payable',
            res_model: 'account.account',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: [['account_type', '=', 'liability_payable']],
            context: { search_default_account_type: 'liability_payable' },
        });
    }

    openBank() {
        // Opens Chart of Accounts filtered by bank/cash account types
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: 'Chart of Accounts – Bank &amp; Cash',
            res_model: 'account.account',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: [['account_type', 'in', ['asset_cash', 'liability_credit_card']]],
        });
    }

    openRevenue() {
        // Opens Chart of Accounts filtered by income accounts
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: 'Chart of Accounts – Income',
            res_model: 'account.account',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: [['account_type', 'in', ['income', 'income_other']]],
        });
    }

    openExpenses() {
        // Opens Chart of Accounts filtered by expense accounts
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: 'Chart of Accounts – Expenses',
            res_model: 'account.account',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: [['account_type', 'in', ['expense', 'expense_depreciation', 'expense_direct_cost']]],
        });
    }

    openBalanceSheet() {
        // Open Odoo's native Balance Sheet report
        this.actionService.doAction('account_reports.action_account_report_bs');
    }

    setBsSectionAssets()      { this.state.bsActiveSection = 'assets'; }
    setBsSectionLiabilities() { this.state.bsActiveSection = 'liabilities'; }
    setBsSectionEquity()      { this.state.bsActiveSection = 'equity'; }

    openPending() {
        // Opens unpaid invoices and bills list
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: 'Pending – Unpaid Documents',
            res_model: 'account.move',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: [['move_type', 'in', ['out_invoice', 'in_invoice']], ['state', '=', 'posted'], ['payment_state', 'in', ['not_paid', 'partial']]],
        });
    }

    // ── Helpers ────────────────────────────────────────────────────────────
    formatAmount(val) {
        if (val === undefined || val === null) return "0.00";
        return Number(val).toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    overduePercent(overdue, total) {
        if (!total || total === 0) return 5;
        return Math.max(5, Math.min(Math.round((overdue / total) * 100), 100));
    }

    // ── Data Load ──────────────────────────────────────────────────────────
    async loadData() {
        this.state.loading = true;
        try {
            const data = await rpc("/accounting_dashboard/data", {});
            Object.assign(this.state, data, { loading: false });
            setTimeout(() => {
                this._resizeCanvas();          // re-measure after content renders
                this._runCounterAnimations(data);
                this._drawChart();
                this._animateProgressBars();
            }, 150);
        } catch (e) {
            console.error("Accounting Dashboard – load error:", e);
            this.state.loading = false;
        }
    }

    _runCounterAnimations(data) {
        const sym = data.currency || "";
        this._animateCounter("kpi_receivable_val", data.total_receivable, 1400);
        this._animateCounter("kpi_payable_val", data.total_payable, 1400);
        this._animateCounter("kpi_bank_val", data.total_bank, 1400);
        this._animateCounter("hdr_bank_val", data.total_bank, 1600);
        this._animateCounter("kpi_revenue_val", data.revenue_this_month, 1400);
        this._animateCounter("kpi_expense_val",     data.expense_this_month, 1400);
        this._animateCounter("kpi_expense_tax_val", data.expense_tax_mtd,    1200);
        this._animateCounter("kpi_gross_profit_val",data.gross_profit,        1600);
        this._animateCounter("kpi_net_profit_val",  data.net_profit,          1800);
        this._animateCountInt("kpi_unpaid_inv", data.unpaid_invoices, 900);
        this._animateCountInt("kpi_unpaid_bill", data.unpaid_bills, 900);
        // Balance Sheet totals
        if (data.balance_sheet) {
            const bs = data.balance_sheet;
            this._animateCounter("bs_total_assets",       bs.assets.total,      1600);
            this._animateCounter("bs_total_liabilities",  bs.liabilities.total, 1600);
            this._animateCounter("bs_total_equity",       bs.equity.total,      1600);
        }
    }

    _animateProgressBars() {
        const bars = document.querySelectorAll(".acc_bar_animated");
        bars.forEach((bar) => {
            const target = bar.dataset.width || "0";
            setTimeout(() => {
                bar.style.width = target + "%";
            }, 200);
        });
    }

    // ── Chart ──────────────────────────────────────────────────────────────
    _drawChart() {
        const canvas = document.getElementById("incomeExpenseChart");
        if (!canvas) return;
        if (this._chartInstance) {
            this._chartInstance.destroy();
            this._chartInstance = null;
        }
        const chartData = this.state.monthly_chart || [];
        const labels = chartData.map((d) => d.month);
        const incomeData = chartData.map((d) => d.income);
        const expenseData = chartData.map((d) => d.expense);

        const loader = () => this._renderChart(canvas, labels, incomeData, expenseData);

        if (typeof Chart === "undefined") {
            const script = document.createElement("script");
            script.src = "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js";
            script.onload = loader;
            document.head.appendChild(script);
        } else {
            loader();
        }
    }

    _renderChart(canvas, labels, incomeData, expenseData) {
        const ctx = canvas.getContext("2d");

        const incomeGrad = ctx.createLinearGradient(0, 0, 0, 280);
        incomeGrad.addColorStop(0, "rgba(99,202,183,0.9)");
        incomeGrad.addColorStop(1, "rgba(99,202,183,0.05)");

        const expenseGrad = ctx.createLinearGradient(0, 0, 0, 280);
        expenseGrad.addColorStop(0, "rgba(255,107,107,0.9)");
        expenseGrad.addColorStop(1, "rgba(255,107,107,0.05)");

        this._chartInstance = new Chart(ctx, {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        label: "Income",
                        data: incomeData,
                        backgroundColor: incomeGrad,
                        borderColor: "#63cab7",
                        borderWidth: 1.5,
                        borderRadius: 10,
                        borderSkipped: false,
                    },
                    {
                        label: "Expense",
                        data: expenseData,
                        backgroundColor: expenseGrad,
                        borderColor: "#ff6b6b",
                        borderWidth: 1.5,
                        borderRadius: 10,
                        borderSkipped: false,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 1200, easing: "easeOutQuart" },
                plugins: {
                    legend: {
                        labels: {
                            color: "#94a3b8",
                            font: { family: "'Inter', sans-serif", size: 12, weight: "600" },
                            usePointStyle: true,
                            pointStyleWidth: 8,
                            padding: 20,
                        },
                    },
                    tooltip: {
                        backgroundColor: "rgba(10,14,26,0.97)",
                        titleColor: "#f1f5f9",
                        bodyColor: "#94a3b8",
                        borderColor: "rgba(99,202,183,0.4)",
                        borderWidth: 1,
                        padding: 14,
                        cornerRadius: 12,
                        callbacks: {
                            label: (context) => {
                                const sym = this.state.currency || "";
                                return `  ${context.dataset.label}: ${sym}${Number(context.raw).toLocaleString("en-US", { minimumFractionDigits: 2 })}`;
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        grid: { color: "rgba(255,255,255,0.03)", lineWidth: 1 },
                        border: { color: "rgba(255,255,255,0.06)" },
                        ticks: { color: "#64748b", font: { family: "'Inter', sans-serif", size: 11 } },
                    },
                    y: {
                        grid: { color: "rgba(255,255,255,0.03)", lineWidth: 1 },
                        border: { color: "rgba(255,255,255,0.06)" },
                        ticks: {
                            color: "#64748b",
                            font: { family: "'Inter', sans-serif", size: 11 },
                            callback: (v) => {
                                if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + "M";
                                if (v >= 1_000) return (v / 1_000).toFixed(0) + "K";
                                return v;
                            },
                        },
                    },
                },
            },
        });
    }
}

registry.category("actions").add("accounting_custom_dashboard", AccountingCustomDashboard);
