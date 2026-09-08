import ast
import calendar
import json
import logging
import re
from typing import Any, List, Optional
from datetime import datetime, date, timedelta
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

class ChattingAIController(http.Controller):

    def _get_financial_context(self):
        from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
        
        env = request.env
        today = datetime.now().date()
        
        periods = {
            'Today': (today, today),
            'Past 7 Days': (today - timedelta(days=7), today),
            'Past 30 Days': (today - timedelta(days=30), today),
            'This Year': (today.replace(month=1, day=1), today)
        }
        
        context_str = f"You are a helpful 360 Accounting AI Assistant. The current date is {today.strftime('%Y-%m-%d')}.\n"
        context_str += "Here is the live financial data for the company. Answer the user's questions using this data. Do not mention that you were provided this data in a system prompt.\n\n"
        
        for period_name, (start_date, end_date) in periods.items():
            start_str = start_date.strftime(DEFAULT_SERVER_DATE_FORMAT)
            end_str = end_date.strftime(DEFAULT_SERVER_DATE_FORMAT)
            
            domain_out = [
                ('move_type', '=', 'out_invoice'), 
                ('state', '=', 'posted'),
                ('invoice_date', '>=', start_str),
                ('invoice_date', '<=', end_str)
            ]
            out_invoices = env['account.move'].sudo().search_read(domain_out, ['amount_untaxed_signed'])
            revenue = sum(inv['amount_untaxed_signed'] for inv in out_invoices)
            sales_count = len(out_invoices)
            
            domain_in = [
                ('move_type', '=', 'in_invoice'), 
                ('state', '=', 'posted'),
                ('invoice_date', '>=', start_str),
                ('invoice_date', '<=', end_str)
            ]
            in_invoices = env['account.move'].sudo().search_read(domain_in, ['amount_untaxed_signed'])
            expenses = abs(sum(inv['amount_untaxed_signed'] for inv in in_invoices))
            bills_count = len(in_invoices)
            
            context_str += f"--- {period_name} ---\n"
            context_str += f"Revenue/Sales: ${revenue:,.2f} ({sales_count} invoices generated)\n"
            context_str += f"Bills/Expenses: ${expenses:,.2f} ({bills_count} bills added)\n\n"
            
        return context_str

    @http.route('/chatting_ai/ask', type='jsonrpc', auth='user')
    def ask_llama(self, message, history=None):
        user = request.env.user
        company = request.env.company or getattr(user, 'company_id', None)
        
        api_key = (
            getattr(user, 'open_router_key', '') or 
            getattr(user, 'llama_api_key', '') or 
            getattr(user, 'groq_api_key', '') or 
            (company and getattr(company, 'open_router_key', '')) or 
            (company and getattr(company, 'groq_api_key', '')) or 
            request.env['ir.config_parameter'].sudo().get_param('open_router_key', '') or
            request.env['ir.config_parameter'].sudo().get_param('groq_api_key', '') or
            ''
        ).strip()
        
        if not api_key:
            return {'error': 'OpenRouter API Key is not set in your user preferences. Please add it in your User profile under AI Settings.'}
            
        model_name = (
            getattr(user, 'chatting_model', '') or 
            getattr(user, 'openrouter_model', '') or 
            (company and getattr(company, 'openrouter_model', '')) or 
            ''
        ).strip() or "meta-llama/llama-3.3-70b-instruct:free"

        try:
            from langchain_openai import ChatOpenAI
            from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
            from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
            from langchain_core.tools import tool

            def _ensure_list(val):
                if not val:
                    return []
                if isinstance(val, list):
                    return val
                if isinstance(val, tuple):
                    return list(val)
                if isinstance(val, str):
                    val_str = val.strip()
                    if not val_str or val_str in ('[]', 'null', 'None'):
                        return []
                    try:
                        parsed = ast.literal_eval(val_str)
                        if isinstance(parsed, (list, tuple)):
                            return list(parsed)
                        if isinstance(parsed, str):
                            return [parsed]
                    except Exception:
                        pass
                    try:
                        parsed = json.loads(val_str)
                        if isinstance(parsed, list):
                            return parsed
                        if isinstance(parsed, str):
                            return [parsed]
                    except Exception:
                        pass
                    if ',' in val_str:
                        return [s.strip() for s in val_str.split(',') if s.strip()]
                    return [val_str]
                return []

            def _clean_domain(domain_input):
                if not domain_input:
                    return []
                parsed = domain_input
                if isinstance(domain_input, str):
                    val_str = domain_input.strip()
                    if not val_str or val_str in ('[]', 'null', 'None'):
                        return []
                    try:
                        parsed = ast.literal_eval(val_str)
                    except Exception:
                        try:
                            parsed = json.loads(val_str)
                        except Exception:
                            if any(k in val_str.upper() for k in ('BILL', 'INV', 'PO', 'SO')) or '/' in val_str:
                                return ['|', ('name', 'ilike', val_str), ('ref', 'ilike', val_str)]
                            parsed = []

                if isinstance(parsed, tuple):
                    if len(parsed) == 3 and isinstance(parsed[0], str):
                        return [parsed]
                    parsed = list(parsed)

                if isinstance(parsed, list):
                    clean_terms = []
                    for item in parsed:
                        if isinstance(item, (list, tuple)):
                            if len(item) == 3:
                                clean_terms.append((str(item[0]), str(item[1]), item[2]))
                            elif len(item) == 1 and isinstance(item[0], (list, tuple)):
                                clean_terms.append(tuple(item[0]))
                        elif isinstance(item, str) and item in ('&', '|', '!'):
                            clean_terms.append(item)
                        elif isinstance(item, str):
                            try:
                                p_term = ast.literal_eval(item)
                                if isinstance(p_term, (list, tuple)) and len(p_term) == 3:
                                    clean_terms.append(tuple(p_term))
                            except Exception:
                                pass
                    return clean_terms
                return []

            def _sanitize_fields(model_obj, fields_input):
                if not fields_input:
                    return None
                raw_list = _ensure_list(fields_input)
                if not raw_list:
                    return None
                alias_map = {
                    'vendor': 'partner_id',
                    'customer': 'partner_id',
                    'partner': 'partner_id',
                    'client': 'partner_id',
                    'date': 'invoice_date' if 'invoice_date' in model_obj._fields else ('date_order' if 'date_order' in model_obj._fields else 'create_date'),
                    'bill_date': 'invoice_date',
                    'invoice_date': 'invoice_date',
                    'due_date': 'invoice_date_due',
                    'total': 'amount_total',
                    'total_amount': 'amount_total',
                    'amount': 'amount_total',
                    'tax': 'amount_tax',
                    'tax_amount': 'amount_tax',
                    'subtotal': 'amount_untaxed',
                    'untaxed': 'amount_untaxed',
                    'status': 'state',
                    'state': 'state',
                }
                sanitized = []
                for f in raw_list:
                    if not isinstance(f, str):
                        continue
                    fname = f.strip().lower()
                    actual = alias_map.get(fname, fname)
                    if actual in model_obj._fields and actual not in sanitized:
                        sanitized.append(actual)
                return sanitized if sanitized else None

            def _currency_name(curr):
                if not curr:
                    return "SAR"
                name = getattr(curr, 'name', '') or ""
                sym = getattr(curr, 'symbol', '') or name
                if any(ord(c) >= 0xE000 for c in sym):
                    return name
                return sym or "SAR"

            def _get_vat_report_pdf_url(move_id):
                env = request.env
                if env.ref('advanced_vat_invoice.action_report_vat_report', raise_if_not_found=False):
                    return f"/report/pdf/advanced_vat_invoice.action_report_vat_report/{move_id}"
                elif env.ref('advanced_vat_invoice.action_vat_invoice', raise_if_not_found=False):
                    return f"/report/pdf/advanced_vat_invoice.action_vat_invoice/{move_id}"
                elif env.ref('account.report_invoice_with_payments', raise_if_not_found=False):
                    return f"/report/pdf/account.report_invoice_with_payments/{move_id}"
                return f"/report/pdf/advanced_vat_invoice.action_report_vat_report/{move_id}"

            def _format_value(val):
                if isinstance(val, tuple) and len(val) == 2:
                    return {"id": val[0], "name": val[1]}
                elif isinstance(val, (datetime, date)):
                    return val.strftime('%Y-%m-%d')
                return val

            def _format_record(rec):
                if isinstance(rec, dict):
                    return {k: _format_value(v) for k, v in rec.items()}
                return rec

            def _parse_period_dates(period_str: str = "", date_from: str = "", date_to: str = ""):
                today = datetime.now().date()
                if date_from and date_to:
                    return str(date_from).strip(), str(date_to).strip()
                p = (period_str or 'this_month').lower().strip()
                year = today.year
                if any(k in p for k in ['last_year', 'last year', 'previous year']):
                    return f'{year-1}-01-01', f'{year-1}-12-31'
                if any(k in p for k in ['this_year', 'this year', 'ytd', 'year']):
                    return f'{year}-01-01', today.strftime('%Y-%m-%d')
                if any(k in p for k in ['last_month', 'last month', 'previous month']):
                    first_this = today.replace(day=1)
                    last_prev = first_this - timedelta(days=1)
                    first_prev = last_prev.replace(day=1)
                    return first_prev.strftime('%Y-%m-%d'), last_prev.strftime('%Y-%m-%d')
                
                # Check for month ranges (e.g. between January and March)
                if 'jan' in p and 'mar' in p:
                    return f'{year}-01-01', f'{year}-03-31'
                if 'apr' in p and 'jun' in p:
                    return f'{year}-04-01', f'{year}-06-30'
                if 'jul' in p and 'sep' in p:
                    return f'{year}-07-01', f'{year}-09-30'
                if 'oct' in p and 'dec' in p:
                    return f'{year}-10-01', f'{year}-12-31'

                month_map = {
                    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
                    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
                    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                }
                for mname, mnum in month_map.items():
                    if mname in p:
                        _, last_day = calendar.monthrange(year, mnum)
                        return f'{year}-{mnum:02d}-01', f'{year}-{mnum:02d}-{last_day:02d}'

                # Default this month
                return f'{year}-{today.month:02d}-01', today.strftime('%Y-%m-%d')

            # =========================================================================
            # LEVEL 1 & LEVEL 2: FINANCIAL BALANCES & LOOKUPS
            # =========================================================================

            @tool
            def get_financial_balances() -> str:
                """Calculates and returns real-time company financial balances directly from 360 Accounting database:
                - Total Accounts Receivable (money customers owe us across all unpaid/partial customer invoices)
                - Total Accounts Payable (money we owe vendors across all unpaid/partial vendor bills)
                - Net Working Position (Receivables minus Payables)
                - Real-time balances for ALL Bank and Cash accounts (SNB, Bank, Cash, etc.)
                - Total Bank & Cash liquidity
                Use this whenever the user asks for invoice balance, bank balance, customer owe amount, vendor owe amount, total receivable, or total payable."""
                env = request.env
                comp = env.company or env.user.company_id
                curr = _currency_name(comp.currency_id)

                # Total Accounts Receivable (customer invoices)
                out_invoices = env['account.move'].sudo().search([
                    ('move_type', '=', 'out_invoice'),
                    ('state', '=', 'posted'),
                    ('payment_state', 'in', ['not_paid', 'partial'])
                ])
                total_receivable = sum(out_invoices.mapped('amount_residual'))
                rec_count = len(out_invoices)

                # Total Accounts Payable (vendor bills)
                in_invoices = env['account.move'].sudo().search([
                    ('move_type', '=', 'in_invoice'),
                    ('state', '=', 'posted'),
                    ('payment_state', 'in', ['not_paid', 'partial'])
                ])
                total_payable = sum(in_invoices.mapped('amount_residual'))
                pay_count = len(in_invoices)

                # Bank & Cash Journals
                bank_cash_journals = env['account.journal'].sudo().search([('type', 'in', ['bank', 'cash'])])
                bank_accounts = []
                total_cash_and_bank = 0.0
                for j in bank_cash_journals:
                    acc = j.default_account_id
                    if acc:
                        lines = env['account.move.line'].sudo().search([
                            ('account_id', '=', acc.id),
                            ('parent_state', '=', 'posted')
                        ])
                        bal = sum(lines.mapped('balance'))
                        total_cash_and_bank += bal
                        bank_accounts.append({
                            'journal': j.name,
                            'type': j.type.title(),
                            'account': acc.name,
                            'code': getattr(acc, 'code', '') or '',
                            'balance': bal
                        })

                res = f"### 360 Accounting — Live Financial Balances\n\n"
                res += f"#### Outstanding Balances (Receivables & Payables)\n"
                res += f"• **Total Accounts Receivable (Customers owe us):** **{total_receivable:,.2f} {curr}** ({rec_count} unpaid customer invoice(s))\n"
                res += f"• **Total Accounts Payable (We owe vendors):** **{total_payable:,.2f} {curr}** ({pay_count} unpaid vendor bill(s))\n"
                net_pos = total_receivable - total_payable
                res += f"• **Net Position (Receivables − Payables):** **{net_pos:,.2f} {curr}**\n\n"

                res += f"#### Bank & Cash Accounts Liquidity\n"
                if bank_accounts:
                    res += f"| Journal | Account | Code | Type | Current Balance |\n"
                    res += f"|---|---|---|---|---|\n"
                    for b in bank_accounts:
                        res += f"| **{b['journal']}** | {b['account']} | {b['code']} | {b['type']} | **{b['balance']:,.2f} {curr}** |\n"
                    res += f"\n• **Total Bank & Cash Liquidity:** **{total_cash_and_bank:,.2f} {curr}**\n\n"
                else:
                    res += "No bank or cash journals found.\n\n"

                res += f"Quick Document Action Links:\n"
                res += f"- [View Unpaid Customer Invoices](/web#action=account.action_move_out_invoice_type)\n"
                res += f"- [View Unpaid Vendor Bills](/web#action=account.action_move_in_invoice_type)"
                return res

            @tool
            def get_unpaid_invoices_or_bills(
                doc_type: str = "invoice",
                partner_name: str = "",
                min_amount: float = 0.0,
                max_amount: float = 0.0,
                days_overdue: int = 0,
                is_overdue: bool = False,
                due_window: str = "",
                limit: int = 15
            ) -> str:
                """Fetch real unpaid or partially paid customer invoices or vendor bills with advanced filtering:
                'doc_type': 'invoice' (customer invoices), 'bill' (vendor bills), or 'all'.
                'partner_name': Customer or vendor name to filter by.
                'min_amount': Minimum total/due amount threshold (e.g. 50000).
                'max_amount': Maximum amount filter.
                'days_overdue': Filter for invoices overdue by more than X days (e.g. 30).
                'is_overdue': True to only return documents whose due date has passed.
                'due_window': 'today', 'this_month', 'next_week', or 'overdue'.
                'limit': Maximum records (default 15)."""
                env = request.env
                today = datetime.now().date()
                clean_type = (doc_type or 'invoice').lower().strip()
                domain = [
                    ('state', '=', 'posted'),
                    ('payment_state', 'in', ['not_paid', 'partial']),
                ]
                if any(k in clean_type for k in ['bill', 'in_invoice', 'vendor', 'expense']):
                    domain.append(('move_type', '=', 'in_invoice'))
                    type_title = 'Unpaid Vendor Bills'
                elif any(k in clean_type for k in ['all', 'both']):
                    domain.append(('move_type', 'in', ['out_invoice', 'in_invoice']))
                    type_title = 'Unpaid Invoices & Bills'
                else:
                    domain.append(('move_type', '=', 'out_invoice'))
                    type_title = 'Unpaid Customer Invoices'

                if partner_name:
                    domain.append(('partner_id.name', 'ilike', partner_name.strip()))

                # Due date filters
                if is_overdue or days_overdue > 0:
                    cutoff = today - timedelta(days=int(days_overdue))
                    domain.append(('invoice_date_due', '<', cutoff.strftime('%Y-%m-%d')))
                elif due_window:
                    dw = due_window.lower().strip()
                    if dw == 'today':
                        domain.append(('invoice_date_due', '=', today.strftime('%Y-%m-%d')))
                    elif dw == 'next_week':
                        domain.extend([
                            ('invoice_date_due', '>=', today.strftime('%Y-%m-%d')),
                            ('invoice_date_due', '<=', (today + timedelta(days=7)).strftime('%Y-%m-%d'))
                        ])
                    elif dw in ('this_month', 'month'):
                        start_m, end_m = _parse_period_dates('this_month')
                        domain.extend([
                            ('invoice_date_due', '>=', start_m),
                            ('invoice_date_due', '<=', end_m)
                        ])

                safe_limit = min(max(int(limit or 15), 1), 50)
                records = env['account.move'].sudo().search(domain, order='invoice_date desc, id desc')

                # Filter by min_amount / max_amount in Python on amount_residual or amount_total
                if min_amount and float(min_amount) > 0:
                    records = records.filtered(lambda r: (r.amount_residual >= float(min_amount)) or (r.amount_total >= float(min_amount)))
                if max_amount and float(max_amount) > 0:
                    records = records.filtered(lambda r: (r.amount_residual <= float(max_amount)) or (r.amount_total <= float(max_amount)))

                total_matched = len(records)
                records = records[:safe_limit]

                if not records:
                    p_str = f" for partner '{partner_name}'" if partner_name else ""
                    filter_desc = []
                    if min_amount:
                        filter_desc.append(f"above {min_amount:,.2f}")
                    if is_overdue or days_overdue:
                        filter_desc.append(f"overdue by > {days_overdue} days" if days_overdue else "overdue")
                    f_str = f" with filter ({', '.join(filter_desc)})" if filter_desc else ""
                    return f"No {type_title.lower()} found in 360 Accounting database{p_str}{f_str}."

                total_residual_sum = sum(records.mapped('amount_residual'))
                total_amount_sum = sum(records.mapped('amount_total'))
                primary_currency = _currency_name(records[0].currency_id) if records else 'SAR'

                res = f"Found **{total_matched}** {type_title} in 360 Accounting:\n\n"
                for idx, inv in enumerate(records, 1):
                    partner = inv.partner_id.name if inv.partner_id else "N/A"
                    curr = _currency_name(inv.currency_id)
                    inv_name = inv.name or f"Draft #{inv.id}"
                    doc_kind = "Vendor Bill" if inv.move_type == 'in_invoice' else "Customer Invoice"
                    pay_status = "Partially Paid" if inv.payment_state == 'partial' else "Not Paid"

                    res += f"{idx}. **{inv_name}** ({doc_kind})\n"
                    if inv.partner_id:
                        res += f"   • **Customer/Partner:** **[{partner}](ask:Show me all invoices and financial details for {partner})**\n"
                    else:
                        res += f"   • **Customer/Partner:** {partner}\n"
                    res += f"   • **Invoice Date:** {inv.invoice_date or 'N/A'} | **Due Date:** {inv.invoice_date_due or 'N/A'}\n"
                    res += f"   • **Status:** {inv.state.title()} | **Payment Status:** {pay_status}\n"
                    res += f"   • **Untaxed:** {inv.amount_untaxed:,.2f} {curr} | **Tax:** {inv.amount_tax:,.2f} {curr}\n"
                    res += f"   • **Total Amount:** {inv.amount_total:,.2f} {curr}\n"
                    res += f"   • **Amount Due (Residual):** {inv.amount_residual:,.2f} {curr}\n"
                    res += f"   • [View Document](/web#id={inv.id}&model=account.move&view_type=form)"
                    if inv.move_type == 'out_invoice':
                        res += f" · [Download Tax Invoice PDF]({_get_vat_report_pdf_url(inv.id)})"
                    res += "\n\n"

                res += f"**Summary:**\n"
                res += f"• **Count Displayed:** {len(records)} of {total_matched} document(s)\n"
                res += f"• **Total Amount:** {total_amount_sum:,.2f} {primary_currency}\n"
                res += f"• **Total Outstanding (Amount Due):** {total_residual_sum:,.2f} {primary_currency}\n"
                return res

            @tool
            def get_document_details(reference: str) -> str:
                """Get complete details and line items for ANY vendor bill, customer invoice, credit note, purchase order, or sales order by its reference/number (e.g. 'BILL/2026/09/0001', 'INV/2026/0001', 'PO00001', 'SO00001', or numeric ID).
                Returns vendor/customer name, dates, status, payment status, untaxed/tax/total amounts, and all line items (products, quantities, unit prices, subtotals) with direct links."""
                env = request.env
                clean_ref = (reference or '').strip()
                if not clean_ref:
                    return "Please provide a document reference or order number (e.g. 'BILL/2026/09/0001')."

                if clean_ref.lower() in ('invoices', 'invoice', 'bills', 'bill', 'orders', 'order', 'document', 'documents', 'unpaid', 'all'):
                    return "Notice: `get_document_details` is for retrieving a SINGLE specific document by its exact reference number (e.g. 'BILL/2026/09/0001' or 'INV/2026/00035'). To view or list all unpaid documents, call `get_unpaid_invoices_or_bills(doc_type='invoice')` or `get_unpaid_invoices_or_bills(doc_type='bill')`."

                # 1. Search in account.move (Bills, Invoices, Credit Notes)
                move = None
                if 'account.move' in env:
                    move_domain = ['|', '|', ('name', '=ilike', clean_ref), ('ref', '=ilike', clean_ref), ('payment_reference', '=ilike', clean_ref)]
                    moves = env['account.move'].sudo().search(move_domain, limit=1, order='id desc')
                    if not moves:
                        moves = env['account.move'].sudo().search(['|', ('name', 'ilike', clean_ref), ('ref', 'ilike', clean_ref)], limit=1, order='id desc')
                    if not moves and clean_ref.isdigit():
                        moves = env['account.move'].sudo().search([('id', '=', int(clean_ref))], limit=1)
                    if moves:
                        move = moves[0]

                if move:
                    request._viewed_doc = {'model': 'account.move', 'id': move.id, 'name': move.name or clean_ref}
                    type_label = {
                        'out_invoice': 'Customer Invoice',
                        'in_invoice': 'Vendor Bill',
                        'out_refund': 'Customer Credit Note',
                        'in_refund': 'Vendor Credit Note',
                        'entry': 'Journal Entry'
                    }.get(move.move_type, 'Accounting Document')

                    curr_sym = _currency_name(move.currency_id)
                    partner_role = 'Vendor' if move.move_type in ('in_invoice', 'in_refund') else 'Customer'
                    partner_name = move.partner_id.name if move.partner_id else 'N/A'
                    
                    state_dict = dict(move._fields['state'].selection) if hasattr(move._fields.get('state'), 'selection') else {}
                    state_label = state_dict.get(move.state, move.state.title() if move.state else 'Draft')
                    
                    pay_state_label = 'N/A'
                    if hasattr(move, 'payment_state') and move.payment_state:
                        pay_dict = dict(move._fields['payment_state'].selection) if hasattr(move._fields.get('payment_state'), 'selection') else {}
                        pay_state_label = pay_dict.get(move.payment_state, move.payment_state.replace('_', ' ').title())

                    lines_data = []
                    for idx, line in enumerate(move.invoice_line_ids, 1):
                        if line.product_id:
                            p_clean = line.product_id.name
                            p_disp = line.product_id.display_name
                            prod_name = f"[{p_disp}](ask:Show details and sales history for product {p_clean})"
                        else:
                            prod_name = line.name or 'Item'
                        taxes_str = ', '.join(line.tax_ids.mapped('name')) if line.tax_ids else 'None'
                        lines_data.append({
                            'item_no': idx,
                            'product': prod_name,
                            'quantity': float(line.quantity or 0.0),
                            'unit_price': float(line.price_unit or 0.0),
                            'taxes': taxes_str,
                            'subtotal': float(line.price_subtotal or 0.0),
                        })

                    res = f"Found **{type_label}**: **{move.name or clean_ref}** (ID: {move.id})\n\n"
                    if move.partner_id:
                        res += f"• **{partner_role}:** **[{partner_name}](ask:Show me all invoices and financial details for {partner_name})**\n"
                    else:
                        res += f"• **{partner_role}:** {partner_name}\n"
                    res += f"• **Bill/Invoice Date:** {move.invoice_date or 'N/A'}\n"
                    res += f"• **Due Date:** {move.invoice_date_due or 'N/A'}\n"
                    res += f"• **Document Status:** {state_label}\n"
                    res += f"• **Payment Status:** {pay_state_label}\n"
                    res += f"• **Untaxed Amount:** {move.amount_untaxed:,.2f} {curr_sym}\n"
                    res += f"• **Tax Amount:** {move.amount_tax:,.2f} {curr_sym}\n"
                    res += f"• **Total Amount:** {move.amount_total:,.2f} {curr_sym}\n"
                    if getattr(move, 'amount_residual', None) is not None:
                        res += f"• **Amount Due (Residual):** {move.amount_residual:,.2f} {curr_sym}\n"

                    if lines_data:
                        res += f"\n**Line Items ({len(lines_data)} item(s)):**\n"
                        res += "| # | Product / Description | Qty | Unit Price | Tax | Subtotal |\n"
                        res += "|---|-----------------------|-----|------------|-----|----------|\n"
                        for l in lines_data:
                            res += f"| {l['item_no']} | {l['product']} | {l['quantity']} | {l['unit_price']:,.2f} | {l['taxes']} | {l['subtotal']:,.2f} {curr_sym} |\n"

                    res += f"\nDirect Document Action Links:\n"
                    if move.move_type in ('out_invoice', 'out_refund', 'in_invoice'):
                        res += f"- [Download Tax Invoice PDF]({_get_vat_report_pdf_url(move.id)})\n"
                    res += f"- [View Document](/web#id={move.id}&model=account.move&view_type=form)"
                    return res

                # 2. Search in purchase.order
                if 'purchase.order' in env:
                    po_domain = ['|', ('name', '=ilike', clean_ref), ('partner_ref', '=ilike', clean_ref)]
                    pos = env['purchase.order'].sudo().search(po_domain, limit=1, order='id desc')
                    if not pos:
                        pos = env['purchase.order'].sudo().search(['|', ('name', 'ilike', clean_ref), ('partner_ref', 'ilike', clean_ref)], limit=1, order='id desc')
                    if not pos and clean_ref.isdigit():
                        pos = env['purchase.order'].sudo().search([('id', '=', int(clean_ref))], limit=1)
                    if pos:
                        p = pos[0]
                        request._viewed_doc = {'model': 'purchase.order', 'id': p.id, 'name': p.name}
                        curr_sym = _currency_name(p.currency_id)
                        res = f"Found **Purchase Order**: **{p.name}** (ID: {p.id})\n\n"
                        res += f"• **Vendor:** {p.partner_id.name if p.partner_id else 'N/A'}\n"
                        res += f"• **Order Date:** {p.date_order or 'N/A'}\n"
                        res += f"• **Status:** {p.state.title() if p.state else 'Draft'}\n"
                        res += f"• **Untaxed Amount:** {p.amount_untaxed:,.2f} {curr_sym}\n"
                        res += f"• **Total Amount:** {p.amount_total:,.2f} {curr_sym}\n\n"
                        if p.order_line:
                            res += f"**Line Items ({len(p.order_line)} item(s)):**\n"
                            res += "| # | Product | Qty | Unit Price | Subtotal |\n"
                            res += "|---|---------|-----|------------|----------|\n"
                            for idx, line in enumerate(p.order_line, 1):
                                res += f"| {idx} | {line.name} | {line.product_qty} | {line.price_unit:,.2f} | {line.price_subtotal:,.2f} {curr_sym} |\n"
                        res += f"\nDirect Action Links:\n- [View Document](/web#id={p.id}&model=purchase.order&view_type=form)"
                        return res

                # 3. Search in sale.order
                if 'sale.order' in env:
                    so_domain = ['|', ('name', '=ilike', clean_ref), ('client_order_ref', '=ilike', clean_ref)]
                    sos = env['sale.order'].sudo().search(so_domain, limit=1, order='id desc')
                    if not sos:
                        sos = env['sale.order'].sudo().search(['|', ('name', 'ilike', clean_ref), ('client_order_ref', 'ilike', clean_ref)], limit=1, order='id desc')
                    if not sos and clean_ref.isdigit():
                        sos = env['sale.order'].sudo().search([('id', '=', int(clean_ref))], limit=1)
                    if sos:
                        s = sos[0]
                        request._viewed_doc = {'model': 'sale.order', 'id': s.id, 'name': s.name}
                        curr_sym = _currency_name(s.currency_id)
                        res = f"Found **Sales Order**: **{s.name}** (ID: {s.id})\n\n"
                        res += f"• **Customer:** {s.partner_id.name if s.partner_id else 'N/A'}\n"
                        res += f"• **Order Date:** {s.date_order or 'N/A'}\n"
                        res += f"• **Status:** {s.state.title() if s.state else 'Draft'}\n"
                        res += f"• **Untaxed Amount:** {s.amount_untaxed:,.2f} {curr_sym}\n"
                        res += f"• **Total Amount:** {s.amount_total:,.2f} {curr_sym}\n\n"
                        if s.order_line:
                            res += f"**Line Items ({len(s.order_line)} item(s)):**\n"
                            res += "| # | Product | Qty | Unit Price | Subtotal |\n"
                            res += "|---|---------|-----|------------|----------|\n"
                            for idx, line in enumerate(s.order_line, 1):
                                res += f"| {idx} | {line.name} | {line.product_uom_qty} | {line.price_unit:,.2f} | {line.price_subtotal:,.2f} {curr_sym} |\n"
                        res += f"\nDirect Action Links:\n- [View Document](/web#id={s.id}&model=sale.order&view_type=form)"
                        return res

                return f"No document, vendor bill, invoice, or order was found matching reference '{clean_ref}' in 360 Accounting."

            @tool
            def get_recent_payments(
                payment_type: str = "all",
                partner_name: str = "",
                limit: int = 10,
                today_only: bool = False,
                date_from: str = "",
                date_to: str = ""
            ) -> str:
                """Retrieve real payment records directly from 360 Accounting database (account.payment):
                'payment_type': 'inbound' (payments received from customers), 'outbound' (payments made to vendors), or 'all'.
                'partner_name': Optional partner name filter.
                'limit': Number of payments to return (default 10).
                'today_only': Set to True to retrieve only payments received/sent today.
                'date_from' / 'date_to': Optional date range filters (YYYY-MM-DD)."""
                env = request.env
                today = datetime.now().date()
                domain = []
                ptype = (payment_type or 'all').lower().strip()
                if 'inbound' in ptype or 'received' in ptype or 'customer' in ptype:
                    domain.append(('payment_type', '=', 'inbound'))
                    title = "Customer Payments Received"
                elif 'outbound' in ptype or 'sent' in ptype or 'vendor' in ptype or 'made' in ptype:
                    domain.append(('payment_type', '=', 'outbound'))
                    title = "Vendor Payments Sent"
                else:
                    title = "Recent Payments"

                if today_only:
                    domain.append(('date', '=', today.strftime('%Y-%m-%d')))
                elif date_from or date_to:
                    if date_from:
                        domain.append(('date', '>=', date_from.strip()))
                    if date_to:
                        domain.append(('date', '<=', date_to.strip()))

                if partner_name:
                    domain.append(('partner_id.name', 'ilike', partner_name.strip()))

                safe_limit = min(max(int(limit or 10), 1), 50)
                payments = env['account.payment'].sudo().search(domain, limit=safe_limit, order='date desc, id desc')

                if not payments:
                    p_str = f" for '{partner_name}'" if partner_name else ""
                    t_str = f" today ({today.strftime('%Y-%m-%d')})" if today_only else ""
                    return f"No {title.lower()} found in 360 Accounting{p_str}{t_str}."

                total_amt = sum(payments.mapped('amount'))
                comp_curr = _currency_name(env.company.currency_id)

                res = f"### {title} ({len(payments)} record(s))\n\n"
                res += "| # | Payment Ref | Date | Partner | Amount | Journal | Type | Status |\n"
                res += "|---|-------------|------|---------|--------|---------|------|--------|\n"
                for idx, p in enumerate(payments, 1):
                    partner = p.partner_id.name if p.partner_id else "N/A"
                    p_link = f"**[{partner}](ask:Show me all invoices and financial details for {partner})**" if p.partner_id else "—"
                    curr = _currency_name(p.currency_id)
                    journal_name = p.journal_id.name if p.journal_id else "N/A"
                    type_str = "Customer (In)" if p.payment_type == 'inbound' else "Vendor (Out)"
                    res += f"| {idx} | **{p.name or 'Draft'}** | {p.date} | {p_link} | **{p.amount:,.2f} {curr}** | {journal_name} | {type_str} | {p.state.title()} |\n"

                res += f"\n• **Total Payments Amount:** **{total_amt:,.2f} {comp_curr}**\n\n"
                res += "Direct Action Links:\n"
                for p in payments[:3]:
                    res += f"- [View Payment {p.name}](/web#id={p.id}&model=account.payment&view_type=form)\n"
                return res

            @tool
            def get_sales_and_expenses_summary(
                period: str = "this_month",
                date_from: str = "",
                date_to: str = "",
                department_or_account: str = ""
            ) -> str:
                """Calculates exact sales, revenue, and expenses for any given period, department, or account.
                'period': 'this_month', 'last_month', 'this_year', 'last_year', 'august', or date ranges like 'between January and March'.
                'date_from' / 'date_to': Specific dates (YYYY-MM-DD).
                'department_or_account': Optional name of analytic account, department, or expense account."""
                env = request.env
                comp = env.company or env.user.company_id
                curr = _currency_name(comp.currency_id)

                d_from, d_to = _parse_period_dates(period, date_from, date_to)

                # Sales / Invoices
                sales_domain = [
                    ('move_type', '=', 'out_invoice'),
                    ('state', '=', 'posted'),
                    ('invoice_date', '>=', d_from),
                    ('invoice_date', '<=', d_to)
                ]
                sales_invoices = env['account.move'].sudo().search(sales_domain)
                sales_count = len(sales_invoices)
                sales_untaxed = sum(sales_invoices.mapped('amount_untaxed_signed'))
                sales_tax = sum(sales_invoices.mapped('amount_tax_signed'))
                sales_total = sum(sales_invoices.mapped('amount_total_signed'))

                # Expenses / Bills
                exp_domain = [
                    ('move_type', '=', 'in_invoice'),
                    ('state', '=', 'posted'),
                    ('invoice_date', '>=', d_from),
                    ('invoice_date', '<=', d_to)
                ]
                bills = env['account.move'].sudo().search(exp_domain)
                bills_count = len(bills)
                bills_untaxed = abs(sum(bills.mapped('amount_untaxed_signed')))
                bills_tax = abs(sum(bills.mapped('amount_tax_signed')))
                bills_total = abs(sum(bills.mapped('amount_total_signed')))

                # Department / Account filter if requested
                dept_lines_summary = ""
                if department_or_account:
                    q = department_or_account.strip()
                    dept_domain = [
                        ('parent_state', '=', 'posted'),
                        ('date', '>=', d_from),
                        ('date', '<=', d_to),
                        '|', '|',
                        ('account_id.name', 'ilike', q),
                        ('account_id.code', 'ilike', q),
                        ('analytic_distribution', 'ilike', q) if 'analytic_distribution' in env['account.move.line']._fields else ('name', 'ilike', q)
                    ]
                    matching_lines = env['account.move.line'].sudo().search(dept_domain)
                    dept_debit = sum(matching_lines.mapped('debit'))
                    dept_credit = sum(matching_lines.mapped('credit'))
                    dept_balance = sum(matching_lines.mapped('balance'))
                    dept_lines_summary = f"\n#### Breakdown for '{q}' ({d_from} to {d_to}):\n"
                    dept_lines_summary += f"• **Total Debit:** {dept_debit:,.2f} {curr}\n"
                    dept_lines_summary += f"• **Total Credit:** {dept_credit:,.2f} {curr}\n"
                    dept_lines_summary += f"• **Net Balance:** {dept_balance:,.2f} {curr} ({len(matching_lines)} journal item(s))\n"

                net_income = sales_untaxed - bills_untaxed

                res = f"### Financial Summary ({d_from} to {d_to})\n\n"
                res += f"#### Customer Sales & Invoices\n"
                res += f"• **Invoices Generated:** {sales_count} invoice(s)\n"
                res += f"• **Untaxed Sales (Revenue):** **{sales_untaxed:,.2f} {curr}**\n"
                res += f"• **VAT / Sales Tax:** {sales_tax:,.2f} {curr}\n"
                res += f"• **Total Sales Amount:** **{sales_total:,.2f} {curr}**\n\n"

                res += f"#### Vendor Bills & Expenses\n"
                res += f"• **Bills Recorded:** {bills_count} bill(s)\n"
                res += f"• **Untaxed Expenses:** **{bills_untaxed:,.2f} {curr}**\n"
                res += f"• **VAT / Purchase Tax:** {bills_tax:,.2f} {curr}\n"
                res += f"• **Total Expenses Amount:** **{bills_total:,.2f} {curr}**\n\n"

                res += f"#### Operating Result\n"
                res += f"• **Net Operating Income (Sales − Expenses):** **{net_income:,.2f} {curr}**\n"

                if dept_lines_summary:
                    res += dept_lines_summary

                return res

            @tool
            def get_credit_and_debit_notes(note_type: str = "all", limit: int = 15) -> str:
                """Retrieve credit notes and debit notes from 360 Accounting database.
                'note_type': 'credit_note' (customer & vendor credit notes), 'debit_note' (debit notes), or 'all'.
                'limit': Maximum results (default 15)."""
                env = request.env
                domain = [('state', '=', 'posted')]
                nt = (note_type or 'all').lower().strip()
                if 'credit' in nt:
                    domain.append(('move_type', 'in', ['out_refund', 'in_refund']))
                    title = "Credit Notes"
                elif 'debit' in nt:
                    if hasattr(env['account.move'], 'debit_origin_id'):
                        domain.append(('debit_origin_id', '!=', False))
                    title = "Debit Notes"
                else:
                    domain.append(('move_type', 'in', ['out_refund', 'in_refund']))
                    title = "Credit & Debit Notes"

                safe_limit = min(max(int(limit or 15), 1), 50)
                notes = env['account.move'].sudo().search(domain, limit=safe_limit, order='invoice_date desc, id desc')
                if not notes:
                    return f"No {title.lower()} found in 360 Accounting database."

                curr_sym = _currency_name(env.company.currency_id)
                res = f"### {title} ({len(notes)} found)\n\n"
                for idx, n in enumerate(notes, 1):
                    partner = n.partner_id.name if n.partner_id else "N/A"
                    p_link = f"**[{partner}](ask:Show me all invoices and financial details for {partner})**" if n.partner_id else "N/A"
                    c = _currency_name(n.currency_id)
                    kind = "Customer Credit Note" if n.move_type == 'out_refund' else ("Vendor Credit Note" if n.move_type == 'in_refund' else "Debit Note")
                    res += f"{idx}. **{n.name}** ({kind}) | Partner: {p_link} | Date: {n.invoice_date or 'N/A'} | Total: **{n.amount_total:,.2f} {c}** | Status: {n.state.title()}\n"
                    res += f"   [View Document](/web#id={n.id}&model=account.move&view_type=form)\n\n"
                return res

            @tool
            def get_account_or_journal_transactions(
                account_code_or_name: str = "",
                journal_name_or_code: str = "",
                limit: int = 15
            ) -> str:
                """Retrieve posted accounting transactions for a specific account (e.g. '400000', '101001', 'Bank') or specific journal.
                'account_code_or_name': Account code or name to filter by.
                'journal_name_or_code': Journal name or code.
                'limit': Max lines to return (default 15)."""
                env = request.env
                domain = [('parent_state', '=', 'posted')]

                if account_code_or_name:
                    ac = account_code_or_name.strip()
                    domain.extend(['|', ('account_id.code', '=ilike', f"{ac}%"), ('account_id.name', 'ilike', ac)])

                if journal_name_or_code:
                    jc = journal_name_or_code.strip()
                    domain.extend(['|', ('journal_id.name', 'ilike', jc), ('journal_id.code', '=ilike', jc)])

                safe_limit = min(max(int(limit or 15), 1), 50)
                lines = env['account.move.line'].sudo().search(domain, limit=safe_limit, order='date desc, id desc')
                if not lines:
                    return f"No posted transactions found for account '{account_code_or_name}' / journal '{journal_name_or_code}'."

                curr = _currency_name(env.company.currency_id)
                res = f"### Transactions for '{account_code_or_name or journal_name_or_code}' ({len(lines)} record(s))\n\n"
                res += "| Date | Number / Entry | Account | Partner | Debit | Credit | Balance |\n"
                res += "|------|----------------|---------|---------|-------|--------|---------|\n"
                for l in lines:
                    pname = l.partner_id.name if l.partner_id else "—"
                    mname = l.move_id.name if l.move_id else f"#{l.id}"
                    acc_str = f"{l.account_id.name} [{l.account_id.code}]" if getattr(l.account_id, 'code', False) else l.account_id.name
                    res += f"| {l.date} | **{mname}** | {acc_str} | {pname} | {l.debit:,.2f} | {l.credit:,.2f} | **{l.balance:,.2f} {curr}** |\n"
                return res

            # =========================================================================
            # LEVEL 3: ACCOUNTING REPORTS
            # =========================================================================

            @tool
            def get_financial_report(
                report_name: str = "pnl",
                date_from: str = "",
                date_to: str = "",
                period: str = "this_year"
            ) -> str:
                """Generates real accounting statements directly from 360 Accounting General Ledger move lines:
                - 'pnl' or 'profit_and_loss': Profit & Loss statement (Revenue, Direct Costs, Operating Expenses, Net Profit)
                - 'balance_sheet': Balance Sheet (Current Assets, Fixed Assets, Liabilities, Equity)
                - 'trial_balance': Trial Balance with Total Debit = Total Credit verification
                - 'tax_report' or 'vat_report': Official VAT Report (Sales VAT, Purchase VAT, Net Tax Payable)
                - 'general_ledger': General Ledger overview
                'period': 'this_year', 'last_year', 'this_month', 'last_month', or custom date range."""
                env = request.env
                comp = env.company or env.user.company_id
                curr = _currency_name(comp.currency_id)
                r_type = (report_name or 'pnl').lower().strip()

                d_from, d_to = _parse_period_dates(period, date_from, date_to)

                # 1. PROFIT AND LOSS STATEMENT
                if any(k in r_type for k in ['pnl', 'profit', 'loss', 'income_statement', 'revenue', 'net_profit']):
                    # Income accounts
                    inc_lines = env['account.move.line'].sudo().search([
                        ('parent_state', '=', 'posted'),
                        ('account_id.account_type', 'in', ['income', 'income_other']),
                        ('date', '>=', d_from),
                        ('date', '<=', d_to)
                    ])
                    # Direct costs
                    cogs_lines = env['account.move.line'].sudo().search([
                        ('parent_state', '=', 'posted'),
                        ('account_id.account_type', '=', 'expense_direct_cost'),
                        ('date', '>=', d_from),
                        ('date', '<=', d_to)
                    ])
                    # Operating expenses & depreciation
                    exp_lines = env['account.move.line'].sudo().search([
                        ('parent_state', '=', 'posted'),
                        ('account_id.account_type', 'in', ['expense', 'expense_depreciation']),
                        ('date', '>=', d_from),
                        ('date', '<=', d_to)
                    ])

                    total_revenue = -sum(inc_lines.mapped('balance'))
                    total_cogs = sum(cogs_lines.mapped('balance'))
                    gross_profit = total_revenue - total_cogs
                    total_opex = sum(exp_lines.mapped('balance'))
                    net_profit = gross_profit - total_opex

                    res = f"### Profit and Loss Statement\n"
                    res += f"**Reporting Period:** {d_from} to {d_to} | **Currency:** {curr}\n\n"
                    res += f"| Financial Category | Amount ({curr}) |\n"
                    res += f"|---|---|\n"
                    res += f"| **Total Operating Revenue** | **{total_revenue:,.2f}** |\n"
                    res += f"| Less: Cost of Goods Sold / Direct Costs | ({total_cogs:,.2f}) |\n"
                    res += f"| **Gross Profit** | **{gross_profit:,.2f}** |\n"
                    res += f"| Less: Operating Expenses & Depreciation | ({total_opex:,.2f}) |\n"
                    res += f"| **Net Profit / (Loss)** | **{net_profit:,.2f}** |\n\n"

                    # Top expense accounts
                    if exp_lines:
                        res += f"#### Major Operating Expense Accounts:\n"
                        acc_map = {}
                        for l in exp_lines:
                            acc_map[l.account_id.name] = acc_map.get(l.account_id.name, 0.0) + l.balance
                        sorted_exp = sorted(acc_map.items(), key=lambda x: x[1], reverse=True)[:5]
                        for aname, abal in sorted_exp:
                            res += f"• **{aname}:** {abal:,.2f} {curr}\n"
                    return res

                # 2. BALANCE SHEET
                elif any(k in r_type for k in ['balance_sheet', 'balancesheet', 'sheet']):
                    # Assets
                    cash_bank = sum(env['account.move.line'].sudo().search([('parent_state', '=', 'posted'), ('account_id.account_type', '=', 'asset_cash'), ('date', '<=', d_to)]).mapped('balance'))
                    receivables = sum(env['account.move.line'].sudo().search([('parent_state', '=', 'posted'), ('account_id.account_type', '=', 'asset_receivable'), ('date', '<=', d_to)]).mapped('balance'))
                    current_assets = sum(env['account.move.line'].sudo().search([('parent_state', '=', 'posted'), ('account_id.account_type', 'in', ['asset_current', 'asset_prepayments']), ('date', '<=', d_to)]).mapped('balance'))
                    fixed_assets = sum(env['account.move.line'].sudo().search([('parent_state', '=', 'posted'), ('account_id.account_type', '=', 'asset_fixed'), ('date', '<=', d_to)]).mapped('balance'))
                    total_assets = cash_bank + receivables + current_assets + fixed_assets

                    # Liabilities
                    payables = -sum(env['account.move.line'].sudo().search([('parent_state', '=', 'posted'), ('account_id.account_type', '=', 'liability_payable'), ('date', '<=', d_to)]).mapped('balance'))
                    current_liab = -sum(env['account.move.line'].sudo().search([('parent_state', '=', 'posted'), ('account_id.account_type', 'in', ['liability_current', 'liability_credit_card']), ('date', '<=', d_to)]).mapped('balance'))
                    non_current_liab = -sum(env['account.move.line'].sudo().search([('parent_state', '=', 'posted'), ('account_id.account_type', '=', 'liability_non_current'), ('date', '<=', d_to)]).mapped('balance'))
                    total_liabilities = payables + current_liab + non_current_liab

                    # Equity
                    equity = -sum(env['account.move.line'].sudo().search([('parent_state', '=', 'posted'), ('account_id.account_type', 'in', ['equity', 'equity_unaffected']), ('date', '<=', d_to)]).mapped('balance'))

                    res = f"### Balance Sheet\n"
                    res += f"**As of Date:** {d_to} | **Currency:** {curr}\n\n"
                    res += f"#### Assets\n"
                    res += f"• **Cash & Bank Balances:** {cash_bank:,.2f} {curr}\n"
                    res += f"• **Accounts Receivable:** {receivables:,.2f} {curr}\n"
                    res += f"• **Other Current Assets & Prepayments:** {current_assets:,.2f} {curr}\n"
                    res += f"• **Fixed / Non-Current Assets:** {fixed_assets:,.2f} {curr}\n"
                    res += f"• **TOTAL ASSETS:** **{total_assets:,.2f} {curr}**\n\n"

                    res += f"#### Liabilities\n"
                    res += f"• **Accounts Payable:** {payables:,.2f} {curr}\n"
                    res += f"• **Other Current Liabilities & Credit Cards:** {current_liab:,.2f} {curr}\n"
                    res += f"• **Non-Current Liabilities:** {non_current_liab:,.2f} {curr}\n"
                    res += f"• **TOTAL LIABILITIES:** **{total_liabilities:,.2f} {curr}**\n\n"

                    res += f"#### Equity\n"
                    res += f"• **Retained / Unaffected Earnings:** {equity:,.2f} {curr}\n"
                    res += f"• **TOTAL LIABILITIES & EQUITY:** **{(total_liabilities + equity):,.2f} {curr}**\n"
                    return res

                # 3. TRIAL BALANCE
                elif any(k in r_type for k in ['trial_balance', 'trial', 'tb']):
                    accounts = env['account.account'].sudo().search([], order='code asc, id asc')
                    tb_rows = []
                    sum_debit = 0.0
                    sum_credit = 0.0
                    for a in accounts:
                        lines = env['account.move.line'].sudo().search([
                            ('account_id', '=', a.id),
                            ('parent_state', '=', 'posted'),
                            ('date', '<=', d_to)
                        ])
                        if lines:
                            dr = sum(lines.mapped('debit'))
                            cr = sum(lines.mapped('credit'))
                            bal = dr - cr
                            sum_debit += dr
                            sum_credit += cr
                            code_str = getattr(a, 'code', '') or ''
                            tb_rows.append({
                                'code': code_str,
                                'name': a.name,
                                'debit': dr,
                                'credit': cr,
                                'balance': bal
                            })

                    res = f"### Trial Balance (As of {d_to})\n\n"
                    res += "| Code | Account Name | Total Debit | Total Credit | Net Balance |\n"
                    res += "|------|--------------|-------------|--------------|-------------|\n"
                    for r in tb_rows[:30]:
                        res += f"| {r['code']} | {r['name']} | {r['debit']:,.2f} | {r['credit']:,.2f} | **{r['balance']:,.2f}** |\n"

                    res += f"\n**Trial Balance Reconciliation:**\n"
                    res += f"• **Total Debit:** **{sum_debit:,.2f} {curr}**\n"
                    res += f"• **Total Credit:** **{sum_credit:,.2f} {curr}**\n"
                    res += f"• **Difference (Debit − Credit):** **{(sum_debit - sum_credit):,.2f} {curr}** (Balanced)\n"
                    return res

                # 4. TAX / VAT REPORT
                elif any(k in r_type for k in ['tax', 'vat']):
                    out_invs = env['account.move'].sudo().search([
                        ('move_type', 'in', ['out_invoice', 'out_refund']),
                        ('state', '=', 'posted'),
                        ('invoice_date', '>=', d_from),
                        ('invoice_date', '<=', d_to)
                    ])
                    in_invs = env['account.move'].sudo().search([
                        ('move_type', 'in', ['in_invoice', 'in_refund']),
                        ('state', '=', 'posted'),
                        ('invoice_date', '>=', d_from),
                        ('invoice_date', '<=', d_to)
                    ])

                    sales_taxable = sum(out_invs.mapped('amount_untaxed_signed'))
                    sales_vat = sum(out_invs.mapped('amount_tax_signed'))
                    purchase_taxable = abs(sum(in_invs.mapped('amount_untaxed_signed')))
                    purchase_vat = abs(sum(in_invs.mapped('amount_tax_signed')))
                    net_vat_due = sales_vat - purchase_vat

                    res = f"### VAT / Tax Return Report ({d_from} to {d_to})\n\n"
                    res += f"| Tax Item | Taxable Base ({curr}) | VAT Amount ({curr}) |\n"
                    res += "|---|---|---|\n"
                    res += f"| **Output VAT (Standard Sales Invoices)** | {sales_taxable:,.2f} | **{sales_vat:,.2f}** |\n"
                    res += f"| **Input VAT (Purchases & Vendor Bills)** | {purchase_taxable:,.2f} | **{purchase_vat:,.2f}** |\n"
                    res += f"| **Net VAT Payable / (Claimable)** | — | **{net_vat_due:,.2f} {curr}** |\n\n"
                    if net_vat_due > 0:
                        res += f"• **Status:** Net VAT Payable of **{net_vat_due:,.2f} {curr}** due to tax authority.\n"
                    else:
                        res += f"• **Status:** Net VAT Credit / Refund of **{abs(net_vat_due):,.2f} {curr}**.\n"
                    return res

                # 5. GENERAL LEDGER
                else:
                    lines = env['account.move.line'].sudo().search([
                        ('parent_state', '=', 'posted'),
                        ('date', '>=', d_from),
                        ('date', '<=', d_to)
                    ], limit=25, order='date desc, id desc')
                    res = f"### General Ledger Overview ({d_from} to {d_to})\n\n"
                    res += "| Date | Entry | Account | Partner | Debit | Credit | Balance |\n"
                    res += "|------|-------|---------|---------|-------|--------|---------|\n"
                    for l in lines:
                        pname = l.partner_id.name if l.partner_id else "—"
                        res += f"| {l.date} | {l.move_id.name} | {l.account_id.name} | {pname} | {l.debit:,.2f} | {l.credit:,.2f} | {l.balance:,.2f} |\n"
                    return res

            @tool
            def get_aged_partner_report(report_type: str = "receivable", partner_name: str = "") -> str:
                """Generates an Aged Receivables or Aged Payables report with aging buckets (Current, 1-30 days, 31-60 days, 61-90 days, 91+ days).
                'report_type': 'receivable' (customer invoices) or 'payable' (vendor bills).
                'partner_name': Optional partner name filter."""
                env = request.env
                today = datetime.now().date()
                comp = env.company or env.user.company_id
                curr = _currency_name(comp.currency_id)

                is_payable = any(k in report_type.lower() for k in ['payable', 'vendor', 'bill', 'payables'])
                move_type = 'in_invoice' if is_payable else 'out_invoice'
                title = "Aged Payables Report (Vendor Bills)" if is_payable else "Aged Receivables Report (Customer Invoices)"

                domain = [
                    ('move_type', '=', move_type),
                    ('state', '=', 'posted'),
                    ('payment_state', 'in', ['not_paid', 'partial'])
                ]
                if partner_name:
                    domain.append(('partner_id.name', 'ilike', partner_name.strip()))

                records = env['account.move'].sudo().search(domain)
                if not records:
                    return f"No outstanding records found for {title.lower()}."

                partner_buckets = {}
                tot_current = 0.0
                tot_1_30 = 0.0
                tot_31_60 = 0.0
                tot_61_90 = 0.0
                tot_91_plus = 0.0

                for r in records:
                    pname = r.partner_id.name if r.partner_id else "Unknown"
                    due = r.invoice_date_due or r.invoice_date or today
                    days = (today - due).days
                    amt = r.amount_residual

                    if pname not in partner_buckets:
                        partner_buckets[pname] = {'current': 0.0, '1_30': 0.0, '31_60': 0.0, '61_90': 0.0, '91_plus': 0.0, 'total': 0.0}

                    partner_buckets[pname]['total'] += amt
                    if days <= 0:
                        partner_buckets[pname]['current'] += amt
                        tot_current += amt
                    elif days <= 30:
                        partner_buckets[pname]['1_30'] += amt
                        tot_1_30 += amt
                    elif days <= 60:
                        partner_buckets[pname]['31_60'] += amt
                        tot_31_60 += amt
                    elif days <= 90:
                        partner_buckets[pname]['61_90'] += amt
                        tot_61_90 += amt
                    else:
                        partner_buckets[pname]['91_plus'] += amt
                        tot_91_plus += amt

                res = f"### {title}\n"
                res += f"**As of:** {today.strftime('%Y-%m-%d')} | **Currency:** {curr}\n\n"
                res += "| Partner Name | Current (Not Due) | 1–30 Days | 31–60 Days | 61–90 Days | 91+ Days | Total Outstanding |\n"
                res += "|---|---|---|---|---|---|---|\n"

                sorted_partners = sorted(partner_buckets.items(), key=lambda x: x[1]['total'], reverse=True)[:15]
                for pname, b in sorted_partners:
                    p_link = f"**[{pname}](ask:Show me all invoices and financial details for {pname})**" if pname != "Unknown" else "**Unknown**"
                    res += f"| {p_link} | {b['current']:,.2f} | {b['1_30']:,.2f} | {b['31_60']:,.2f} | {b['61_90']:,.2f} | {b['91_plus']:,.2f} | **{b['total']:,.2f}** |\n"

                total_all = tot_current + tot_1_30 + tot_31_60 + tot_61_90 + tot_91_plus
                res += f"| **TOTAL** | **{tot_current:,.2f}** | **{tot_1_30:,.2f}** | **{tot_31_60:,.2f}** | **{tot_61_90:,.2f}** | **{tot_91_plus:,.2f}** | **{total_all:,.2f} {curr}** |\n\n"
                return res

            # =========================================================================
            # LEVEL 4: COMPARISON & ANALYSIS
            # =========================================================================

            @tool
            def analyze_financial_comparison(metric: str = "sales", compare_period: str = "month") -> str:
                """Performs period-over-period comparisons (Month-over-Month or Year-over-Year) for sales or expenses, and explains drivers behind increases/decreases.
                'metric': 'sales' (customer revenue) or 'expenses' (vendor bills).
                'compare_period': 'month' (Current Month vs Last Month) or 'year' (Current Year vs Last Year)."""
                env = request.env
                comp = env.company or env.user.company_id
                curr = _currency_name(comp.currency_id)
                today = datetime.now().date()
                year = today.year

                is_expense = any(k in metric.lower() for k in ['expense', 'bill', 'cost'])
                move_type = 'in_invoice' if is_expense else 'out_invoice'
                label = "Expenses" if is_expense else "Sales Revenue"

                if compare_period.lower() == 'year':
                    p1_from, p1_to = f'{year}-01-01', today.strftime('%Y-%m-%d')
                    p2_from, p2_to = f'{year-1}-01-01', f'{year-1}-12-31'
                    p1_name, p2_name = f"This Year ({year})", f"Last Year ({year-1})"
                else:
                    p1_from, p1_to = _parse_period_dates('this_month')
                    p2_from, p2_to = _parse_period_dates('last_month')
                    p1_name, p2_name = "This Month", "Last Month"

                m1_records = env['account.move'].sudo().search([
                    ('move_type', '=', move_type),
                    ('state', '=', 'posted'),
                    ('invoice_date', '>=', p1_from),
                    ('invoice_date', '<=', p1_to)
                ])
                m2_records = env['account.move'].sudo().search([
                    ('move_type', '=', move_type),
                    ('state', '=', 'posted'),
                    ('invoice_date', '>=', p2_from),
                    ('invoice_date', '<=', p2_to)
                ])

                val1 = abs(sum(m1_records.mapped('amount_untaxed_signed')))
                val2 = abs(sum(m2_records.mapped('amount_untaxed_signed')))
                diff = val1 - val2
                pct_change = ((diff / val2) * 100.0) if val2 > 0 else (100.0 if val1 > 0 else 0.0)
                direction = "increased" if diff >= 0 else "decreased"

                res = f"### Financial Comparison — {label}\n\n"
                res += f"| Period | Record Count | Total Amount ({curr}) |\n"
                res += f"|---|---|---|\n"
                res += f"| **{p1_name}** ({p1_from} to {p1_to}) | {len(m1_records)} | **{val1:,.2f}** |\n"
                res += f"| **{p2_name}** ({p2_from} to {p2_to}) | {len(m2_records)} | **{val2:,.2f}** |\n"
                res += f"| **Variance / Difference** | {len(m1_records) - len(m2_records):+d} | **{diff:+,.2f} ({pct_change:+.1f}%)** |\n\n"

                res += f"• **Analysis:** {label} {direction} by **{abs(diff):,.2f} {curr}** ({abs(pct_change):.1f}%) in {p1_name} compared to {p2_name}.\n\n"

                # Driver analysis (partners with biggest impact)
                res += f"#### Top Drivers Contributing to {p1_name} {label}:\n"
                p_map = {}
                for r in m1_records:
                    pname = r.partner_id.name if r.partner_id else "Other"
                    p_map[pname] = p_map.get(pname, 0.0) + abs(r.amount_untaxed_signed)
                top_drivers = sorted(p_map.items(), key=lambda x: x[1], reverse=True)[:5]
                for pname, amt in top_drivers:
                    if pname != "Other":
                        res += f"• **[{pname}](ask:Show me all invoices and financial details for {pname})**: {amt:,.2f} {curr}\n"
                    else:
                        res += f"• **{pname}:** {amt:,.2f} {curr}\n"

                return res

            @tool
            def get_top_partners(partner_type: str = "customer", criteria: str = "revenue", limit: int = 10) -> str:
                """Ranks top customers or vendors by revenue, payments, or highest outstanding balance.
                'partner_type': 'customer' or 'vendor'.
                'criteria': 'revenue' (total sales/bills), 'outstanding' (unpaid balance owed), or 'payment' (highest payment received/made).
                'limit': Number of top partners to return (default 10)."""
                env = request.env
                comp = env.company or env.user.company_id
                curr = _currency_name(comp.currency_id)
                is_vendor = any(k in partner_type.lower() for k in ['vendor', 'supplier', 'payable'])
                move_type = 'in_invoice' if is_vendor else 'out_invoice'
                label = "Vendor" if is_vendor else "Customer"
                safe_limit = min(max(int(limit or 10), 1), 50)

                crit = (criteria or 'revenue').lower().strip()

                if 'outstanding' in crit:
                    # Ranked by amount_residual
                    unpaid = env['account.move'].sudo().search([
                        ('move_type', '=', move_type),
                        ('state', '=', 'posted'),
                        ('payment_state', 'in', ['not_paid', 'partial'])
                    ])
                    partner_map = {}
                    for u in unpaid:
                        pname = u.partner_id.name if u.partner_id else "N/A"
                        partner_map[pname] = partner_map.get(pname, 0.0) + u.amount_residual

                    sorted_ranks = sorted(partner_map.items(), key=lambda x: x[1], reverse=True)[:safe_limit]
                    res = f"### Top {label}s with Highest Outstanding Balance\n\n"
                    res += f"| # | {label} Name | Outstanding Balance ({curr}) |\n"
                    res += f"|---|---|---|\n"
                    for idx, (pname, amt) in enumerate(sorted_ranks, 1):
                        plink = f"**[{pname}](ask:Show me all invoices and financial details for {pname})**" if pname != "N/A" else "**N/A**"
                        res += f"| {idx} | {plink} | **{amt:,.2f}** |\n"
                    return res

                elif 'payment' in crit:
                    ptype = 'outbound' if is_vendor else 'inbound'
                    payments = env['account.payment'].sudo().search([
                        ('payment_type', '=', ptype),
                        ('state', '=', 'paid')
                    ])
                    p_map = {}
                    for p in payments:
                        pname = p.partner_id.name if p.partner_id else "N/A"
                        p_map[pname] = p_map.get(pname, 0.0) + p.amount
                    sorted_p = sorted(p_map.items(), key=lambda x: x[1], reverse=True)[:safe_limit]
                    res = f"### Top {label}s by Payment Volume\n\n"
                    res += f"| # | {label} Name | Total Payments ({curr}) |\n"
                    res += f"|---|---|---|\n"
                    for idx, (pname, amt) in enumerate(sorted_p, 1):
                        plink = f"**[{pname}](ask:Show me all invoices and financial details for {pname})**" if pname != "N/A" else "**N/A**"
                        res += f"| {idx} | {plink} | **{amt:,.2f}** |\n"
                    return res

                else:
                    # Ranked by revenue / billing volume
                    invoices = env['account.move'].sudo().search([
                        ('move_type', '=', move_type),
                        ('state', '=', 'posted')
                    ])
                    partner_map = {}
                    partner_counts = {}
                    for i in invoices:
                        pname = i.partner_id.name if i.partner_id else "N/A"
                        amt = abs(i.amount_total)
                        partner_map[pname] = partner_map.get(pname, 0.0) + amt
                        partner_counts[pname] = partner_counts.get(pname, 0) + 1

                    sorted_ranks = sorted(partner_map.items(), key=lambda x: x[1], reverse=True)[:safe_limit]
                    res = f"### Top {len(sorted_ranks)} {label}s by Revenue Volume\n\n"
                    res += f"| # | {label} Name | Invoices | Total Volume ({curr}) |\n"
                    res += f"|---|---|---|---|\n"
                    for idx, (pname, amt) in enumerate(sorted_ranks, 1):
                        plink = f"**[{pname}](ask:Show me all invoices and financial details for {pname})**" if pname != "N/A" else "**N/A**"
                        res += f"| {idx} | {plink} | {partner_counts.get(pname, 0)} | **{amt:,.2f}** |\n"
                    return res

            @tool
            def get_business_kpis_and_analytics() -> str:
                """Calculates key accounting KPIs and business metrics:
                - Overdue invoice percentage (count & amount)
                - Average invoice value
                - Top products by revenue
                - Most active accounts"""
                env = request.env
                today = datetime.now().date()
                comp = env.company or env.user.company_id
                curr = _currency_name(comp.currency_id)

                all_posted = env['account.move'].sudo().search([
                    ('move_type', '=', 'out_invoice'),
                    ('state', '=', 'posted')
                ])
                total_invoices_count = len(all_posted)
                total_invoiced_amt = sum(all_posted.mapped('amount_total'))
                avg_inv_val = (total_invoiced_amt / total_invoices_count) if total_invoices_count > 0 else 0.0

                overdue = all_posted.filtered(lambda i: i.payment_state in ('not_paid', 'partial') and (i.invoice_date_due or i.invoice_date or today) < today)
                overdue_count = len(overdue)
                overdue_amt = sum(overdue.mapped('amount_residual'))
                overdue_pct_count = (overdue_count / total_invoices_count * 100.0) if total_invoices_count > 0 else 0.0

                # Top products by revenue
                lines = env['account.move.line'].sudo().search([
                    ('move_id.move_type', '=', 'out_invoice'),
                    ('move_id.state', '=', 'posted'),
                    ('product_id', '!=', False)
                ])
                prod_map = {}
                for l in lines:
                    pname = l.product_id.display_name or l.product_id.name
                    prod_map[pname] = prod_map.get(pname, 0.0) + l.price_subtotal
                top_prods = sorted(prod_map.items(), key=lambda x: x[1], reverse=True)[:5]

                res = f"### 360 Accounting — Key Financial Metrics & Analytics\n\n"
                res += f"• **Average Invoice Value:** **{avg_inv_val:,.2f} {curr}**\n"
                res += f"• **Overdue Invoices Ratio:** **{overdue_pct_count:.1f}%** ({overdue_count} of {total_invoices_count} customer invoices overdue)\n"
                res += f"• **Total Overdue Amount:** **{overdue_amt:,.2f} {curr}**\n\n"

                if top_prods:
                    res += f"#### Top 5 Products by Revenue:\n"
                    for idx, (pname, ptotal) in enumerate(top_prods, 1):
                        res += f"{idx}. **[{pname}](ask:Show details and sales history for product {pname})**: {ptotal:,.2f} {curr}\n"

                return res

            @tool
            def get_partner_details_and_history(partner_name: str) -> str:
                """Retrieves full financial profile, contact information, total sales, vendor bills, outstanding due balances, and table of recent invoices/bills for a customer, vendor, or company partner.
                'partner_name': Name of the customer, vendor, or company (e.g. 'ABC', 'sandeep', 'Dream Art Advertising')."""
                env = request.env
                clean_name = (partner_name or '').strip()
                for prefix in [
                    'ask:Show me all invoices and financial details for',
                    'ask:show me all invoices and financial details for',
                    'show me all invoices and financial details for',
                    'show all invoices for',
                    'financial details for',
                    'invoices for',
                ]:
                    if clean_name.lower().startswith(prefix.lower()):
                        clean_name = clean_name[len(prefix):].strip()
                clean_name = clean_name.strip(' \'\":')

                if not clean_name:
                    return "Please provide a partner, customer, or vendor name."

                partners = env['res.partner'].sudo().search([
                    '|', ('name', 'ilike', clean_name), ('commercial_partner_id.name', 'ilike', clean_name)
                ])
                if not partners:
                    return f"No customer or vendor found matching '{clean_name}' in 360 Accounting."

                best_partner = partners[0]
                best_moves_count = -1
                for p in partners:
                    cnt = env['account.move'].sudo().search_count([('partner_id', '=', p.id)])
                    if cnt > best_moves_count:
                        best_moves_count = cnt
                        best_partner = p

                partner = best_partner
                request._viewed_doc = {'model': 'res.partner', 'id': partner.id, 'name': partner.name}
                comp_curr = _currency_name(env.company.currency_id)

                sales_invoices = env['account.move'].sudo().search([
                    ('partner_id', '=', partner.id),
                    ('move_type', 'in', ['out_invoice', 'out_refund']),
                    ('state', '=', 'posted')
                ])
                tot_sales = sum(sales_invoices.mapped('amount_total_signed'))

                vendor_bills = env['account.move'].sudo().search([
                    ('partner_id', '=', partner.id),
                    ('move_type', 'in', ['in_invoice', 'in_refund']),
                    ('state', '=', 'posted')
                ])
                tot_bills = abs(sum(vendor_bills.mapped('amount_total_signed')))

                unpaid_moves = env['account.move'].sudo().search([
                    ('partner_id', '=', partner.id),
                    ('state', '=', 'posted'),
                    ('payment_state', 'in', ['not_paid', 'partial'])
                ])
                rec_due = sum(m.amount_residual for m in unpaid_moves if m.move_type == 'out_invoice')
                pay_due = sum(m.amount_residual for m in unpaid_moves if m.move_type == 'in_invoice')

                recent_moves = env['account.move'].sudo().search([
                    ('partner_id', '=', partner.id),
                    ('move_type', 'in', ['out_invoice', 'in_invoice', 'out_refund', 'in_refund'])
                ], limit=10, order='invoice_date desc, id desc')

                res = f"### Partner Profile: **{partner.name}**\n\n"
                res += f"• **Customer/Vendor Name:** {partner.name}\n"
                if getattr(partner, 'email', None):
                    res += f"• **Email:** {partner.email}\n"
                phone_num = getattr(partner, 'phone', None) or getattr(partner, 'mobile', None)
                if phone_num:
                    res += f"• **Phone:** {phone_num}\n"
                if getattr(partner, 'city', None) or getattr(partner, 'country_id', None):
                    loc = ', '.join(filter(None, [getattr(partner, 'street', None), getattr(partner, 'city', None), partner.country_id.name if partner.country_id else '']))
                    if loc:
                        res += f"• **Address:** {loc}\n"
                if getattr(partner, 'vat', None):
                    res += f"• **Tax ID / VAT:** {partner.vat}\n"

                res += f"\n#### Financial Overview\n"
                res += f"• **Total Sales Invoiced:** **{tot_sales:,.2f} {comp_curr}** ({len(sales_invoices)} invoice(s))\n"
                res += f"• **Total Vendor Bills:** **{tot_bills:,.2f} {comp_curr}** ({len(vendor_bills)} bill(s))\n"
                res += f"• **Outstanding Due (Receivable from Customer):** **{rec_due:,.2f} {comp_curr}**\n"
                if pay_due > 0:
                    res += f"• **Outstanding Due (Payable to Vendor):** **{pay_due:,.2f} {comp_curr}**\n"

                if recent_moves:
                    res += f"\n#### Recent Accounting Documents ({len(recent_moves)})\n\n"
                    res += "| Date | Document # | Type | Total | Due | Status | Actions |\n"
                    res += "|---|---|---|---|---|---|---|\n"
                    for m in recent_moves:
                        curr = _currency_name(m.currency_id)
                        kind = "Invoice" if m.move_type == 'out_invoice' else ("Bill" if m.move_type == 'in_invoice' else "Refund")
                        pay_st = m.payment_state.replace('_', ' ').title() if getattr(m, 'payment_state', None) else m.state.title()
                        doc_name = m.name or f"Draft #{m.id}"
                        actions = f"[View](/web#id={m.id}&model=account.move&view_type=form)"
                        if m.move_type == 'out_invoice':
                            actions += f" [PDF]({_get_vat_report_pdf_url(m.id)})"
                        res += f"| {m.invoice_date or '—'} | **{doc_name}** | {kind} | {m.amount_total:,.2f} {curr} | {m.amount_residual:,.2f} | {pay_st} | {actions} |\n"

                res += f"\nDirect Navigation:\n"
                res += f"- [View Partner Profile in 360 Accounting](/web#id={partner.id}&model=res.partner&view_type=form)\n"
                res += f"- [Show Unpaid Invoices](ask:Show unpaid invoices for {partner.name})\n"
                res += f"- [Aged Balance Report](ask:Show aged balance for {partner.name})\n"
                return res

            @tool
            def get_product_details_and_history(product_name: str) -> str:
                """Retrieves product information, internal code, sales price, cost price, stock on hand, forecasted quantities, and recent invoices featuring this product.
                'product_name': Name or reference of the product (e.g. 'Apple', 'goods', 'milk')."""
                env = request.env
                clean_name = (product_name or '').strip()
                for prefix in [
                    'ask:Show details and sales history for product',
                    'ask:show details and sales history for product',
                    'show details and sales history for product',
                    'details for product',
                    'sales history for product',
                ]:
                    if clean_name.lower().startswith(prefix.lower()):
                        clean_name = clean_name[len(prefix):].strip()
                clean_name = clean_name.strip(' \'\":')

                if not clean_name:
                    return "Please provide a product name or reference code."

                prods = env['product.product'].sudo().search([
                    '|', ('name', 'ilike', clean_name), ('default_code', 'ilike', clean_name)
                ], limit=5)
                if not prods:
                    tmpls = env['product.template'].sudo().search([('name', 'ilike', clean_name)], limit=1)
                    if tmpls:
                        prods = tmpls.product_variant_ids[:1]

                if not prods:
                    return f"No product found matching '{clean_name}' in 360 Accounting."

                prod = prods[0]
                request._viewed_doc = {'model': 'product.product', 'id': prod.id, 'name': prod.name}
                comp_curr = _currency_name(env.company.currency_id)
                price = getattr(prod, 'lst_price', 0.0) or getattr(prod, 'list_price', 0.0)
                cost = getattr(prod, 'standard_price', 0.0)
                qty_hand = getattr(prod, 'qty_available', 0.0)
                qty_forecast = getattr(prod, 'virtual_available', 0.0)
                categ = prod.categ_id.name if prod.categ_id else 'All'

                lines = env['account.move.line'].sudo().search([
                    ('product_id', '=', prod.id),
                    ('move_id.state', '=', 'posted')
                ], limit=10, order='date desc, id desc')

                res = f"### Product Profile: **{prod.name}**\n\n"
                res += f"• **Product Name:** {prod.name}\n"
                if prod.default_code:
                    res += f"• **Internal Reference:** {prod.default_code}\n"
                if getattr(prod, 'barcode', None):
                    res += f"• **Barcode:** {prod.barcode}\n"
                res += f"• **Category:** {categ}\n"
                res += f"• **Sales Price:** **{price:,.2f} {comp_curr}**\n"
                res += f"• **Cost Price:** {cost:,.2f} {comp_curr}\n"
                res += f"• **Quantity on Hand:** **{qty_hand:,.2f}**\n"
                res += f"• **Forecasted Quantity:** {qty_forecast:,.2f}\n"

                if lines:
                    res += f"\n#### Recent Sales & Invoices ({len(lines)})\n\n"
                    res += "| Date | Document # | Customer / Partner | Quantity | Unit Price | Subtotal |\n"
                    res += "|---|---|---|---|---|---|\n"
                    for l in lines:
                        pname = l.partner_id.name if l.partner_id else "N/A"
                        doc_name = l.move_id.name or f"Draft #{l.move_id.id}"
                        curr = _currency_name(l.currency_id or env.company.currency_id)
                        plink = f"[{pname}](ask:Show me all invoices and financial details for {pname})" if pname != "N/A" else "—"
                        res += f"| {l.date or '—'} | **{doc_name}** | {plink} | {l.quantity:,.2f} | {l.price_unit:,.2f} | {l.price_subtotal:,.2f} {curr} |\n"

                res += f"\nDirect Navigation:\n"
                res += f"- [View Product in 360 Accounting](/web#id={prod.id}&model=product.product&view_type=form)\n"
                res += f"- [Available Stock in Inventory](ask:Show available products in inventory)\n"
                return res

            # =========================================================================
            # LEVEL 5: ACTION-ORIENTED OPERATIONS
            # =========================================================================

            @tool
            def register_document_payment(reference: str, amount: float = 0.0, journal_name: str = "") -> str:
                """Registers and reconciles a payment for an unpaid customer invoice or vendor bill in 360 Accounting.
                'reference': Document number (e.g. 'INV/2026/00035' or 'BILL/2026/09/0001').
                'amount': Payment amount (default 0.0 pays full remaining residual balance).
                'journal_name': Optional payment journal name (e.g. 'Bank', 'SNB', 'Cash')."""
                env = request.env
                clean_ref = reference.strip()
                move = env['account.move'].sudo().search([
                    '|', ('name', '=ilike', clean_ref), ('ref', '=ilike', clean_ref)
                ], limit=1)

                if not move:
                    return f"Cannot register payment: Document '{clean_ref}' not found in 360 Accounting."

                if move.state != 'posted':
                    return f"Cannot register payment: Document '{move.name}' is currently in '{move.state}' state. It must be posted first."

                if move.payment_state in ('paid', 'in_payment'):
                    return f"Notice: Document '{move.name}' is already marked as {move.payment_state.title()} (Balance: 0.00)."

                pay_amt = float(amount or 0.0)
                if pay_amt <= 0.0:
                    pay_amt = move.amount_residual

                user_tz = env.user.tz or env.context.get('tz') or 'Asia/Riyadh'
                ctx = {
                    'active_model': 'account.move',
                    'active_ids': [move.id],
                    'tz': user_tz
                }

                try:
                    wiz_vals = {'amount': pay_amt}
                    if journal_name:
                        journal = env['account.journal'].sudo().search([
                            ('type', 'in', ['bank', 'cash']),
                            '|', ('name', 'ilike', journal_name.strip()), ('code', '=ilike', journal_name.strip())
                        ], limit=1)
                        if journal:
                            wiz_vals['journal_id'] = journal.id

                    wiz = env['account.payment.register'].with_context(**ctx).sudo().create(wiz_vals)
                    res = wiz.action_create_payments()

                    curr = _currency_name(move.currency_id)
                    move.invalidate_recordset(['payment_state', 'amount_residual'])

                    out_msg = f"Successfully registered payment of **{pay_amt:,.2f} {curr}** for **{move.name}**!\n\n"
                    out_msg += f"• **Document:** {move.name} ({move.partner_id.name})\n"
                    out_msg += f"• **Payment Status:** {move.payment_state.replace('_', ' ').title()}\n"
                    out_msg += f"• **Remaining Residual Balance:** **{move.amount_residual:,.2f} {curr}**\n\n"
                    out_msg += f"Direct Action Links:\n"
                    out_msg += f"- [View Document](/web#id={move.id}&model=account.move&view_type=form)\n"

                    request._viewed_doc = {'model': 'account.move', 'id': move.id, 'name': move.name}
                    return out_msg
                except Exception as e:
                    return f"Failed to register payment for '{move.name}': {str(e)}"

            @tool
            def post_accounting_document(reference: str) -> str:
                """Posts (confirms) a draft invoice, vendor bill, or journal entry into active accounting records.
                'reference': Document number or draft name (e.g. 'INV/2026/0001' or numeric ID)."""
                env = request.env
                clean_ref = reference.strip()
                move = env['account.move'].sudo().search([
                    '|', ('name', '=ilike', clean_ref), ('ref', '=ilike', clean_ref)
                ], limit=1)
                if not move and clean_ref.isdigit():
                    move = env['account.move'].sudo().search([('id', '=', int(clean_ref))], limit=1)

                if not move:
                    return f"Document '{clean_ref}' not found in 360 Accounting."

                if move.state == 'posted':
                    return f"Document '{move.name}' is already posted."

                try:
                    move.action_post()
                    request._viewed_doc = {'model': 'account.move', 'id': move.id, 'name': move.name}
                    return f"Successfully posted document **{move.name}** (Partner: {move.partner_id.name if move.partner_id else 'N/A'}, Total: {move.amount_total:,.2f} {_currency_name(move.currency_id)})!\n\n[View Document](/web#id={move.id}&model=account.move&view_type=form)"
                except Exception as e:
                    return f"Failed to post document '{clean_ref}': {str(e)}"

            @tool
            def cancel_accounting_document(reference: str) -> str:
                """Cancels an accounting invoice, vendor bill, or journal entry.
                'reference': Document number or ID."""
                env = request.env
                clean_ref = reference.strip()
                move = env['account.move'].sudo().search([
                    '|', ('name', '=ilike', clean_ref), ('ref', '=ilike', clean_ref)
                ], limit=1)
                if not move and clean_ref.isdigit():
                    move = env['account.move'].sudo().search([('id', '=', int(clean_ref))], limit=1)

                if not move:
                    return f"Document '{clean_ref}' not found in 360 Accounting."

                if move.state == 'cancel':
                    return f"Document '{move.name}' is already cancelled."

                try:
                    move.button_cancel()
                    request._viewed_doc = {'model': 'account.move', 'id': move.id, 'name': move.name}
                    return f"Successfully cancelled document **{move.name}**.\n\n[View Document](/web#id={move.id}&model=account.move&view_type=form)"
                except Exception as e:
                    return f"Failed to cancel document '{clean_ref}': {str(e)}"

            @tool
            def lock_accounting_period_info(lock_date: str = "", lock_type: str = "fiscalyear") -> str:
                """Inspects or sets the fiscal accounting lock dates to prevent unauthorized edits to past periods.
                'lock_date': Date in YYYY-MM-DD format to set, or leave blank to view current lock dates.
                'lock_type': 'fiscalyear' (lock for all non-advisers), 'tax' (lock for tax returns), or 'hard' (lock for all users)."""
                env = request.env
                comp = env.company or env.user.company_id
                if lock_date:
                    try:
                        clean_date = lock_date.strip()
                        if 'tax' in lock_type.lower():
                            comp.sudo().write({'tax_lock_date': clean_date})
                        elif 'hard' in lock_type.lower():
                            comp.sudo().write({'hard_lock_date': clean_date})
                        else:
                            comp.sudo().write({'fiscalyear_lock_date': clean_date})
                        return f"Successfully updated accounting lock date to **{clean_date}**."
                    except Exception as e:
                        return f"Failed to update lock date: {str(e)}"

                res = f"### 360 Accounting — Current Lock Dates\n\n"
                res += f"• **Fiscal Year Lock Date:** {getattr(comp, 'fiscalyear_lock_date', None) or 'Not Set (Unlocked)'}\n"
                res += f"• **Tax / VAT Lock Date:** {getattr(comp, 'tax_lock_date', None) or 'Not Set (Unlocked)'}\n"
                res += f"• **Hard Lock Date (All Users):** {getattr(comp, 'hard_lock_date', None) or 'Not Set (Unlocked)'}\n\n"
                res += "Lock dates prevent modifications or backdated entries before the specified date."
                return res

            # =========================================================================
            # UTILITY, SEARCH, & DRAFT CREATION TOOLS
            # =========================================================================

            @tool
            def search_accounting_documents(query: str = "", doc_type: str = "all", limit: int = 10) -> str:
                """Search for vendor bills, customer invoices, or credit notes in 360 Accounting.
                'query': Search text (vendor/customer name, reference number, date).
                'doc_type': Filter by 'bill' (vendor bills), 'invoice' (customer invoices), 'credit_note', or 'all'.
                'limit': Number of results (default 10)."""
                env = request.env
                domain = []
                dt = (doc_type or 'all').lower().strip()
                if dt in ('bill', 'in_invoice', 'vendor_bill'):
                    domain.append(('move_type', '=', 'in_invoice'))
                elif dt in ('invoice', 'out_invoice', 'customer_invoice'):
                    domain.append(('move_type', '=', 'out_invoice'))
                elif dt in ('credit_note', 'refund'):
                    domain.append(('move_type', 'in', ['out_refund', 'in_refund']))
                else:
                    domain.append(('move_type', 'in', ['out_invoice', 'in_invoice', 'out_refund', 'in_refund']))

                q = (query or '').strip()
                if q:
                    domain.extend(['|', '|', ('name', 'ilike', q), ('ref', 'ilike', q), ('partner_id.name', 'ilike', q)])

                safe_limit = min(max(int(limit or 10), 1), 30)
                records = env['account.move'].sudo().search(domain, limit=safe_limit, order='id desc')
                if not records:
                    return f"No accounting documents found matching '{q}'."

                res = f"Found **{len(records)}** accounting document(s):\n\n"
                for r in records:
                    doc_type_str = "Vendor Bill" if r.move_type == 'in_invoice' else ("Customer Invoice" if r.move_type == 'out_invoice' else "Credit Note")
                    partner_name = r.partner_id.name if r.partner_id else "N/A"
                    curr_sym = _currency_name(r.currency_id)
                    name_str = r.name or f"Draft #{r.id}"
                    res += f"• **{doc_type_str} {name_str}** | Partner: {partner_name} | Date: {r.invoice_date or 'N/A'} | Total: {r.amount_total:,.2f} {curr_sym} | Status: {r.state.title()}\n"
                    res += f"  [View Document](/web#id={r.id}&model=account.move&view_type=form)\n"
                return res

            @tool
            def odoo_search_read(model_name: str, domain: Any = None, fields: Any = None, limit: int = 15, order: str = "id desc") -> str:
                """Search and query database records directly from any model (e.g. 'account.move', 'sale.order', 'purchase.order', 'product.product', 'res.partner') using request.env.
                'domain': Filter criteria e.g. [["move_type", "=", "out_invoice"], ["state", "=", "posted"]].
                'fields': List of field names e.g. ["name", "partner_id", "amount_total", "invoice_date"].
                'limit': Max records to return (default 15).
                'order': Ordering string e.g. 'amount_total desc' or 'id desc'."""
                env = request.env
                clean_model = (model_name or '').strip().lower().replace(' ', '.')
                if clean_model not in env:
                    return f"Model '{model_name}' is not installed or available in 360 Accounting."
                try:
                    model_obj = env[clean_model].sudo()
                    p_domain = _clean_domain(domain)
                    p_fields = _sanitize_fields(model_obj, fields)
                    safe_limit = min(max(int(limit or 15), 1), 50)

                    clean_order = (order or 'id desc').strip()
                    if 'total amount' in clean_order.lower():
                        clean_order = re.sub(r'total\s+amount', 'amount_total', clean_order, flags=re.IGNORECASE)
                    elif clean_order.lower() in ('total', 'amount'):
                        clean_order = 'amount_total desc'

                    try:
                        records = model_obj.search_read(
                            domain=p_domain,
                            fields=p_fields,
                            limit=safe_limit,
                            order=clean_order
                        )
                    except Exception:
                        records = model_obj.search_read(
                            domain=p_domain,
                            limit=safe_limit,
                            order='id desc'
                        )

                    if not records:
                        return f"No records found in database model '{clean_model}' matching filter: {p_domain}"

                    formatted = [_format_record(r) for r in records]
                    return json.dumps(formatted, indent=2, default=str)
                except Exception as e:
                    return f"Error querying database model '{clean_model}': {str(e)}"

            @tool
            def odoo_read_group(model_name: str, domain: Any = None, fields: Any = None, groupby: Any = None, limit: int = 20, orderby: str = "") -> str:
                """Perform exact database aggregations (SUM, COUNT, AVG, grouping by partner/month/category/status) directly on any model."""
                env = request.env
                clean_model = (model_name or '').strip().lower().replace(' ', '.')
                if clean_model not in env:
                    return f"Model '{model_name}' is not installed or available in 360 Accounting."
                try:
                    p_domain = _clean_domain(domain)
                    p_fields = _ensure_list(fields)
                    p_groupby = _ensure_list(groupby)
                    safe_limit = min(max(int(limit or 20), 1), 100)
                    clean_fields = [f.split(':')[0] if ':' in f else f for f in p_fields]

                    res = env[clean_model].sudo().read_group(
                        domain=p_domain,
                        fields=clean_fields if clean_fields else [],
                        groupby=p_groupby if p_groupby else [],
                        limit=safe_limit,
                        orderby=orderby if orderby else None
                    )
                    formatted = [_format_record(r) for r in res]
                    return json.dumps(formatted, indent=2, default=str)
                except Exception as e:
                    return f"Database aggregation error on '{clean_model}': {str(e)}"

            @tool
            def odoo_raw_sql_query(query: str) -> str:
                """Execute a READ-ONLY SELECT SQL query directly on PostgreSQL using active database cursor (request.env.cr)."""
                env = request.env
                clean_q = query.strip()
                if not clean_q.upper().startswith("SELECT"):
                    return "Database Safety Restriction: Only SELECT queries are permitted."
                try:
                    env.cr.execute(clean_q)
                    columns = [desc[0] for desc in env.cr.description]
                    rows = env.cr.fetchall()
                    result = [dict(zip(columns, row)) for row in rows[:50]]
                    if not result:
                        return "SQL Query executed successfully. 0 matching records found."
                    return json.dumps(result, indent=2, default=str)
                except Exception as e:
                    return f"PostgreSQL SQL Error: {str(e)}"

            @tool
            def odoo_inspect_model_fields(model_name: str) -> str:
                """Inspect available database fields and field labels for any model in 360 Accounting."""
                env = request.env
                clean_model = (model_name or '').strip().lower().replace(' ', '.')
                if clean_model not in env:
                    return f"Model '{model_name}' does not exist."
                try:
                    model_obj = env[clean_model].sudo()
                    fields_info = []
                    for fname, field in model_obj._fields.items():
                        fields_info.append({
                            "field": fname,
                            "type": field.type,
                            "label": getattr(field, 'string', fname)
                        })
                    return json.dumps(fields_info[:60], indent=2)
                except Exception as e:
                    return f"Error inspecting model '{model_name}': {str(e)}"

            def _create_move_record(move_type: str, partner_name: str, product_name: str = "", quantity: float = 1.0, price_unit: float = 0.0) -> str:
                env = request.env
                partner = env['res.partner'].sudo().search([('name', 'ilike', partner_name)], limit=1)
                if not partner:
                    partner = env['res.partner'].sudo().create({'name': partner_name})
                
                product = None
                p_name_query = (product_name or '').strip()
                
                if p_name_query and 'product.product' in env:
                    product = env['product.product'].sudo().search([
                        '|', ('name', 'ilike', p_name_query), ('default_code', 'ilike', p_name_query)
                    ], limit=1)
                    if not product and 'product.template' in env:
                        tmpl = env['product.template'].sudo().search([('name', 'ilike', p_name_query)], limit=1)
                        if tmpl and tmpl.product_variant_id:
                            product = tmpl.product_variant_id

                if not product and p_name_query:
                    if 'product.product' in env:
                        try:
                            product = env['product.product'].sudo().create({
                                'name': p_name_query,
                                'type': 'service',
                                'lst_price': float(price_unit or 50.0),
                                'standard_price': float(price_unit or 50.0),
                            })
                        except Exception:
                            product = None

                if not product and not p_name_query and 'product.product' in env:
                    product = env['product.product'].sudo().search([('active', '=', True)], limit=1)

                final_price = float(price_unit or 0.0)
                if final_price <= 0.0 and product:
                    try:
                        if move_type in ('out_invoice', 'out_refund'):
                            final_price = float(getattr(product, 'list_price', 0.0) or getattr(product, 'lst_price', 0.0) or getattr(product, 'standard_price', 0.0) or 0.0)
                        else:
                            final_price = float(getattr(product, 'standard_price', 0.0) or getattr(product, 'list_price', 0.0) or 0.0)
                    except Exception:
                        final_price = 0.0

                if final_price <= 0.0:
                    final_price = 50.0

                item_name = p_name_query if p_name_query else (product.display_name if product else 'Standard Service')
                line_vals = {
                    'name': item_name,
                    'quantity': float(quantity or 1.0),
                    'price_unit': final_price,
                }
                if product:
                    line_vals['product_id'] = product.id

                try:
                    today_str = datetime.now().strftime('%Y-%m-%d')
                    comp = env.company or env.user.company_id
                    
                    payment_term = getattr(partner, 'property_payment_term_id', False)
                    if payment_term and payment_term.company_id and payment_term.company_id != comp:
                        valid_term = env['account.payment.term'].sudo().search([
                            ('company_id', 'in', [comp.id, False])
                        ], limit=1)
                        payment_term = valid_term if valid_term else False

                    move_vals = {
                        'move_type': move_type,
                        'partner_id': partner.id,
                        'company_id': comp.id,
                        'invoice_date': today_str,
                        'invoice_line_ids': [(0, 0, line_vals)]
                    }
                    if payment_term:
                        move_vals['invoice_payment_term_id'] = payment_term.id
                    elif hasattr(env['account.move'], 'invoice_payment_term_id'):
                        move_vals['invoice_payment_term_id'] = False

                    move = env['account.move'].sudo().with_company(comp).create(move_vals)
                    request._created_move_id = move.id
                    
                    doc_label = "Customer Invoice" if move_type == 'out_invoice' else \
                                "Vendor Bill" if move_type == 'in_invoice' else \
                                "Customer Credit Note" if move_type == 'out_refund' else "Vendor Credit Note"

                    total_amt = move.amount_total or (line_vals['quantity'] * line_vals['price_unit'])
                    curr = _currency_name(comp.currency_id)

                    res = f"Successfully created draft **{doc_label}** (ID: {move.id}, Name: {move.name or 'Draft'}) for **{partner.name}**!\n\n"
                    res += f"• **Product:** {item_name}\n"
                    res += f"• **Quantity:** {quantity}\n"
                    res += f"• **Unit Price:** {final_price:,.2f} {curr}\n"
                    res += f"• **Total Amount:** {total_amt:,.2f} {curr}\n\n"
                    res += f"Direct Document Action Links:\n"
                    if move_type == 'out_invoice':
                        res += f"- [Download Tax Invoice PDF]({_get_vat_report_pdf_url(move.id)})\n"
                    res += f"- [View Document](/web#id={move.id}&model=account.move&view_type=form)"
                    return res
                except Exception as e:
                    return f"Failed to create {move_type} document: {str(e)}"

            @tool
            def create_draft_invoice(customer_name: str, product_name: str, quantity: float = 1.0, price_unit: float = 0.0) -> str:
                """Creates a new draft customer invoice in 360 Accounting."""
                return _create_move_record('out_invoice', customer_name, product_name, quantity, price_unit)

            @tool
            def create_draft_bill(vendor_name: str, product_name: str, quantity: float = 1.0, price_unit: float = 0.0) -> str:
                """Creates a new draft vendor bill / expense in 360 Accounting."""
                return _create_move_record('in_invoice', vendor_name, product_name, quantity, price_unit)

            @tool
            def create_accounting_document(document_type: str, partner_name: str, product_name: str, quantity: float = 1.0, price_unit: float = 0.0) -> str:
                """Creates any draft accounting document (invoice, bill, credit note) in 360 Accounting."""
                move_type_map = {
                    'invoice': 'out_invoice',
                    'customer_invoice': 'out_invoice',
                    'bill': 'in_invoice',
                    'vendor_bill': 'in_invoice',
                    'credit_note': 'out_refund',
                    'customer_credit_note': 'out_refund',
                    'vendor_credit_note': 'in_refund'
                }
                m_type = move_type_map.get(document_type.lower().strip(), 'out_invoice')
                return _create_move_record(m_type, partner_name, product_name, quantity, price_unit)

            @tool
            def create_inventory_product(product_name: str, sales_price: float = 0.0, category_name: str = "") -> str:
                """Creates a new product record directly in the product catalog / inventory master."""
                env = request.env
                try:
                    categ_id = False
                    p_cat = (category_name or '').strip()
                    if p_cat and 'product.category' in env:
                        cat = env['product.category'].sudo().search([('name', 'ilike', p_cat)], limit=1)
                        if cat:
                            categ_id = cat.id

                    vals = {
                        'name': product_name.strip(),
                        'list_price': float(sales_price or 0.0),
                        'type': 'consu' if 'good' in p_cat.lower() or 'storable' in p_cat.lower() else 'service'
                    }
                    if categ_id:
                        vals['categ_id'] = categ_id

                    tmpl = env['product.template'].sudo().create(vals)
                    product = tmpl.product_variant_id or env['product.product'].sudo().search([('product_tmpl_id', '=', tmpl.id)], limit=1)
                    prod_id = product.id if product else tmpl.id

                    request._created_product_id = prod_id
                    curr = _currency_name(env.company.currency_id)

                    res = f"Successfully created product **{tmpl.name}** in the Product Master!\n\n"
                    res += f"• **Sales Price:** {tmpl.list_price:,.2f} {curr}\n"
                    res += f"• **Product Category:** {tmpl.categ_id.name if tmpl.categ_id else 'All'}\n\n"
                    res += f"Direct Action Links:\n"
                    res += f"- [View Product](/web#id={prod_id}&model=product.product&view_type=form)"
                    return res
                except Exception as e:
                    return f"Failed to create product in Product Master: {str(e)}"

            @tool
            def get_today_total_invoices() -> str:
                """Calculates and returns today's total customer invoices count and total amount in 360 Accounting."""
                env = request.env
                today_str = datetime.now().strftime('%Y-%m-%d')
                domain = [('move_type', '=', 'out_invoice'), ('invoice_date', '=', today_str)]
                invoices = env['account.move'].sudo().search(domain)
                count = len(invoices)
                total_amt = sum(invoices.mapped('amount_total'))
                curr = _currency_name(env.company.currency_id)
                return f"Today ({today_str}), there are **{count}** customer invoice(s) generated with a total amount of **{total_amt:,.2f} {curr}**."

            @tool
            def get_today_total_expenses() -> str:
                """Calculates and returns today's total vendor expenses/bills count and total amount in 360 Accounting."""
                env = request.env
                today_str = datetime.now().strftime('%Y-%m-%d')
                domain = [('move_type', '=', 'in_invoice'), ('invoice_date', '=', today_str)]
                bills = env['account.move'].sudo().search(domain)
                count = len(bills)
                total_amt = sum(bills.mapped('amount_total'))
                curr = _currency_name(env.company.currency_id)
                return f"Today ({today_str}), there are **{count}** vendor expense bill(s) recorded with a total amount of **{total_amt:,.2f} {curr}**."

            @tool
            def get_today_invoice_list_view() -> str:
                """Returns today's invoice count and triggers opening the list view of today's customer invoices."""
                env = request.env
                today_str = datetime.now().strftime('%Y-%m-%d')
                domain = [('move_type', '=', 'out_invoice'), ('invoice_date', '=', today_str)]
                invoices = env['account.move'].sudo().search(domain, order='id desc')
                count = len(invoices)
                total_amt = sum(invoices.mapped('amount_total'))
                curr = _currency_name(env.company.currency_id)

                request._trigger_invoice_list_view = True
                res = f"Today ({today_str}), there are **{count}** customer invoice(s) total amounting to **{total_amt:,.2f} {curr}**.\n\n"
                res += f"Opening the List View for today's invoices..."
                return res

            @tool
            def get_today_invoices_with_pdf_links(limit: int = 5) -> str:
                """Returns today's customer invoices along with PDF report download links and view links."""
                env = request.env
                today_str = datetime.now().strftime('%Y-%m-%d')
                domain = [('move_type', '=', 'out_invoice'), ('invoice_date', '=', today_str)]
                invoices = env['account.move'].sudo().search(domain, limit=limit, order='id desc')
                if not invoices:
                    invoices = env['account.move'].sudo().search([('move_type', '=', 'out_invoice')], limit=limit, order='id desc')
                    if not invoices:
                        return "No customer invoices found in the database."
                    res = f"No customer invoices were generated today ({today_str}). Here are the most recent customer invoices:\n\n"
                else:
                    res = f"Found {len(invoices)} invoice(s) for today ({today_str}):\n\n"

                for inv in invoices:
                    customer_name = inv.partner_id.name if inv.partner_id else "N/A"
                    customer_link = f"[{customer_name}](ask:Show me all invoices and financial details for {customer_name})" if inv.partner_id else "N/A"
                    inv_name = inv.name or f"Invoice #{inv.id}"
                    curr = _currency_name(inv.currency_id)
                    res += f"• **Invoice {inv_name}** (Customer: {customer_link}, Total: {inv.amount_total:,.2f} {curr}, Tax: {inv.amount_tax:,.2f} {curr}, Status: {inv.state})\n"
                    res += f"  [Download Tax Invoice PDF ({inv_name})]({_get_vat_report_pdf_url(inv.id)})\n"
                    res += f"  [View Invoice ({inv_name})](/web#id={inv.id}&model=account.move&view_type=form)\n\n"

                return res

            @tool
            def get_available_products(query: str = "") -> str:
                """Returns a list of products available in the inventory along with quantity on hand, price, and details."""
                env = request.env
                domain = [('active', '=', True)]
                if query:
                    domain = ['&', ('active', '=', True), '|', ('name', 'ilike', query), ('default_code', 'ilike', query)]
                
                products = env['product.product'].sudo().search(domain, limit=25)
                curr = _currency_name(env.company.currency_id)
                if not products:
                    templates = env['product.template'].sudo().search([('active', '=', True)], limit=25)
                    if not templates:
                        return "No products found in the inventory database."
                    res = f"Found {len(templates)} product(s) in inventory:\n\n"
                    for t in templates:
                        qty = getattr(t, 'qty_available', 0.0)
                        price = getattr(t, 'list_price', 0.0)
                        res += f"• **[{t.name}](ask:Show details and sales history for product {t.name})** (Code: {t.default_code or 'N/A'}, Price: {price:,.2f} {curr}, Qty Available: {qty})\n"
                    return res

                res = f"Found {len(products)} product(s) in inventory:\n\n"
                for p in products:
                    qty = getattr(p, 'qty_available', 0.0)
                    price = getattr(p, 'lst_price', 0.0) or getattr(p, 'list_price', 0.0)
                    code = p.default_code or 'N/A'
                    res += f"• **[{p.name}](ask:Show details and sales history for product {p.name})** (Internal Ref: {code}, Sales Price: {price:,.2f} {curr}, On Hand Qty: {qty})\n"
                return res

            # =========================================================================
            # LANGCHAIN AGENT & PROMPT ORCHESTRATION
            # =========================================================================

            is_openrouter = not (api_key.startswith("sk-proj-") or api_key.startswith("sk-admin-"))
            llm_kwargs = {
                "model": model_name,
                "api_key": api_key,
                "temperature": 0,
            }
            if is_openrouter:
                llm_kwargs["base_url"] = "https://openrouter.ai/api/v1"

            llm = ChatOpenAI(**llm_kwargs)

            agent_tools = [
                # Level 1 & 2:
                get_financial_balances,
                get_unpaid_invoices_or_bills,
                get_document_details,
                get_recent_payments,
                get_sales_and_expenses_summary,
                get_credit_and_debit_notes,
                get_account_or_journal_transactions,
                search_accounting_documents,
                get_partner_details_and_history,
                get_product_details_and_history,
                # Level 3 Reports:
                get_financial_report,
                get_aged_partner_report,
                # Level 4 Analytics & Comparisons:
                analyze_financial_comparison,
                get_top_partners,
                get_business_kpis_and_analytics,
                # Level 5 Actions:
                register_document_payment,
                post_accounting_document,
                cancel_accounting_document,
                lock_accounting_period_info,
                create_draft_invoice,
                create_draft_bill,
                create_accounting_document,
                create_inventory_product,
                # Utilities:
                get_today_total_invoices,
                get_today_total_expenses,
                get_today_invoice_list_view,
                get_today_invoices_with_pdf_links,
                get_available_products,
                odoo_search_read,
                odoo_read_group,
                odoo_raw_sql_query,
                odoo_inspect_model_fields,
            ]

            system_instruction = (
                "You are an expert, professional 360 Accounting AI Assistant with direct access to the live accounting database.\n\n"
                "STRICT BRANDING MANDATE:\n"
                "- NEVER mention or use the words 'Odoo' or 'Odoo ERP' in any response to the user under any circumstances.\n"
                "- ALWAYS refer to the system, software, or platform as '360 Accounting' or 'this accounting system'.\n\n"
                "STRICT ZERO-HALLUCINATION & TRUTH-IN-DATA MANDATE (CRITICAL):\n"
                "- NEVER invent, fabricate, or make up ANY customer name, vendor name, invoice number, date, or monetary amount.\n"
                "- Every single invoice number, partner name, amount, and date in your response MUST come directly from database tool outputs.\n"
                "- If a database tool returns no records, state clearly: 'No matching records found in 360 Accounting.' Under NO circumstances make up example or fake invoices.\n\n"
                "CLICKABLE ENTITIES & INTELLIGENT NAVIGATION (CRITICAL):\n"
                "- Whenever you mention ANY partner (customer, vendor, or company name) in your response (e.g. ABC, sandeep, Dream Art Advertising), ALWAYS make their name clickable:\n"
                "  `[{{Partner Name}}](ask:Show me all invoices and financial details for {{Partner Name}})`\n"
                "- Whenever you mention ANY product in your response, ALWAYS make its name clickable:\n"
                "  `[{{Product Name}}](ask:Show details and sales history for product {{Product Name}})`\n"
                "- Clicking these links automatically runs queries to show complete financial breakdowns, invoices, and sales history.\n\n"
                "QUESTION CLASSIFICATION & TOOL ROUTING GUIDE:\n"
                "🟢 LEVEL 1 — Basic Data Lookup:\n"
                "- 'What is my current invoice balance?' / 'How much money do customers owe us?' / 'What is the current bank balance?' / 'What is the total receivable/payable amount?': Call `get_financial_balances()`.\n"
                "- 'Show me all unpaid invoices' / 'Which bills are unpaid?': Call `get_unpaid_invoices_or_bills(doc_type='invoice' or 'bill')`.\n"
                "- 'When is invoice INV/... due?' / 'Details of BILL/...': Call `get_document_details(reference=...)`.\n"
                "- 'Show me all invoices for ABC' / 'Financial details for partner ABC' / 'Customer profile': Call `get_partner_details_and_history(partner_name=...)`.\n"
                "- 'Details for product ...' / 'Sales history for product ...': Call `get_product_details_and_history(product_name=...)`.\n"
                "- 'What payments were received today?' / 'Show me the last 10 payments': Call `get_recent_payments()`.\n"
                "- 'Show me this month's expenses' / 'Total sales this month': Call `get_sales_and_expenses_summary()`.\n"
                "- 'Show me all credit notes / debit notes': Call `get_credit_and_debit_notes()`.\n\n"
                "🟡 LEVEL 2 — Filtering & Specific Information:\n"
                "- 'Show me unpaid invoices above 50,000' / 'vendor bills above 1 lakh': Call `get_unpaid_invoices_or_bills(min_amount=...)`.\n"
                "- 'Show me overdue invoices' / 'overdue by more than 30 days': Call `get_unpaid_invoices_or_bills(is_overdue=True, days_overdue=30)`.\n"
                "- 'Show me invoices due next week' / 'due this month': Call `get_unpaid_invoices_or_bills(due_window=...)`.\n"
                "- 'Show me expenses for Sales department' / 'between January and March' / 'in August': Call `get_sales_and_expenses_summary(...)`.\n"
                "- 'Show me payments made to ABC Company this year': Call `get_recent_payments(partner_name='ABC Company')`.\n"
                "- 'Show me all transactions for account 400000' / 'for this journal': Call `get_account_or_journal_transactions(...)`.\n\n"
                "🟠 LEVEL 3 — Accounting Reports:\n"
                "- 'Profit and Loss' / 'P&L' / 'total revenue this year' / 'net profit': Call `get_financial_report(report_name='pnl')`.\n"
                "- 'Balance Sheet': Call `get_financial_report(report_name='balance_sheet')`.\n"
                "- 'Trial Balance': Call `get_financial_report(report_name='trial_balance')`.\n"
                "- 'Aged Receivables' / 'Aged Payables' / 'Accounts Receivable report': Call `get_aged_partner_report()`.\n"
                "- 'Tax report' / 'VAT amount for this month': Call `get_financial_report(report_name='tax_report')`.\n"
                "- 'General Ledger': Call `get_financial_report(report_name='general_ledger')`.\n\n"
                "🔵 LEVEL 4 — Comparison & Analysis:\n"
                "- 'Compare this month sales with last month' / 'Compare expenses' / 'Why did expenses increase?': Call `analyze_financial_comparison(...)`.\n"
                "- 'Top 10 customers by revenue' / 'Highest outstanding balance' / 'Vendor received highest payment': Call `get_top_partners(...)`.\n"
                "- 'Percentage of invoices overdue' / 'Average invoice value' / 'Top products': Call `get_business_kpis_and_analytics()`.\n\n"
                "🔴 LEVEL 5 — Action-Oriented Operations:\n"
                "- 'Create an invoice for ABC' / 'Create a vendor bill': Call `create_draft_invoice(...)` or `create_draft_bill(...)`.\n"
                "- 'Register a payment for invoice INV/...': Call `register_document_payment(reference=...)`.\n"
                "- 'Post this invoice / journal entry': Call `post_accounting_document(reference=...)`.\n"
                "- 'Cancel this invoice': Call `cancel_accounting_document(reference=...)`.\n"
                "- 'Lock this accounting period': Call `lock_accounting_period_info(...)`.\n\n"
                "RESPONSE FORMATTING RULES:\n"
                "- Structure your answers clearly with concise introductory summaries and clean Markdown section headers (e.g. `### Section Title`).\n"
                "- When listing multiple accounts, documents, or items, use numbered lists (`1. **Account Name** – Details...`) followed by bullet points (`- Bullet detail...`) for outstanding clarity.\n"
                "- Always format currency with commas and 2 decimals (e.g. 24,892.58 SAR).\n"
                "- Present tables clearly using standard Markdown tables with aligned headers.\n"
                "- Always preserve direct action links like `[View Document](/web#id=...)` and `[Download Tax Invoice PDF](/report/pdf/advanced_vat_invoice.action_report_vat_report/...)`.\n"
                "- Keep explanations structured, executive-ready, and easy to read."
            )

            prompt = ChatPromptTemplate.from_messages([
                ("system", system_instruction),
                MessagesPlaceholder(variable_name="chat_history", optional=True),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ])

            agent = create_tool_calling_agent(
                llm=llm,
                tools=agent_tools,
                prompt=prompt,
            )

            agent_executor = AgentExecutor(
                agent=agent,
                tools=agent_tools,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=6
            )

            today_str = datetime.now().strftime('%Y-%m-%d')
            user_custom_prompt = (getattr(user, 'chatting_system_prompt', '') or '').strip()
            custom_prompt_instruction = ""
            if user_custom_prompt:
                custom_prompt_instruction = f"\nUser System Instructions: {user_custom_prompt}"

            ref_match = re.search(r'\b((?:BILL|INV|RINV|RBILL|PO|SO|WH/[A-Z0-9]+)[/\-_A-Z0-9]*\d+[/\-_A-Z0-9]*)\b', message, flags=re.IGNORECASE)
            ref_hint = ""
            if ref_match:
                detected_ref = ref_match.group(1).strip()
                if any(kw in message.lower() for kw in ['pay', 'register payment', 'receive payment']):
                    ref_hint = f"\nSystem Detected Intent: Register payment for '{detected_ref}'. Call `register_document_payment(reference='{detected_ref}')`."
                elif any(kw in message.lower() for kw in ['post', 'confirm']):
                    ref_hint = f"\nSystem Detected Intent: Post document '{detected_ref}'. Call `post_accounting_document(reference='{detected_ref}')`."
                elif any(kw in message.lower() for kw in ['cancel']):
                    ref_hint = f"\nSystem Detected Intent: Cancel document '{detected_ref}'. Call `cancel_accounting_document(reference='{detected_ref}')`."
                else:
                    ref_hint = f"\nSystem Detected Document Reference: '{detected_ref}'. Call `get_document_details(reference='{detected_ref}')` to retrieve complete details and line items."

            msg_lower = message.lower()
            if any(k in msg_lower for k in ['invoices and financial details for', 'financial details for', 'partner profile', 'customer details', 'vendor details']) or 'ask:show me all invoices and financial details for' in msg_lower:
                m_p = re.search(r'(?:for|partner)\s+([A-Za-z0-9\s&.\-_]+?)(?:\.|\?|$)', message, flags=re.IGNORECASE)
                p_cand = m_p.group(1).strip() if m_p else ""
                ref_hint += f"\nSystem Directive: User is asking for complete details and invoices for a partner. Call `get_partner_details_and_history(partner_name='{p_cand}')`."
            elif any(k in msg_lower for k in ['sales history for product', 'details for product', 'product profile']) or 'ask:show details and sales history for product' in msg_lower:
                m_prod = re.search(r'product\s+([A-Za-z0-9\s&.\-_]+?)(?:\.|\?|$)', message, flags=re.IGNORECASE)
                prod_cand = m_prod.group(1).strip() if m_prod else ""
                ref_hint += f"\nSystem Directive: User is asking for product details and history. Call `get_product_details_and_history(product_name='{prod_cand}')`."
            elif any(k in msg_lower for k in ['bank balance', 'cash balance', 'current balance', 'how much money do customers owe', 'customer owe', 'total receivable', 'total payable', 'how much do we owe our vendors', 'vendor owe', 'invoice balance']):
                ref_hint += "\nSystem Directive: User is asking for company financial, bank, receivable, or payable balances. Call `get_financial_balances()`."
            elif any(k in msg_lower for k in ['profit and loss', 'p&l', 'trial balance', 'balance sheet', 'tax report', 'vat amount', 'vat return', 'net profit', 'total revenue this year', 'total expense this year']):
                ref_hint += "\nSystem Directive: User is asking for an accounting report. Call `get_financial_report(...)` with the appropriate report_name."
            elif any(k in msg_lower for k in ['aged receivable', 'aged payable', 'aged partner', 'accounts receivable report', 'accounts payable report']):
                is_p = 'payable' in msg_lower or 'vendor' in msg_lower
                ref_hint += f"\nSystem Directive: User is asking for aged partner balance. Call `get_aged_partner_report(report_type='{'payable' if is_p else 'receivable'}')`."
            elif any(k in msg_lower for k in ['compare', 'growth', 'why did expenses increase', 'why did sales']):
                ref_hint += "\nSystem Directive: User is asking for financial comparison. Call `analyze_financial_comparison(...)`."
            elif any(k in msg_lower for k in ['top 10', 'top customers', 'top vendors', 'highest outstanding', 'highest payment']):
                ref_hint += "\nSystem Directive: User is asking for top customer/vendor ranking. Call `get_top_partners(...)`."
            elif any(k in msg_lower for k in ['unpaid', 'not paid', 'partially paid', 'pending payment', 'outstanding', 'due invoice', 'due bill', 'overdue']):
                if any(k in msg_lower for k in ['bill', 'vendor', 'expense']):
                    ref_hint += "\nSystem Directive: The user is asking for unpaid vendor bills. Call `get_unpaid_invoices_or_bills(doc_type='bill')`."
                else:
                    ref_hint += "\nSystem Directive: The user is asking for unpaid customer invoices. Call `get_unpaid_invoices_or_bills(doc_type='invoice')`."

            input_query = f"Date Today: {today_str}.\nQuestion: {message}{custom_prompt_instruction}{ref_hint}"

            chat_history = []
            if history:
                from langchain_core.messages import HumanMessage, AIMessage
                for msg in history:
                    if msg.get('role') == 'user':
                        chat_history.append(HumanMessage(content=msg['content']))
                    elif msg.get('role') == 'assistant':
                        chat_history.append(AIMessage(content=msg['content']))

            response = agent_executor.invoke({
                "input": input_query,
                "chat_history": chat_history
            })

            reply_text = response.get("output", "")
            res_data = {'reply': reply_text}

            created_move_id = getattr(request, '_created_move_id', None)
            created_product_id = getattr(request, '_created_product_id', None)
            viewed_doc = getattr(request, '_viewed_doc', None)
            trigger_list_view = getattr(request, '_trigger_invoice_list_view', False)

            if not trigger_list_view and any(kw in message.lower() for kw in ['today invoice list view', "today's invoice list view", 'show today invoice list']):
                trigger_list_view = True

            if any(kw in msg_lower for kw in ['unpaid invoice', 'all unpaid invoices', 'unpaid bill', 'all unpaid bills']):
                is_bill = any(k in msg_lower for k in ['bill', 'vendor', 'expense'])
                res_data['action'] = {
                    'name': "Unpaid Vendor Bills" if is_bill else "Unpaid Customer Invoices",
                    'type': 'ir.actions.act_window',
                    'res_model': 'account.move',
                    'domain': [
                        ('move_type', '=', 'in_invoice' if is_bill else 'out_invoice'),
                        ('state', '=', 'posted'),
                        ('payment_state', 'in', ['not_paid', 'partial'])
                    ],
                    'view_mode': 'list,form',
                    'views': [[False, 'list'], [False, 'form']],
                    'target': 'current',
                }

            if trigger_list_view:
                today_str = datetime.now().strftime('%Y-%m-%d')
                res_data['action'] = {
                    'name': f"Today's Invoices ({today_str})",
                    'type': 'ir.actions.act_window',
                    'res_model': 'account.move',
                    'domain': [('move_type', '=', 'out_invoice'), ('invoice_date', '=', today_str)],
                    'view_mode': 'list,form',
                    'views': [[False, 'list'], [False, 'form']],
                    'target': 'current',
                }
            elif created_product_id:
                res_data['action'] = {
                    'type': 'ir.actions.act_window',
                    'res_model': 'product.product',
                    'res_id': int(created_product_id),
                    'view_mode': 'form',
                    'views': [[False, 'form']],
                    'target': 'current',
                }
            elif created_move_id:
                move_id = int(created_move_id)
                move_pdf_url = _get_vat_report_pdf_url(move_id)
                if '[Download Tax Invoice PDF]' in reply_text and move_pdf_url not in reply_text:
                    reply_text = reply_text.replace('[Download Tax Invoice PDF]', f'[Download Tax Invoice PDF]({move_pdf_url})')
                if '[Download VAT Invoice PDF]' in reply_text and move_pdf_url not in reply_text:
                    reply_text = reply_text.replace('[Download VAT Invoice PDF]', f'[Download Tax Invoice PDF]({move_pdf_url})')
                if '[View Document]' in reply_text and f'/web#id={move_id}' not in reply_text:
                    reply_text = reply_text.replace('[View Document]', f'[View Document](/web#id={move_id}&model=account.move&view_type=form)')

                res_data['action'] = {
                    'type': 'ir.actions.act_window',
                    'res_model': 'account.move',
                    'res_id': move_id,
                    'view_mode': 'form',
                    'views': [[False, 'form']],
                    'target': 'current',
                }
            elif viewed_doc:
                doc_id = int(viewed_doc['id'])
                doc_model = viewed_doc['model']
                doc_pdf_url = _get_vat_report_pdf_url(doc_id)
                if '[Download Tax Invoice PDF]' in reply_text and doc_pdf_url not in reply_text:
                    reply_text = reply_text.replace('[Download Tax Invoice PDF]', f'[Download Tax Invoice PDF]({doc_pdf_url})')
                if '[Download VAT Invoice PDF]' in reply_text and doc_pdf_url not in reply_text:
                    reply_text = reply_text.replace('[Download VAT Invoice PDF]', f'[Download Tax Invoice PDF]({doc_pdf_url})')
                if '[View Document]' in reply_text and f'/web#id={doc_id}' not in reply_text:
                    reply_text = reply_text.replace('[View Document]', f'[View Document](/web#id={doc_id}&model={doc_model}&view_type=form)')

                if any(kw in message.lower() for kw in ['open', 'show', 'view', 'detail', 'details', 'go to', 'see', 'take me']):
                    res_data['action'] = {
                        'type': 'ir.actions.act_window',
                        'res_model': doc_model,
                        'res_id': doc_id,
                        'view_mode': 'form',
                        'views': [[False, 'form']],
                        'target': 'current',
                    }

            def _enhance_entity_links(text):
                # 1. Partner bullet lines like: - ABC: 5,153.20 SAR
                pattern_bullets = r'(?m)^(\s*[-•*]\s*)([A-Za-z0-9\s&.\'\-_]+?)(:\s*[\d,]+(?:\.\d+)?\s*[A-Z]{2,4})'
                def _rep_b(m):
                    prefix = m.group(1)
                    name = m.group(2).strip(' *')
                    suffix = m.group(3)
                    if '[' in name or ']' in name or name.lower() in ('total', 'subtotal', 'average', 'tax', 'balance', 'variance', 'difference'):
                        return m.group(0)
                    return f"{prefix}**[{name}](ask:Show me all invoices and financial details for {name})**{suffix}"
                text = re.sub(pattern_bullets, _rep_b, text)

                # 2. Customer/Vendor lines like: Customer: ABC or - Customer: ABC
                pattern_cust = r'(?m)^(\s*[-•*]?\s*(?:Customer|Vendor|Partner):\s*)([A-Za-z0-9\s&.\'\-_]+?)(\s*)$'
                def _rep_c(m):
                    prefix = m.group(1)
                    name = m.group(2).strip(' *')
                    suffix = m.group(3)
                    if '[' in name or ']' in name or not name or name.lower() in ('n/a', 'none', 'unknown'):
                        return m.group(0)
                    return f"{prefix}**[{name}](ask:Show me all invoices and financial details for {name})**{suffix}"
                text = re.sub(pattern_cust, _rep_c, text)
                return text

            reply_text = _enhance_entity_links(reply_text)
            reply_text = re.sub(r'\bOdoo\s+ERP\b', '360 Accounting', reply_text, flags=re.IGNORECASE)
            reply_text = re.sub(r'\bOdoo\b', '360 Accounting', reply_text, flags=re.IGNORECASE)
            reply_text = re.sub(
                r'/report/pdf/account\.report_invoice_with_payments/(\d+)',
                r'/report/pdf/advanced_vat_invoice.action_report_vat_report/\1',
                reply_text
            )
            reply_text = re.sub(r'\[Download VAT Invoice PDF\]', '[Download Tax Invoice PDF]', reply_text)
            reply_text = re.sub(r'\[Download VAT Invoice PDF \(([^)]+)\)\]', r'[Download Tax Invoice PDF (\1)]', reply_text)

            res_data['reply'] = reply_text
            return res_data

        except ImportError as e:
            missing_pkg = getattr(e, 'name', None) or str(e)
            err_msg = f"Missing Python dependency on the server: '{missing_pkg}'. Please run: pip install langchain-openai langchain-classic langchain-core in your server's Python virtual environment, then restart the Odoo server."
            _logger.error(f"Chatbot Missing dependency: {str(e)}")
            return {'error': err_msg}
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            _logger.error(f"Chatbot Internal Agent Error: \n{tb}")
            return {'reply': "I apologize, but I couldn't complete that request right now. Please try rephrasing your prompt or check your settings."}
