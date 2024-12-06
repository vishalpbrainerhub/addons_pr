from odoo import models, fields

class comment_like(models.Model):
    _name = 'social_media.comment_like'
    _description = 'Comment Like'


    comment_id = fields.Many2one('social_media.comment', string='Comment', ondelete='cascade')
    timestamp = fields.Datetime("Timestamp", default=lambda self: fields.Datetime.now())
    user_id = fields.Many2one('res.users', string='User', required=True)
    

class comment_report(models.Model):
    _name = 'social_media.comment_report'
    _description = 'Reported Comment'

    comment_id = fields.Many2one('social_media.comment', string='Comment', ondelete='cascade')
    user_id = fields.Many2one('res.users', string='User', required=True)
    timestamp = fields.Datetime("Timestamp", default=lambda self: fields.Datetime.now())


    