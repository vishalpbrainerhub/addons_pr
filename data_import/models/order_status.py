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



class DataImporter(models.TransientModel):
    _inherit = 'data.importer'
    _description = 'Data Import Wizard'
    
    # Remove @api.model decorator since this is an instance method
    def import_order_status(self):
        try:
            _logger.info("Starting order status import process...")
            file_path = os.environ.get('ORDER_STATUS_DATA_PATH')
            
            notification_service = CustomerController()
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
                    if order_status == record['state']:
                        # For 'sale' status, also check if notification was already sent
                        if record['state'] == 'sale' and order.sale_notification:
                            _logger.info(f"Order {order.name} already has status {record['state']} and notification was sent")
                            continue
                        # For other statuses, we just check if status hasn't changed
                        elif record['state'] != 'sale':
                            _logger.info(f"Order {order.name} already has status {record['state']}")
                            continue
                    
                    message = ""
                    if record['state'] == 'sale':
                        message = f"Il tuo ordine {order.name} è stato confermato!"
                        # Mark that notification for sale status was sent
                        order.write({'sale_notification': True})
                    elif record['state'] == 'draft':
                        message = f"Il tuo ordine {order.name} è in fase di preventivo."
                    elif record['state'] == 'sent':
                        message = f"Il preventivo per il tuo ordine {order.name} è stato inviato."
                    elif record['state'] == 'done':
                        message = f"Il tuo ordine {order.name} è stato completato e bloccato."
                    elif record['state'] == 'cancel':
                        message = f"Il tuo ordine {order.name} è stato cancellato."
                    else:
                        _logger.warning(f"Unknown state {record['state']} for order {order.name}")
                        continue
                        
                        
                    if record['state'] == 'draft':
                        _logger.info(f"Skipping update for order {order.name} - incoming status is 'draft'")
                        continue

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
                                'patner_id': partner_id, 
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