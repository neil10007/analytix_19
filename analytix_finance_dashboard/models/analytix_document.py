# -*- coding: utf-8 -*-
import logging
import os
import base64
import json
from io import BytesIO
from odoo import models, api, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)



class AnalytixDocument(models.Model):
    """General-purpose document store for the Analytix Finance Dashboard."""
    _name = 'analytix.document'
    _description = 'Analytix Finance Document'
    _order = 'upload_date desc, id desc'

    name = fields.Char(string='Document Name', required=True)
    description = fields.Char(string='Description')
    doc_type = fields.Selection([
        ('invoice',  'Invoice'),
        ('bill',     'Bills'),
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


    # ── Label maps ────────────────────────────────────────────────────
    STATUS_LABELS = {
        'submitted': 'Submitted',
        'approved':  'Approved',
        'rejected':  'Rejected',
    }
    DOC_TYPE_LABELS = {
        'invoice': 'Invoice',
        'bill':    'Bills',
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
        _logger.info(
            "save_analytix_document called: name=%s file_name=%s mimetype=%s "
            "file_size=%s doc_type=%s description=%s b64_len=%s",
            name, file_name, mimetype, file_size, doc_type, description,
            len(file_data_b64) if file_data_b64 else 0,
        )
        try:
            # ── 1. Create the metadata record (no binary here) ──────────────
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
            _logger.info("Created analytix.document id=%s", doc.id)

            # ── 2. Write binary via the Binary field (attachment=True) ───────
            #    Odoo 19: Binary(attachment=True) stores via ir.attachment.
            #    The ORM accepts a plain base64 string when writing through the
            #    field; it converts internally. Pass exactly what we received.
            if file_data_b64:
                # Ensure we have a clean base64 string (strip whitespace/newlines)
                b64_clean = file_data_b64.strip() if isinstance(file_data_b64, str) else file_data_b64
                doc.sudo().write({'file_data': b64_clean})
                _logger.info("File data written to doc id=%s", doc.id)

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
        ALLOWED = {'description', 'name', 'review'}
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
        # Binary(attachment=True) returns bytes in Odoo 19; decode to str for JSON
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

    PROMPT = """
You are an OCR and financial document extraction engine.

Your task is to extract structured data from the document image.

Return ONLY valid JSON. Do not return markdown. Do not explain anything.

First, identify what kind of document this is:
- "invoice"      → A sales invoice issued TO a customer (money owed to the seller)
- "bill"         → A purchase invoice / vendor bill received FROM a supplier (money owed by the buyer)
- "credit_note"  → A credit memo that reduces an amount owed (issued by seller to customer)
- "debit_note"   → A debit memo that increases an amount owed
- "receipt"      → A payment receipt confirming money received
- "other"        → Any other financial document

Use exactly this schema:

{
  "document_type": "",
  "invoice_number": "",
  "invoice_date": "",
  "vendor_name": "",
  "customer_name": "",
  "currency": "",

  "items": [
    {
      "description": "",
      "quantity": 0,
      "unit_price": 0,
      "tax_rate": 0
    }
  ],

  "subtotal": 0,
  "tax": 0,
  "total": 0
}

Rules:

- Set "document_type" to one of: invoice, bill, credit_note, debit_note, receipt, other.
- If the document is addressed FROM a supplier/vendor TO a buyer, it is a "bill".
- If the document is issued BY a company TO their customer, it is an "invoice".
- For "tax_rate" per item: extract the tax percentage applied to that line (e.g. 5 for 5%, 15 for 15%). If no tax on that line, use 0.
- Never hallucinate values.
- Missing string -> ""
- Missing number -> 0
- Missing array -> []
- Dates should be YYYY-MM-DD.
- Numbers should not contain commas.
- Ignore signatures, logos, QR codes and stamps.
- Extract every visible line item.
"""

    def _image_to_base64(self, image):
        """Convert a PIL Image to a base64-encoded PNG string."""
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def _call_openrouter(self, client, image_b64):
        """
        Send a single page/image to OpenRouter (Gemini model) and return the
        parsed JSON dict describing the document (invoice/bill/receipt/etc).

        `client` is an openai.OpenAI instance already pointed at OpenRouter.
        `image_b64` is a base64-encoded PNG/JPEG string (no data: prefix),
        as produced by self._image_to_base64().
        """
        system_prompt = (
            "You are a document-extraction engine for an accounting system. "
            "Given an image of an invoice, bill, receipt or credit note, extract "
            "the data and respond with ONLY a valid JSON object (no markdown, no "
            "commentary) using this shape:\n"
            "{\n"
            '  "document_type": "invoice|bill|credit_note|debit_note|receipt|other",\n'
            '  "vendor_name": "string or null",\n'
            '  "customer_name": "string or null",\n'
            '  "invoice_date": "YYYY-MM-DD or null",\n'
            '  "currency": "3-letter ISO code or null",\n'
            '  "subtotal": number,\n'
            '  "tax": number,\n'
            '  "total": number,\n'
            '  "items": [\n'
            '    {"description": "string", "quantity": number, "unit_price": number, "tax_rate": number}\n'
            "  ]\n"
            "}"
        )

        model_name = getattr(self.env.user, 'openrouter_model', False) or getattr(self.env.company, 'openrouter_model', False) or "google/gemini-2.5-flash"

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract the document data as JSON."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}"
                            },
                        },
                    ],
                },
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )

        content = response.choices[0].message.content

        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError):
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`")
                if cleaned.lower().startswith("json"):
                    cleaned = cleaned[4:]
            return json.loads(cleaned.strip())

    def _call_groq(self, client, image_b64):
        """Call Groq API with the given base64 image."""
        completion = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": self.PROMPT
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}"
                            }
                        }
                    ]
                }
            ],
            temperature=0,
            max_completion_tokens=4096,
            top_p=1,
            stream=False,
            stop=None,
            response_format={"type": "json_object"},
        )
        return json.loads(completion.choices[0].message.content)

    def _resolve_tax(self, move_type, tax_rate):
        """Find an account.tax record matching the given percentage."""
        if not tax_rate:
            return self.env['account.tax']

        tax_type = 'sale' if move_type in ('out_invoice', 'out_refund') else 'purchase'
        rate = round(float(tax_rate), 2)
        company = self.env.company

        tax = self.env['account.tax'].search([
            ('type_tax_use', '=', tax_type),
            ('amount', '=', rate),
            ('amount_type', '=', 'percent'),
            ('company_id', '=', company.id),
            ('active', '=', True),
        ], limit=1)

        if not tax:
            tax = self.env['account.tax'].search([
                ('amount', '=', rate),
                ('amount_type', '=', 'percent'),
                ('company_id', '=', company.id),
                ('active', '=', True),
            ], limit=1)

        return tax

    def _get_next_sequence_number(self, move_type, journal):
        """Retrieve the last account.move number/ref and auto-increment it."""
        import re
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

    def action_analyze_and_create_entry(self):
        """Process the document file with OpenRouter (Gemini) and create corresponding accounting entry."""
        self.ensure_one()
        if not self.file_data:
            raise UserError("No file uploaded for this document record.")

        # Determine OpenRouter API key (check user first, then company)
        api_key = self.env.user.open_router_key or getattr(self.env.user, 'openrouter_api_key', False) or self.env.company.open_router_key or getattr(self.env.company, 'openrouter_api_key', False)

        if not api_key:
            raise UserError("Please configure an OpenRouter API Key on your User profile or Company settings.")

        # Print the API key in the logs as requested
        print("--------------------------------------------------")
        print("OPENROUTER API KEY IS:", api_key)
        print("--------------------------------------------------")
        _logger.info("OPENROUTER API KEY IS: %s", api_key)

        try:
            import fitz          # PyMuPDF
            from PIL import Image
            from openai import OpenAI
        except ImportError as e:
            raise UserError(
                f"Missing dependency: {e}\n"
                "Please run: pip install pymupdf openai pillow"
            )

        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key.strip(),
        )

        raw_data = self.file_data
        if not raw_data:
            raise UserError("No file data found.")

        if isinstance(raw_data, str):
            raw_data = raw_data.encode('utf-8')

        if b'base64,' in raw_data[:100]:
            raw_data = raw_data.split(b'base64,')[1]

        decoded_data = None
        try:
            decoded_data = base64.b64decode(raw_data)
        except Exception:
            pass

        doc = None
        if decoded_data:
            try:
                doc = fitz.open(stream=decoded_data)
            except Exception:
                pass

        if not doc:
            try:
                doc = fitz.open(stream=raw_data)
            except Exception as e_fitz_raw:
                try:
                    if decoded_data:
                        image = Image.open(BytesIO(decoded_data)).convert("RGB")
                    else:
                        image = Image.open(BytesIO(raw_data)).convert("RGB")

                    image_b64 = self._image_to_base64(image)
                    output = self._call_openrouter(client, image_b64)
                except Exception as e_pil:
                    raise UserError(f"Could not parse file format.\nPyMuPDF error: {e_fitz_raw}\nPillow error: {e_pil}")

        if doc:
            results = []
            for page_index in range(len(doc)):
                page = doc.load_page(page_index)
                pix = page.get_pixmap(dpi=250, alpha=False)
                image = Image.open(BytesIO(pix.tobytes("png"))).convert("RGB")
                image_b64 = self._image_to_base64(image)
                result = self._call_openrouter(client, image_b64)
                results.append(result)
            doc.close()
            output = results[0] if len(results) == 1 else results

        self.response_json = json.dumps(output, indent=4)
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

        SUPPORTED_TYPES = {'invoice', 'bill', 'receipt', 'credit_note', 'debit_note'}
        raw_doc_type = (data.get('document_type') or '').strip().lower()

        if not raw_doc_type or raw_doc_type not in SUPPORTED_TYPES:
            display_type = data.get('document_type') or 'Other/Unknown'
            raise UserError(
                f"Unsupported Document Type: '{display_type}'.\n\n"
                "The AI analyzed this document and detected that it is not a valid Invoice or Bill. "
                "Only Invoices and Bills (or Receipts/Credit Notes) are supported for automatic entry creation."
            )

        DOC_TYPE_MAP = {
            'invoice':     'out_invoice',   # Customer Invoice
            'bill':        'in_invoice',    # Vendor Bill
            'credit_note': 'out_refund',    # Customer Credit Note
            'debit_note':  'in_invoice',    # Treated as vendor bill variant
            'receipt':     'in_invoice',    # Treat receipt as vendor bill
        }
        move_type = DOC_TYPE_MAP[raw_doc_type]

        # Resolve / Create Partner
        partner = None
        partner_name = (data.get('vendor_name') or data.get('customer_name') or '').strip()
        if partner_name:
            partner = self.env['res.partner'].search(
                [('name', 'ilike', partner_name)], limit=1
            )
            if not partner:
                partner = self.env['res.partner'].create({'name': partner_name})

        # Resolve Invoice Date (default to today if missing or invalid)
        from datetime import date as _date
        today_str = _date.today().strftime('%Y-%m-%d')
        invoice_date = data.get('invoice_date') or today_str
        try:
            _date.fromisoformat(invoice_date)
        except (ValueError, TypeError):
            invoice_date = today_str

        # Resolve Currency
        currency_id = False
        currency_code = (data.get('currency') or '').strip().upper()
        if currency_code:
            currency = self.env['res.currency'].search(
                [('name', '=', currency_code)], limit=1
            )
            if currency:
                currency_id = currency.id

        company = self.env.company
        journal = self.env['account.journal'].search(
            [
                ('type', '=', 'sale' if move_type == 'out_invoice' else 'purchase'),
                ('company_id', '=', company.id),
            ],
            limit=1,
        )
        if not journal:
            raise UserError(
                "No '%s' journal found. Please configure one in Accounting."
                % ('Sales' if move_type == 'out_invoice' else 'Purchase')
            )

        default_account = (
            journal.default_account_id
            or self.env['account.account'].search(
                [
                    ('account_type', 'in',
                     ['income', 'income_other'] if move_type == 'out_invoice'
                     else ['expense', 'expense_depreciation']),
                    ('company_ids', 'in', company.id),
                    ('deprecated', '=', False),
                ],
                limit=1,
            )
        )
        if not default_account:
            raise UserError(
                "Could not determine a default account. "
                "Please set a Default Account on the journal."
            )

        # Build lines
        items = data.get('items') or []
        invoice_line_vals = []

        global_tax_rate = 0.0
        json_subtotal = float(data.get('subtotal') or 0.0)
        json_tax = float(data.get('tax') or 0.0)
        if json_subtotal and json_tax:
            global_tax_rate = round((json_tax / json_subtotal) * 100, 4)

        for item in items:
            desc = item.get('description') or 'Item'
            qty = float(item.get('quantity') or 1)
            price = float(item.get('unit_price') or 0.0)
            tax_rate = float(item.get('tax_rate') or 0.0)

            if not tax_rate and global_tax_rate:
                tax_rate = global_tax_rate

            tax_ids = []
            if tax_rate:
                tax = self._resolve_tax(move_type, tax_rate)
                if tax:
                    tax_ids = [(4, tax.id)]

            line_vals = {
                'name': desc,
                'quantity': qty,
                'price_unit': price,
                'account_id': default_account.id,
            }
            if tax_ids:
                line_vals['tax_ids'] = tax_ids

            invoice_line_vals.append((0, 0, line_vals))

        if not invoice_line_vals:
            total = float(data.get('total') or data.get('subtotal') or 0.0)
            subtotal = float(data.get('subtotal') or 0.0)
            price_unit = subtotal if subtotal else total

            tax_ids = []
            if global_tax_rate:
                tax = self._resolve_tax(move_type, global_tax_rate)
                if tax:
                    tax_ids = [(4, tax.id)]

            line_vals = {
                'name': self.name or 'Document',
                'quantity': 1,
                'price_unit': price_unit,
                'account_id': default_account.id,
            }
            if tax_ids:
                line_vals['tax_ids'] = tax_ids
            invoice_line_vals.append((0, 0, line_vals))

        # Always auto-generate the sequence number (no call from the JSON)
        invoice_ref = self._get_next_sequence_number(move_type, journal)

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

        move = self.env['account.move'].create(move_vals)
        self.created_move_id = move.id

        # Also create attachment for the newly created account.move containing the document's file_data
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

