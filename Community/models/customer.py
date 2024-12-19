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