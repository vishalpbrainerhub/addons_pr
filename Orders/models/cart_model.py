from odoo import models, fields, api



class Cart(models.Model):
    _name = 'mobile_ecommerce.cart'
    _description = 'Mobile Ecommerce Cart'
    
    user_id = fields.Many2one('res.partner', string='User', required=True)  # Changed to res.partner
    product_id = fields.Many2one('product.product', string='Product', required=True)
    quantity = fields.Integer(string='Quantity', required=True)
    price = fields.Float(string='Price', compute='_compute_price', store=True)
    


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Fields to store the address directly on the order
    shipping_address_id = fields.Integer(string='Shipping Address ID')
    
    # def _create_invoices(self, grouped=False, final=False):
    #     invoices = super(SaleOrder, self)._create_invoices(grouped=grouped, final=final)
    #     for invoice in invoices:
    #         if invoice.state == 'draft':
    #             invoice.action_post()  # Transition to 'posted'
    #             print("Action for when the transition in state-------------")  # This will print when the invoice is posted
    #     return invoices
    