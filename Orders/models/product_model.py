from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    discount = fields.Float(string='Discount', default=0.0)
    rewards_score = fields.Integer(string='Score', default=0)
    code_ = fields.Char(string='Code', required=True)

