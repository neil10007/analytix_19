# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestInvoiceReset360(TransactionCase):
    """Tests for invoice_reset_360 with user permission and period controls."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].search([], limit=1)
        if not cls.partner:
            partner_vals = {'name': 'Test Customer'}
            if 'group_rfq' in cls.env['res.partner']._fields:
                partner_vals['group_rfq'] = 'default'
            cls.partner = cls.env['res.partner'].create(partner_vals)

        cls.product = cls.env['product.product'].search([('sale_ok', '=', True)], limit=1)
        if not cls.product:
            cls.product = cls.env['product.product'].create({
                'name': 'Test Service',
                'list_price': 250.0,
            })

        # Test user without permissions
        cls.test_user = cls.env['res.users'].create({
            'name': 'Regular Invoicing User',
            'login': 'regular_invoicing_user',
            'email': 'regular_user@example.com',
            'group_ids': [(6, 0, [cls.env.ref('account.group_account_invoice').id, cls.env.ref('base.group_user').id])],
        })

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tz='UTC'))
        self.env.user.tz = 'UTC'

    def _create_test_invoice(self):
        return self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'name': 'Consulting',
                'quantity': 1,
                'price_unit': 250.0,
            })],
        })

    def test_01_draft_has_no_qr(self):
        """Invoice in draft has no QR code."""
        invoice = self._create_test_invoice()
        self.assertEqual(invoice.state, 'draft')
        self.assertFalse(invoice._has_generated_qr_code())

    def test_02_posted_without_qr_can_reset(self):
        """Posted invoice without QR code can still be reset if needed."""
        self.env.company.vat = False
        self.env['ir.config_parameter'].sudo().set_param('advanced_vat_invoice.generate_qr', 'manually')
        self.env.registry.clear_cache()
        invoice = self._create_test_invoice()
        invoice.action_post()
        self.assertEqual(invoice.state, 'posted')
        self.assertFalse(invoice._has_generated_qr_code())
        # Should reset to draft without error
        invoice.button_draft()
        self.assertEqual(invoice.state, 'draft')

    def test_03_posted_with_qr_unauthorized_user_raises_validation_error(self):
        """User without permission gets ValidationError on button_draft."""
        self.env.company.vat = '300000000000003'
        self.env['ir.config_parameter'].sudo().set_param('advanced_vat_invoice.generate_qr', 'automatically')
        self.env.registry.clear_cache()
        invoice = self._create_test_invoice()
        invoice.action_post()
        self.assertEqual(invoice.state, 'posted')
        self.assertTrue(invoice._has_generated_qr_code())

        # Ensure test user has no permission
        self.test_user.write({
            'allow_invoice_reset_draft': False,
            'reset_draft_valid_from': False,
            'reset_draft_valid_until': False,
        })
        invoice_as_user = invoice.with_user(self.test_user)

        with self.assertRaises(ValidationError) as cm:
            invoice_as_user.button_draft()

        self.assertIn("cannot reset invoice", str(cm.exception))
        self.assertIn("QR code has been generated", str(cm.exception))

    def test_04_authorized_user_can_reset(self):
        """User with allow_invoice_reset_draft permission CAN reset to draft."""
        self.env.company.vat = '300000000000003'
        self.env['ir.config_parameter'].sudo().set_param('advanced_vat_invoice.generate_qr', 'automatically')
        self.env.registry.clear_cache()
        invoice = self._create_test_invoice()
        invoice.action_post()
        self.assertEqual(invoice.state, 'posted')
        self.assertTrue(invoice._has_generated_qr_code())

        # Grant permission to test user
        self.test_user.write({
            'allow_invoice_reset_draft': True,
            'reset_draft_valid_from': False,
            'reset_draft_valid_until': False,
        })
        invoice_as_user = invoice.with_user(self.test_user)
        invoice_as_user.button_draft()
        self.assertEqual(invoice.state, 'draft')

    def test_05_expired_period_raises_validation_error(self):
        """User whose permission period has expired cannot reset to draft."""
        self.env.company.vat = '300000000000003'
        self.env['ir.config_parameter'].sudo().set_param('advanced_vat_invoice.generate_qr', 'automatically')
        self.env.registry.clear_cache()
        invoice = self._create_test_invoice()
        invoice.action_post()
        self.assertEqual(invoice.state, 'posted')

        # Set permission that expired yesterday
        yesterday = fields.Datetime.now() - timedelta(days=1)
        two_days_ago = fields.Datetime.now() - timedelta(days=2)
        self.test_user.write({
            'allow_invoice_reset_draft': True,
            'reset_draft_valid_from': two_days_ago,
            'reset_draft_valid_until': yesterday,
        })
        invoice_as_user = invoice.with_user(self.test_user)

        with self.assertRaises(ValidationError) as cm:
            invoice_as_user.button_draft()

        self.assertIn("expired", str(cm.exception))

    def test_06_active_period_can_reset(self):
        """User with active valid period CAN reset to draft."""
        self.env.company.vat = '300000000000003'
        self.env['ir.config_parameter'].sudo().set_param('advanced_vat_invoice.generate_qr', 'automatically')
        self.env.registry.clear_cache()
        invoice = self._create_test_invoice()
        invoice.action_post()
        self.assertEqual(invoice.state, 'posted')

        # Set permission valid from yesterday until tomorrow
        yesterday = fields.Datetime.now() - timedelta(days=1)
        tomorrow = fields.Datetime.now() + timedelta(days=1)
        self.test_user.write({
            'allow_invoice_reset_draft': True,
            'reset_draft_valid_from': yesterday,
            'reset_draft_valid_until': tomorrow,
        })
        invoice_as_user = invoice.with_user(self.test_user)
        invoice_as_user.button_draft()
        self.assertEqual(invoice.state, 'draft')

    def test_07_group_permission_can_reset(self):
        """User in group_allow_invoice_reset_draft CAN reset to draft."""
        self.env.company.vat = '300000000000003'
        self.env['ir.config_parameter'].sudo().set_param('advanced_vat_invoice.generate_qr', 'automatically')
        self.env.registry.clear_cache()
        invoice = self._create_test_invoice()
        invoice.action_post()
        self.assertEqual(invoice.state, 'posted')

        # Assign security group to user
        group = self.env.ref('invoice_reset_360.group_allow_invoice_reset_draft')
        self.test_user.write({
            'allow_invoice_reset_draft': False,
            'reset_draft_valid_from': False,
            'reset_draft_valid_until': False,
            'group_ids': [(4, group.id)],
        })
        invoice_as_user = invoice.with_user(self.test_user)
        invoice_as_user.button_draft()
        self.assertEqual(invoice.state, 'draft')
