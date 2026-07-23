# from odoo import models, fields, api


# class proforma_invoice(models.Model):
#     _name = 'proforma_invoice.proforma_invoice'
#     _description = 'proforma_invoice.proforma_invoice'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

