from odoo import models, api, fields
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

# Child/line item models and system models to exclude from logging
SKIP_MODELS = {
    'user.logs.history',
    
    # Sub-line / child detail item models (prevents log noise on line items)
    'account.move.line',
    'sale.order.line',
    'purchase.order.line',
    'stock.move',
    'stock.move.line',
    'stock.quant',
    'stock.valuation.layer',
    'account.partial.reconcile',
    'account.full.reconcile',
    'account.analytic.line',
    'account.payment.register',
    
    # Framework infrastructure
    'bus.bus',
    'bus.presence',
    'ir.attachment',
    'ir.logging',
    'ir.property',
    'ir.session',
    'ir.ui.view',
    'ir.ui.menu',
    'ir.model.data',
    'ir.model.fields',
    'ir.model',
    'mail.message',
    'mail.followers',
    'mail.notification',
    'mail.tracking.value',
    'mail.activity',
    'mail.compose.message',
    'ir.cron',
    'ir.filters',
    'res.users.log',
    'ir.module.module',
    'web_editor.assets',
    'ir.asset',
    'ir.actions.act_window',
    'ir.actions.actions',
    'ir.actions.server',
    'ir.exports',
    'ir.exports.line',
    'digest.digest',
    'res.country',
    'res.country.state',
    'res.currency',
    'res.currency.rate',
    'res.partner.bank',
}

def get_client_ip():
    try:
        if request and hasattr(request, 'httprequest'):
            return request.httprequest.remote_addr or ''
    except Exception:
        pass
    return ''

def get_model_category(model_name):
    if model_name.startswith('account.') or model_name in ('account.move', 'account.payment', 'account.bank.statement'):
        return 'accounting'
    elif model_name.startswith('sale.'):
        return 'sale'
    elif model_name.startswith('purchase.'):
        return 'purchase'
    elif model_name.startswith('stock.'):
        return 'inventory'
    elif model_name in ('res.partner', 'res.partner.category'):
        return 'contact'
    elif model_name.startswith('analytix.'):
        return 'accounting'
    elif model_name in ('res.config.settings', 'res.users', 'res.groups', 'res.company', 'ir.config_parameter'):
        return 'system'
    return 'other'

def is_should_log(env, model_name):
    # 1. Skip Cron jobs, background automated tasks, and system user ID 1
    if env.user.id == 1 or env.user.login == '__system__' or env.context.get('cron_id') or env.context.get('scheduled_action'):
        return False

    # 2. Skip explicitly listed internal/framework or child line models
    if model_name in SKIP_MODELS:
        return False

    # 3. Restrict strictly to target business modules requested:
    # (Accounting, Sales, Purchase, Inventory, Settings, Contacts, Products, Analytix Documents)
    is_accounting = model_name.startswith('account.') or model_name in ('account.move', 'account.payment', 'account.bank.statement')
    is_sale = model_name.startswith('sale.')
    is_purchase = model_name.startswith('purchase.')
    is_inventory = model_name.startswith('stock.')
    is_contacts = model_name == 'res.partner' or model_name.startswith('res.partner.')
    is_settings = model_name in ('res.config.settings', 'res.users', 'res.groups', 'res.company', 'ir.config_parameter') or model_name.startswith('res.config')
    is_products = model_name in ('product.template', 'product.product', 'product.category')
    is_analytix = model_name.startswith('analytix.')

    if not (is_accounting or is_sale or is_purchase or is_inventory or is_contacts or is_settings or is_products or is_analytix):
        return False

    return True

def get_log_priority(op_type, model_name, vals=None):
    """ Priority score to select EXACTLY ONE primary action per HTTP request """
    if vals and 'state' in vals:
        st = vals['state']
        if st in ('posted', 'sale', 'purchase', 'done', 'cancel'):
            return 10
        return 8

    if op_type in ('unlink', 'create'):
        if model_name in ('account.move', 'account.payment', 'sale.order', 'purchase.order', 'stock.picking', 'product.template', 'product.product', 'analytix.document'):
            return 8
        return 6

    if model_name in ('account.move', 'account.payment', 'sale.order', 'purchase.order', 'stock.picking', 'product.template', 'product.product', 'analytix.document'):
        return 6

    if model_name in ('res.partner', 'res.users', 'res.config.settings', 'res.company'):
        return 4

    return 2

def format_changed_fields_summary(record, vals):
    """ Formats altered fields into human-friendly phrases for the headline summary """
    if not vals:
        return ""
    
    ignore = {
        'write_uid', 'write_date', 'create_uid', 'create_date', '__last_update',
        'message_follower_ids', 'activity_ids', 'message_ids', 'website_message_ids'
    }
    filtered_keys = [k for k in vals.keys() if k not in ignore]
    if not filtered_keys:
        return ""

    field_summaries = []
    for k in filtered_keys[:3]:  # Top 3 changed fields in headline
        field_obj = record._fields.get(k)
        raw_label = field_obj.string if (field_obj and field_obj.string) else k.replace('_id', '').replace('_', ' ').title()
        
        if raw_label.lower().startswith('image') or raw_label.lower().startswith('avatar'):
            clean_label = "Image"
        else:
            clean_label = raw_label
            
        val = vals[k]
        field_type = field_obj.type if field_obj else 'char'

        # Binary / Image fields
        if field_type == 'binary' or 'image' in k or 'avatar' in k:
            if not val:
                field_summaries.append(f"Removed {clean_label}")
            else:
                field_summaries.append(f"Updated {clean_label}")
        # Boolean fields
        elif field_type == 'boolean':
            if val:
                field_summaries.append(f"Enabled {clean_label}")
            else:
                field_summaries.append(f"Disabled {clean_label}")
        # Falsy values (Empty text, None, False)
        elif val is False or val is None or val == '':
            field_summaries.append(f"Cleared {clean_label}")
        # Many2one tuple (id, name)
        elif isinstance(val, tuple) and len(val) == 2:
            field_summaries.append(f"{clean_label}: {val[1]}")
        # Numeric / Currency
        elif isinstance(val, (int, float)):
            if any(term in k for term in ('price', 'amount', 'cost', 'total', 'fee')):
                field_summaries.append(f"{clean_label}: ${val:,.2f}")
            else:
                field_summaries.append(f"{clean_label}: {val}")
        # General text
        else:
            val_str = str(val)
            if len(val_str) > 20:
                val_str = val_str[:17] + "..."
            field_summaries.append(f"{clean_label}: {val_str}")

    if len(filtered_keys) > 3:
        field_summaries.append(f"+{len(filtered_keys) - 3} more")

    return f" ({', '.join(field_summaries)})"

def generate_business_summary(op_type, record, vals=None):
    model_name = record._name
    rec_name = ''
    try:
        rec_name = record.display_name or str(record.id)
    except Exception:
        rec_name = f"ID: {record.id}"

    # Invoices, Vendor Bills, Credit Notes
    if model_name == 'account.move':
        move_type = getattr(record, 'move_type', 'entry')
        type_label = {
            'out_invoice': 'Customer Invoice',
            'in_invoice': 'Vendor Bill',
            'out_refund': 'Customer Credit Note',
            'in_refund': 'Vendor Credit Note',
            'entry': 'Journal Entry',
        }.get(move_type, 'Invoice / Bill')
        
        partner = getattr(record, 'partner_id', False)
        partner_str = f" for {partner.name}" if partner else ""
        amount = getattr(record, 'amount_total', 0.0)
        amount_str = f" (${amount:,.2f})" if amount else ""
        
        if op_type == 'create':
            return f"Created {type_label}: {rec_name}{partner_str}{amount_str}"
        elif op_type == 'write' and vals:
            if 'state' in vals:
                st = vals['state']
                if st == 'posted':
                    return f"Posted {type_label}: {rec_name}{partner_str}{amount_str}"
                elif st == 'cancel':
                    return f"Cancelled {type_label}: {rec_name}{partner_str}"
                elif st == 'draft':
                    return f"Reset {type_label} to Draft: {rec_name}"
            changed_info = format_changed_fields_summary(record, vals)
            return f"Updated {type_label}: {rec_name}{partner_str}{changed_info}"
        elif op_type == 'unlink':
            return f"Deleted {type_label}: {rec_name}{partner_str}"

    # Customer & Vendor Payments
    elif model_name == 'account.payment':
        partner = getattr(record, 'partner_id', False)
        partner_str = f" ({partner.name})" if partner else ""
        amount = getattr(record, 'amount', 0.0)
        payment_type = getattr(record, 'payment_type', '')
        p_label = "Customer Payment" if payment_type == 'inbound' else ("Vendor Payment" if payment_type == 'outbound' else "Payment")
        
        if op_type == 'create':
            return f"Created {p_label}: {rec_name} - ${amount:,.2f}{partner_str}"
        elif op_type == 'write' and vals and 'state' in vals:
            return f"Payment {rec_name} Status -> '{vals['state']}'"
        elif op_type == 'write' and vals:
            changed_info = format_changed_fields_summary(record, vals)
            return f"Updated {p_label}: {rec_name}{changed_info}"
        elif op_type == 'unlink':
            return f"Deleted {p_label}: {rec_name} (${amount:,.2f})"

    # Sales Orders & Quotations
    elif model_name == 'sale.order':
        partner = getattr(record, 'partner_id', False)
        partner_str = f" for {partner.name}" if partner else ""
        amount = getattr(record, 'amount_total', 0.0)
        
        if op_type == 'create':
            return f"Created Sales Quotation: {rec_name}{partner_str} (${amount:,.2f})"
        elif op_type == 'write' and vals and 'state' in vals:
            st = vals['state']
            if st == 'sale':
                return f"Confirmed Sales Order: {rec_name}{partner_str} (${amount:,.2f})"
            elif st == 'cancel':
                return f"Cancelled Sales Order: {rec_name}"
        elif op_type == 'write' and vals:
            changed_info = format_changed_fields_summary(record, vals)
            return f"Updated Sales Order: {rec_name}{changed_info}"
        elif op_type == 'unlink':
            return f"Deleted Sales Order: {rec_name}"

    # Purchase Orders & RFQs
    elif model_name == 'purchase.order':
        partner = getattr(record, 'partner_id', False)
        partner_str = f" from {partner.name}" if partner else ""
        amount = getattr(record, 'amount_total', 0.0)
        
        if op_type == 'create':
            return f"Created Purchase RFQ: {rec_name}{partner_str} (${amount:,.2f})"
        elif op_type == 'write' and vals and 'state' in vals:
            st = vals['state']
            if st == 'purchase':
                return f"Confirmed Purchase Order: {rec_name}{partner_str} (${amount:,.2f})"
            elif st == 'cancel':
                return f"Cancelled Purchase Order: {rec_name}"
        elif op_type == 'write' and vals:
            changed_info = format_changed_fields_summary(record, vals)
            return f"Updated Purchase Order: {rec_name}{changed_info}"
        elif op_type == 'unlink':
            return f"Deleted Purchase Order: {rec_name}"

    # Products
    elif model_name in ('product.template', 'product.product'):
        op_label = {'create': 'Created', 'write': 'Updated', 'unlink': 'Deleted'}.get(op_type, 'Modified')
        changed_info = format_changed_fields_summary(record, vals) if op_type == 'write' and vals else ""
        return f"{op_label} Product: {rec_name}{changed_info}"

    # Analytix Documents
    elif model_name.startswith('analytix.'):
        op_label = {'create': 'Created', 'write': 'Updated', 'unlink': 'Deleted'}.get(op_type, 'Modified')
        changed_info = format_changed_fields_summary(record, vals) if op_type == 'write' and vals else ""
        return f"{op_label} Document: {rec_name}{changed_info}"

    # Stock Transfers & Deliveries
    elif model_name == 'stock.picking':
        picking_type = getattr(record, 'picking_type_id', False)
        pt_str = picking_type.name if picking_type else "Stock Transfer"
        
        if op_type == 'create':
            return f"Created {pt_str}: {rec_name}"
        elif op_type == 'write' and vals and 'state' in vals:
            st = vals['state']
            if st == 'done':
                return f"Processed & Validated {pt_str}: {rec_name}"
            elif st == 'cancel':
                return f"Cancelled {pt_str}: {rec_name}"
        elif op_type == 'write' and vals:
            changed_info = format_changed_fields_summary(record, vals)
            return f"Updated {pt_str}: {rec_name}{changed_info}"
        elif op_type == 'unlink':
            return f"Deleted {pt_str}: {rec_name}"

    # Contacts & Partners
    elif model_name == 'res.partner':
        op_label = {'create': 'Created', 'write': 'Updated', 'unlink': 'Deleted'}.get(op_type, 'Modified')
        changed_info = format_changed_fields_summary(record, vals) if op_type == 'write' and vals else ""
        return f"{op_label} Contact / Partner: {rec_name}{changed_info}"

    # System Settings & Users
    elif model_name in ('res.users', 'res.groups', 'res.config.settings', 'res.company'):
        op_action = {'create': 'Created', 'write': 'Updated Settings/User', 'unlink': 'Deleted'}.get(op_type, 'Modified')
        changed_info = format_changed_fields_summary(record, vals) if op_type == 'write' and vals else ""
        return f"{op_action}: {rec_name}{changed_info}"

    op_action = {'create': 'Created', 'write': 'Updated', 'unlink': 'Deleted'}.get(op_type, 'Modified')
    try:
        model_desc = record.env['ir.model'].sudo().search([('model', '=', model_name)], limit=1).name or model_name
    except Exception:
        model_desc = model_name
    
    changed_info = format_changed_fields_summary(record, vals) if op_type == 'write' and vals else ""
    return f"{op_action} {model_desc}: {rec_name}{changed_info}"

def save_single_request_log(env, candidate_data, priority):
    """ Guarantees EXACTLY ONE primary log record per user HTTP request """
    if not request or not hasattr(request, 'httprequest'):
        env['user.logs.history'].sudo().with_context(skip_user_log=True).create(candidate_data)
        return

    current_log_id = getattr(request, '_audit_single_log_id', None)
    current_priority = getattr(request, '_audit_single_log_priority', 0)

    if not current_log_id:
        log_rec = env['user.logs.history'].sudo().with_context(skip_user_log=True).create(candidate_data)
        request._audit_single_log_id = log_rec.id
        request._audit_single_log_priority = priority
    else:
        if priority > current_priority:
            existing_rec = env['user.logs.history'].sudo().browse(current_log_id)
            if existing_rec.exists():
                existing_rec.with_context(skip_user_log=True).write(candidate_data)
                request._audit_single_log_priority = priority


class BaseAuditHook(models.AbstractModel):
    _inherit = 'base'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        
        if not is_should_log(self.env, self._name) or self._transient or self.env.context.get('skip_user_log'):
            return records
        
        try:
            user = self.env.user
            ip_addr = get_client_ip()
            model_desc = self.env['ir.model'].sudo().search([('model', '=', self._name)], limit=1).name or self._name
            cat = get_model_category(self._name)

            for rec in records:
                rec_name = ''
                try:
                    rec_name = rec.display_name or str(rec.id)
                except Exception:
                    rec_name = f"ID: {rec.id}"
                
                details_lines = []
                if isinstance(vals_list, list) and vals_list:
                    val_dict = vals_list[0] if len(vals_list) == len(records) else vals_list[0]
                    for k, v in val_dict.items():
                        if k not in ('create_uid', 'create_date', 'write_uid', 'write_date', '__last_update'):
                            details_lines.append(f"{k} -> {v}")
                
                details_text = "\n".join(details_lines) if details_lines else "Record created."
                summary = generate_business_summary('create', rec)
                prio = get_log_priority('create', self._name)

                candidate = {
                    'name': summary,
                    'user_id': user.id,
                    'user_name': user.name,
                    'operation_type': 'create',
                    'category': cat,
                    'model_name': self._name,
                    'model_description': model_desc,
                    'res_id': rec.id,
                    'record_name': rec_name,
                    'details': details_text,
                    'ip_address': ip_addr,
                    'company_id': self.env.company.id if hasattr(self.env, 'company') else False,
                }
                save_single_request_log(self.env, candidate, prio)
        except Exception as e:
            _logger.debug("Failed to record create audit log for model %s: %s", self._name, str(e))

        return records

    def write(self, vals):
        if not is_should_log(self.env, self._name) or self._transient or self.env.context.get('skip_user_log'):
            return super().write(vals)

        tracked_fields = [k for k in vals.keys() if k not in ('write_uid', 'write_date', '__last_update')]
        old_values = {}
        
        if tracked_fields and len(self) <= 50:
            try:
                for rec in self:
                    old_values[rec.id] = {}
                    for field_name in tracked_fields:
                        if field_name in rec._fields:
                            field_obj = rec._fields[field_name]
                            if field_obj.type not in ('binary', 'one2many'):
                                try:
                                    val = getattr(rec, field_name)
                                    old_values[rec.id][field_name] = val.display_name if hasattr(val, 'display_name') else str(val)
                                except Exception:
                                    pass
            except Exception:
                pass

        result = super().write(vals)

        if not tracked_fields:
            return result

        try:
            user = self.env.user
            ip_addr = get_client_ip()
            model_desc = self.env['ir.model'].sudo().search([('model', '=', self._name)], limit=1).name or self._name
            cat = get_model_category(self._name)

            for rec in self:
                rec_name = ''
                try:
                    rec_name = rec.display_name or str(rec.id)
                except Exception:
                    rec_name = f"ID: {rec.id}"

                details_lines = []
                rec_old = old_values.get(rec.id, {})
                for k, new_val in vals.items():
                    if k in ('write_uid', 'write_date', '__last_update'):
                        continue
                    old_v = rec_old.get(k, 'N/A')
                    details_lines.append(f"{k}: {old_v} -> {new_val}")

                details_text = "\n".join(details_lines) if details_lines else "Record updated."
                summary = generate_business_summary('write', rec, vals)
                prio = get_log_priority('write', self._name, vals)

                candidate = {
                    'name': summary,
                    'user_id': user.id,
                    'user_name': user.name,
                    'operation_type': 'write',
                    'category': cat,
                    'model_name': self._name,
                    'model_description': model_desc,
                    'res_id': rec.id,
                    'record_name': rec_name,
                    'details': details_text,
                    'ip_address': ip_addr,
                    'company_id': self.env.company.id if hasattr(self.env, 'company') else False,
                }
                save_single_request_log(self.env, candidate, prio)
        except Exception as e:
            _logger.debug("Failed to record write audit log for model %s: %s", self._name, str(e))

        return result

    def unlink(self):
        if not is_should_log(self.env, self._name) or self._transient or self.env.context.get('skip_user_log'):
            return super().unlink()

        try:
            user = self.env.user
            ip_addr = get_client_ip()
            model_desc = self.env['ir.model'].sudo().search([('model', '=', self._name)], limit=1).name or self._name
            cat = get_model_category(self._name)

            for rec in self:
                rec_name = ''
                try:
                    rec_name = rec.display_name or str(rec.id)
                except Exception:
                    rec_name = f"ID: {rec.id}"
                
                summary = generate_business_summary('unlink', rec)
                prio = get_log_priority('unlink', self._name)
                
                candidate = {
                    'res_id': rec.id,
                    'record_name': rec_name,
                    'name': summary,
                    'user_id': user.id,
                    'user_name': user.name,
                    'operation_type': 'unlink',
                    'category': cat,
                    'model_name': self._name,
                    'model_description': model_desc,
                    'details': f"Record '{rec_name}' (ID: {rec.id}) of model {self._name} was deleted.",
                    'ip_address': ip_addr,
                    'company_id': self.env.company.id if hasattr(self.env, 'company') else False,
                }
                save_single_request_log(self.env, candidate, prio)
        except Exception as e:
            _logger.debug("Failed to gather unlink info for model %s: %s", self._name, str(e))

        result = super().unlink()
        return result
