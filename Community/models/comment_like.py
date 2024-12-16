from odoo import models, fields

class CommentLike(models.Model):
    _name = 'social_media.comment_like'
    _description = 'Comment Like'

    comment_id = fields.Many2one('social_media.comment', string='Comment', ondelete='cascade')
    timestamp = fields.Datetime("Timestamp", default=lambda self: fields.Datetime.now())
    partner_id = fields.Many2one('res.partner', string='Customer', 
                                required=True,
                                domain=[('customer_rank', '>', 0)])
    
    _sql_constraints = [
        ('unique_comment_like', 'unique(comment_id, partner_id)', 
         'A customer can only like a comment once!')
    ]

class CommentReport(models.Model):
    _name = 'social_media.comment_report'
    _description = 'Reported Comment'

    comment_id = fields.Many2one('social_media.comment', string='Comment', ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Customer', 
                                required=True,
                                domain=[('customer_rank', '>', 0)])
    timestamp = fields.Datetime("Timestamp", default=lambda self: fields.Datetime.now())

    _sql_constraints = [
        ('unique_comment_report', 'unique(comment_id, partner_id)', 
         'A customer can only report a comment once!')
    ]