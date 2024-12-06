from odoo import models, fields
from odoo.exceptions import AccessDenied
import logging


class ResUsers(models.Model):
    _inherit = 'res.users'

    blocked_users = fields.Many2many(
        'res.users', 'res_users_blocked_rel', 'user_id', 'blocked_user_id',
        string='Blocked Users'
    )
    x_last_name = fields.Char("last_name",)

    
class UserAddressModel(models.Model):
    _name = 'social_media.address'
    _description = 'User Address'
    
    user_id = fields.Many2one('res.users', string='User', required=True)
    address = fields.Text("Address")
    continued_address = fields.Text("Continued Address")
    city = fields.Char("City")
    postal_code = fields.Char("Postal Code")
    village = fields.Char("Village")
    default = fields.Boolean("Default", default=False)
    country_id = fields.Char("Country")
    state_id = fields.Char("State")