from odoo import models, fields, api

class RewardsPoints(models.Model):
    _name = 'rewards.points'
    _description = 'Rewards Points'

    user_id = fields.Many2one('res.partner', string='User', required=True)
    order_id = fields.Many2one('sale.order', string='Order', required=False)
    points = fields.Integer(string='Points', required=True)
    date = fields.Datetime(string='Date', required=True, default=fields.Datetime.now)
    status = fields.Selection([
        ('gain', 'Gain'),
        ('redeem', 'Redeem'),
    ], string='Status', required=True, default='gain')
    catalog_id = fields.Many2one('rewards.catalog', string='Catalog',required=False)
        

class RewardsCatalog(models.Model):
    _name = 'rewards.catalog'
    _description = 'Rewards Catalog'
    
    title = fields.Char(string='Title', required=True)
    description = fields.Text(string='Description')
    points = fields.Integer(string='Points', required=True)
    image = fields.Binary(string='Image', required=True)


class TotalPoints(models.Model):
    _name = 'rewards.totalpoints'
    _description = 'Total Points'

    total_points = fields.Integer(string='Total Points', required=True, default=0)
    user_id = fields.Many2one('res.partner', string='User', required=True)