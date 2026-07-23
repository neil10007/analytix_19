# from odoo import http


# class ProformaInvoice(http.Controller):
#     @http.route('/proforma_invoice/proforma_invoice', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/proforma_invoice/proforma_invoice/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('proforma_invoice.listing', {
#             'root': '/proforma_invoice/proforma_invoice',
#             'objects': http.request.env['proforma_invoice.proforma_invoice'].search([]),
#         })

#     @http.route('/proforma_invoice/proforma_invoice/objects/<model("proforma_invoice.proforma_invoice"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('proforma_invoice.object', {
#             'object': obj
#         })

