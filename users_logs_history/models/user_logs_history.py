from odoo import models, fields, api, _

class UserLogsHistory(models.Model):
    _name = 'user.logs.history'
    _description = 'User Activity & Database Log History'
    _order = 'log_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(string='Action Outcome Summary', required=True, index=True)
    user_id = fields.Many2one(
        'res.users', 
        string='User', 
        default=lambda self: self.env.user,
        ondelete='set null',
        index=True
    )
    user_name = fields.Char(string='User Name', index=True)
    operation_type = fields.Selection([
        ('create', 'Create'),
        ('write', 'Update / Write'),
        ('unlink', 'Delete')
    ], string='Operation', required=True, index=True)

    category = fields.Selection([
        ('accounting', 'Invoicing & Accounting'),
        ('sale', 'Sales'),
        ('purchase', 'Purchases'),
        ('inventory', 'Inventory & Stock'),
        ('contact', 'Contacts & Partners'),
        ('system', 'System & Users'),
        ('other', 'Other Modules')
    ], string='Category', default='other', index=True)
    
    model_name = fields.Char(string='Model Technical Name', required=True, index=True)
    model_description = fields.Char(string='Model Name', index=True)
    model_id = fields.Many2one('ir.model', string='Model Reference', compute='_compute_model_id', store=True)
    
    res_id = fields.Integer(string='Record ID', index=True)
    record_name = fields.Char(string='Record Display Name', index=True)
    
    details = fields.Text(string='Log Details')
    details_html = fields.Html(string='Formatted Details', compute='_compute_details_html')
    
    log_date = fields.Datetime(string='Timestamp', default=fields.Datetime.now, required=True, index=True)
    ip_address = fields.Char(string='IP Address')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    @api.depends('model_name')
    def _compute_model_id(self):
        for rec in self:
            if rec.model_name:
                model = self.env['ir.model'].sudo().search([('model', '=', rec.model_name)], limit=1)
                rec.model_id = model.id if model else False
            else:
                rec.model_id = False

    @api.depends('details')
    def _compute_details_html(self):
        for rec in self:
            if not rec.details:
                rec.details_html = '<div class="text-muted p-2" style="font-style:italic;">No field changes recorded for this action.</div>'
                continue
            
            lines = rec.details.strip().split('\n')
            html_rows = []
            for line in lines:
                if '->' in line:
                    parts = line.split('->', 1)
                    raw_field = parts[0].strip()
                    val = parts[1].strip()
                    clean_field = raw_field.replace('_id', '').replace('_', ' ').title()
                    html_rows.append(
                        f'<tr>'
                        f'<td style="font-weight:600; padding:8px 12px; border-bottom:1px solid #eef2f5; color:#495057; width:35%;">{clean_field}</td>'
                        f'<td style="padding:8px 12px; border-bottom:1px solid #eef2f5; color:#0d6efd; font-family:monospace;">{val}</td>'
                        f'</tr>'
                    )
                elif ':' in line:
                    parts = line.split(':', 1)
                    raw_field = parts[0].strip()
                    val = parts[1].strip()
                    clean_field = raw_field.replace('_id', '').replace('_', ' ').title()
                    html_rows.append(
                        f'<tr>'
                        f'<td style="font-weight:600; padding:8px 12px; border-bottom:1px solid #eef2f5; color:#495057; width:35%;">{clean_field}</td>'
                        f'<td style="padding:8px 12px; border-bottom:1px solid #eef2f5; color:#0d6efd; font-family:monospace;">{val}</td>'
                        f'</tr>'
                    )
                else:
                    html_rows.append(f'<tr><td colspan="2" style="padding:8px 12px; border-bottom:1px solid #eef2f5; color:#495057;">{line}</td></tr>')
            
            rec.details_html = (
                '<div class="border rounded bg-white shadow-sm overflow-hidden mt-2">'
                '<table class="table table-hover mb-0" style="width:100%; font-size:13px;">'
                '<thead><tr style="background-color:#f8f9fa;"><th style="padding:8px 12px; border-bottom:2px solid #dee2e6; color:#6c757d;">Field Name</th><th style="padding:8px 12px; border-bottom:2px solid #dee2e6; color:#6c757d;">Value / Details</th></tr></thead>'
                f'<tbody>{"".join(html_rows)}</tbody>'
                '</table>'
                '</div>'
            )

    def action_open_record(self):
        """ Smart button action to open target record """
        self.ensure_one()
        if not self.model_name or not self.res_id:
            return False
        
        if self.model_name not in self.env:
            return False
        
        record = self.env[self.model_name].sudo().browse(self.res_id)
        if not record.exists():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Record Unavailable'),
                    'message': _('Record #%s of model %s no longer exists in database.') % (self.res_id, self.model_name),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.model_name,
            'res_id': self.res_id,
            'view_mode': 'form',
            'target': 'current',
        }
