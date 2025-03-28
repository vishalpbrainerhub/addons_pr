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
            _logger.warning(f"Using file path: {file_path}")
            
            notification_service = CustomerController()
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                records = [row for row in reader if row.get('id')]
                _logger.info(f"Found {len(records)} records in CSV")
                
                for record in records:
                    _logger.warning(f"Processing record ID: {record.get('id')} with state: {record.get('state')}")
                    
                    if record['state'] == 'error':
                        _logger.warning(f"Skipping record with ID {record.get('id')} due to error state")
                        continue
                    
                    
                    order = self.env['sale.order'].search([('id', '=', int(record['mobile_app_order_ref']))], limit=1)
                    if not order:
                        _logger.warning(f"Order with reference {record['mobile_app_order_ref']} not found")
                        continue
                    
                    partner_id = order.partner_id.id
                    _logger.warning(f"Found partner ID: {partner_id} for order {order.name}")
                    
                    order_status = order.state
                    _logger.warning(f'Checking for {order.name} and current state is {order.state} and csv state is {order_status} and sale flag is {order.sale_notification}')
                    
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
                    filter_notification = self.env['notification.status'].sudo().search([('partner_id', '=', partner_id)], limit=1)
                    _logger.warning(f"Notification filter status for partner {partner_id}: {filter_notification and 'Found' or 'Not Found'}")
                    if filter_notification:
                        _logger.warning(f"Order notifications enabled for partner {partner_id}: {filter_notification.order}")
                    
                    if filter_notification.order:
                        customer = self.env['customer.notification'].sudo().search([('partner_id', '=', partner_id)], limit=1)
                        _logger.warning(f"Customer notification record for partner {partner_id}: {customer and 'Found' or 'Not Found'}")
                        
                        device_token = customer.onesignal_player_id
                        _logger.warning(f"Device token for partner {partner_id}: {device_token or 'None'}")
                             
                        if device_token:
                            # Send notification about order status change
                            _logger.warning(f"Attempting to send notification to {device_token} for order {order.name}")
                            try:
                                notification_service.send_onesignal_notification(
                                    device_token,
                                    message,
                                    'Aggiornamento Ordine',
                                    {'type': 'order_status_change', 'new_status': new_status}
                                )
                                _logger.warning(f"Notification sent successfully to {device_token} for order {order.name}")
                            except Exception as notification_error:
                                _logger.warning(f"Failed to send notification: {notification_error}")
                            
                            # Store notification in database
                            try:
                                self.env['notification.storage'].sudo().create({
                                    'message': message,
                                    'patner_id': partner_id, 
                                    'title': 'Aggiornamento Ordine',
                                    'data': {'type': 'order_status_change', 'new_status': new_status},
                                    'include_player_ids': device_token,
                                    'filter': 'order'
                                })
                                _logger.warning(f"Notification stored in database for partner {partner_id}")
                            except Exception as storage_error:
                                _logger.warning(f"Failed to store notification: {storage_error}")

                            
                    _logger.warning(f"Order {order.name} updated to status {record['state']}")
                return True
        except Exception as e:
            _logger.error(f"Error importing order status: {e}")
            return False
    
    # Remove @api.model here too if you want to call it from a button
    def import_all_data(self):
        _logger.info("Starting all data import process...")
        return self.import_order_status()