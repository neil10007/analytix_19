# -*- coding: utf-8 -*-
import logging
import os
import base64
import json
import re
from io import BytesIO
from odoo import models, api, fields
from odoo.exceptions import UserError

try:
    from PIL import Image
    import PIL.WebPImagePlugin
    import PIL.PngImagePlugin
    import PIL.JpegImagePlugin
    import PIL.GifImagePlugin
    import PIL.BmpImagePlugin
    import PIL.TiffImagePlugin
except ImportError:
    pass

_logger = logging.getLogger(__name__)

EXPENSE_KEYWORDS_MAP = {
    'RENT_EXPENSE': ['rent', 'rental', 'lease', 'leasing', 'tenancy', 'office rent', 'warehouse rent', 'shop rent', 'showroom rent', 'accommodation rent', 'staff accommodation', 'premises rent', 'building rent', 'commercial rent', 'property rental', 'annual rent', 'monthly rent', 'إيجار'],
    'UTILITIES_EXPENSE': ['electricity', 'electric bill', 'power', 'utility', 'utilities', 'water', 'sewage', 'electricity consumption', 'sec', 'saudi electricity', 'national water company', 'nwc', 'كهرباء', 'مياه'],
    'TELECOMMUNICATION_EXPENSE': ['telephone', 'telecom', 'mobile', 'sim', 'internet', 'broadband', 'fibre', 'fiber', 'data package', 'communication', 'stc', 'mobily', 'zain', 'salam', 'phone bill', 'هاتف', 'إنترنت', 'اتصالات'],
    'PROFESSIONAL_FEES': ['consulting', 'consultancy', 'consultant', 'advisory', 'professional services', 'management consulting', 'business advisory', 'feasibility study', 'strategy consulting', 'corporate advisory', 'استشارات'],
    'ACCOUNTING_FEES': ['accounting', 'bookkeeping', 'accountant', 'monthly accounting', 'financial reporting', 'management accounts', 'account maintenance', 'مسك الدفاتر', 'محاسبة'],
    'AUDIT_FEES': ['audit', 'external audit', 'statutory audit', 'financial statement audit', 'auditor', 'audit support', 'مراجعة', 'تدقيق'],
    'TAX_AND_COMPLIANCE_FEES': ['vat filing', 'vat return', 'vat advisory', 'tax filing', 'tax return', 'tax consulting', 'corporate tax', 'withholding tax', 'wht', 'zakat', 'zatca', 'tax compliance', 'tax assessment', 'tax appeal', 'transfer pricing', 'الزكاة', 'ضريبة'],
    'LEGAL_FEES': ['legal', 'lawyer', 'attorney', 'legal consultation', 'legal advisory', 'court', 'litigation', 'arbitration', 'contract drafting', 'legal notice', 'debt recovery', 'law firm', 'محامي', 'قانوني'],
    'GOVERNMENT_FEES': ['government fee', 'government service', 'ministry fee', 'municipality', 'balady', 'misa', 'ministry of commerce', 'moc', 'qiwa', 'muqeem', 'absher business', 'chamber of commerce', 'cr renewal', 'commercial registration', 'licence', 'license renewal', 'permit', 'government portal', 'رسوم حكومية'],
    'VISA_AND_IMMIGRATION_EXPENSE': ['visa', 'work visa', 'business visa', 'visit visa', 'exit re-entry', 'final exit', 'immigration', 'iqama', 'residency', 'work permit', 'muqeem', 'jawazat', 'border number', 'إقامة', 'تأشيرة', 'رخصة عمل'],
    'HR_COMPLIANCE_EXPENSE': ['saudization', 'nitaqat', 'qiwa', 'mudad', 'gosi', 'social insurance', 'hrsd', 'ministry of human resources', 'labour office', 'labor office', 'employee registration', 'التأمينات', 'قوى', 'مدد'],
    'SALARY_AND_WAGES': ['salary', 'salaries', 'wages', 'payroll', 'overtime', 'bonus', 'allowance', 'commission', 'employee remuneration', 'راتب', 'رواتب', 'أجور'],
    'EMPLOYEE_BENEFITS': ['medical insurance', 'employee insurance', 'staff benefit', 'employee welfare', 'end-of-service', 'eosb', 'leave salary', 'staff welfare'],
    'RECRUITMENT_EXPENSE': ['recruitment', 'hiring', 'placement fee', 'recruitment agency', 'candidate sourcing', 'job advertisement', 'linkedin recruitment', 'manpower recruitment'],
    'TRAINING_EXPENSE': ['training', 'seminar', 'workshop', 'executive education', 'certification', 'professional course', 'conference registration', 'employee development'],
    'AIR_TRAVEL_EXPENSE': ['airline', 'flight', 'flights', 'airfare', 'air ticket', 'air travel', 'boarding', 'boarding pass', 'pnr', 'flyadeal', 'flynas', 'saudia', 'saudi airlines', 'emirates', 'qatar airways', 'etihad', 'air arabia', 'ruh-med', 'med-ruh', 'jed-ruh', 'ruh-jed', 'ticket', 'airport', 'passage', 'رحلة', 'رحلات', 'تذكرة', 'طيران', 'طيران أديل', 'طيران ناس', 'الخطوط السعودية'],
    'HOTEL_AND_ACCOMMODATION': ['hotel', 'accommodation', 'room charge', 'lodging', 'hotel stay', 'booking', 'serviced apartment'],
    'LOCAL_TRANSPORTATION': ['taxi', 'uber', 'careem', 'transportation', 'transport', 'limousine', 'bus', 'train', 'riyadh metro'],
    'FUEL_EXPENSE': ['fuel', 'petrol', 'gasoline', 'diesel', 'fuel station', 'sasco', 'aldrees', 'petromin'],
    'VEHICLE_REPAIR_AND_MAINTENANCE': ['vehicle repair', 'car repair', 'car service', 'tyre', 'tire', 'battery', 'spare parts', 'garage', 'oil change', 'vehicle inspection'],
    'VEHICLE_RENTAL_EXPENSE': ['car rental', 'vehicle rental', 'rent a car', 'fleet rental', 'monthly vehicle rental', 'leasing vehicle'],
    'OFFICE_SUPPLIES': ['office supplies', 'stationery', 'paper', 'pen', 'file', 'folder', 'toner', 'cartridge', 'printer supplies'],
    'PRINTING_AND_STATIONERY': ['printing', 'photocopy', 'business card', 'letterhead', 'envelope', 'brochure', 'flyer', 'banner', 'signage'],
    'SOFTWARE_AND_SUBSCRIPTIONS': ['software', 'saas', 'software licence', 'software license', 'subscription', 'erp', 'crm', 'odoo', 'microsoft 365', 'adobe', 'zoom', 'slack', 'antivirus'],
    'IT_AND_CLOUD_EXPENSE': ['aws', 'amazon web services', 'azure', 'google cloud', 'cloud hosting', 'vps', 'server', 'hosting', 'domain', 'ssl', 'data centre', 'data center'],
    'IT_EQUIPMENT': ['computer', 'laptop', 'desktop', 'monitor', 'router', 'switch', 'firewall', 'keyboard', 'mouse', 'it equipment'],
    'FIXED_ASSET_REVIEW_REQUIRED': ['furniture', 'office furniture', 'machinery', 'equipment', 'air conditioner', 'fit-out', 'leasehold improvement', 'generator'],
    'MARKETING_AND_ADVERTISING': ['advertising', 'advertisement', 'marketing', 'promotion', 'campaign', 'google ads', 'meta ads', 'facebook ads', 'instagram ads', 'linkedin ads', 'billboard', 'outdoor advertising'],
    'DIGITAL_MARKETING_EXPENSE': ['seo', 'ppc', 'social media management', 'content marketing', 'digital campaign', 'influencer', 'lead generation', 'search engine optimisation', 'search engine optimization'],
    'WEBSITE_AND_DIGITAL_EXPENSE': ['website development', 'web development', 'website maintenance', 'website amc', 'web design'],
    'REPAIRS_AND_MAINTENANCE': ['repair', 'maintenance', 'amc', 'annual maintenance', 'service contract', 'servicing', 'maintenance contract'],
    'CLEANING_EXPENSE': ['cleaning', 'housekeeping', 'janitorial', 'cleaning materials', 'pest control', 'sanitation'],
    'SECURITY_EXPENSE': ['security', 'security guard', 'cctv monitoring', 'guarding', 'surveillance service'],
    'INSURANCE_EXPENSE': ['insurance', 'premium', 'policy', 'property insurance', 'vehicle insurance', 'professional indemnity', 'liability insurance'],
    'BANK_CHARGES': ['bank fee', 'bank charge', 'transfer charge', 'remittance charge', 'swift fee', 'processing fee', 'account maintenance fee'],
    'PAYMENT_PROCESSING_FEES': ['merchant fee', 'payment gateway', 'card processing', 'pos commission', 'transaction fee', 'mada fee', 'visa fee', 'mastercard fee'],
    'COURIER_AND_POSTAGE': ['courier', 'postage', 'delivery', 'shipping document', 'dhl', 'fedex', 'aramex', 'smsa'],
    'FREIGHT_AND_LOGISTICS': ['freight', 'shipping', 'cargo', 'logistics', 'transportation of goods', 'customs clearance', 'port charge', 'airway bill', 'bill of lading'],
    'CUSTOMS_AND_IMPORT_COST': ['customs', 'customs duty', 'import duty', 'zatca customs', 'port fees', 'import charges'],
    'MEALS_AND_ENTERTAINMENT': ['restaurant', 'food', 'meal', 'lunch', 'dinner', 'catering', 'refreshments', 'coffee', 'client meal'],
    'EMPLOYEE_WELFARE': ['staff welfare', 'employee event', 'staff refreshments', 'office refreshments', 'team event', 'staff party'],
    'MEMBERSHIP_AND_SUBSCRIPTIONS': ['membership', 'annual membership', 'chamber membership', 'professional membership', 'association fee'],
    'WAREHOUSING_EXPENSE': ['warehouse', 'storage', 'warehousing', 'storage fee'],
    'PACKAGING_EXPENSE': ['packaging', 'packing material', 'carton', 'box', 'label', 'wrapping', 'packing supplies'],
    'UNIFORM_AND_PPE_EXPENSE': ['uniform', 'safety shoes', 'helmet', 'ppe', 'protective equipment', 'staff uniform'],
}

CATEGORY_ACCOUNT_SEARCH_TERMS = {
    'AIR_TRAVEL_EXPENSE': ['travel', 'flight', 'airfare', 'airline', 'air ticket', 'air travel', 'passage'],
    'RENT_EXPENSE': ['rent', 'lease', 'tenancy', 'premises'],
    'UTILITIES_EXPENSE': ['utility', 'utilities', 'electric', 'water', 'sewage', 'power'],
    'TELECOMMUNICATION_EXPENSE': ['telephone', 'telecom', 'internet', 'communication', 'mobile', 'phone'],
    'PROFESSIONAL_FEES': ['consulting', 'professional', 'advisory'],
    'ACCOUNTING_FEES': ['accounting', 'bookkeeping', 'accountant'],
    'AUDIT_FEES': ['audit', 'auditor'],
    'TAX_AND_COMPLIANCE_FEES': ['tax', 'vat', 'zakat', 'compliance'],
    'LEGAL_FEES': ['legal', 'lawyer', 'attorney'],
    'GOVERNMENT_FEES': ['government', 'license', 'licence', 'permit', 'municipal'],
    'VISA_AND_IMMIGRATION_EXPENSE': ['visa', 'iqama', 'immigration', 'residency'],
    'HR_COMPLIANCE_EXPENSE': ['hr', 'gosi', 'saudization', 'social insurance'],
    'SALARY_AND_WAGES': ['salary', 'salaries', 'wage', 'wages', 'payroll'],
    'EMPLOYEE_BENEFITS': ['benefit', 'welfare', 'medical insurance', 'eosb'],
    'RECRUITMENT_EXPENSE': ['recruitment', 'hiring'],
    'TRAINING_EXPENSE': ['training', 'seminar', 'course'],
    'HOTEL_AND_ACCOMMODATION': ['hotel', 'accommodation', 'lodging'],
    'LOCAL_TRANSPORTATION': ['transport', 'transportation', 'taxi', 'car'],
    'FUEL_EXPENSE': ['fuel', 'petrol', 'gasoline', 'diesel'],
    'VEHICLE_REPAIR_AND_MAINTENANCE': ['vehicle', 'car repair', 'maintenance'],
    'VEHICLE_RENTAL_EXPENSE': ['vehicle rental', 'car rental'],
    'OFFICE_SUPPLIES': ['office supply', 'office supplies', 'stationery'],
    'PRINTING_AND_STATIONERY': ['printing', 'stationery'],
    'SOFTWARE_AND_SUBSCRIPTIONS': ['software', 'subscription', 'saas', 'license'],
    'IT_AND_CLOUD_EXPENSE': ['cloud', 'hosting', 'it', 'server'],
    'IT_EQUIPMENT': ['equipment', 'computer', 'it equipment'],
    'FIXED_ASSET_REVIEW_REQUIRED': ['asset', 'fixed asset', 'equipment'],
    'MARKETING_AND_ADVERTISING': ['marketing', 'advertising', 'advertisement', 'promotion'],
    'DIGITAL_MARKETING_EXPENSE': ['digital marketing', 'seo', 'ppc'],
    'WEBSITE_AND_DIGITAL_EXPENSE': ['website', 'web'],
    'REPAIRS_AND_MAINTENANCE': ['repair', 'repairs', 'maintenance'],
    'CLEANING_EXPENSE': ['cleaning', 'janitorial', 'sanitation'],
    'SECURITY_EXPENSE': ['security', 'guard'],
    'INSURANCE_EXPENSE': ['insurance', 'premium'],
    'BANK_CHARGES': ['bank charge', 'bank fees', 'bank fee', 'bank charges'],
    'PAYMENT_PROCESSING_FEES': ['processing fee', 'gateway', 'merchant', 'pos'],
    'COURIER_AND_POSTAGE': ['courier', 'postage', 'delivery', 'shipping'],
    'FREIGHT_AND_LOGISTICS': ['freight', 'logistics', 'shipping', 'cargo'],
    'CUSTOMS_AND_IMPORT_COST': ['customs', 'duty', 'import'],
    'MEALS_AND_ENTERTAINMENT': ['meal', 'meals', 'entertainment', 'food', 'restaurant'],
    'EMPLOYEE_WELFARE': ['welfare', 'staff welfare'],
    'MEMBERSHIP_AND_SUBSCRIPTIONS': ['membership', 'subscription'],
    'WAREHOUSING_EXPENSE': ['warehouse', 'storage', 'warehousing'],
    'PACKAGING_EXPENSE': ['packaging', 'packing'],
    'UNIFORM_AND_PPE_EXPENSE': ['uniform', 'ppe', 'safety'],
}


class AnalytixDocument(models.Model):
    """General-purpose document store for the Analytix Finance Dashboard."""
    _name = 'analytix.document'
    _description = 'Analytix Finance Document'
    _order = 'upload_date desc, id desc'

    name = fields.Char(string='Document Name', required=True)
    description = fields.Char(string='Description')
    doc_type = fields.Selection([
        ('invoice',  'Sales Invoice'),
        ('bill',     'Purchase Bills'),
        ('expense_bill', 'Expense Bills'),
        ('bank_statement', 'Bank Statement'),
        ('receipt_voucher', 'Receipt Voucher'),
        ('payment_voucher', 'Payment Voucher'),
        ('debit_note', 'Debit Note'),
        ('credit_note', 'Credit Note'),
        ('other',    'Other Documents'),
    ], string='Document Type', required=True, default='other')
    review = fields.Text(string='Review / Notes')
    upload_date = fields.Date(string='Upload Date', default=fields.Date.today)
    file_data = fields.Binary(string='File', attachment=True)
    file_name = fields.Char(string='File Name')
    file_size = fields.Integer(string='File Size (bytes)')
    mimetype = fields.Char(string='MIME Type')
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='Uploaded By',
                              default=lambda self: self.env.user)
    response_json = fields.Text(string='AI Response (JSON)', readonly=True)
    detected_doc_type = fields.Char(string='Detected Type', readonly=True)
    created_move_id = fields.Many2one('account.move', string='Created Entry', readonly=True)
    status = fields.Selection([
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', required=True, default='submitted', readonly=True)

    @api.constrains('file_size', 'file_data')
    def _check_file_size(self):
        max_size = 5 * 1024 * 1024  # 5 MB
        for doc in self:
            if doc.file_size and doc.file_size > max_size:
                raise UserError("The document size is more than 5 MB")
            if doc.file_data:
                b64_len = len(doc.file_data) if isinstance(doc.file_data, (str, bytes)) else 0
                approx_bytes = (b64_len * 3) // 4
                if approx_bytes > max_size * 1.05:
                    raise UserError("The document size is more than 5 MB")

    # ── Label maps ────────────────────────────────────────────────────
    STATUS_LABELS = {
        'submitted': 'Submitted',
        'approved':  'Approved',
        'rejected':  'Rejected',
    }
    DOC_TYPE_LABELS = {
        'invoice': 'Sales Invoice',
        'bill':    'Purchase Bills',
        'expense_bill': 'Expense Bills',
        'bank_statement': 'Bank Statement',
        'receipt_voucher': 'Receipt Voucher',
        'payment_voucher': 'Payment Voucher',
        'debit_note': 'Debit Note',
        'credit_note': 'Credit Note',
        'other':   'Other Documents',
    }
    DOC_TYPE_COLORS = {
        'invoice': {'bg': '#e3f2fd', 'text': '#1565c0'},
        'bill':    {'bg': '#fce4ec', 'text': '#c62828'},
        'expense_bill': {'bg': '#fff3e0', 'text': '#e65100'},
        'bank_statement': {'bg': '#e8f5e9', 'text': '#2e7d32'},
        'receipt_voucher': {'bg': '#fff3e0', 'text': '#ef6c00'},
        'payment_voucher': {'bg': '#fbe9e7', 'text': '#d84315'},
        'debit_note': {'bg': '#e8eaf6', 'text': '#283593'},
        'credit_note': {'bg': '#e0f7fa', 'text': '#00838f'},
        'other':   {'bg': '#f3e5f5', 'text': '#6a1b9a'},
    }

    # ── Dashboard RPC ─────────────────────────────────────────────────
    @api.model
    def get_analytix_documents_list(self):
        """Return all documents for the current user's allowed companies."""
        company_ids = self.env.companies.ids
        docs = self.search([('company_id', 'in', company_ids)],
                           order='upload_date desc, id desc', limit=200)
        records = []
        for doc in docs:
            dt = doc.doc_type or 'other'
            records.append({
                'id':           doc.id,
                'name':         doc.name or doc.file_name or 'Unnamed',
                'description':  doc.description or '',
                'doc_type':     dt,
                'doc_type_label': self.DOC_TYPE_LABELS.get(dt, 'Other Documents'),
                'doc_type_bg':  self.DOC_TYPE_COLORS.get(dt, self.DOC_TYPE_COLORS['other'])['bg'],
                'doc_type_text': self.DOC_TYPE_COLORS.get(dt, self.DOC_TYPE_COLORS['other'])['text'],
                'review':       doc.review or '',
                'file_name':    doc.file_name or '',
                'file_size':    doc.file_size or 0,
                'mimetype':     doc.mimetype or '',
                'upload_date':  doc.upload_date.strftime('%Y-%m-%d') if doc.upload_date else '',
                'company_id':   doc.company_id.id,
                'company_name': doc.company_id.name or '',
                'user_name':    doc.user_id.name or '',
                'created_move_id': doc.created_move_id.id if doc.created_move_id else False,
                'status':       doc.status or 'submitted',
                'status_label': self.STATUS_LABELS.get(doc.status or 'submitted', 'Submitted'),
            })
        return {
            'records': records,
            'total_count': len(records),
            'is_validator': self.env.user.has_group('analytix_finance_dashboard.group_validate_documents'),
        }

    @api.model
    def save_analytix_document(self, name, file_name, file_data_b64, mimetype,
                               file_size, description='', doc_type='other'):
        """Create a new document record and attach the file via ir.attachment."""
        max_size = 5 * 1024 * 1024  # 5 MB
        if file_size and int(file_size) > max_size:
            raise UserError("The document size is more than 5 MB")
        if file_data_b64:
            b64_len = len(file_data_b64) if isinstance(file_data_b64, (str, bytes)) else 0
            if (b64_len * 3) // 4 > max_size * 1.05:
                raise UserError("The document size is more than 5 MB")
        _logger.info(
            "save_analytix_document called: name=%s file_name=%s mimetype=%s "
            "file_size=%s doc_type=%s description=%s b64_len=%s",
            name, file_name, mimetype, file_size, doc_type, description,
            len(file_data_b64) if file_data_b64 else 0,
        )
        try:
            doc = self.create({
                'name':        name or file_name or 'Unnamed',
                'description': description or '',
                'doc_type':    doc_type or 'other',
                'file_name':   file_name or '',
                'file_size':   int(file_size or 0),
                'mimetype':    mimetype or 'application/octet-stream',
                'company_id':  self.env.company.id,
                'user_id':     self.env.user.id,
            })
            if file_data_b64:
                b64_clean = file_data_b64.strip() if isinstance(file_data_b64, str) else file_data_b64
                doc.sudo().write({'file_data': b64_clean})
            return doc.id
        except Exception as e:
            _logger.exception("save_analytix_document FAILED: %s", e)
            raise

    @api.model
    def delete_analytix_document(self, doc_id):
        """Delete a document by id."""
        doc = self.browse(doc_id)
        if doc.exists():
            doc.unlink()
            return True
        return False

    @api.model
    def update_analytix_document(self, doc_id, vals):
        """Update writable fields for a document (description, name, review)."""
        ALLOWED = {'description', 'name', 'review', 'doc_type'}
        safe_vals = {k: v for k, v in vals.items() if k in ALLOWED}
        if not safe_vals:
            return False
        doc = self.browse(doc_id)
        if doc.exists():
            doc.write(safe_vals)
            return True
        return False

    @api.model
    def approve_analytix_document(self, doc_id):
        """Approve a document."""
        if not self.env.user.has_group('analytix_finance_dashboard.group_validate_documents'):
            raise UserError("Only validators can approve documents.")
        doc = self.browse(doc_id)
        if doc.exists():
            doc.sudo().write({'status': 'approved'})
            return True
        return False

    @api.model
    def reject_analytix_document(self, doc_id):
        """Reject a document."""
        if not self.env.user.has_group('analytix_finance_dashboard.group_validate_documents'):
            raise UserError("Only validators can reject documents.")
        doc = self.browse(doc_id)
        if doc.exists():
            doc.sudo().write({'status': 'rejected'})
            return True
        return False

    @api.model
    def get_analytix_document_data(self, doc_id):
        """Return base64 file data + filename for download."""
        doc = self.browse(doc_id)
        if not doc.exists():
            return False
        raw = doc.file_data
        if raw:
            if isinstance(raw, bytes):
                file_data_str = raw.decode('utf-8')
            else:
                file_data_str = str(raw)
        else:
            file_data_str = ''
        return {
            'id':        doc.id,
            'file_name': doc.file_name or doc.name or 'document',
            'mimetype':  doc.mimetype or 'application/octet-stream',
            'file_data': file_data_str,
        }

    # ── AI Helper Methods ──────────────────────────────────────────────
    def _clean_float(self, val):
        """Safely convert formatted strings (with commas, %, currency symbols) or numbers to float."""
        if not val:
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            cleaned = re.sub(r'[^\d.-]', '', val.replace(',', ''))
            try:
                return float(cleaned) if cleaned else 0.0
            except (ValueError, TypeError):
                return 0.0
        return 0.0

    def _image_to_base64(self, image):
        """Convert a PIL Image to a fast, compressed base64 JPEG string (max 1200px) to prevent payload timeouts."""
        from PIL import Image
        img = image.copy()
        max_dim = 1200
        if max(img.width, img.height) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=75, optimize=True)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def _repair_json_string(self, s):
        """Repair truncated or slightly malformed JSON string returned by AI."""
        if not s:
            return "{}"
        s = s.strip()

        if "```" in s:
            match = re.search(r"```(?:json)?\s*({[\s\S]*?})\s*```", s, re.IGNORECASE)
            if match:
                s = match.group(1)
            else:
                s = s.replace("```json", "").replace("```", "").strip()

        # Step 1: Remove invalid control characters
        s = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', s)

        # Step 2: Remove trailing commas before closing braces/brackets
        s = re.sub(r',\s*([}\]])', r'\1', s)

        # Step 3: Check if string has unclosed quotes at end
        quote_count = len(re.findall(r'(?<!\\)"', s))
        if quote_count % 2 != 0:
            s += '"'

        # Remove trailing comma if truncated right after a comma
        s = re.sub(r',\s*$', '', s)

        # Step 4: Balance unclosed braces and brackets
        stack = []
        in_string = False
        escape = False
        for char in s:
            if escape:
                escape = False
                continue
            if char == '\\':
                escape = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if not in_string:
                if char in '{[':
                    stack.append(char)
                elif char == '}':
                    if stack and stack[-1] == '{':
                        stack.pop()
                elif char == ']':
                    if stack and stack[-1] == '[':
                        stack.pop()

        for char in reversed(stack):
            if char == '{':
                s += '}'
            elif char == '[':
                s += ']'

        s = re.sub(r',\s*([}\]])', r'\1', s)
        return s

    def _regex_extract_json_fallback(self, s):
        """Regex fallback to extract essential fields if JSON structure is severely corrupted."""
        doc_type = 'invoice'
        m_dt = re.search(r'"document_type"\s*:\s*"([^"]+)"', s, re.IGNORECASE)
        if m_dt:
            doc_type = m_dt.group(1)

        def _extract_str(key):
            m = re.search(rf'"{key}"\s*:\s*"([^"]+)"', s, re.IGNORECASE)
            return m.group(1) if m else None

        def _extract_num(key):
            m = re.search(rf'"{key}"\s*:\s*([0-9]+(?:\.[0-9]+)?)', s, re.IGNORECASE)
            return float(m.group(1)) if m else 0.0

        vendor_name = _extract_str('vendor_name') or _extract_str('name')
        customer_name = _extract_str('customer_name')
        invoice_date = _extract_str('invoice_date')
        currency = _extract_str('currency') or None
        subtotal = _extract_num('subtotal')
        tax = _extract_num('tax')
        total = _extract_num('total') or (subtotal + tax)

        is_simplified = False
        m_simp = re.search(r'"is_simplified_invoice"\s*:\s*(true|false)', s, re.IGNORECASE)
        if m_simp:
            is_simplified = m_simp.group(1).lower() == 'true'

        return {
            "document_type": doc_type,
            "is_simplified_invoice": is_simplified,
            "vendor": {"name": vendor_name},
            "customer": {"name": customer_name},
            "vendor_name": vendor_name,
            "customer_name": customer_name,
            "invoice_date": invoice_date,
            "currency": currency,
            "subtotal": subtotal,
            "tax": tax,
            "total": total,
            "items": []
        }

    def _call_openrouter(self, client, image_b64):
        """
        Send a single page/image to OpenRouter (Gemini model) and return the
        parsed JSON dict describing the document.
        """
        system_prompt = (
            "You are a document-extraction engine for an accounting system. "
            "Given an image of an invoice, bill, receipt or credit note, extract "
            "the data and respond with ONLY a valid JSON object (no markdown, no "
            "commentary) using this shape:\n"
            "{\n"
            '  "document_type": "invoice|bill|credit_note|debit_note|receipt|other",\n'
            '  "is_simplified_invoice": true|false,\n'
            '  "vendor": {\n'
            '    "name": "string or null",\n'
            '    "street": "building number / street address or null",\n'
            '    "street2": "district / additional street address or null",\n'
            '    "city": "city name or null",\n'
            '    "zip": "postal/ZIP code or null",\n'
            '    "country": "country name or null",\n'
            '    "vat": "tax ID / VAT number or null"\n'
            '  },\n'
            '  "customer": {\n'
            '    "name": "string or null",\n'
            '    "street": "building number / street address or null",\n'
            '    "street2": "district / additional street address or null",\n'
            '    "city": "city name or null",\n'
            '    "zip": "postal/ZIP code or null",\n'
            '    "country": "country name or null",\n'
            '    "vat": "tax ID / VAT number or null"\n'
            '  },\n'
            '  "invoice_number": "sequence / invoice / bill / reference number or null",\n'
            '  "invoice_date": "YYYY-MM-DD or null",\n'
            '  "currency": "3-letter ISO code or null",\n'
            '  "subtotal": number,\n'
            '  "tax": number,\n'
            '  "total": number,\n'
            '  "items": [\n'
            '    {"description": "string", "quantity": number, "unit_price": number, "discount": number, "tax_rate": number, "vat_amount": number}\n'
            "  ]\n"
            "}\n"
            "Rules:\n"
            "- CRITICAL FOR SIMPLIFIED INVOICE / RECEIPT IDENTIFICATION:\n"
            "  1. Set 'is_simplified_invoice' to true if the document is a simplified tax invoice, cash receipt, retail receipt, small customer purchase, restaurant bill, petrol station receipt, or retail invoice where seller details are present, but customer details (such as customer name, customer VAT number, customer CRN number) are NOT specified / omitted / absent, or if the document title contains 'Simplified Tax Invoice' / 'فاتورة ضريبية مبسطة' / 'Receipt'.\n"
            "  2. Set 'is_simplified_invoice' to false if the document is a standard B2B tax invoice where full customer details and customer VAT numbers are explicitly mentioned.\n"
            "- Extract full partner details for both vendor and customer including street, city, zip, country, and vat (tax ID).\n"
            "- CRITICAL FOR CURRENCY EXTRACTION:\n"
            "  1. Look carefully everywhere on the document (headers, table column headers like 'Taxable Amount (AED)', totals like 'AED 4,730.00' or 'SAR 500', currency labels, bank details, tax summary section, etc.).\n"
            "  2. Extract the exact currency mentioned on the document and convert it to its 3-letter ISO 4217 code (e.g., 'AED' for AED/Dirham/Dhs, 'SAR' for SAR/SR/Saudi Riyal, 'USD' for $, 'EUR' for €, 'GBP' for £, 'QAR', 'KWD', 'BHD', 'OMR', 'EGP', etc.).\n"
            "  3. If ANY currency is present or indicated anywhere on the document, return that 3-letter ISO code in 'currency'. ONLY if absolutely NO currency is mentioned or implied on the document, set 'currency' to null.\n"
            "- CRITICAL FOR SUBTOTAL, TAX & TOTAL ACCURACY:\n"
            "  1. 'subtotal' MUST be the exact untaxed subtotal before VAT. If not explicitly labeled as subtotal, calculate it as the sum of line item untaxed prices.\n"
            "  2. 'tax' MUST be the total VAT/tax amount listed on the document (e.g., 'Total Vat', 'VAT Amount', 'Tax').\n"
            "  3. 'total' MUST be the final gross total amount including VAT ('subtotal' + 'tax').\n"
            "  4. For each item in 'items', extract 'vat_amount' (the specific VAT amount for that line) and 'tax_rate' (the percentage e.g. 15 for 15%).\n"
            "- tax_rate must be the tax percentage applied (e.g. 15 for 15%, 5 for 5%). If no tax, use 0.\n"
            "- discount must be the discount percentage (0 to 100) applied on the line item. If discount is listed as an amount, convert it to the discount percentage (0 to 100). If no discount, use 0.\n"
            "- numbers should be numeric without currency symbols.\n"
            "- CRITICAL FOR LINE ITEM UNIT PRICES & AMOUNTS:\n"
            "  1. The sum of (quantity * unit_price * (1 - discount/100)) across all items MUST be consistent with the document subtotal.\n"
            "  2. Do NOT misread formatting commas or period delimiters as extra zeros (e.g. 20.23 is not 20230450).\n"
            "  3. unit_price must be the single unit rate before discount if a discount percentage is extracted, or net rate if no discount.\n"
        )

        # ── OpenRouter Model Selection: Use Frontend Field if configured, else Fallback to Backend Default ──
        user_model = False
        try:
            user_model = (getattr(self.env.user, 'openrouter_model', '') or '').strip()
        except Exception:
            user_model = False

        company_model = False
        try:
            company_model = (getattr(self.env.company, 'openrouter_model', '') or '').strip()
        except Exception:
            company_model = False

        if user_model:
            model_name = user_model
        elif company_model:
            model_name = company_model
        else:
            model_name = "google/gemini-2.5-flash"

        _logger.info("Calling OpenRouter with model: %s (User configured: %s, Company configured: %s)", model_name, user_model, company_model)

        user_content = [{"type": "text", "text": "Extract all document data across all pages as a single combined JSON object."}]
        if isinstance(image_b64, list):
            for b64 in image_b64:
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{b64}"
                    },
                })
        else:
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_b64}"
                },
            })

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": user_content,
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=4096,
            )
        except Exception as conn_err:
            _logger.exception("OpenRouter AI Connection Error: %s", conn_err)
            err_str = str(conn_err)
            if "401" in err_str or "unauthorized" in err_str.lower() or "user not found" in err_str.lower():
                raise UserError(
                    "Authentication failed with OpenRouter API. Please verify that the OpenRouter API Key is correctly set in your user or company settings."
                )
            if "Connection error" in err_str or "connect" in err_str.lower() or "timeout" in err_str.lower():
                raise UserError(
                    f"Connection Error while connecting to OpenRouter API (https://openrouter.ai/api/v1).\n\n"
                    f"Possible Live Server issues:\n"
                    f"1. Outbound Firewall: Ensure port 443 is allowed for external connections.\n"
                    f"2. Network/DNS: Check if live server can reach openrouter.ai (run: curl -v https://openrouter.ai/api/v1/models).\n"
                    f"3. SSL Certificates: Update CA certs on server (run: pip install --upgrade certifi).\n"
                    f"Original Error: {err_str}"
                )
            raise UserError(f"AI Service Error: {err_str}")

        content = response.choices[0].message.content or "{}"
        cleaned = content.strip()

        if "```" in cleaned:
            match = re.search(r"```(?:json)?\s*({[\s\S]*?})\s*```", cleaned, re.IGNORECASE)
            if match:
                cleaned = match.group(1)
            else:
                cleaned = cleaned.replace("```json", "").replace("```", "").strip()

        # Multi-Tier JSON Parsing with Automatic Repair
        parsed_data = None
        try:
            parsed_data = json.loads(cleaned)
        except Exception as exc_direct:
            _logger.warning("Direct JSON parse failed: %s. Attempting auto-repair...", exc_direct)
            try:
                repaired_str = self._repair_json_string(cleaned)
                parsed_data = json.loads(repaired_str)
                _logger.info("JSON successfully repaired and parsed.")
            except Exception as exc_repair:
                _logger.warning("JSON repair failed: %s. Using regex extraction fallback...", exc_repair)
                parsed_data = self._regex_extract_json_fallback(cleaned)

        formatted_json = json.dumps(parsed_data, indent=4)

        # Extract Token & Credit / Cost stats from API response
        usage_info = getattr(response, 'usage', None)
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        cost = None

        if usage_info:
            if isinstance(usage_info, dict):
                prompt_tokens = usage_info.get('prompt_tokens', 0) or 0
                completion_tokens = usage_info.get('completion_tokens', 0) or 0
                total_tokens = usage_info.get('total_tokens', 0) or 0
                cost = usage_info.get('cost') or usage_info.get('total_cost')
            else:
                prompt_tokens = getattr(usage_info, 'prompt_tokens', 0) or 0
                completion_tokens = getattr(usage_info, 'completion_tokens', 0) or 0
                total_tokens = getattr(usage_info, 'total_tokens', 0) or 0
                cost = getattr(usage_info, 'cost', None) or getattr(usage_info, 'total_cost', None)

        if cost is None:
            cost = getattr(response, 'cost', None) or getattr(response, 'total_cost', None)

        response_model = getattr(response, 'model', model_name)

        # Print prominent token & credit log to terminal stdout & Odoo server log
        print("\n" + "=" * 80)
        print(f">>> ANALYTIX AI MODEL TOKEN & CREDIT USAGE [DOCUMENT ID: {self.id}] <<<")
        print("=" * 80)
        print(f"  • AI Model Used          : {response_model}")
        print(f"  • Prompt (Input) Tokens  : {prompt_tokens:,}")
        print(f"  • Completion (Output)    : {completion_tokens:,}")
        print(f"  • Total Tokens Consumed  : {total_tokens:,}")
        if cost is not None:
            print(f"  • OpenRouter Credit/Cost : ${cost:.6f}")
        print("=" * 80 + "\n")

        _logger.info(
            "ANALYTIX AI USAGE STATS [Doc ID %s | Model: %s]: Prompt Tokens = %s, Completion Tokens = %s, Total Tokens = %s%s",
            self.id, response_model, prompt_tokens, completion_tokens, total_tokens,
            f", Cost = ${cost:.6f}" if cost is not None else ""
        )

        print("\n" + "=" * 80)
        print(">>> ANALYTIX AI EXTRACTED JSON RESPONSE <<<")
        print("=" * 80)
        print(formatted_json)
        print("=" * 80 + "\n")
        _logger.info("ANALYTIX AI EXTRACTED JSON RESPONSE:\n%s", formatted_json)

        return parsed_data

    def _resolve_tax(self, move_type, tax_rate=0.0, tax_amount=0.0, subtotal=0.0, total=0.0):
        """
        Find an account.tax record in Odoo matching the PDF tax percentage.
        1. If tax_rate > 0, use tax_rate.
        2. If tax_rate is missing or 0 but tax_amount > 0, calculate percentage = (tax_amount / subtotal) * 100.
        3. Search account.tax in Odoo for matching percentage.
        4. If a matching Odoo tax is found, return it.
        5. If NO matching Odoo tax exists for that percentage (or if tax is 0), return empty account.tax recordset (leave BLANK).
        """
        rate_val = self._clean_float(tax_rate)
        amt_val = self._clean_float(tax_amount)
        subtotal_val = self._clean_float(subtotal)
        total_val = self._clean_float(total)
        company = self.env.company
        tax_type = 'sale' if move_type in ('out_invoice', 'out_refund') else 'purchase'

        # If tax_rate is missing or 0, but tax_amount > 0, calculate percentage from PDF tax amount & subtotal/total
        if rate_val <= 0 and amt_val > 0:
            if subtotal_val > 0:
                rate_val = (amt_val / subtotal_val) * 100.0
            elif total_val > amt_val:
                subtotal_calc = total_val - amt_val
                rate_val = (amt_val / subtotal_calc) * 100.0

        if rate_val <= 0 and amt_val <= 0:
            return self.env['account.tax']

        rate = round(rate_val, 2)
        _logger.info("Resolving tax for type '%s': target percentage = %.2f%% (tax_amount=%.2f, subtotal=%.2f)", tax_type, rate, amt_val, subtotal_val)

        # 1. Search exact percentage match for tax_type and company
        tax = self.env['account.tax'].search([
            ('type_tax_use', '=', tax_type),
            ('amount', '=', rate),
            ('amount_type', '=', 'percent'),
            ('company_id', 'in', [company.id, False]),
            ('active', '=', True),
        ], limit=1)

        # 2. Search with floating point tolerance (e.g. 4.99% -> 5.0%)
        if not tax:
            taxes = self.env['account.tax'].search([
                ('type_tax_use', '=', tax_type),
                ('amount_type', '=', 'percent'),
                ('company_id', 'in', [company.id, False]),
                ('active', '=', True),
            ])
            for t in taxes:
                if abs(t.amount - rate) < 0.15:
                    tax = t
                    break

        # 3. Search across all active percent taxes for company
        if not tax:
            taxes = self.env['account.tax'].search([
                ('amount_type', '=', 'percent'),
                ('company_id', 'in', [company.id, False]),
                ('active', '=', True),
            ])
            for t in taxes:
                if abs(t.amount - rate) < 0.15:
                    tax = t
                    break

        if tax:
            _logger.info("Matched PDF tax percentage %.2f%% to Odoo tax '%s' (ID: %s, Amount: %.2f%%)", rate, tax.name, tax.id, tax.amount)
            return tax

        _logger.info("No Odoo tax found matching percentage %.2f%% for company %s. Leaving tax BLANK.", rate, company.name)
        return self.env['account.tax']

    def _get_next_sequence_number(self, move_type, journal):
        """Retrieve the last account.move number/ref and auto-increment it."""
        last_move = self.env['account.move'].search([
            ('move_type', '=', move_type),
            ('journal_id', '=', journal.id),
            ('state', '!=', 'cancel'),
        ], order='id desc', limit=1)

        prefix = 'INV-' if move_type in ('out_invoice', 'out_refund') else 'BILL-'
        default_number = 1000

        last_val = None
        if last_move:
            last_val = last_move.name or last_move.ref

        if not last_val or last_val == '/':
            return f"{prefix}{default_number}"

        match = re.search(r'(\d+)(?!.*\d)', last_val)
        if match:
            num_str = match.group(1)
            num_len = len(num_str)
            next_num = int(num_str) + 1
            start_idx = match.start(1)
            end_idx = match.end(1)
            new_num_str = str(next_num).zfill(num_len)
            return last_val[:start_idx] + new_num_str + last_val[end_idx:]
        else:
            return f"{last_val}-1000"

    @api.model
    def get_analytix_accounts_list(self, doc_type=None):
        """Return filtered chart of accounts strictly based on doc_type (Income accounts for Sales Invoices, Expense/Asset accounts for Purchase & Expense Bills)."""
        domain = [('company_ids', 'in', self.env.company.ids)]

        effective_type = (doc_type or (self.doc_type if hasattr(self, 'doc_type') else '') or getattr(self, 'detected_doc_type', '') or '').strip().lower()
        
        if effective_type in ('invoice', 'out_invoice', 'sales_invoice'):
            domain.append(('account_type', 'in', ['income', 'income_other']))
        elif effective_type in ('bill', 'in_invoice', 'purchase_bill', 'expense_bill'):
            domain.append(('account_type', 'in', [
                'expense', 'expense_depreciation', 'expense_direct_cost', 'cost_of_goods_sold',
                'asset_current', 'liability_current'
            ]))
        else:
            domain.append(('account_type', 'in', [
                'income', 'income_other', 'expense', 'expense_depreciation', 'expense_direct_cost',
                'cost_of_goods_sold', 'asset_current'
            ]))

        accounts = self.env['account.account'].search(domain, order='code asc')

        res = []
        for a in accounts:
            res.append({
                'id': a.id,
                'code': a.code or '',
                'name': a.name or '',
                'account_type': a.account_type or '',
                'display_name': f"{a.code or ''} {a.name or ''}".strip(),
            })

        # Safe Fallback: If strict filter yields empty list, load all company accounts
        if not res:
            all_accounts = self.env['account.account'].search([
                ('company_ids', 'in', self.env.company.ids)
            ], order='code asc')
            for a in all_accounts:
                res.append({
                    'id': a.id,
                    'code': a.code or '',
                    'name': a.name or '',
                    'account_type': a.account_type or '',
                    'display_name': f"{a.code or ''} {a.name or ''}".strip(),
                })
        return res

    @api.model
    def get_analytix_tax_accounts_list(self):
        """Return GL accounts suitable for Tax posting (Tax Paid, Asset Current, Liability Current, Expenses)."""
        domain = [
            ('company_ids', 'in', self.env.company.ids),
            ('account_type', 'in', ['asset_current', 'liability_current', 'expense', 'expense_direct_cost'])
        ]
        accounts = self.env['account.account'].search(domain, order='code asc')
        res = []
        for a in accounts:
            res.append({
                'id': a.id,
                'code': a.code or '',
                'name': a.name or '',
                'account_type': a.account_type or '',
                'display_name': f"{a.code or ''} {a.name or ''}".strip(),
            })
        if not res:
            all_accounts = self.env['account.account'].search([('company_ids', 'in', self.env.company.ids)], order='code asc')
            for a in all_accounts:
                res.append({
                    'id': a.id,
                    'code': a.code or '',
                    'name': a.name or '',
                    'account_type': a.account_type or '',
                    'display_name': f"{a.code or ''} {a.name or ''}".strip(),
                })
        return res

    def _get_decoded_file_bytes(self):
        """Extract and clean binary bytes from self.file_data regardless of format (base64, data URL, raw bytes)."""
        if not self.file_data:
            return b''

        raw = self.file_data
        if isinstance(raw, str):
            raw = raw.encode('utf-8')

        raw = raw.strip()

        # Handle Data URL headers like b'data:image/webp;base64,...' or b'data:image/png;base64,...'
        if b';base64,' in raw[:120]:
            raw = raw.split(b';base64,')[1].strip()
        elif b'base64,' in raw[:120]:
            raw = raw.split(b'base64,')[1].strip()

        # Remove line breaks or whitespace within base64 body
        raw_clean = re.sub(rb'\s+', b'', raw)

        # Check if raw_clean is ALREADY unencoded binary (starts with magic bytes)
        if raw_clean.startswith(b'%PDF') or raw_clean.startswith(b'\x89PNG') or raw_clean.startswith(b'\xff\xd8') or raw_clean.startswith(b'GIF8') or raw_clean.startswith(b'RIFF'):
            return raw_clean

        # Attempt base64 decoding with padding repair
        try:
            missing_padding = len(raw_clean) % 4
            if missing_padding:
                raw_clean += b'=' * (4 - missing_padding)
            decoded = base64.b64decode(raw_clean, validate=False)

            # Check if double encoded base64
            if decoded.startswith(b'data:image') or decoded.startswith(b'iVBORw') or decoded.startswith(b'UklGR') or decoded.startswith(b'JVBERi'):
                if b';base64,' in decoded[:120]:
                    decoded = decoded.split(b';base64,')[1].strip()
                missing_padding = len(decoded) % 4
                if missing_padding:
                    decoded += b'=' * (4 - missing_padding)
                decoded = base64.b64decode(decoded, validate=False)

            return decoded
        except Exception as exc:
            _logger.warning("Base64 decode warning for doc %s: %s. Using raw bytes.", self.id, exc)
            return raw_clean

    def action_analyze_and_create_entry(self, override_account_id=None, override_line_accounts=None, override_tax_account_id=None):
        """Process the document file with OpenRouter (Gemini) and create corresponding accounting entry with product search & account validation."""
        self.ensure_one()
        if not self.file_data:
            raise UserError("No file uploaded for this document record.")

        api_key = (self.env.user.open_router_key or self.env.company.open_router_key)
        if api_key:
            api_key = api_key.strip()
        else:
            api_key = False
        if not api_key:
            raise UserError("Please configure an OpenRouter API Key on your User profile or Company settings.")

        _logger.info("OpenRouter API key found for entry creation.")

        try:
            import fitz          # PyMuPDF
            from PIL import Image
            from openai import OpenAI
        except ImportError as e:
            raise UserError(
                f"Missing dependency: {e}\n"
                "Please run: pip install pymupdf openai pillow"
            )

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key.strip(),
            default_headers={
                "HTTP-Referer": base_url,
                "X-Title": "Analytix Finance Dashboard",
            },
            timeout=60.0,
        )

        file_bytes = self._get_decoded_file_bytes()
        if not file_bytes:
            raise UserError("Document file content is empty or unreadable.")

        output = None

        # Determine file format based on magic bytes or mimetype
        is_pdf = file_bytes.startswith(b'%PDF') or (self.mimetype and 'pdf' in self.mimetype.lower())

        if is_pdf:
            # Process PDF via PyMuPDF in 1 single multi-image batch request to stay under Cloudflare timeout
            try:
                doc = fitz.open(stream=file_bytes, filetype="pdf")
            except Exception as e_fitz:
                raise UserError(f"Could not open/read PDF file format: {e_fitz}")

            try:
                # Process up to 15 pages in 1 single API call
                max_pages = min(len(doc), 15)
                page_b64_list = []
                for page_index in range(max_pages):
                    page = doc.load_page(page_index)
                    pix = page.get_pixmap(dpi=110, alpha=False)
                    image = Image.open(BytesIO(pix.tobytes("png"))).convert("RGB")
                    page_b64_list.append(self._image_to_base64(image))

                output = self._call_openrouter(client, page_b64_list)
            finally:
                doc.close()

            _logger.info("Processed document as PDF via multi-image OpenRouter request for doc ID %s", self.id)
        else:
            # Process image formats (PNG, JPG, WEBP, GIF, BMP, TIFF) via Pillow & fitz fallback
            image = None
            try:
                import PIL.WebPImagePlugin
                import PIL.PngImagePlugin
                import PIL.JpegImagePlugin
                import PIL.GifImagePlugin
                image = Image.open(BytesIO(file_bytes)).convert("RGB")
            except Exception as e_pil:
                _logger.info("Direct Pillow load failed (%s) for doc ID %s. Trying PyMuPDF Pixmap...", e_pil, self.id)
                try:
                    pix = fitz.Pixmap(file_bytes)
                    if pix.colorspace and pix.colorspace.name == fitz.csGRAY.name:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    png_bytes = pix.tobytes("png")
                    image = Image.open(BytesIO(png_bytes)).convert("RGB")
                except Exception as e_pix:
                    _logger.warning("PyMuPDF Pixmap load failed (%s) for doc ID %s", e_pix, self.id)

            if not image:
                raise UserError(
                    f"Could not parse uploaded document image format.\n"
                    f"Please ensure the file is a valid PNG, JPG, WEBP, GIF, or PDF document."
                )

            image_b64 = self._image_to_base64(image)
            output = self._call_openrouter(client, image_b64)
            _logger.info("Processed document image via vision pipeline for doc ID %s", self.id)

        self.response_json = json.dumps(output, indent=4)
        print("\n" + "#" * 80)
        print(f"### ANALYTIX DOCUMENT [ID: {self.id} | NAME: '{self.name}'] FINAL EXTRACTED JSON ###")
        print("#" * 80)
        print(self.response_json)
        print("#" * 80 + "\n")
        _logger.info("AI EXTRACTED JSON FORMAT FOR DOC %s:\n%s", self.id, self.response_json)

        if isinstance(output, dict):
            self.detected_doc_type = output.get('document_type') or ''
        elif isinstance(output, list) and output:
            self.detected_doc_type = output[0].get('document_type') or ''

        if not self.response_json:
            raise UserError("AI processing succeeded but did not return any JSON response.")

        try:
            data = json.loads(self.response_json)
        except (json.JSONDecodeError, ValueError) as exc:
            raise UserError(f"Invalid JSON in response: {exc}")

        if isinstance(data, list):
            data = data[0] if data else {}

        if not isinstance(data, dict):
            raise UserError("Unexpected JSON structure — expected a JSON object.")

        effective_doc_type = (self.doc_type or '').strip().lower()
        if not effective_doc_type:
            effective_doc_type = (data.get('document_type') or '').strip().lower()

        if effective_doc_type not in ('invoice', 'bill', 'expense_bill'):
            raise UserError(
                f"AI entry creation is only allowed for 'invoice', 'bill', or 'expense_bill' document types.\n"
                f"The current document type is '{effective_doc_type or 'other'}'. Entry creation cannot proceed for this document type."
            )

        if effective_doc_type == 'invoice':
            move_type = 'out_invoice'
        elif effective_doc_type in ('bill', 'expense_bill'):
            move_type = 'in_invoice'
        else:
            move_type = 'in_invoice'
        _logger.info("Selected move_type '%s' for effective_doc_type '%s'", move_type, effective_doc_type)

        # Extract sequence / reference number from AI document JSON
        seq_ref = (
            data.get('invoice_number')
            or data.get('bill_number')
            or data.get('document_number')
            or data.get('reference_number')
            or data.get('reference')
            or data.get('ref')
            or data.get('seq_number')
            or data.get('number')
            or ''
        ).strip()

        # Identify if document is a Simplified Invoice
        is_simplified_invoice = bool(data.get('is_simplified_invoice'))
        if not is_simplified_invoice:
            cust_check = data.get('customer')
            c_name = (cust_check.get('name') if isinstance(cust_check, dict) else data.get('customer_name')) or ''
            c_vat = (cust_check.get('vat') if isinstance(cust_check, dict) else data.get('customer_vat')) or ''
            doc_title_check = (data.get('document_title') or self.name or '').lower()
            if not c_name.strip() and not c_vat.strip():
                is_simplified_invoice = True
            elif any(kw in doc_title_check for kw in ['simplified', 'مبسطة', 'receipt', 'فاتورة ضريبية مبسطة']):
                is_simplified_invoice = True

        _logger.info("Document ID %s Simplified Invoice Detection Result: %s", self.id, is_simplified_invoice)

        # Resolve / Create / Update Partner (Vendor or Customer with full address & VAT)
        partner = None
        my_company_names = {c.name.strip().lower() for c in self.env.companies if c.name}

        def _get_partner_dict(p_data, p_name_str):
            if isinstance(p_data, dict):
                p_name = (p_data.get('name') or p_name_str or '').strip()
                return {
                    'name': p_name,
                    'street': (p_data.get('street') or '').strip(),
                    'street2': (p_data.get('street2') or '').strip(),
                    'city': (p_data.get('city') or '').strip(),
                    'zip': (p_data.get('zip') or '').strip(),
                    'country': (p_data.get('country') or '').strip(),
                    'vat': (p_data.get('vat') or '').strip(),
                }
            else:
                return {
                    'name': (p_name_str or '').strip(),
                    'street': '', 'street2': '', 'city': '', 'zip': '', 'country': '', 'vat': '',
                }

        vendor_dict = _get_partner_dict(data.get('vendor'), data.get('vendor_name'))
        customer_dict = _get_partner_dict(data.get('customer'), data.get('customer_name'))

        if move_type in ('out_invoice', 'out_refund'):
            if customer_dict['name'] and customer_dict['name'].lower() not in my_company_names:
                target_pdict = customer_dict
            elif vendor_dict['name'] and vendor_dict['name'].lower() not in my_company_names:
                target_pdict = vendor_dict
            else:
                target_pdict = customer_dict if customer_dict['name'] else vendor_dict
        else:
            if vendor_dict['name'] and vendor_dict['name'].lower() not in my_company_names:
                target_pdict = vendor_dict
            elif customer_dict['name'] and customer_dict['name'].lower() not in my_company_names:
                target_pdict = customer_dict
            else:
                target_pdict = vendor_dict if vendor_dict['name'] else customer_dict

        partner_name = target_pdict['name']
        if partner_name:
            if target_pdict['vat']:
                partner = self.env['res.partner'].search([('vat', '=', target_pdict['vat'])], limit=1)

            if not partner:
                partner = self.env['res.partner'].search([('name', 'ilike', partner_name)], limit=1)

            country_id = False
            if target_pdict['country']:
                c_name = target_pdict['country']
                country = self.env['res.country'].search([
                    '|', ('name', 'ilike', c_name), ('code', '=ilike', c_name)
                ], limit=1)
                if country:
                    country_id = country.id

            partner_vals = {}
            if target_pdict['street']:
                partner_vals['street'] = target_pdict['street']
            if target_pdict['street2']:
                partner_vals['street2'] = target_pdict['street2']
            if target_pdict['city']:
                partner_vals['city'] = target_pdict['city']
            if target_pdict['zip']:
                partner_vals['zip'] = target_pdict['zip']
            if target_pdict['vat']:
                partner_vals['vat'] = target_pdict['vat']
            if country_id:
                partner_vals['country_id'] = country_id

            if not partner:
                create_vals = {'name': partner_name}
                create_vals.update(partner_vals)
                partner = self.env['res.partner'].create(create_vals)
            else:
                update_vals = {}
                for k, v in partner_vals.items():
                    if not getattr(partner, k):
                        update_vals[k] = v
                if update_vals:
                    partner.write(update_vals)

        # Determine if partner/invoice is outside the company's country
        company = self.company_id or self.env.company
        is_foreign_country = False
        company_country = (company.country_id.code or 'SA').upper()
        partner_country = (target_pdict.get('country') or '').strip().upper() if target_pdict else ''
        partner_city = (target_pdict.get('city') or '').strip().upper() if target_pdict else ''
        partner_street = (target_pdict.get('street') or '').strip().upper() if target_pdict else ''
        partner_street2 = (target_pdict.get('street2') or '').strip().upper() if target_pdict else ''

        if partner_country:
            if partner_country not in (company_country, 'SA', 'SAU', 'SAUDI', 'SAUDI ARABIA', 'KSA', 'المملكة العربية السعودية', 'السعودية'):
                is_foreign_country = True
        if not is_foreign_country:
            for val in (partner_country, partner_city, partner_street, partner_street2):
                if any(kw in val for kw in ('DUBAI', 'UAE', 'UNITED ARAB EMIRATES', 'EMIRATES', 'دبي', 'الإمارات')):
                    is_foreign_country = True
                    break
        if not is_foreign_country and partner and partner.country_id:
            if partner.country_id.code != company_country:
                is_foreign_country = True

        # Resolve Invoice Date
        from datetime import date as _date
        today_str = _date.today().strftime('%Y-%m-%d')
        invoice_date = data.get('invoice_date') or today_str
        try:
            _date.fromisoformat(invoice_date)
        except (ValueError, TypeError):
            invoice_date = today_str

        # Resolve Currency: Extract from PDF or Fallback to Current Company Currency
        raw_currency_code = (data.get('currency') or '').strip().upper()

        CURRENCY_MAP = {
            'AED': 'AED', 'DIRHAM': 'AED', 'DIRHAMS': 'AED', 'DHS': 'AED', 'DH': 'AED', 'د.إ': 'AED',
            'SAR': 'SAR', 'SR': 'SAR', 'RIYAL': 'SAR', 'RIYALS': 'SAR', 'SAUDI RIYAL': 'SAR', 'ر.س': 'SAR',
            'USD': 'USD', '$': 'USD', 'US DOLLAR': 'USD', 'DOLLAR': 'USD',
            'EUR': 'EUR', '€': 'EUR', 'EURO': 'EUR',
            'GBP': 'GBP', '£': 'GBP', 'POUND': 'GBP',
            'QAR': 'QAR', 'KWD': 'KWD', 'BHD': 'BHD', 'OMR': 'OMR', 'EGP': 'EGP', 'INR': 'INR', '₹': 'INR',
        }

        currency_code = CURRENCY_MAP.get(raw_currency_code, raw_currency_code)

        currency_id = False
        currency = False

        if currency_code:
            # Search with active_test=False to find currency even if inactive in database
            currency = self.env['res.currency'].with_context(active_test=False).search([
                '|', ('name', '=ilike', currency_code), ('symbol', '=ilike', currency_code)
            ], limit=1)

        if currency:
            if not currency.active:
                currency.sudo().write({'active': True})
            currency_id = currency.id
            currency_code = currency.name
            _logger.info("Using document extracted currency '%s' (ID: %s)", currency_code, currency_id)
        else:
            # Fallback: Call current company's currency if not mentioned in PDF or not found in system
            company_currency = self.env.company.currency_id
            if company_currency:
                currency_id = company_currency.id
                currency_code = company_currency.name
                _logger.info("Currency not mentioned in PDF or not found in system. Calling current company's currency '%s' (ID: %s)", currency_code, currency_id)

        company = self.env.company
        if currency_code and company.currency_id and currency_code.upper() != company.currency_id.name.upper():
            is_foreign_country = True

        if move_type == 'entry':
            journal = self.env['account.journal'].search(
                [
                    ('type', '=', 'general'),
                    ('company_id', '=', company.id),
                ],
                limit=1,
            )
            if not journal:
                journal = self.env['account.journal'].search(
                    [
                        ('company_id', '=', company.id),
                    ],
                    limit=1,
                )
        else:
            journal_type = 'sale' if move_type in ('out_invoice', 'out_refund') else 'purchase'
            journal = self.env['account.journal'].search(
                [
                    ('type', '=', journal_type),
                    ('company_id', '=', company.id),
                ],
                limit=1,
            )
        if not journal:
            raise UserError(
                "No appropriate journal found for company '%s'. Please configure one in Accounting."
                % company.name
            )

        # ── Fetch AI GL Configuration for current Document Type and Company ──
        config_type_map = {
            'invoice': 'sales_invoice',
            'sales_invoice': 'sales_invoice',
            'out_invoice': 'sales_invoice',
            'bill': 'purchase_bill',
            'purchase_bill': 'purchase_bill',
            'in_invoice': 'purchase_bill',
            'expense_bill': 'expense_bill',
        }
        cfg_type = config_type_map.get(effective_doc_type, 'sales_invoice')
        ai_config = self.env['ai.gl.config'].get_config_for_type(cfg_type, company_id=company.id)

        config_account = None
        config_tax = None
        config_tax_account = None

        if ai_config:
            if cfg_type == 'sales_invoice':
                config_account = ai_config.income_account_id
                config_tax = ai_config.sale_tax_id
                config_tax_account = ai_config.sale_tax_account_id
            elif cfg_type == 'purchase_bill':
                config_account = ai_config.expense_account_id
                config_tax = ai_config.purchase_tax_id
                config_tax_account = ai_config.tax_account_id
            elif cfg_type == 'expense_bill':
                config_account = ai_config.expense_bill_account_id
                config_tax = ai_config.expense_bill_tax_id
                config_tax_account = ai_config.expense_bill_tax_account_id

        # Resolve Foreign Services configuration for Sales Invoices
        foreign_service_line = None
        if move_type in ('out_invoice', 'out_refund') and ai_config and ai_config.foreign_service_line_ids:
            target_stage = 'international_sales' if is_foreign_country else 'domestic_sales'
            foreign_service_line = ai_config.foreign_service_line_ids.filtered(lambda l: l.service_stage == target_stage)
            if foreign_service_line:
                if foreign_service_line[0].account_id:
                    config_account = foreign_service_line[0].account_id
                if foreign_service_line[0].tax_id:
                    config_tax = foreign_service_line[0].tax_id

        # Resolve Foreign Expenses configuration for Purchase Bills
        foreign_expense_line = None
        if move_type in ('in_invoice', 'in_refund') and ai_config and ai_config.foreign_expense_line_ids:
            target_stage = 'international_import' if is_foreign_country else 'domestic_purchase'
            foreign_expense_line = ai_config.foreign_expense_line_ids.filtered(lambda l: l.expense_stage == target_stage)
            if foreign_expense_line:
                if foreign_expense_line[0].account_id:
                    config_account = foreign_expense_line[0].account_id
                if foreign_expense_line[0].tax_id:
                    config_tax = foreign_expense_line[0].tax_id

        account_types = ['income', 'income_other'] if move_type in ('out_invoice', 'out_refund') else ['expense', 'expense_depreciation', 'expense_direct_cost']
        default_account = (
            config_account
            or journal.default_account_id
            or self.env['account.account'].search(
                [
                    ('account_type', 'in', account_types),
                    ('company_ids', 'in', company.id),
                ],
                limit=1,
            )
        )

        # Build lines, perform product search, & resolve account
        items = data.get('items') or []
        invoice_line_vals = []

        global_tax_rate = 0.0
        json_subtotal = self._clean_float(
            data.get('subtotal') or data.get('sub_total') or data.get('amount_untaxed') or data.get('untaxed_amount')
        )
        json_tax = self._clean_float(
            data.get('tax') or data.get('tax_amount') or data.get('vat') or data.get('vat_amount') or data.get('total_tax') or data.get('total_vat')
        )
        json_total = self._clean_float(
            data.get('total') or data.get('total_amount') or data.get('amount_total') or data.get('grand_total')
        )

        if json_subtotal > 0 and json_tax > 0:
            global_tax_rate = round((json_tax / json_subtotal) * 100, 4)
        elif json_total > 0 and json_tax > 0 and json_total > json_tax:
            subtotal_calc = json_total - json_tax
            global_tax_rate = round((json_tax / subtotal_calc) * 100, 4)

        # ── Smart Sanity Check & Normalization for Item Unit Prices ──
        is_tax_inclusive_detected = False
        if items and (json_subtotal > 0 or json_total > 0):
            valid_items_sum = sum(
                (self._clean_float(it.get('quantity')) or 1.0) * self._clean_float(it.get('unit_price'))
                for it in items
            )
            target_subtotal = json_subtotal if json_subtotal > 0 else (
                (json_total - json_tax) if (json_total > json_tax and json_tax > 0) else json_total
            )

            if target_subtotal > 0 and valid_items_sum > 0:
                # 1. Check if extracted prices are tax-inclusive (sum of item prices matches total rather than untaxed subtotal)
                if json_tax > 0 and json_total > target_subtotal:
                    diff_from_total = abs(valid_items_sum - json_total)
                    diff_from_subtotal = abs(valid_items_sum - target_subtotal)
                    if diff_from_total < diff_from_subtotal and diff_from_total < (json_total * 0.05):
                        is_tax_inclusive_detected = True

                # 2. Check if item sum diverges wildly or matches tax-inclusive total
                is_wild_divergence = valid_items_sum > (target_subtotal * 1.5) or valid_items_sum < (target_subtotal * 0.5)

                if is_tax_inclusive_detected or is_wild_divergence:
                    _logger.info(
                        "Normalizing line item unit prices (tax_inclusive=%s, wild_divergence=%s). Extracted item sum: %.2f, Target subtotal: %.2f",
                        is_tax_inclusive_detected, is_wild_divergence, valid_items_sum, target_subtotal
                    )
                    ratio = target_subtotal / valid_items_sum
                    for item in items:
                        orig_p = self._clean_float(item.get('unit_price'))
                        item['unit_price'] = round(orig_p * ratio, 4)

        validation_warnings = []
        detected_expense_type = False

        if cfg_type == 'expense_bill':
            # ── 1. Comprehensive Document Keyword Text Scanner ──
            search_text_parts = [
                str(data.get('summary') or ''),
                str(data.get('description') or ''),
                str(data.get('document_title') or ''),
                str(data.get('vendor_name') or ''),
                str(data.get('partner_name') or ''),
                str(data.get('notes') or ''),
                str(self.name or ''),
                partner.name if partner else '',
            ]
            for it in items:
                search_text_parts.append(str(it.get('product_name') or ''))
                search_text_parts.append(str(it.get('name') or ''))
                search_text_parts.append(str(it.get('description') or ''))
                search_text_parts.append(str(it.get('category') or ''))
                search_text_parts.append(str(it.get('expense_type') or ''))

            full_text_lower = " ".join(search_text_parts).lower()

            # ── 2. Strict Keyword Classifier for Configured Expense Lines (Built-in + Custom Line Keywords) ──
            from .ai_gl_config import EXPENSE_BILLS_TYPES
            type_dict = dict(EXPENSE_BILLS_TYPES)

            # Check for duplicate keyword conflicts across different GL accounts
            if ai_config and ai_config.expense_line_ids:
                keyword_acc_map = {}
                for eline in ai_config.expense_line_ids:
                    if not eline.keywords or not eline.expense_account_id:
                        continue
                    acc_label = f"{eline.expense_account_id.code or ''} {eline.expense_account_id.name or ''}".strip()
                    cat_label = type_dict.get(eline.expense_bills_type, eline.expense_bills_type)
                    kws = [k.strip().lower() for k in re.split(r'[,;\n]', eline.keywords) if k.strip()]
                    for kw in kws:
                        if kw in keyword_acc_map:
                            prev_acc_id, prev_acc_label, prev_cat_label = keyword_acc_map[kw]
                            if eline.expense_account_id.id != prev_acc_id:
                                raise UserError(
                                    f"AI GL Configuration Conflict!\n\n"
                                    f"The duplicate keyword '{kw}' is mapped to two different GL Expense Accounts:\n"
                                    f" 1. Line Category: '{prev_cat_label}' → Account: '{prev_acc_label}'\n"
                                    f" 2. Line Category: '{cat_label}' → Account: '{acc_label}'\n\n"
                                    f"Please open Configuration > AI GL Configuration and remove or adjust the duplicate keyword '{kw}' before creating the bill entry."
                                )
                        else:
                            keyword_acc_map[kw] = (eline.expense_account_id.id, acc_label, cat_label)

            configured_categories = []
            custom_line_keywords = {}
            if ai_config and ai_config.expense_line_ids:
                configured_categories = [eline.expense_bills_type for eline in ai_config.expense_line_ids if eline.expense_bills_type]
                for eline in ai_config.expense_line_ids:
                    if eline.expense_bills_type and eline.keywords:
                        # Extract custom keywords (comma, semicolon or newline separated)
                        kws = [k.strip().lower() for k in re.split(r'[,;\n]', eline.keywords) if k.strip()]
                        if kws:
                            custom_line_keywords[eline.expense_bills_type] = kws

            category_scores = {}
            # Evaluate base dictionary keywords (+1 weight per match)
            for cat_key, keywords in EXPENSE_KEYWORDS_MAP.items():
                match_count = sum(1 for kw in keywords if kw in full_text_lower)
                if match_count > 0:
                    category_scores[cat_key] = category_scores.get(cat_key, 0) + match_count

            # Evaluate custom user-configured line keywords (+3 weight per match for high precision)
            for cat_key, c_keywords in custom_line_keywords.items():
                c_match_count = sum(1 for kw in c_keywords if kw in full_text_lower)
                if c_match_count > 0:
                    category_scores[cat_key] = category_scores.get(cat_key, 0) + (c_match_count * 3)

            raw_detected_category = None
            if category_scores:
                raw_detected_category = max(category_scores, key=category_scores.get)

            # Strictly check if detected category is configured in ai.gl.config
            if raw_detected_category and raw_detected_category in configured_categories:
                detected_category = raw_detected_category
                _logger.info("Category '%s' matched and is configured in ai.gl.config", detected_category)
            else:
                detected_category = 'OTHER_ACCOUNT'
                _logger.info("Raw detected category '%s' is not mapped in ai.gl.config. Falling back to 'OTHER_ACCOUNT'", raw_detected_category)

            detected_expense_type = detected_category

            print("\n================ AI EXPENSE BILL PROCESSOR LOG ================")
            print(f"[AI BILL DEBUG] Active Company: {company.name} (ID: {company.id})")
            print(f"[AI BILL DEBUG] AI GL Config Record Found: {ai_config} (ID: {ai_config.id if ai_config else 'None'})")
            if ai_config:
                print(f"[AI BILL DEBUG] Configured Expense Category Mapping Lines: {configured_categories}")
                print(f"[AI BILL DEBUG] Custom Line Keywords Configured: {custom_line_keywords}")
                for eline in ai_config.expense_line_ids:
                    print(f"   -> Line: Type='{eline.expense_bills_type}', Keywords='{eline.keywords or ''}', Account='{eline.expense_account_id.code if eline.expense_account_id else ''} {eline.expense_account_id.name if eline.expense_account_id else 'None'}', Tax='{eline.tax_id.name if eline.tax_id else 'None'}'")
            print(f"[AI BILL DEBUG] Keyword Scanner Match Scores: {category_scores}")
            print(f"[AI BILL DEBUG] Keyword Scanner Raw Match: '{raw_detected_category}'")
            print(f"[AI BILL DEBUG] Final Enforced Category: '{detected_category}'")

            # ── 3. Resolve GL Account & Tax Strictly from ai.gl.config Mappings ──
            line_account = None
            line_tax = None

            # Priority 1: Direct line match in ai.gl.config.expense.line for detected_category
            if ai_config and ai_config.expense_line_ids:
                matched_line = ai_config.expense_line_ids.filtered(lambda l: l.expense_bills_type == detected_category)
                if matched_line and matched_line[0].expense_account_id:
                    line_account = matched_line[0].expense_account_id
                    print(f"[AI BILL DEBUG] Priority 1 Success: Found line mapping for '{detected_category}' -> Account: {line_account.code} {line_account.name}")
                    if (json_tax > 0 or global_tax_rate > 0) and matched_line[0].tax_id:
                        line_tax = matched_line[0].tax_id
                        print(f"[AI BILL DEBUG] Priority 1 Tax: Found line tax -> {line_tax.name}")

                # If detected_category wasn't OTHER_ACCOUNT but has no account mapped, try OTHER_ACCOUNT line
                if (not line_account or not line_account.exists()) and detected_category != 'OTHER_ACCOUNT':
                    other_line = ai_config.expense_line_ids.filtered(lambda l: l.expense_bills_type == 'OTHER_ACCOUNT')
                    if other_line and other_line[0].expense_account_id:
                        line_account = other_line[0].expense_account_id
                        detected_category = 'OTHER_ACCOUNT'
                        detected_expense_type = 'OTHER_ACCOUNT'
                        print(f"[AI BILL DEBUG] Fallback to OTHER_ACCOUNT line mapping -> Account: {line_account.code} {line_account.name}")
                        if (json_tax > 0 or global_tax_rate > 0) and other_line[0].tax_id:
                            line_tax = other_line[0].tax_id

            # Priority 2: Use Default Expense Account from ai.gl.config Settings (expense_bill_account_id)
            if not line_account or not line_account.exists():
                if ai_config and ai_config.expense_bill_account_id and ai_config.expense_bill_account_id.exists():
                    line_account = ai_config.expense_bill_account_id
                    print(f"[AI BILL DEBUG] Priority 2 Fallback: Used Default Expense Bill Account from Config -> {line_account.code} {line_account.name}")
                    if not line_tax and (json_tax > 0 or global_tax_rate > 0) and ai_config.expense_bill_tax_id:
                        line_tax = ai_config.expense_bill_tax_id

            # Priority 3: System Journal Default Account Fallback
            if not line_account or not line_account.exists():
                line_account = default_account
                print(f"[AI BILL DEBUG] Priority 3 Fallback: Used System Default Account -> {line_account.code if line_account else ''} {line_account.name if line_account else 'None'}")

            print(f"[AI BILL DEBUG] FINAL ASSIGNED EXPENSE ACCOUNT -> {line_account.code if line_account else ''} {line_account.name if line_account else 'None'}")
            print(f"[AI BILL DEBUG] FINAL ASSIGNED EXPENSE TAX -> {line_tax.name if line_tax else 'None'}")
            print("=================================================================\n")

            items_sum = sum(
                (self._clean_float(it.get('quantity')) or 1.0) * self._clean_float(it.get('unit_price'))
                for it in items
            ) if items else 0.0

            if is_simplified_invoice:
                # Detect mixed tax rates — if items carry different VAT %, create individual lines
                _simp_mixed = False
                if items and len(items) > 1:
                    _srates = []
                    for it in items:
                        _r = self._clean_float(it.get('tax_rate'))
                        _va = self._clean_float(it.get('vat_amount') or it.get('tax_amount') or it.get('vat') or it.get('tax'))
                        _p = self._clean_float(it.get('unit_price'))
                        _q = self._clean_float(it.get('quantity')) or 1.0
                        if _r <= 0 and _va > 0 and _p > 0:
                            _s = _q * _p
                            if _s > 0:
                                _r = round((_va / _s) * 100, 2)
                        _srates.append(round(_r, 2))
                    if len(set(_srates)) > 1:
                        _simp_mixed = True
                        _logger.info("Simplified Expense Bill: Mixed tax rates %s. Creating individual lines.", list(set(_srates)))

                if _simp_mixed:
                    validation_warnings.append(
                        f"• Document Classification: Simplified Invoice with Mixed VAT Rates detected. "
                        f"Creating individual lines per item for correct tax calculation."
                    )
                    exp_price_unit = 0.0
                    for idx, it in enumerate(items):
                        _iname = (it.get('product_name') or it.get('name') or it.get('description') or f"Item {idx+1}").strip()
                        _iqty = self._clean_float(it.get('quantity')) or 1.0
                        _iprice = self._clean_float(it.get('unit_price')) or 0.0
                        _irate = self._clean_float(it.get('tax_rate'))
                        _ivat = self._clean_float(it.get('vat_amount') or it.get('tax_amount') or it.get('vat') or it.get('tax'))
                        _isub = round(_iqty * _iprice, 2)
                        if _irate <= 0 and _ivat > 0 and _isub > 0:
                            _irate = round((_ivat / _isub) * 100, 2)
                        _iltax = None
                        if _irate > 0 or _ivat > 0:
                            _rtax = self._resolve_tax(move_type, tax_rate=_irate, tax_amount=_ivat, subtotal=_isub, total=_isub + _ivat)
                            if _rtax:
                                _iltax = _rtax
                        _ilv = {'name': _iname, 'quantity': _iqty, 'price_unit': _iprice}
                        if line_account and line_account.exists():
                            _ilv['account_id'] = line_account.id
                        if _iltax:
                            _ilv['tax_ids'] = [(6, 0, [_iltax.id])]
                        invoice_line_vals.append((0, 0, _ilv))
                        exp_price_unit += _isub
                        validation_warnings.append(
                            f"   - Line {idx+1}: {_iname} (Qty: {_iqty:g}, Unit Price: {_iprice:.2f}, VAT Rate: {_irate:.2f}%, Line Total: {_isub:.2f})"
                        )
                    _logger.info("Created %d individual lines for Simplified Expense Bill with mixed VAT rates", len(items))

                else:
                    # Standard simplified: 1 gross line, no separate tax
                    _logger.info("Expense Bill: Simplified Invoice. Setting line price to total gross (%.2f), clearing tax.", json_total)
                    exp_price_unit = json_total if json_total > 0 else (
                        (items_sum + json_tax) if (items_sum > 0 and json_tax > 0) else (
                            (json_subtotal + json_tax) if (json_subtotal > 0 and json_tax > 0) else (items_sum or json_subtotal)
                        )
                    )
                    line_tax = False
                    json_tax = 0.0
                    validation_warnings.append(
                        f"• Document Classification: Simplified Invoice / Retail Receipt detected. "
                        f"Total gross amount ({exp_price_unit:.2f}) set directly as expense amount without separate line tax."
                    )
                    exp_desc = data.get('summary') or data.get('description') or (partner and f"Expense Bill - {partner.name}") or "Expense Bill Summary"
                    if items:
                        _names = [(it.get('product_name') or it.get('name') or it.get('description') or '').strip() for it in items if (it.get('name') or it.get('description') or it.get('product_name'))]
                        if _names:
                            exp_desc = f"Expense Summary: {', '.join(_names[:5])}"
                    _sl = {'name': exp_desc, 'quantity': 1.0, 'price_unit': exp_price_unit}
                    if line_account and line_account.exists():
                        _sl['account_id'] = line_account.id
                    invoice_line_vals.append((0, 0, _sl))
                    _logger.info("Created 1 simplified single line for Expense Bill (price_unit=%.2f, no tax)", exp_price_unit)

            elif is_foreign_country:
                _logger.info("Expense Bill: Foreign Expense detected. Setting line price to total gross (%.2f).", json_total)
                exp_price_unit = json_total if json_total > 0 else (
                    (items_sum + json_tax) if (items_sum > 0 and json_tax > 0) else (
                        (json_subtotal + json_tax) if (json_subtotal > 0 and json_tax > 0) else (items_sum or json_subtotal)
                    )
                )
                line_tax = False
                json_tax = 0.0
                if ai_config and ai_config.foreign_expense_line_ids:
                    _fel = ai_config.foreign_expense_line_ids.filtered(lambda l: l.expense_stage == 'international_import')
                    if _fel and _fel[0].account_id:
                        line_account = _fel[0].account_id
                        if _fel[0].tax_id:
                            line_tax = _fel[0].tax_id
                validation_warnings.append(
                    f"• Document Classification: Expense From Foreign (outside country). "
                    f"Total ({exp_price_unit:.2f}) set as expense without local tax."
                )
                exp_desc = data.get('summary') or data.get('description') or (partner and f"Expense Bill - {partner.name}") or "Expense Bill Summary"
                if items:
                    _names = [(it.get('product_name') or it.get('name') or it.get('description') or '').strip() for it in items if (it.get('name') or it.get('description') or it.get('product_name'))]
                    if _names:
                        exp_desc = f"Expense Summary: {', '.join(_names[:5])}"
                _sl = {'name': exp_desc, 'quantity': 1.0, 'price_unit': exp_price_unit}
                if line_account and line_account.exists():
                    _sl['account_id'] = line_account.id
                if line_tax:
                    _sl['tax_ids'] = [(6, 0, [line_tax.id])]
                invoice_line_vals.append((0, 0, _sl))
                _logger.info("Created 1 foreign expense single line (price_unit=%.2f)", exp_price_unit)

            else:
                # ── Standard Domestic Expense Bill ──
                if json_tax <= 0 and items:
                    _itax_sum = sum(self._clean_float(it.get('tax_amount') or it.get('vat_amount') or it.get('vat') or it.get('tax')) for it in items)
                    if _itax_sum > 0:
                        json_tax = _itax_sum
                    elif json_total > 0 and items_sum > 0 and json_total > items_sum:
                        json_tax = json_total - items_sum
                if json_tax > 0 and (not global_tax_rate or global_tax_rate <= 0):
                    _base = items_sum if items_sum > 0 else (json_subtotal if json_subtotal > 0 else (json_total - json_tax))
                    if _base > 0:
                        global_tax_rate = round((json_tax / _base) * 100, 4)

                # Detect mixed tax rates across items
                has_mixed_tax_rates = False
                if items and len(items) > 1:
                    _rates = []
                    for it in items:
                        _r = self._clean_float(it.get('tax_rate'))
                        _va = self._clean_float(it.get('vat_amount') or it.get('tax_amount') or it.get('vat') or it.get('tax'))
                        _p = self._clean_float(it.get('unit_price'))
                        _q = self._clean_float(it.get('quantity')) or 1.0
                        if _r <= 0 and _va > 0 and _p > 0:
                            _s = _q * _p
                            if _s > 0:
                                _r = round((_va / _s) * 100, 2)
                        _rates.append(round(_r, 2))
                    if len(set(_rates)) > 1:
                        has_mixed_tax_rates = True
                        _logger.info("Expense Bill: Mixed tax rates %s detected. Creating individual lines.", list(set(_rates)))

                if has_mixed_tax_rates:
                    # ── Multi-Line: one line per item with its own correct tax ──
                    from .ai_gl_config import EXPENSE_BILLS_TYPES
                    _cdict = dict(EXPENSE_BILLS_TYPES)
                    _clabel = _cdict.get(detected_category, detected_category)
                    _alabel = f"{line_account.code} {line_account.name}" if (line_account and line_account.code) else (line_account.name if line_account else "Default Expense")
                    validation_warnings.append(
                        f"• Document Classification: Standard Tax Invoice with Mixed VAT Rates detected. "
                        f"Creating individual lines per item for correct tax calculation."
                    )
                    validation_warnings.append(f"• Expense Category Detected: {_clabel} [{detected_category}]")
                    validation_warnings.append(f"• Applied GL Expense Account: {_alabel}")
                    validation_warnings.append(f"• Extracted PDF Item Lines ({len(items)} items — INDIVIDUAL lines due to mixed VAT rates):")
                    exp_price_unit = 0.0
                    for idx, it in enumerate(items):
                        _iname = (it.get('product_name') or it.get('name') or it.get('description') or f"Item {idx+1}").strip()
                        _iqty = self._clean_float(it.get('quantity')) or 1.0
                        _iprice = self._clean_float(it.get('unit_price')) or 0.0
                        _irate = self._clean_float(it.get('tax_rate'))
                        _ivat = self._clean_float(it.get('vat_amount') or it.get('tax_amount') or it.get('vat') or it.get('tax'))
                        _isub = round(_iqty * _iprice, 2)
                        if _irate <= 0 and _ivat > 0 and _isub > 0:
                            _irate = round((_ivat / _isub) * 100, 2)
                        _iltax = None
                        if _irate > 0 or _ivat > 0:
                            _rtax = self._resolve_tax(move_type, tax_rate=_irate, tax_amount=_ivat, subtotal=_isub, total=_isub + _ivat)
                            if _rtax:
                                _iltax = _rtax
                        _ilv = {'name': _iname, 'quantity': _iqty, 'price_unit': _iprice}
                        if line_account and line_account.exists():
                            _ilv['account_id'] = line_account.id
                        if _iltax:
                            _ilv['tax_ids'] = [(6, 0, [_iltax.id])]
                        invoice_line_vals.append((0, 0, _ilv))
                        exp_price_unit += _isub
                        validation_warnings.append(f"   - Line {idx+1}: {_iname} (Qty: {_iqty:g}, Unit Price: {_iprice:.2f}, VAT Rate: {_irate:.2f}%, Line Total: {_isub:.2f})")
                    _logger.info("Created %d individual lines for Expense Bill with mixed VAT rates (category=%s)", len(items), detected_category)

                else:
                    # ── Single-Line: all items share the same tax rate ──
                    if (json_tax > 0 or global_tax_rate > 0):
                        _rtax = self._resolve_tax(move_type, tax_rate=global_tax_rate, tax_amount=json_tax, subtotal=items_sum or json_subtotal, total=json_total)
                        if _rtax:
                            line_tax = _rtax
                    if items_sum > 0:
                        if json_subtotal > 0 and abs(items_sum - json_subtotal) <= 0.5:
                            exp_price_unit = json_subtotal
                        elif json_total > 0 and json_tax > 0 and abs(items_sum - (json_total - json_tax)) <= 0.5:
                            exp_price_unit = items_sum
                        else:
                            exp_price_unit = items_sum
                    else:
                        exp_price_unit = json_subtotal if json_subtotal > 0 else ((json_total - json_tax) if (json_total > json_tax and json_tax > 0) else json_total)
                    validation_warnings.append(
                        f"• Document Classification: Standard (Normal) Tax Invoice detected. "
                        f"Extracted untaxed subtotal ({exp_price_unit:.2f}) and resolved standard VAT."
                    )
                    exp_desc = data.get('summary') or data.get('description') or (partner and f"Expense Bill - {partner.name}") or "Expense Bill Summary"
                    if items:
                        _names = [(it.get('product_name') or it.get('name') or it.get('description') or '').strip() for it in items if (it.get('name') or it.get('description') or it.get('product_name'))]
                        if _names:
                            exp_desc = f"Expense Summary: {', '.join(_names[:5])}"
                    _sl = {'name': exp_desc, 'quantity': 1.0, 'price_unit': exp_price_unit}
                    if line_account and line_account.exists():
                        _sl['account_id'] = line_account.id
                    if line_tax:
                        _sl['tax_ids'] = [(6, 0, [line_tax.id])]
                    invoice_line_vals.append((0, 0, _sl))
                    _logger.info("Created 1 consolidated single line for Expense Bill (category=%s, price_unit=%.2f)", detected_category, exp_price_unit)
                    from .ai_gl_config import EXPENSE_BILLS_TYPES
                    _cdict = dict(EXPENSE_BILLS_TYPES)
                    _clabel = _cdict.get(detected_category, detected_category)
                    _alabel = f"{line_account.code} {line_account.name}" if (line_account and line_account.code) else (line_account.name if line_account else "Default Expense")
                    validation_warnings.append(f"• Expense Category Detected: {_clabel} [{detected_category}]")
                    validation_warnings.append(f"• Applied GL Expense Account: {_alabel}")
                    if items:
                        validation_warnings.append(f"• Extracted PDF Item Lines ({len(items)} items consolidated into single bill line):")
                        for idx, it in enumerate(items):
                            _iname = (it.get('product_name') or it.get('name') or it.get('description') or f"Item {idx+1}").strip()
                            _iqty = self._clean_float(it.get('quantity')) or 1.0
                            _iprice = self._clean_float(it.get('unit_price')) or 0.0
                            _itotal = round(_iqty * _iprice, 2)
                            validation_warnings.append(f"   - Line {idx+1}: {_iname} (Qty: {_iqty:g}, Unit Price: {_iprice:.2f}, Line Total: {_itotal:.2f})")
        else:
            # ── Multi-Line Item Processing for Sales Invoices and Purchase Bills ──
            if move_type in ('out_invoice', 'out_refund'):
                if is_foreign_country:
                    validation_warnings.append(
                        "• Document Classification: Foreign / Export Sales Invoice. Identified as international sales outside the country."
                    )
                elif is_simplified_invoice:
                    validation_warnings.append(
                        "• Document Classification: Simplified Sales Invoice (B2C / Retail). Customer details omitted or simplified invoice detected."
                    )
                else:
                    validation_warnings.append(
                        "• Document Classification: Standard B2B Sales Invoice. Full customer and VAT details extracted."
                    )
            elif move_type in ('in_invoice', 'in_refund'):
                if is_foreign_country:
                    validation_warnings.append(
                        "• Document Classification: Foreign Import Vendor Bill. Identified as international purchase outside the country."
                    )
                elif is_simplified_invoice:
                    validation_warnings.append(
                        "• Document Classification: Simplified Vendor Receipt / Retail Bill. Identified as a simplified retail purchase/receipt."
                    )
                else:
                    validation_warnings.append(
                        "• Document Classification: Standard B2B Vendor Bill. Full vendor details and VAT extracted."
                    )

            for idx, item in enumerate(items):
                desc = (item.get('description') or 'Item').strip()
                qty = self._clean_float(item.get('quantity')) or 1.0
                price = self._clean_float(item.get('unit_price'))
                tax_rate = self._clean_float(item.get('tax_rate'))
                discount = self._clean_float(
                    item.get('discount')
                    or item.get('discount_percentage')
                    or item.get('disc')
                    or item.get('discount_pct')
                    or item.get('discount_rate')
                )
                discount_amount = self._clean_float(
                    item.get('discount_amount')
                    or item.get('disc_amount')
                    or item.get('discount_val')
                )

                if discount <= 0 and discount_amount > 0 and price > 0 and qty > 0:
                    total_before_disc = price * qty
                    discount = round((discount_amount / total_before_disc) * 100, 4)

                if not tax_rate and global_tax_rate:
                    tax_rate = global_tax_rate

                item_subtotal = (qty * price) if (qty > 0 and price > 0) else 0.0
                if (json_tax > 0 or tax_rate > 0):
                    resolved_tax = self._resolve_tax(
                        move_type,
                        tax_rate=tax_rate,
                        tax_amount=json_tax if not tax_rate else 0.0,
                        subtotal=item_subtotal or json_subtotal,
                        total=json_total
                    )
                    tax = resolved_tax if resolved_tax else None
                else:
                    tax = None

                # ── Product Search in Odoo (Multi-stage Code & Name Matching) ──
                product = None

                # Extract explicit JSON product fields if present
                raw_code = (
                    item.get('product_code')
                    or item.get('code')
                    or item.get('sku')
                    or item.get('item_code')
                    or item.get('default_code')
                    or ''
                ).strip()
                raw_name = (
                    item.get('product_name')
                    or item.get('name')
                    or item.get('item_name')
                    or ''
                ).strip()

                code_candidates = []
                name_candidates = []

                if raw_code:
                    code_candidates.append(raw_code)

                if raw_name:
                    name_candidates.append(raw_name)

                if desc:
                    name_candidates.append(desc)
                    # Split embedded code/sku if present: e.g. "P00001: laptop" or "P00001 - laptop" or "[P00001] laptop"
                    if ':' in desc:
                        parts = desc.split(':', 1)
                        if parts[0].strip():
                            code_candidates.append(parts[0].strip())
                        if parts[1].strip():
                            name_candidates.append(parts[1].strip())
                    elif '-' in desc:
                        parts = desc.split('-', 1)
                        if parts[0].strip():
                            code_candidates.append(parts[0].strip())
                        if parts[1].strip():
                            name_candidates.append(parts[1].strip())
                    elif '[' in desc and ']' in desc:
                        c_part = desc[desc.find('[')+1:desc.find(']')]
                        n_part = desc[desc.find(']')+1:]
                        if c_part.strip():
                            code_candidates.append(c_part.strip())
                        if n_part.strip():
                            name_candidates.append(n_part.strip())

                # 1. Search by Code / SKU candidates
                for c_code in code_candidates:
                    if not product and c_code:
                        product = self.env['product.product'].sudo().search([
                            '|', '|',
                            ('default_code', '=ilike', c_code),
                            ('barcode', '=', c_code),
                            ('default_code', 'ilike', c_code)
                        ], limit=1)
                    if product:
                        break

                # 2. Search by exact or full Name candidates
                for n_name in name_candidates:
                    if not product and n_name and len(n_name) >= 3:
                        product = self.env['product.product'].sudo().search([
                            '|',
                            ('name', '=ilike', n_name),
                            ('name', 'ilike', n_name)
                        ], limit=1)
                    if product:
                        break

                # Record product validation warning if missing in inventory catalog
                if not product:
                    validation_warnings.append(
                        f"• Line {idx + 1}: Product '{desc}' not found in inventory catalog (added with description only)."
                    )

                # Record tax mismatch warning if extracted tax differs from applied tax
                if (json_tax > 0 or tax_rate > 0) and tax:
                    ext_rate = tax_rate or global_tax_rate
                    applied_rate = abs(tax.amount) if tax.amount_type == 'percent' else 0.0
                    if ext_rate > 0 and applied_rate > 0 and abs(ext_rate - applied_rate) > 0.5:
                        validation_warnings.append(
                            f"• Line {idx + 1} Tax Mismatch: Extracted PDF tax rate is {ext_rate:.1f}%, but applied configuration tax '{tax.name}' rate is {applied_rate:.1f}%."
                        )
                elif (json_tax > 0 or tax_rate > 0) and not tax:
                    validation_warnings.append(
                        f"• Line {idx + 1} Tax Warning: Document specifies tax, but no tax rule was applied."
                    )

                line_account = None

                # 1. Check per-line override account
                specific_acc_id = None
                if not line_account and override_line_accounts and isinstance(override_line_accounts, dict):
                    specific_acc_id = override_line_accounts.get(str(idx)) or override_line_accounts.get(idx)

                if specific_acc_id:
                    line_account = self.env['account.account'].browse(int(specific_acc_id))
                elif not line_account and override_account_id:
                    line_account = self.env['account.account'].browse(int(override_account_id))
                elif not line_account and product:
                    # Product exists in master: get income/expense account from product or category
                    if move_type in ('out_invoice', 'out_refund'):
                        line_account = product.property_account_income_id or product.categ_id.property_account_income_categ_id
                    else:
                        line_account = product.property_account_expense_id or product.categ_id.property_account_expense_categ_id

                if not line_account or not line_account.exists():
                    line_account = default_account

                # ── Foreign Services mapping for Sales Invoice line items ──
                is_international_sales = False
                if move_type in ('out_invoice', 'out_refund') and ai_config and ai_config.foreign_service_line_ids:
                    target_stage = 'international_sales' if is_foreign_country else 'domestic_sales'
                    if foreign_service_line:
                        if foreign_service_line[0].account_id:
                            line_account = foreign_service_line[0].account_id
                        
                        if target_stage == 'international_sales':
                            is_international_sales = True
                            if not foreign_service_line[0].tax_id:
                                tax = self.env['account.tax']
                            else:
                                tax = foreign_service_line[0].tax_id
                        else:
                            if foreign_service_line[0].tax_id:
                                tax = foreign_service_line[0].tax_id
                            else:
                                tax = self.env['account.tax']

                if is_international_sales:
                    # Absorb tax into price_unit: e.g. 100 + 15 = 115
                    item_tax_rate = tax_rate or global_tax_rate
                    original_price = price
                    if item_tax_rate > 0:
                        tax_amt = price * (item_tax_rate / 100.0)
                        price = round(price + tax_amt, 2)
                        _logger.info("Absorbed %.2f%% tax into price unit (original: %.2f, new: %.2f) for international sales", item_tax_rate, original_price, price)
                    elif json_subtotal > 0 and json_tax > 0:
                        ratio = json_tax / json_subtotal
                        price = round(price * (1.0 + ratio), 2)
                        _logger.info("Absorbed global tax ratio %.4f into price unit (original: %.2f, new: %.2f) for international sales", ratio, original_price, price)
                    
                    # Add to validation warnings so it's highlighted for the accountant
                    validation_warnings.append(
                        f"• Line {idx + 1} (International Sales): Absorbed extracted tax into price unit (was {original_price:.2f}, now {price:.2f})."
                    )

                # ── Foreign Expenses mapping for Purchase Bill line items ──
                is_international_import = False
                if move_type in ('in_invoice', 'in_refund') and ai_config and ai_config.foreign_expense_line_ids:
                    target_stage = 'international_import' if is_foreign_country else 'domestic_purchase'
                    if foreign_expense_line:
                        if foreign_expense_line[0].account_id:
                            line_account = foreign_expense_line[0].account_id
                        
                        if target_stage == 'international_import':
                            is_international_import = True
                            if not foreign_expense_line[0].tax_id:
                                tax = self.env['account.tax']
                            else:
                                tax = foreign_expense_line[0].tax_id
                        else:
                            if foreign_expense_line[0].tax_id:
                                tax = foreign_expense_line[0].tax_id
                            else:
                                tax = self.env['account.tax']

                if is_international_import:
                    # Absorb tax into price_unit: e.g. 100 + 15 = 115 total expense
                    item_tax_rate = tax_rate or global_tax_rate
                    original_price = price
                    if item_tax_rate > 0:
                        tax_amt = price * (item_tax_rate / 100.0)
                        price = round(price + tax_amt, 2)
                        _logger.info("Absorbed %.2f%% tax into price unit (original: %.2f, new: %.2f) for international import purchase", item_tax_rate, original_price, price)
                    elif json_subtotal > 0 and json_tax > 0:
                        ratio = json_tax / json_subtotal
                        price = round(price * (1.0 + ratio), 2)
                        _logger.info("Absorbed global tax ratio %.4f into price unit (original: %.2f, new: %.2f) for international import purchase", ratio, original_price, price)
                    
                    # Add to validation warnings so it's highlighted for the accountant
                    validation_warnings.append(
                        f"• Line {idx + 1} (International Import Purchase): Absorbed extracted tax into price unit (was {original_price:.2f}, now {price:.2f})."
                    )

                item_display_name = raw_name or desc
                line_vals = {
                    'name': item_display_name,
                    'quantity': qty,
                    'price_unit': price,
                }
                if discount > 0:
                    line_vals['discount'] = discount
                if product:
                    line_vals['product_id'] = product.id
                if line_account and line_account.exists():
                    line_vals['account_id'] = line_account.id
                if tax:
                    line_vals['tax_ids'] = [(6, 0, [tax.id])]

                invoice_line_vals.append((0, 0, line_vals))

        if not invoice_line_vals:
            total = json_total or json_subtotal
            price_unit = json_subtotal if json_subtotal > 0 else total
            if (json_tax > 0 or global_tax_rate > 0):
                resolved_tax = self._resolve_tax(
                    move_type,
                    tax_rate=global_tax_rate,
                    tax_amount=json_tax,
                    subtotal=json_subtotal,
                    total=json_total
                )
                tax = resolved_tax if resolved_tax else None
            else:
                tax = None

            line_account = None
            if override_account_id:
                line_account = self.env['account.account'].browse(int(override_account_id))

            if not line_account or not line_account.exists():
                line_account = default_account

            # ── Foreign Services mapping for Sales Invoice fallback line ──
            is_international_sales = False
            if move_type in ('out_invoice', 'out_refund') and ai_config and ai_config.foreign_service_line_ids:
                target_stage = 'international_sales' if is_foreign_country else 'domestic_sales'
                if foreign_service_line:
                    if foreign_service_line[0].account_id:
                        line_account = foreign_service_line[0].account_id
                    
                    if target_stage == 'international_sales':
                        is_international_sales = True
                        if not foreign_service_line[0].tax_id:
                            tax = self.env['account.tax']
                        else:
                            tax = foreign_service_line[0].tax_id
                    else:
                        if foreign_service_line[0].tax_id:
                            tax = foreign_service_line[0].tax_id
                        else:
                            tax = self.env['account.tax']

            if is_international_sales:
                original_price = price_unit
                if global_tax_rate > 0:
                    price_unit = round(price_unit * (1.0 + (global_tax_rate / 100.0)), 2)
                    _logger.info("Absorbed global tax rate %.2f%% into price unit (original: %.2f, new: %.2f) for international sales", global_tax_rate, original_price, price_unit)
                elif json_subtotal > 0 and json_tax > 0:
                    ratio = json_tax / json_subtotal
                    price_unit = round(price_unit * (1.0 + ratio), 2)
                    _logger.info("Absorbed global tax ratio %.4f into price unit (original: %.2f, new: %.2f) for international sales", ratio, original_price, price_unit)
                
                validation_warnings.append(
                    f"• International Sales: Absorbed extracted tax into price unit (was {original_price:.2f}, now {price_unit:.2f})."
                )

            # ── Foreign Expenses mapping for Purchase Bill fallback line ──
            is_international_import = False
            if move_type in ('in_invoice', 'in_refund') and ai_config and ai_config.foreign_expense_line_ids:
                target_stage = 'international_import' if is_foreign_country else 'domestic_purchase'
                if foreign_expense_line:
                    if foreign_expense_line[0].account_id:
                        line_account = foreign_expense_line[0].account_id
                    
                    if target_stage == 'international_import':
                        is_international_import = True
                        if not foreign_expense_line[0].tax_id:
                            tax = self.env['account.tax']
                        else:
                            tax = foreign_expense_line[0].tax_id
                    else:
                        if foreign_expense_line[0].tax_id:
                            tax = foreign_expense_line[0].tax_id
                        # Do not clear tax if tax_id is not configured on domestic_purchase line

            if is_international_import:
                original_price = price_unit
                if global_tax_rate > 0:
                    price_unit = round(price_unit * (1.0 + (global_tax_rate / 100.0)), 2)
                    _logger.info("Absorbed global tax rate %.2f%% into price unit (original: %.2f, new: %.2f) for international import purchase", global_tax_rate, original_price, price_unit)
                elif json_subtotal > 0 and json_tax > 0:
                    ratio = json_tax / json_subtotal
                    price_unit = round(price_unit * (1.0 + ratio), 2)
                    _logger.info("Absorbed global tax ratio %.4f into price unit (original: %.2f, new: %.2f) for international import purchase", ratio, original_price, price_unit)
                
                validation_warnings.append(
                    f"• International Import Purchase: Absorbed extracted tax into price unit (was {original_price:.2f}, now {price_unit:.2f})."
                )

            line_vals = {
                'name': self.name or 'Document',
                'quantity': 1.0,
                'price_unit': price_unit,
            }
            if line_account and line_account.exists():
                line_vals['account_id'] = line_account.id
            if tax:
                line_vals['tax_ids'] = [(6, 0, [tax.id])]
            invoice_line_vals.append((0, 0, line_vals))

        # Check document total mismatch vs lines sum
        if json_total > 0 and items:
            lines_total = sum((self._clean_float(it.get('quantity')) or 1.0) * self._clean_float(it.get('unit_price')) for it in items)
            eff_subtotal = exp_price_unit if (cfg_type == 'expense_bill' and 'exp_price_unit' in locals()) else json_subtotal
            if eff_subtotal > 0 and abs(lines_total - eff_subtotal) > 0.5 and abs((lines_total + json_tax) - json_total) > 0.5:
                validation_warnings.append(
                    f"• Amount Discrepancy: Extracted document subtotal ({eff_subtotal:.2f}) / total ({json_total:.2f}) differs from lines sum ({lines_total:.2f})."
                )

        invoice_ref = seq_ref or self._get_next_sequence_number(move_type, journal)

        if move_type == 'entry':
            journal_line_vals = []
            total_expense_debit = 0.0
            total_tax_debit = 0.0

            # 1. Debit Expense Lines
            for idx, tuple_val in enumerate(invoice_line_vals):
                l_dict = tuple_val[2]
                price_u = float(l_dict.get('price_unit') or 0.0)
                q_val = float(l_dict.get('quantity') or 1.0)
                debit_amt = round(price_u * q_val, 2)
                if debit_amt <= 0 and json_total > 0:
                    debit_amt = json_total

                d_acc = l_dict.get('account_id') or (default_account.id if default_account else False)

                d_line = {
                    'name': l_dict.get('name') or self.name or 'Expense Line',
                    'debit': debit_amt,
                    'credit': 0.0,
                }
                if d_acc:
                    d_line['account_id'] = d_acc
                if 'product_id' in l_dict:
                    d_line['product_id'] = l_dict['product_id']
                if 'tax_ids' in l_dict:
                    # Calculate expected tax amount for fallback if json_tax not present
                    tax_objs = self.env['account.tax'].browse(l_dict['tax_ids'][0][2])
                    for t in tax_objs:
                        if t.amount_type == 'percent':
                            total_tax_debit += round(debit_amt * (t.amount / 100.0), 2)
                        elif t.amount_type == 'fixed':
                            total_tax_debit += t.amount

                if partner:
                    d_line['partner_id'] = partner.id

                journal_line_vals.append((0, 0, d_line))
                total_expense_debit += debit_amt

            if total_expense_debit <= 0:
                total_expense_debit = json_subtotal or json_total or 1.0

            # 2. Debit Tax Line (Explicit Tax Line for Expense Bill)
            actual_tax_amt = json_tax if json_tax > 0 else total_tax_debit
            if actual_tax_amt > 0:
                tax_acc_id = override_tax_account_id
                if not tax_acc_id and config_tax_account and config_tax_account.exists():
                    tax_acc_id = config_tax_account.id
                if not tax_acc_id:
                    # Find default Tax Paid account (e.g. 131000 Tax Paid or tax/asset_current account)
                    tax_acc = self.env['account.account'].search([
                        ('code', '=like', '131%'),
                        ('company_ids', 'in', company.id)
                    ], limit=1)
                    if not tax_acc:
                        tax_acc = self.env['account.account'].search([
                            ('name', 'ilike', 'tax'),
                            ('company_ids', 'in', company.id)
                        ], limit=1)
                    if tax_acc:
                        tax_acc_id = tax_acc.id

                if tax_acc_id:
                    t_line = {
                        'name': f"Tax Paid ({currency_code or ''})",
                        'debit': round(actual_tax_amt, 2),
                        'credit': 0.0,
                        'account_id': tax_acc_id,
                    }
                    if partner:
                        t_line['partner_id'] = partner.id
                    journal_line_vals.append((0, 0, t_line))

            total_entry_credit = round(total_expense_debit + actual_tax_amt, 2)
            if json_total > 0 and abs(total_entry_credit - json_total) < 2.0:
                total_entry_credit = json_total

            # 3. Credit Balancing Line (Payable Account for Partner)
            credit_acc = partner.property_account_payable_id if (partner and getattr(partner, 'property_account_payable_id', False)) else None
            if not credit_acc or not credit_acc.exists():
                credit_acc = self.env['account.account'].search([
                    ('account_type', '=', 'liability_payable'),
                    ('company_ids', 'in', company.id)
                ], limit=1)
            if not credit_acc or not credit_acc.exists():
                credit_acc = journal.default_account_id or default_account

            c_line = {
                'name': invoice_ref or self.name or 'Expense Bill',
                'account_id': credit_acc.id if credit_acc else default_account.id,
                'debit': 0.0,
                'credit': total_entry_credit,
            }
            if partner:
                c_line['partner_id'] = partner.id

            journal_line_vals.append((0, 0, c_line))

            move_vals = {
                'move_type': 'entry',
                'journal_id': journal.id,
                'company_id': journal.company_id.id,
                'date': invoice_date or False,
                'ref': invoice_ref,
                'line_ids': journal_line_vals,
            }
        else:
            move_vals = {
                'move_type': move_type,
                'journal_id': journal.id,
                'company_id': journal.company_id.id,
                'invoice_date': invoice_date or False,
                'ref': invoice_ref,
                'invoice_line_ids': invoice_line_vals,
            }
        if partner:
            move_vals['partner_id'] = partner.id
        if currency_id:
            move_vals['currency_id'] = currency_id
        if detected_expense_type:
            move_vals['expense_bills_type'] = detected_expense_type

        # Assign AI Validation notes and status
        if validation_warnings:
            move_vals['ai_validation_status'] = 'warning'
            move_vals['ai_validation_notes'] = "\n".join(validation_warnings)
        else:
            move_vals['ai_validation_status'] = 'matched'
            move_vals['ai_validation_notes'] = "✓ All extracted line items, products, taxes, and totals match system configuration perfectly."

        _logger.info("Creating draft entry %s with %d lines for partner %s", move_type, len(invoice_line_vals), partner.name if partner else 'None')

        move = self.env['account.move'].create(move_vals)
        self.created_move_id = move.id

        # Attach file data to created account.move
        self.env['ir.attachment'].create({
            'name':      self.file_name or self.name,
            'res_model': 'account.move',
            'res_id':    move.id,
            'datas':     self.file_data,
            'mimetype':  self.mimetype or 'application/octet-stream',
            'type':      'binary',
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Created Entry',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
        }

    def action_batch_analyze_and_create(self):
        """Process multiple document records at once with OpenRouter AI and create accounting entries for each.
        Returns a list-view action opening all created account.move records.
        """
        if not self:
            raise UserError("No documents selected for batch AI processing.")

        created_move_ids = []
        errors = []

        for doc in self:
            try:
                result = doc.action_analyze_and_create_entry()
                if result and result.get('res_id'):
                    created_move_ids.append(result['res_id'])
            except Exception as e:
                _logger.warning("Batch AI: Failed to process doc ID %s (%s): %s", doc.id, doc.name, e)
                errors.append(f"• [{doc.name or doc.id}]: {e}")

        if errors and not created_move_ids:
            raise UserError(
                "Batch AI processing failed for all documents:\n" + "\n".join(errors)
            )

        # Build summary notification via chatter on last processed record (optional)
        summary_lines = [f"✓ {len(created_move_ids)} entries created successfully."]
        if errors:
            summary_lines.append(f"✗ {len(errors)} failed:")
            summary_lines.extend(errors)

        _logger.info("Batch AI Create Summary:\n%s", "\n".join(summary_lines))

        if len(created_move_ids) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Created Entry',
                'res_model': 'account.move',
                'res_id': created_move_ids[0],
                'view_mode': 'form',
                'views': [[False, 'form']],
                'target': 'current',
            }

        return {
            'type': 'ir.actions.act_window',
            'name': f'AI Created Entries ({len(created_move_ids)})',
            'res_model': 'account.move',
            'domain': [('id', 'in', created_move_ids)],
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'target': 'current',
            'context': {
                'batch_ai_summary': "\n".join(summary_lines),
            },
        }

