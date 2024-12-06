from odoo import models, fields

class Like(models.Model):
    _name = 'social_media.like'
    _description = 'Like'

    post_id = fields.Many2one('social_media.post', string='Post', ondelete='cascade')
    timestamp = fields.Datetime("Timestamp", default=lambda self: fields.Datetime.now())
    user_id = fields.Many2one('res.users', string='User', required=True)