from odoo import models, fields, api

class Comment(models.Model):
    _name = 'social_media.comment'
    _description = 'Comment'

    post_id = fields.Many2one('social_media.post', string='Post', ondelete='cascade')
    timestamp = fields.Datetime("Timestamp", default=lambda self: fields.Datetime.now())
    content = fields.Text("Content")
    partner_id = fields.Many2one('res.partner', string='Customer', 
                                required=True,
                                domain=[('customer_rank', '>', 0)])
    comment_likes = fields.One2many('social_media.comment_like', 'comment_id', string="Comment Likes")
    comment_reports = fields.One2many('social_media.comment_report', 'comment_id', string="Comment Reports")

    like_comments_count = fields.Integer("Like Comments Count", compute='_compute_like_comments_count', store=True)
    report_comments_count = fields.Integer("Report Comments Count", compute='_compute_report_comments_count', store=True)

    @api.depends('comment_likes')
    def _compute_like_comments_count(self):
        for record in self:
            record.like_comments_count = len(record.comment_likes)

    @api.depends('comment_reports')
    def _compute_report_comments_count(self):
        for record in self:
            record.report_comments_count = len(record.comment_reports)