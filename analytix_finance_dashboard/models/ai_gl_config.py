# -*- coding: utf-8 -*-
import logging
import re
from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

DOC_TYPES = [
    ('sales_invoice', 'Sales Invoice'),
    ('purchase_bill', 'Purchase Bills'),
    ('expense_bill', 'Expense Bills'),
]

EXPENSE_BILLS_TYPES = [
    ('RENT_EXPENSE', 'Rent Expense'),
    ('UTILITIES_EXPENSE', 'Utilities Expense'),
    ('TELECOMMUNICATION_EXPENSE', 'Telecommunication Expense'),
    ('PROFESSIONAL_FEES', 'Professional Fees'),
    ('ACCOUNTING_FEES', 'Accounting Fees'),
    ('AUDIT_FEES', 'Audit Fees'),
    ('TAX_AND_COMPLIANCE_FEES', 'Tax and Compliance Fees'),
    ('LEGAL_FEES', 'Legal Fees'),
    ('GOVERNMENT_FEES', 'Government Fees'),
    ('VISA_AND_IMMIGRATION_EXPENSE', 'Visa and Immigration Expense'),
    ('HR_COMPLIANCE_EXPENSE', 'HR Compliance Expense'),
    ('SALARY_AND_WAGES', 'Salary and Wages'),
    ('EMPLOYEE_BENEFITS', 'Employee Benefits'),
    ('RECRUITMENT_EXPENSE', 'Recruitment Expense'),
    ('TRAINING_EXPENSE', 'Training Expense'),
    ('AIR_TRAVEL_EXPENSE', 'Air Travel Expense'),
    ('HOTEL_AND_ACCOMMODATION', 'Hotel and Accommodation'),
    ('LOCAL_TRANSPORTATION', 'Local Transportation'),
    ('FUEL_EXPENSE', 'Fuel Expense'),
    ('VEHICLE_REPAIR_AND_MAINTENANCE', 'Vehicle Repair and Maintenance'),
    ('VEHICLE_RENTAL_EXPENSE', 'Vehicle Rental Expense'),
    ('OFFICE_SUPPLIES', 'Office Supplies'),
    ('PRINTING_AND_STATIONERY', 'Printing and Stationery'),
    ('SOFTWARE_AND_SUBSCRIPTIONS', 'Software and Subscriptions'),
    ('IT_AND_CLOUD_EXPENSE', 'IT and Cloud Expense'),
    ('IT_EQUIPMENT', 'IT Equipment'),
    ('MARKETING_AND_ADVERTISING', 'Marketing and Advertising'),
    ('DIGITAL_MARKETING_EXPENSE', 'Digital Marketing Expense'),
    ('WEBSITE_AND_DIGITAL_EXPENSE', 'Website and Digital Expense'),
    ('REPAIRS_AND_MAINTENANCE', 'Repairs and Maintenance'),
    ('CLEANING_EXPENSE', 'Cleaning Expense'),
    ('SECURITY_EXPENSE', 'Security Expense'),
    ('INSURANCE_EXPENSE', 'Insurance Expense'),
    ('BANK_CHARGES', 'Bank Charges'),
    ('PAYMENT_PROCESSING_FEES', 'Payment Processing Fees'),
    ('COURIER_AND_POSTAGE', 'Courier and Postage'),
    ('FREIGHT_AND_LOGISTICS', 'Freight and Logistics'),
    ('CUSTOMS_AND_IMPORT_COST', 'Customs and Import Cost'),
    ('MEALS_AND_ENTERTAINMENT', 'Meals and Entertainment'),
    ('EMPLOYEE_WELFARE', 'Employee Welfare'),
    ('MEMBERSHIP_AND_SUBSCRIPTIONS', 'Membership and Subscriptions'),
    ('WAREHOUSING_EXPENSE', 'Warehousing Expense'),
    ('PACKAGING_EXPENSE', 'Packaging Expense'),
    ('UNIFORM_AND_PPE_EXPENSE', 'Uniform and PPE Expense'),
    ('FIXED_ASSET_REVIEW_REQUIRED', 'Fixed Asset Review Required'),
    ('OTHER_ACCOUNT', 'Other Account'),
]


class AiGlConfig(models.Model):
    """AI GL Configuration model for managing default accounting GL accounts and taxes

    by document type (Sales Invoice, Purchase Bills, Expense Bills).
    """
    _name = 'ai.gl.config'
    _description = 'AI GL Configuration'
    _order = 'company_id, type'

    name = fields.Char(
        string='Configuration Name',
        compute='_compute_name',
        store=True,
        readonly=False
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    type = fields.Selection(
        DOC_TYPES,
        string='Document Type',
        required=True,
        default='sales_invoice'
    )

    # --- Expense Bills Line Table ---
    expense_line_ids = fields.One2many(
        'ai.gl.config.expense.line',
        'config_id',
        string='Expense Category Mapping Lines'
    )

    # --- Sales Invoice Foreign Services Mapping Lines ---
    foreign_service_line_ids = fields.One2many(
        'ai.gl.config.foreign.service.line',
        'config_id',
        string='Foreign Services Mapping Lines'
    )

    # --- Purchase Bills Foreign Expenses Mapping Lines ---
    foreign_expense_line_ids = fields.One2many(
        'ai.gl.config.foreign.expense.line',
        'config_id',
        string='Foreign Expenses Mapping Lines'
    )

    # --- Sales Invoice Configuration ---
    income_account_id = fields.Many2one(
        'account.account',
        string='Default Income Account',
        domain="[('account_type', 'in', ['income', 'income_other']), ('company_ids', 'in', company_id)]",
        check_company=True,
        help="Default Chart of Account for Sales Invoices (Income based)"
    )
    sale_tax_id = fields.Many2one(
        'account.tax',
        string='Default Sales Tax',
        domain="[('type_tax_use', '=', 'sale'), ('company_id', 'in', [company_id, False])]",
        check_company=True,
        help="Default Tax set for Sales Invoices"
    )
    sale_tax_account_id = fields.Many2one(
        'account.account',
        string='Default Tax Account',
        domain="[('account_type', 'in', ['asset_current', 'liability_current', 'expense', 'expense_direct_cost']), ('company_ids', 'in', company_id)]",
        check_company=True,
        help="Default GL Tax Account for Sales Invoices (Auto-set from selected Sales Tax)"
    )

    # --- Purchase Bills Configuration ---
    expense_account_id = fields.Many2one(
        'account.account',
        string='Default Expense Account',
        domain="[('account_type', 'in', ['expense', 'expense_depreciation', 'expense_direct_cost', 'cost_of_goods_sold']), ('company_ids', 'in', company_id)]",
        check_company=True,
        help="Default Chart of Account for Purchase Bills (Expense based)"
    )
    purchase_tax_id = fields.Many2one(
        'account.tax',
        string='Default Purchase Tax',
        domain="[('type_tax_use', '=', 'purchase'), ('company_id', 'in', [company_id, False])]",
        check_company=True,
        help="Default Tax set for Purchase Bills"
    )
    tax_account_id = fields.Many2one(
        'account.account',
        string='Default Tax Account',
        domain="[('account_type', 'in', ['asset_current', 'liability_current', 'expense', 'expense_direct_cost']), ('company_ids', 'in', company_id)]",
        check_company=True,
        help="Default GL Tax Account for Purchase Bills (Auto-set from selected Purchase Tax)"
    )

    # --- Expense Bills Configuration ---
    expense_bill_account_id = fields.Many2one(
        'account.account',
        string='Default Expense Account (Bills)',
        domain="[('account_type', 'in', ['expense', 'expense_depreciation', 'expense_direct_cost', 'cost_of_goods_sold']), ('company_ids', 'in', company_id)]",
        check_company=True,
        help="Default Expense Account for Expense Bills"
    )
    expense_bill_tax_id = fields.Many2one(
        'account.tax',
        string='Default Expense Tax',
        domain="[('type_tax_use', '=', 'purchase'), ('company_id', 'in', [company_id, False])]",
        check_company=True,
        help="Default Tax for Expense Bills"
    )
    expense_bill_tax_account_id = fields.Many2one(
        'account.account',
        string='Default Tax Account (Expense)',
        domain="[('account_type', 'in', ['asset_current', 'liability_current', 'expense', 'expense_direct_cost']), ('company_ids', 'in', company_id)]",
        check_company=True,
        help="Default Tax Account for Expense Bills (Auto-set from selected Expense Tax)"
    )

    # ── Helper method to get tax account from account.tax repartition lines ──
    def _get_tax_account_from_tax(self, tax):
        if not tax:
            return False
        # Extract account_id from invoice repartition lines
        accounts = tax.invoice_repartition_line_ids.mapped('account_id').filtered(lambda a: a)
        if accounts:
            return accounts[0].id
        # Fallback to refund repartition lines
        refund_accounts = tax.refund_repartition_line_ids.mapped('account_id').filtered(lambda a: a)
        if refund_accounts:
            return refund_accounts[0].id
        return False

    @api.onchange('sale_tax_id')
    def _onchange_sale_tax_id(self):
        """Auto-populate default tax account when sale tax is selected."""
        if self.sale_tax_id:
            acc_id = self._get_tax_account_from_tax(self.sale_tax_id)
            if acc_id:
                self.sale_tax_account_id = acc_id

    @api.onchange('purchase_tax_id')
    def _onchange_purchase_tax_id(self):
        """Auto-populate default tax account when purchase tax is selected."""
        if self.purchase_tax_id:
            acc_id = self._get_tax_account_from_tax(self.purchase_tax_id)
            if acc_id:
                self.tax_account_id = acc_id

    @api.onchange('expense_bill_tax_id')
    def _onchange_expense_bill_tax_id(self):
        """Auto-populate default tax account when expense bill tax is selected."""
        if self.expense_bill_tax_id:
            acc_id = self._get_tax_account_from_tax(self.expense_bill_tax_id)
            if acc_id:
                self.expense_bill_tax_account_id = acc_id

    @api.depends('type', 'company_id')
    def _compute_name(self):
        type_dict = dict(DOC_TYPES)
        for record in self:
            label = type_dict.get(record.type, '')
            comp = record.company_id.name if record.company_id else ''
            if label and comp:
                record.name = f"AI GL Config - {label} ({comp})"
            elif label:
                record.name = f"AI GL Config - {label}"
            else:
                record.name = "AI GL Config"

    _sql_constraints = [
        ('type_company_uniq', 'unique(type, company_id)',
         'AI GL Configuration for this document type already exists for this company!')
    ]

    @api.model
    def _create_default_configs_for_company(self, company_id):
        """Auto-generate default AI GL Config records for a given company if missing."""
        comp = self.env['res.company'].browse(company_id)
        if not comp.exists():
            return

        doc_types = ['sales_invoice', 'purchase_bill', 'expense_bill']
        for dtype in doc_types:
            existing = self.search([('type', '=', dtype), ('company_id', '=', comp.id)], limit=1)
            if not existing:
                vals = {
                    'type': dtype,
                    'company_id': comp.id,
                }
                if dtype == 'sales_invoice':
                    inc_acc = self.env['account.account'].search([
                        ('account_type', 'in', ['income', 'income_other']),
                        ('company_ids', 'in', comp.id),
                    ], limit=1)
                    if inc_acc:
                        vals['income_account_id'] = inc_acc.id
                    sale_tax = self.env['account.tax'].search([
                        ('type_tax_use', '=', 'sale'),
                        ('company_id', 'in', [comp.id, False]),
                        ('active', '=', True),
                    ], limit=1)
                    if sale_tax:
                        vals['sale_tax_id'] = sale_tax.id
                    if inc_acc:
                        vals['foreign_service_line_ids'] = [
                            (0, 0, {
                                'service_stage': 'domestic_sales',
                                'account_id': inc_acc.id,
                                'tax_id': sale_tax.id if sale_tax else False,
                            }),
                            (0, 0, {
                                'service_stage': 'international_sales',
                                'account_id': inc_acc.id,
                                'tax_id': False,
                            }),
                        ]

                elif dtype == 'purchase_bill':
                    exp_acc = self.env['account.account'].search([
                        ('account_type', 'in', ['expense', 'expense_depreciation', 'expense_direct_cost', 'cost_of_goods_sold']),
                        ('company_ids', 'in', comp.id),
                    ], limit=1)
                    if exp_acc:
                        vals['expense_account_id'] = exp_acc.id
                    pur_tax = self.env['account.tax'].search([
                        ('type_tax_use', '=', 'purchase'),
                        ('company_id', 'in', [comp.id, False]),
                        ('active', '=', True),
                    ], limit=1)
                    if pur_tax:
                        vals['purchase_tax_id'] = pur_tax.id
                    if exp_acc:
                        vals['foreign_expense_line_ids'] = [
                            (0, 0, {
                                'expense_stage': 'domestic_purchase',
                                'account_id': exp_acc.id,
                                'tax_id': pur_tax.id if pur_tax else False,
                            }),
                            (0, 0, {
                                'expense_stage': 'international_import',
                                'account_id': exp_acc.id,
                                'tax_id': False,
                            }),
                        ]

                elif dtype == 'expense_bill':
                    exp_acc = self.env['account.account'].search([
                        ('account_type', 'in', ['expense', 'expense_depreciation', 'expense_direct_cost', 'cost_of_goods_sold']),
                        ('company_ids', 'in', comp.id),
                    ], limit=1)
                    if exp_acc:
                        vals['expense_bill_account_id'] = exp_acc.id
                    exp_tax = self.env['account.tax'].search([
                        ('type_tax_use', '=', 'purchase'),
                        ('company_id', 'in', [comp.id, False]),
                        ('active', '=', True),
                    ], limit=1)
                    if exp_tax:
                        vals['expense_bill_tax_id'] = exp_tax.id

                self.create(vals)

    @api.model
    def get_config_for_type(self, doc_type, company_id=None):
        """Helper method to fetch AI GL Configuration record for a given document type and company."""
        if not company_id:
            company_id = self.env.company.id

        type_mapping = {
            'invoice': 'sales_invoice',
            'sales_invoice': 'sales_invoice',
            'out_invoice': 'sales_invoice',
            'bill': 'purchase_bill',
            'purchase_bill': 'purchase_bill',
            'in_invoice': 'purchase_bill',
            'expense_bill': 'expense_bill',
        }
        target_type = type_mapping.get(doc_type, doc_type)
        cfg = self.search([
            ('type', '=', target_type),
            ('company_id', '=', company_id)
        ], limit=1)
        if not cfg:
            self.sudo()._create_default_configs_for_company(company_id)
            cfg = self.search([
                ('type', '=', target_type),
                ('company_id', '=', company_id)
            ], limit=1)

        # Graceful backfill: Ensure domestic stage line exists for existing records
        if cfg and cfg.type == 'sales_invoice' and cfg.income_account_id:
            if not cfg.foreign_service_line_ids.filtered(lambda l: l.service_stage == 'domestic_sales'):
                self.env['ai.gl.config.foreign.service.line'].sudo().create({
                    'config_id': cfg.id,
                    'service_stage': 'domestic_sales',
                    'account_id': cfg.income_account_id.id,
                    'tax_id': cfg.sale_tax_id.id if cfg.sale_tax_id else False,
                })
        elif cfg and cfg.type == 'purchase_bill' and cfg.expense_account_id:
            if not cfg.foreign_expense_line_ids.filtered(lambda l: l.expense_stage == 'domestic_purchase'):
                self.env['ai.gl.config.foreign.expense.line'].sudo().create({
                    'config_id': cfg.id,
                    'expense_stage': 'domestic_purchase',
                    'account_id': cfg.expense_account_id.id,
                    'tax_id': cfg.purchase_tax_id.id if cfg.purchase_tax_id else False,
                })

        return cfg


    @api.constrains('expense_line_ids')
    def _check_duplicate_line_keywords(self):
        """Validate that no keyword is mapped to multiple different GL expense accounts within the same config."""
        type_dict = dict(EXPENSE_BILLS_TYPES)
        for config in self:
            if not config.expense_line_ids:
                continue
            keyword_account_map = {}
            for line in config.expense_line_ids:
                if not line.keywords or not line.expense_account_id:
                    continue
                acc_name = f"{line.expense_account_id.code or ''} {line.expense_account_id.name or ''}".strip()
                cat_label = type_dict.get(line.expense_bills_type, line.expense_bills_type)
                kws = [k.strip().lower() for k in re.split(r'[,;\n]', line.keywords) if k.strip()]
                for kw in kws:
                    if kw in keyword_account_map:
                        existing_acc_id, existing_acc_name, existing_cat_label = keyword_account_map[kw]
                        if line.expense_account_id.id != existing_acc_id:
                            raise ValidationError(
                                f"Duplicate Keyword Conflict Detected!\n\n"
                                f"The keyword '{kw}' is mapped to two different GL Expense Accounts:\n"
                                f" 1. Line Category: '{existing_cat_label}' -> Account: '{existing_acc_name}'\n"
                                f" 2. Line Category: '{cat_label}' -> Account: '{acc_name}'\n\n"
                                f"Please remove or edit the duplicate keyword '{kw}' so that each keyword uniquely identifies a single GL Expense Account."
                            )
                    else:
                        keyword_account_map[kw] = (
                            line.expense_account_id.id,
                            acc_name,
                            cat_label
                        )


class AiGlConfigExpenseLine(models.Model):
    """Line model for mapping specific Expense Types to Accounts and Taxes in AI GL Config."""
    _name = 'ai.gl.config.expense.line'
    _description = 'AI GL Config Expense Category Line'
    _order = 'config_id, expense_bills_type'

    config_id = fields.Many2one(
        'ai.gl.config',
        string='Configuration',
        ondelete='cascade',
        required=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='config_id.company_id',
        store=True,
        readonly=True
    )
    expense_bills_type = fields.Selection(
        EXPENSE_BILLS_TYPES,
        string='Expense Type',
        required=True
    )
    keywords = fields.Char(
        string='Keywords',
        help='Comma-separated custom keywords to enhance AI GL auto-matching (e.g. flight, airline, ticket, uber)'
    )
    expense_account_id = fields.Many2one(
        'account.account',
        string='Expense Account',
        domain="[('account_type', 'in', ['expense', 'expense_depreciation', 'expense_direct_cost', 'cost_of_goods_sold', 'asset_fixed', 'asset_current']), ('company_ids', 'in', company_id)]",
        check_company=True,
        required=True
    )
    tax_id = fields.Many2one(
        'account.tax',
        string='Expense Tax',
        domain="[('type_tax_use', '=', 'purchase'), ('company_id', 'in', [company_id, False])]",
        check_company=True
    )
    tax_account_id = fields.Many2one(
        'account.account',
        string='Tax Account',
        domain="[('account_type', 'in', ['asset_current', 'liability_current', 'expense', 'expense_direct_cost']), ('company_ids', 'in', company_id)]",
        check_company=True
    )

    @api.onchange('tax_id')
    def _onchange_tax_id(self):
        """Auto-populate default tax account when expense tax is selected."""
        if self.tax_id and self.config_id:
            acc_id = self.config_id._get_tax_account_from_tax(self.tax_id)
            if acc_id:
                self.tax_account_id = acc_id

    @api.constrains('keywords', 'expense_account_id')
    def _check_line_keywords(self):
        """Trigger parent config validation when line keywords or accounts change."""
        for line in self:
            if line.config_id:
                line.config_id._check_duplicate_line_keywords()


class AiGlConfigForeignServiceLine(models.Model):
    """Line model for mapping specific Sales Service Stages (Domestic, International) to Accounts and Taxes."""
    _name = 'ai.gl.config.foreign.service.line'
    _description = 'AI GL Config Foreign Service Line'
    _order = 'config_id, service_stage'

    config_id = fields.Many2one(
        'ai.gl.config',
        string='Configuration',
        ondelete='cascade',
        required=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='config_id.company_id',
        store=True,
        readonly=True
    )
    service_stage = fields.Selection(
        [
            ('domestic_sales', 'Domestic Sales'),
            ('international_sales', 'International Sales'),
        ],
        string='Stage',
        required=True
    )
    account_id = fields.Many2one(
        'account.account',
        string='Chart of Account',
        domain="[('account_type', 'in', ['income', 'income_other']), ('company_ids', 'in', company_id)]",
        check_company=True,
        required=True
    )
    tax_id = fields.Many2one(
        'account.tax',
        string='Tax',
        domain="[('type_tax_use', '=', 'sale'), ('company_id', 'in', [company_id, False])]",
        check_company=True
    )


class AiGlConfigForeignExpenseLine(models.Model):
    """Line model for mapping specific Purchase/Expense Stages (Domestic Purchase, International Import Purchase) to Accounts and Taxes."""
    _name = 'ai.gl.config.foreign.expense.line'
    _description = 'AI GL Config Foreign Expense Line'
    _order = 'config_id, expense_stage'

    config_id = fields.Many2one(
        'ai.gl.config',
        string='Configuration',
        ondelete='cascade',
        required=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='config_id.company_id',
        store=True,
        readonly=True
    )
    expense_stage = fields.Selection(
        [
            ('domestic_purchase', 'Domestic Purchase'),
            ('international_import', 'International Import Purchase'),
        ],
        string='Stage',
        required=True
    )
    account_id = fields.Many2one(
        'account.account',
        string='Chart of Account',
        domain="[('account_type', 'in', ['expense', 'expense_depreciation', 'expense_direct_cost']), ('company_ids', 'in', company_id)]",
        check_company=True,
        required=True
    )
    tax_id = fields.Many2one(
        'account.tax',
        string='Tax',
        domain="[('type_tax_use', '=', 'purchase'), ('company_id', 'in', [company_id, False])]",
        check_company=True
    )


