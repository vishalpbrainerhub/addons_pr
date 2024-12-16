# -*- coding: utf-8 -*-
import base64
import csv
import os
from datetime import datetime

from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError

class OrderExportController(http.Controller):
    @http.route('/api/export/orders', type='http', auth='user', methods=['GET'], csrf=False)
    def export_orders(self):
        """
        API endpoint to export orders to CSV
        Accessible at: http://your-odoo-instance/api/export/orders
        
        Parameters:
        - Optional: state (default: ['sent', 'sale', 'done'])
        - Optional: date_from 
        - Optional: date_to
        """
        try:
            # Get optional query parameters
            states = request.params.get('state', 'sent,sale,done').split(',')
            date_from = request.params.get('date_from')
            date_to = request.params.get('date_to')

            # Prepare output directory
            out_dir = '/var/lib/odoo/Out'
            os.makedirs(out_dir, exist_ok=True)

            # Generate unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'orders_export_{timestamp}.csv'
            full_path = os.path.join(out_dir, filename)

            # Prepare domain for search
            domain = [('state', 'in', states)]
            if date_from:
                domain.append(('date_order', '>=', date_from))
            if date_to:
                domain.append(('date_order', '<=', date_to))

            # Search for orders
            SaleOrder = request.env['sale.order'].sudo()
            orders = SaleOrder.search(domain)

            # Prepare CSV file
            fieldnames = [
                'order_number',
                'date_order',
                'partner_name',
                'partner_email',
                'company_name',
                'total_amount',
                'state',
                'product_name',
                'product_quantity',
                'product_price'
            ]

            # Write CSV
            with open(full_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for order in orders:
                    base_row = {
                        'order_number': order.name,
                        'date_order': order.date_order.strftime('%Y-%m-%d %H:%M:%S') if order.date_order else '',
                        'partner_name': order.partner_id.name or '',
                        'partner_email': order.partner_id.email or '',
                        'company_name': order.company_id.name or '',
                        'total_amount': order.amount_total,
                        'state': order.state
                    }

                    # Handle multiple order lines
                    if not order.order_line:
                        # Write order with empty product details if no lines
                        writer.writerow({**base_row, 
                            'product_name': '', 
                            'product_quantity': 0, 
                            'product_price': 0
                        })
                    else:
                        for line in order.order_line:
                            row = base_row.copy()
                            row.update({
                                'product_name': line.product_id.name or '',
                                'product_quantity': line.product_uom_qty,
                                'product_price': line.price_unit
                            })
                            writer.writerow(row)

            # Return success response
            return request.make_response(
                None, 
                headers=[
                    ('Content-Type', 'application/json'),
                    ('X-Filename', filename)
                ],
                data='{{"success": true, "filename": "{}", "path": "{}"}}'.format(filename, full_path)
            )

        except Exception as e:
            # Log the error and return error response
            request.env['ir.logging'].sudo().create({
                'name': 'Order Export API',
                'type': 'server',
                'dbname': request.env.cr.dbname,
                'level': 'ERROR',
                'message': str(e),
                'path': 'OrderExportController.export_orders',
                'func': 'export_orders',
                'line': '0'
            })
            
            return request.make_response(
                None, 
                headers=[('Content-Type', 'application/json')],
                data='{{"success": false, "error": "{}"}}'.format(str(e))
            )