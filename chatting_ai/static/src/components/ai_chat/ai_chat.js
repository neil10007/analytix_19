/** @odoo-module **/

import { Component, useState, markup, useRef, onPatched } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

function formatMarkdown(rawText) {
    if (!rawText) return "";

    let lines = rawText.replace(/\r\n/g, '\n').split('\n');
    let inTable = false;
    let tableLines = [];
    let processedLines = [];

    const renderTable = (tLines) => {
        if (tLines.length < 2) return tLines.join('\n');
        const headerRow = tLines[0].trim();
        const headerCols = headerRow.split('|')
            .map(c => c.trim())
            .filter((c, i, a) => !(i === 0 && c === '') && !(i === a.length - 1 && c === ''));
        
        let html = '<div class="ai_table_wrapper"><table class="table table-sm mb-0 ai_chat_table">';
        html += '<thead><tr>';
        for (const col of headerCols) {
            html += `<th>${col}</th>`;
        }
        html += '</tr></thead><tbody>';

        for (let i = 2; i < tLines.length; i++) {
            const row = tLines[i].trim();
            if (!row || !row.includes('|')) continue;
            const cols = row.split('|')
                .map(c => c.trim())
                .filter((c, idx, a) => !(idx === 0 && c === '') && !(idx === a.length - 1 && c === ''));
            html += '<tr>';
            for (const col of cols) {
                html += `<td>${col}</td>`;
            }
            html += '</tr>';
        }
        html += '</tbody></table></div>';
        return html;
    };

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const isTableLine = line.trim().startsWith('|') && line.trim().endsWith('|');
        if (isTableLine) {
            inTable = true;
            tableLines.push(line);
        } else {
            if (inTable) {
                processedLines.push(renderTable(tableLines));
                tableLines = [];
                inTable = false;
            }
            
            let trimmed = line.trim();
            // Headings
            if (trimmed.startsWith('#### ')) {
                processedLines.push(`<div class="ai_chat_heading_4"><i class="fa fa-caret-right me-1 text-primary"></i>${trimmed.substring(5)}</div>`);
            } else if (trimmed.startsWith('### ')) {
                processedLines.push(`<div class="ai_chat_heading_3"><i class="fa fa-dot-circle-o me-2 text-primary"></i>${trimmed.substring(4)}</div>`);
            } else if (trimmed.startsWith('## ')) {
                processedLines.push(`<div class="ai_chat_heading_2"><i class="fa fa-bookmark me-2 text-primary"></i>${trimmed.substring(3)}</div>`);
            } else if (trimmed.startsWith('# ')) {
                processedLines.push(`<div class="ai_chat_heading_1">${trimmed.substring(2)}</div>`);
            }
            // Numbered list items: "1. Item" or "1) Item"
            else if (/^\d+[\.\)]\s+/.test(trimmed)) {
                const match = trimmed.match(/^(\d+)[\.\)]\s+(.*)/);
                if (match) {
                    const num = match[1];
                    const content = match[2];
                    processedLines.push(`<div class="ai_numbered_step"><span class="ai_step_badge">${num}</span><div class="ai_step_content">${content}</div></div>`);
                } else {
                    processedLines.push(line);
                }
            }
            // Bullet items: "- Item", "* Item", "• Item"
            else if (/^[-*•]\s+/.test(trimmed)) {
                const content = trimmed.replace(/^[-*•]\s+/, '');
                processedLines.push(`<div class="ai_bullet_line"><span class="ai_bullet_dot"></span><div class="ai_bullet_text">${content}</div></div>`);
            }
            // Blockquotes
            else if (trimmed.startsWith('> ')) {
                processedLines.push(`<div class="ai_callout_card"><i class="fa fa-info-circle me-2 text-primary"></i>${trimmed.substring(2)}</div>`);
            } else {
                processedLines.push(line);
            }
        }
    }
    if (inTable) {
        processedLines.push(renderTable(tableLines));
    }

    let parsed = processedLines.join('\n');

    // Bold surrounding links: **[Label](url)** -> [Label](url)
    parsed = parsed.replace(/\*\*\[([^\]]+)\]\(([^)]+)\)\*\*/g, '[$1]($2)');

    // Bold formatting: **text**
    parsed = parsed.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Italics formatting: *text* (when not part of a tag or bullet)
    parsed = parsed.replace(/(^|[^\*])\*([^\*]+)\*([^\*]|$)/g, '$1<em>$2</em>$3');

    // Inline code: `code`
    parsed = parsed.replace(/`([^`]+)`/g, '<code class="ai_inline_code">$1</code>');

    // Links and Interactive Entity Tags: [Label](url)
    parsed = parsed.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, label, url) => {
        const cleanUrl = url.trim();
        const cleanLabel = label.replace(/<\/?strong>/g, '');
        
        // Entity click-to-ask link (e.g. ask:Show me all invoices for ABC)
        if (cleanUrl.startsWith('ask:') || cleanUrl.startsWith('action:ask:')) {
            const prompt = cleanUrl.replace(/^(action:)?ask:/, '');
            return `<a href="${cleanUrl}" class="o_ai_entity_tag text-decoration-none" data-ask="${prompt}" title="Click to ask AI for all details and invoices"><i class="fa fa-bolt me-1 text-primary"></i><strong>${cleanLabel}</strong></a>`;
        }

        const isPdf = cleanUrl.includes('/report/pdf');
        const icon = isPdf ? 'fa-file-pdf-o' : 'fa-external-link';
        const btnClass = isPdf ? 'ai_btn_pdf' : 'ai_btn_action';
        return `<a href="${cleanUrl}" class="btn btn-sm ${btnClass} ai_action_link text-decoration-none my-1 me-1 d-inline-flex align-items-center"><i class="fa ${icon} me-1"></i>${cleanLabel}</a>`;
    });

    // Metric and status highlights (only applied to text nodes outside HTML tags)
    const parts = parsed.split(/(<[^>]+>)/g);
    for (let i = 0; i < parts.length; i++) {
        if (!parts[i].startsWith('<')) {
            // Currency amounts (e.g. 24,892.58 SAR, SAR 24,892.58, $500, etc.)
            parts[i] = parts[i].replace(/\b(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?\s*(?:SAR|USD|EUR|GBP|AED|QAR|KWD|OMR|BHD))\b/gi, '<span class="ai_metric_chip">$1</span>');
            parts[i] = parts[i].replace(/\b((?:SAR|USD|EUR|AED)\s*\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\b/gi, '<span class="ai_metric_chip">$1</span>');
            
            // Overdue highlights
            parts[i] = parts[i].replace(/\b(\d+\s+(?:currently\s+)?overdue)\b/gi, '<span class="ai_badge_danger">$1</span>');
            parts[i] = parts[i].replace(/\b(overdue)\b/gi, '<span class="ai_badge_danger">$1</span>');

            // Payment status highlights
            parts[i] = parts[i].replace(/\b(not paid|unpaid)\b/gi, '<span class="ai_badge_warning">$1</span>');
            parts[i] = parts[i].replace(/\b(fully paid|paid)\b/gi, '<span class="ai_badge_success">$1</span>');
        }
    }
    parsed = parts.join('');

    // Line breaks
    parsed = parsed.replace(/\n/g, '<br/>');

    // Clean up excessive <br/> around styled blocks
    parsed = parsed.replace(/(<br\/>)+(<div class="ai_)/g, '$2');
    parsed = parsed.replace(/(<\/div>)(<br\/>)+/g, '$1');
    parsed = parsed.replace(/(<br\/>)+(<div class="table-responsive)/g, '$2');

    return parsed;
}

export class AiChatWidget extends Component {
    static template = "chatting_ai.AiChatWidget";
    
    setup() {
        this.actionService = useService("action");
        this.chatBodyRef = useRef("chatBody");
        this.state = useState({
            isOpen: false,
            messages: [],
            inputValue: "",
            isLoading: false
        });

        onPatched(() => {
            this.scrollToBottom();
        });
    }

    toggleChat() {
        this.state.isOpen = !this.state.isOpen;
        if (this.state.isOpen) {
            setTimeout(() => this.scrollToBottom(), 100);
        }
    }

    clearChat() {
        this.state.messages = [];
    }

    scrollToBottom() {
        if (this.chatBodyRef && this.chatBodyRef.el) {
            this.chatBodyRef.el.scrollTop = this.chatBodyRef.el.scrollHeight;
        }
    }

    onKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.sendMessage();
        }
    }

    clickSuggestion(text) {
        this.state.inputValue = text;
        this.sendMessage();
    }

    copyMessage(index) {
        const msg = this.state.messages[index];
        if (!msg || !msg.content) return;

        const textToCopy = msg.content;
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(textToCopy).then(() => {
                msg.copied = true;
                setTimeout(() => { msg.copied = false; }, 2000);
            }).catch(() => {
                this._fallbackCopy(textToCopy, msg);
            });
        } else {
            this._fallbackCopy(textToCopy, msg);
        }
    }

    _fallbackCopy(text, msg) {
        const textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand("copy");
            msg.copied = true;
            setTimeout(() => { msg.copied = false; }, 2000);
        } catch (e) {
            console.error("Copy failed", e);
        }
        document.body.removeChild(textarea);
    }

    onChatClick(ev) {
        const link = ev.target.closest("a");
        if (!link) return;

        const href = link.getAttribute("href");
        if (!href) return;

        // Check if it's an interactive entity ask link (e.g. ask:Show me all invoices for ABC)
        if (href.startsWith("ask:") || href.startsWith("action:ask:") || link.dataset.ask) {
            ev.preventDefault();
            ev.stopPropagation();
            const prompt = link.dataset.ask || href.replace(/^(action:)?ask:/, '');
            this.clickSuggestion(decodeURIComponent(prompt));
            return;
        }

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
            const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            this.state.messages.push({ role: 'user', content: text, time: timeStr });
            this.state.inputValue = "";
            this.state.isLoading = true;
            this.scrollToBottom();
            
            try {
                // Pass the history up to the current message
                const history = this.state.messages.slice(0, -1);
                
                const response = await rpc("/chatting_ai/ask", {
                    message: text,
                    history: history
                });
                
                const replyTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                if (response.error) {
                    this.state.messages.push({ role: 'assistant', content: `Error: ${response.error}`, time: replyTime });
                } else if (response.reply) {
                    const html = formatMarkdown(response.reply);
                    this.state.messages.push({ 
                        role: 'assistant', 
                        content: response.reply, 
                        htmlContent: markup(html),
                        time: replyTime,
                        copied: false
                    });

                    // Automatically open document/window if action returned
                    if (response.action) {
                        this.actionService.doAction(response.action);
                    }
                }
            } catch (error) {
                this.state.messages.push({ 
                    role: 'assistant', 
                    content: "An error occurred while connecting to the server.",
                    time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                });
            } finally {
                this.state.isLoading = false;
                setTimeout(() => this.scrollToBottom(), 50);
            }
        }
    }
}

registry.category("main_components").add("chatting_ai.AiChatWidget", {
    Component: AiChatWidget,
});
