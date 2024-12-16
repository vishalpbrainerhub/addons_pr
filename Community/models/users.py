from odoo import models, fields
from odoo.exceptions import AccessDenied
import logging

class ResPartner(models.Model):
    _inherit = 'res.partner'

    blocked_customers = fields.Many2many(
        'res.partner', 
        'res_partner_blocked_rel', 
        'partner_id', 
        'blocked_partner_id',
        string='Blocked Customers'
    )

class CustomerAddressModel(models.Model):
    _name = 'social_media.address'
    _description = 'Customer Address'
    
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    address = fields.Text("Address")
    continued_address = fields.Text("Continued Address")
    city = fields.Char("City")
    postal_code = fields.Char("Postal Code")
    village = fields.Char("Village")
    default = fields.Boolean("Default", default=False)
    country_id = fields.Char("Country")
    state_id = fields.Char("State")