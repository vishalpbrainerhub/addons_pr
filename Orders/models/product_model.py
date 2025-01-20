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
        
        for record in self:
        
            notification_service.send_onesignal_notification_to_all(
                f'Nuovo codice promozionale disponibile: {record.name}',
                'Nuovo Codice Promo', 
                {'type': 'promo'}
            )
        return {'type': 'ir.actions.client', 'tag': 'reload'}
    
    def unlink(self):
       for record in self:
           record.product_id.write({'discount': 0.0})
       return super(PromoCode, self).unlink()
    