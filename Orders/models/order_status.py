from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _send_status_email(self, old_state, new_state):
        try:
            template = self.env['mail.template'].sudo().create({
                'name': f'Order Status Change: {new_state}',
                'email_from': 'admin@primapaint.com',
                'email_to': '${object.partner_id.email}',
                'subject': 'Order ${object.name} Status Update',
                'body_html': f'''
                    <p>Dear ${{object.partner_id.name}},</p>
                    <p>Your order ${{object.name}} status has been updated from {old_state} to {new_state}.</p>
                    <p>Order Details:</p>
                    <ul>
                        <li>Order Total: ${{format_amount(object.amount_total)}}</li>
                        <li>Order Date: ${{object.date_order.strftime('%Y-%m-%d')}}</li>
                    </ul>
                ''',
                'model_id': self.env['ir.model']._get('sale.order').id,
                'auto_delete': True
            })
            template.send_mail(self.id, force_send=True)
        except Exception as e:
            _logger.error(f'Error sending status change email: {str(e)}')

    def write(self, vals):
        if 'state' in vals:
            old_state = self.state
            new_state = vals['state']
            res = super().write(vals)
            self._send_status_email(old_state, new_state)
            return res
        return super().write(vals)