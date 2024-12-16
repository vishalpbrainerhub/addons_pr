from odoo import models, fields

class CustomerAddressModel(models.Model):
    _name = 'social_media.custom_address'
    _description = 'Customer Address Model'
    
    partner_id = fields.Many2one('res.partner', string='Customer', 
                                required=True, 
                                ondelete='cascade',
                                domain=[('customer_rank', '>', 0)])
    address = fields.Text("Address", required=True)
    continued_address = fields.Text("Continued Address")
    city = fields.Char("City", required=True)
    postal_code = fields.Char("Postal Code", required=True)
    village = fields.Char("Village")
    default = fields.Boolean("Default", default=False)
    country_id = fields.Many2one('res.country', string="Country")
    state_id = fields.Many2one('res.country.state', string="State", domain="[('country_id', '=', country_id)]", required=False)