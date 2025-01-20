from odoo import models, fields, api
from odoo.http import request
from ..controllers.notification_service import CustomerController

notification_service = CustomerController()

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    discount = fields.Float(string='Discount', default=0.0)
    rewards_score = fields.Integer(string='Score', default=0)
    code_ = fields.Char(string='Code', required=True)
    is_published = fields.Boolean(string='Is Published', default=True, help='Determines if product is visible in store')
    external_import_id = fields.Integer(string='External Import ID', help='External ID for product import')
    
    
class PromoCode(models.Model):
    _name = 'product.promo.code'
    _description = 'Product Promotional Code'

    name = fields.Char(string='Promo Code', required=True)
    product_id = fields.Many2one('product.template', string='Product', required=True, ondelete='cascade')
    discount = fields.Float(related='product_id.discount', string='Discount', readonly=False)
    active = fields.Boolean(string='Active', default=True)

    def submit_promo(self):
        # get all users onsignal id from the database
        users_ids = request.env['customer.notification'].search([])
        data = []
        for user in users_ids:
            data.append(user.onesignal_player_id)
            
        for record in self:
            # print(f"Promo Code: {record.name}")
            # print(f"Product: {record.product_id.name}")
            # print(f"Discount: {record.discount}")
                    
            # send notification to all users
            print(data,"-----------------data---------------------")
            notification_service.send_onesignal_notification(
                data,
                'Promo Code: ' + record.name,
                'Promo Code',
                {'type': 'promo_code'}
            )
            
            
        return {'type': 'ir.actions.client', 'tag': 'reload'}