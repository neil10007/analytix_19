/** @odoo-module **/

import { Component, useState, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

export class AiChatWidget extends Component {
    static template = "chatting_ai.AiChatWidget";
    
    setup() {
        this.actionService = useService("action");
        this.state = useState({
            isOpen: false,
            messages: [],
            inputValue: "",
            isLoading: false
        });
    }

    toggleChat() {
        this.state.isOpen = !this.state.isOpen;
    }

    onKeydown(ev) {
        if (ev.key === "Enter") {
            this.sendMessage();
        }
    }

    clickSuggestion(text) {
        this.state.inputValue = text;
        this.sendMessage();
    }

    onChatClick(ev) {
        const link = ev.target.closest("a");
        if (!link) return;

        const href = link.getAttribute("href");
        if (!href) return;

        // Check if it's an Odoo form view link like /web#id=123&model=account.move&view_type=form
        if (href.includes("/web#") || href.includes("model=")) {
            ev.preventDefault();
            ev.stopPropagation();

            const modelMatch = href.match(/model=([^&]+)/);
            const idMatch = href.match(/id=([^&]+)/);

            if (modelMatch && idMatch) {
                const model = modelMatch[1];
                const resId = parseInt(idMatch[1]);

                this.actionService.doAction({
                    type: 'ir.actions.act_window',
                    res_model: model,
                    res_id: resId,
                    views: [[false, 'form']],
                    target: 'current',
                });
                return;
            }
        }

        // Check if it's a PDF report link like /report/pdf/...
        if (href.includes("/report/pdf/")) {
            ev.preventDefault();
            ev.stopPropagation();
            window.open(href, '_blank');
            return;
        }
    }

    async sendMessage() {
        const text = this.state.inputValue.trim();
        if (text) {
            this.state.messages.push({ role: 'user', content: text });
            this.state.inputValue = "";
            this.state.isLoading = true;
            
            try {
                // Pass the history up to the current message
                const history = this.state.messages.slice(0, -1);
                
                const response = await rpc("/chatting_ai/ask", {
                    message: text,
                    history: history
                });
                
                if (response.error) {
                    this.state.messages.push({ role: 'assistant', content: `Error: ${response.error}` });
                } else if (response.reply) {
                    // Safely convert markdown bold, links, and line breaks to HTML
                    let html = response.reply
                        .replace(/&/g, '&amp;')
                        .replace(/</g, '&lt;')
                        .replace(/>/g, '&gt;')
                        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
                        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, label, url) => {
                            const isPdf = url.includes('/report/pdf');
                            const icon = isPdf ? 'fa-file-pdf-o' : 'fa-external-link';
                            const btnClass = isPdf ? 'btn-outline-primary' : 'btn-outline-secondary';
                            return `<a href="${url}" class="btn btn-sm ${btnClass} shadow-sm text-decoration-none my-1 me-1 d-inline-block" style="font-weight:600;"><i class="fa ${icon} me-1"></i>${label}</a>`;
                        })
                        .replace(/\n/g, '<br/>');
                    
                    this.state.messages.push({ role: 'assistant', content: response.reply, htmlContent: markup(html) });

                    // Automatically open the created invoice/bill form view in Odoo!
                    if (response.action) {
                        this.actionService.doAction(response.action);
                    }
                }
            } catch (error) {
                this.state.messages.push({ role: 'assistant', content: "An error occurred while connecting to the server." });
            } finally {
                this.state.isLoading = false;
            }
        }
    }
}

registry.category("main_components").add("chatting_ai.AiChatWidget", {
    Component: AiChatWidget,
});
