from odoo import models, fields, api

class FinanceAlert(models.Model):
    _name = 'analytix.finance.alert'
    _description = 'Finance Alert'

    # 1. Basic Information
    name = fields.Char(string='Alert Name', required=True)
    module = fields.Selection([
        ('accounting', 'Accounting'),
        ('sales', 'Sales'),
        ('purchases', 'Purchases'),
    ], string='Module', required=True, default='accounting')
    alert_category = fields.Selection([
        ('tax_compliance', 'Tax & Compliance'),
        ('cash_flow', 'Cash Flow'),
        ('budgeting', 'Budgeting'),
    ], string='Alert Category', required=True, default='tax_compliance')
    alert_type = fields.Selection([
        ('business_rule', 'Business Rule'),
        ('threshold', 'Threshold'),
        ('anomaly', 'Anomaly'),
    ], string='Alert Type', required=True, default='business_rule')
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ], string='Priority', required=True, default='medium')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    tag_ids = fields.Many2many('analytix.finance.alert.tag', string='Tags')

    # 2. Trigger Configuration
    trigger_type = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('event', 'Event Driven'),
    ], string='Trigger Type', required=True, default='scheduled')
    check_frequency = fields.Selection([
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ], string='Check Frequency', required=True, default='daily')
    execution_time = fields.Float(string='Time', required=True, default=8.0)
    run_for = fields.Selection([
        ('all_companies', 'All Companies'),
        ('specific_company', 'Specific Company'),
    ], string='Run For', required=True, default='all_companies')
    start_from = fields.Date(string='Start From')
    next_execution = fields.Datetime(string='Next Execution', readonly=True)
    stop_after = fields.Date(string='Stop After')

    # 3. Rule Configuration
    model_id = fields.Many2one('ir.model', string='Model', required=True, ondelete='cascade')
    domain_condition = fields.Char(string='Domain / Condition', required=True)
    due_date_field_id = fields.Many2one('ir.model.fields', string='Due Date Field', domain="[('model_id', '=', model_id), ('ttype', 'in', ('date', 'datetime'))]", required=True, ondelete='cascade')
    warning_days = fields.Integer(string='Warning Days', required=True, default=30)
    trigger_when = fields.Selection([
        ('within_warning', 'Due Date is within Warning Days'),
        ('overdue', 'Is Overdue'),
    ], string='Trigger When', required=True, default='within_warning')
    create_alert = fields.Selection([
        ('once', 'Once'),
        ('every_time', 'Every Time'),
    ], string='Create Alert', required=True, default='once')
    auto_close = fields.Selection([
        ('when_filed', 'When VAT Return is Filed'),
        ('manual', 'Manual'),
    ], string='Auto Close', required=True, default='when_filed')
    rule_description = fields.Text(string='Rule Description', compute='_compute_rule_description')

    @api.depends('warning_days', 'trigger_when', 'due_date_field_id')
    def _compute_rule_description(self):
        for rec in self:
            if rec.warning_days and rec.due_date_field_id:
                rec.rule_description = f"Rule will trigger when {rec.due_date_field_id.field_description} is within {rec.warning_days} days."
            else:
                rec.rule_description = ""

    # 4. Alert Message
    alert_title = fields.Char(string='Title', required=True)
    alert_description = fields.Text(string='Description', required=True)
    action_button_label = fields.Char(string='Button Label')
    action_button_link = fields.Char(string='Button Link')

    # 5. Notification Settings
    notify_dashboard = fields.Boolean(string='Dashboard Alert', default=True)
    notify_bell = fields.Boolean(string='Bell Notification', default=True)
    notify_email = fields.Boolean(string='Email', default=True)
    notify_mobile_push = fields.Boolean(string='Mobile Push Notification', default=True)
    notify_whatsapp = fields.Boolean(string='WhatsApp', default=False)
    recipient_ids = fields.Many2many('res.users', string='Recipients')

    # 6. AI Recommendation
    enable_ai_recommendation = fields.Boolean(string='Enable AI Recommendation', default=True)

    # 7. Escalation Rules
    escalation_rule_ids = fields.One2many('analytix.finance.alert.escalation', 'alert_id', string='Escalation Rules')

    def action_run_test(self):
        # Placeholder for test rule action
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Test Rule',
                'message': 'Test executed successfully!',
                'sticky': False,
            }
        }

class FinanceAlertTag(models.Model):
    _name = 'analytix.finance.alert.tag'
    _description = 'Finance Alert Tag'

    name = fields.Char(string='Name', required=True)
    color = fields.Integer(string='Color Index')

class FinanceAlertEscalation(models.Model):
    _name = 'analytix.finance.alert.escalation'
    _description = 'Finance Alert Escalation Rule'

    alert_id = fields.Many2one('analytix.finance.alert', string='Alert', ondelete='cascade')
    days_remaining = fields.Integer(string='Days Remaining', required=True)
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ], string='Priority', required=True)
    action = fields.Char(string='Action', required=True)
