from odoo import models, fields

class Like(models.Model):
    _name = 'social_media.like'
    _description = 'Like'

    post_id = fields.Many2one('social_media.post', string='Post', ondelete='cascade')
    timestamp = fields.Datetime("Timestamp", default=lambda self: fields.Datetime.now())
    partner_id = fields.Many2one('res.partner', string='Customer', required=True,
                                domain=[('customer_rank', '>', 0)])  # Only customers can like

    _sql_constraints = [
        ('unique_like', 'unique(post_id, partner_id)', 
         'A customer can only like a post once!')
    ]