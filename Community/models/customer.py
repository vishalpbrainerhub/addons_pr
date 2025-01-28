from odoo import models, fields, api
from passlib.context import CryptContext

class CustomerPassword(models.Model):
    _name = 'customer.password'
    _description = 'Customer Password'

    partner_id = fields.Many2one('res.partner', string='Customer', required=True, ondelete='cascade')
    password_hash = fields.Char(string='Password Hash', readonly=True)
    
    _pwd_context = CryptContext(schemes=['pbkdf2_sha256'], deprecated='auto')

    def set_password(self, password):
        self.password_hash = self._pwd_context.hash(password)

    def verify_password(self, password):
        return self._pwd_context.verify(password, self.password_hash)
    
    

class CustomerNotification(models.Model):
    _name = 'customer.notification'
    _description = 'Customer Notification'

    partner_id = fields.Many2one('res.partner', string='Customer', required=True, ondelete='cascade')
    onesignal_player_id = fields.Char(string='OneSignal Player ID', required=True)
    
    

    
class NoticationStorage(models.Model):
    _name = 'notification.storage'
    _description = 'Notification Storage'

    message = fields.Text(string='Message', required=True)
    patner_id = fields.Many2one('res.partner', string='Customer', required=True, ondelete='cascade')
    title = fields.Char(string='Title', required=True)
    data = fields.Char(string='Data')
    include_player_ids = fields.Char(string='Include Player IDs', required=True)
    filter = fields.Char(string='Filter')
    read_status = fields.Boolean(string='Read Status', default=False)
    
    
class NotificationStatus(models.Model):
    _name = 'notification.status'
    _description = 'Notification Status'
    
    community = fields.Boolean(string='Community', default=True)
    promo = fields.Boolean(string='Promo', default=True)
    order = fields.Boolean(string='Order', default=True)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, ondelete='cascade')

    