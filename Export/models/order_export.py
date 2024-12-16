import csv
import os
from datetime import datetime
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class OrderExportCron(models.Model):
    _name = 'order.export.cron'
    _description = 'Order Export Cron Job'

    def _export_orders(self):
        try:
            # Create OUT directory if it doesn't exist
            os.makedirs('OUT', exist_ok=True)

            # Use a fixed filename for orders export
            filename = 'OUT/orders_export.csv'

            # Get sale order model
            SaleOrder = self.env['sale.order'].sudo()
            
            # Define fields to export matching the API structure
            fieldnames = [
                'id',
                'name',
                'state',
                'taxable_amount',
                'date_order',
                'partner_id',
                'partner_name',
                'partner_email',
                'partner_phone',
                'partner_address',
                'vat_1_percentage',
                'vat_2_percentage',
                'shipping_charge',
                'vat_1_value',
                'vat_2_value',
                'total_amount',
                'reward_points',
                'product_id',
                'product_name',
                'product_quantity',
                'product_price',
                'product_code'
            ]

            # Get all orders
            orders = SaleOrder.search([('state', 'in', ['sent', 'sale', 'done'])])

            # Write to CSV
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Write headers
                writer.writeheader()
                
                # Write order data
                for order in orders:
                    # Get shipping address
                    user_address = self.env['social_media.custom_address'].sudo().search([
                        ('id', '=', order.shipping_address_id)
                    ])

                    shipping_address = f'{user_address.address}, {user_address.continued_address}, {user_address.city}, {user_address.postal_code}, {user_address.village}, {user_address.state_id.name}, {user_address.country_id.name}' if user_address else None

                    # Get reward points
                    order_reward_points = self.env['rewards.points'].sudo().search([('order_id', '=', order.id)]).points

                    # Base order information
                    base_row = {
                        'id': order.id,
                        'name': order.name or '',
                        'state': order.state or '',
                        'taxable_amount': order.amount_total,
                        'date_order': order.date_order.strftime('%Y-%m-%d %H:%M:%S') if order.date_order else '',
                        'partner_id': order.partner_id.id if order.partner_id else '',
                        'partner_name': order.partner_id.name if order.partner_id else '',
                        'partner_email': order.partner_id.email if order.partner_id else '',
                        'partner_phone': order.partner_id.phone if order.partner_id else '',
                        'partner_address': shipping_address or '',
                        'vat_1_percentage': 0,
                        'vat_2_percentage': 0,
                        'shipping_charge': 0,
                        'vat_1_value': 0,
                        'vat_2_value': 0,
                        'total_amount': order.amount_total + 0,
                        'reward_points': order_reward_points or 0,
                    }

                    # Create a row for each product in the order
                    for line in order.order_line:
                        row = base_row.copy()
                        discount = self.env['product.template'].sudo().search([('id', '=', line.product_id.id)]).discount
                        
                        # Add product specific information
                        row.update({
                            'product_id': line.product_id.id,
                            'product_name': line.product_id.name,
                            'product_quantity': line.product_uom_qty,
                            'product_price': line.price_unit,
                            'product_code': line.product_id.code_ or ''
                        })
                        
                        writer.writerow(row)

            _logger.info(f"Order export completed successfully at {datetime.now()}")

        except Exception as e:
            _logger.error(f"Error in order export cron: {str(e)}")