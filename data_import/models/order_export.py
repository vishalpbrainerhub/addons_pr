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
            # Handle environment variable safely with fallback
            out_dir = os.environ.get("EXPORT_OUTPUT_DIR", "/tmp/odoo_exports")
            os.makedirs(out_dir, exist_ok=True)
            
            # Add timestamp to filename to prevent overwriting previous exports
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'{out_dir}/orders_export_{timestamp}.csv'
            
            # Get SaleOrder model with sudo permissions
            SaleOrder = self.env['sale.order'].sudo()
            
            # Define CSV fields - keeping original fields and adding useful ones
            fieldnames = [
                'order_number',
                'date_order',
                'partner_id', 
                'partner_name',  # Added partner name for readability
                'company_id',
                'partner_invoice_id',
                'partner_shipping_id', 
                'pricelist_id',
                'order_state',  # Added order state
                'order_line/product_id',
                'order_line/product_code',  # Added product code
                'order_line/product_name',  # Added product name
                'order_line/product_uom_qty',
                'order_line/price_unit',
                'order_line/price_subtotal'  # Added line subtotal
            ]

            # Get orders in confirmed states
            orders = SaleOrder.search([('state', 'in', ['sent', 'sale', 'done'])])

            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for order in orders:
                    base_row = {
                        'order_number': order.id,
                        'date_order': order.date_order.strftime('%Y-%m-%d %H:%M:%S') if order.date_order else '',
                        'partner_id': order.partner_id.id if order.partner_id else '',
                        'partner_name': order.partner_id.name if order.partner_id else '',
                        'company_id': order.company_id.id if order.company_id else '',
                        'partner_invoice_id': order.partner_invoice_id.id if order.partner_invoice_id else '',
                        'partner_shipping_id': order.partner_shipping_id.id if order.partner_shipping_id else '',
                        'pricelist_id': order.pricelist_id.id if order.pricelist_id else '',
                        'order_state': order.state,
                    }

                    # If order has no lines, still write the base order info
                    if not order.order_line:
                        writer.writerow(base_row)
                        continue

                    for line in order.order_line:
                        row = base_row.copy()
                        row.update({
                            'order_line/product_id': line.product_id.id if line.product_id else '',
                            'order_line/product_code': line.product_id.default_code if line.product_id and line.product_id.default_code else '',
                            'order_line/product_name': line.product_id.name if line.product_id else line.name,
                            'order_line/product_uom_qty': line.product_uom_qty,
                            'order_line/price_unit': line.price_unit,
                            'order_line/price_subtotal': line.price_subtotal
                        })
                        writer.writerow(row)

            _logger.info(f"Order export completed successfully at {datetime.now()}. File created: {filename}")
            return True

        except Exception as e:
            _logger.error(f"Error in order export cron: {str(e)}")
            return False
            
    @api.model
    def run_export(self):
        """
        Method that can be called from cron job or manually
        """
        return self._export_orders()