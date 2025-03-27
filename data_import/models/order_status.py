# -*- coding: utf-8 -*-
from odoo import models, fields, api
import csv
import logging
import ast
from contextlib import closing
from odoo.http import request
from .notification_service import CustomerController
import os

_logger = logging.getLogger(__name__)
notification_service = CustomerController()


class DataImporter(models.TransientModel):
    _inherit = 'data.importer'
    _description = 'Data Import Wizard'
    
    # Remove @api.model decorator since this is an instance method
    def import_order_status(self):
        try:
            _logger.info("Starting order status import process...")
            file_path = os.environ.get('ORDER_STATUS_DATA_PATH')
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                records = [row for row in reader if row.get('id')]
                _logger.info(f"Found {len(records)} records in CSV")
                
                for record in records:
                    
                    if record['state'] == 'error':
                        continue
                    
                    order = self.env['sale.order'].search([('id', '=', int(record['mobile_app_order_ref']))], limit=1)
                    partner_id = order.partner_id.id
                    
                    order_status = order.state
                    if order_status == record['state'] and order.sale_notification:
                        _logger.info(f"Order {order.name} already has status {record['state']}")
                        continue
                    
                    # message = ""
                    # if record['state'] == 'sale':
                    #     message = "Il tuo ordine è stato spedito!"
                    # elif record['state'] == 'draft':
                    #     message = "Il tuo ordine è in fase elaborazione."
                    # elif record['state'] == 'cancel':
                    #     message = "Il tuo ordine è stato cancellato."
                    # elif record['state'] == 'invoice':
                    #     message = "La fattura del tuo ordine è stata confermata."
                        
                        
                    message = ""
                    if record['state'] == 'sale':
                        message = f"Your order {order.name} has been shipped!"
                        # Mark that notification for sale status was sent
                        order.write({'sale_notification': True})
                    elif record['state'] == 'draft':
                        message = f"Your order {order.name} is being processed."
                    elif record['state'] == 'cancel':
                        message = f"Your order {order.name} has been canceled."
                    elif record['state'] == 'invoice':
                        message = f"The invoice for your order {order.name} has been confirmed."

                    order.write({'state': record['state']})
                    new_status = record['state']
                    filter_notification = request.env['notification.status'].sudo().search([('partner_id', '=', partner_id)], limit=1)
                    if filter_notification.order:
                        customer = request.env['customer.notification'].sudo().search([('partner_id', '=', partner_id)], limit=1)
                        device_token = customer.onesignal_player_id       
                        if device_token:
                            # Send notification about order status change
                            notification_service.send_onesignal_notification(
                                device_token,
                                message,
                                'Aggiornamento Ordine',
                                {'type': 'order_status_change', 'new_status': new_status}
                            )
                            
                            # Store notification in database
                            request.env['notification.storage'].sudo().create({
                                'message': message,
                                'partner_id': partner_id, 
                                'title': 'Aggiornamento Ordine',
                                'data': {'type': 'order_status_change', 'new_status': new_status},
                                'include_player_ids': device_token,
                                'filter': 'order'
                            })

                            
                    _logger.info(f"Order {order.name} updated to status {record['state']}")
                return True
        except Exception as e:
            _logger.error(f"Error importing order status: {e}")
            return False
    
    # Remove @api.model here too if you want to call it from a button
    def import_all_data(self):
        _logger.info("Starting all data import process...")
        return self.import_order_status()