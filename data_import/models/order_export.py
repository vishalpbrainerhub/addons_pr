import csv
import os
from datetime import datetime
from odoo import models, fields, api
import logging
from odoo.http import request, Response


_logger = logging.getLogger(__name__)

class OrderExportCron(models.Model):
    _name = 'order.export.cron'
    _description = 'Order Export Cron Job'

    def _export_orders(self):
        try:
            out_dir = os.environ.get('EXPORT_OUTPUT_DIR')
            os.makedirs(out_dir, exist_ok=True)
            filename = f'{out_dir}/orders_export.csv'
            
            if not os.access(out_dir, os.W_OK):
                _logger.error(f"No write permission for directory: {out_dir}")
                return False

            # Debug log to confirm the cron job is running
            _logger.info(f"Starting order export job at {datetime.now()}")
    
            # Directly open file in write mode - this overwrites existing file
            SaleOrder = self.env['sale.order'].sudo()
            
            fieldnames = [
                'order_number',
                'date_order',
                'partner_id', 
                'company_id',
                'partner_invoice_id',
                'partner_shipping_id', 
                'pricelist_id',
                'order_line/product_id',
                'order_line/product_uom_qty',
                'order_line/price_unit'
            ]

            # Get confirmed orders - log the domain and count
            domain = [('state', 'in', ['sent', 'sale', 'done'])]
            orders = SaleOrder.search(domain)
            _logger.info(f"Found {len(orders)} orders with domain {domain}")

            # If no orders found, try getting draft orders as a fallback
            if not orders:
                _logger.warning("No confirmed orders found. Checking for draft orders...")
                domain = [('state', '=', 'draft')]
                orders = SaleOrder.search(domain)
                _logger.info(f"Found {len(orders)} draft orders")

            # As a final check, try getting all orders regardless of state
            if not orders:
                _logger.warning("No orders found. Retrieving all orders...")
                orders = SaleOrder.search([])
                _logger.info(f"Found {len(orders)} total orders")

            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                rows_written = 0
                
                for order in orders:
                    # Log each order for debugging
                    _logger.info(f"Processing order ID: {order.id}, state: {order.state}, partner: {order.partner_id.name if order.partner_id else 'None'}")
                    
                    partner_external_id = ''
                    if order.partner_id:
                        # Search for external ID in the external.import model
                        external_import_record = self.env['external.import'].sudo().search([
                            ('partner_id', '=', order.partner_id.id)
                        ], limit=1)
                        
                        if external_import_record:
                            partner_external_id = external_import_record.external_import_id
                            _logger.info(f"Found external import ID {partner_external_id} for partner {order.partner_id.id}")
                        else:
                            partner_external_id = order.partner_id.id
                            _logger.warning(f"External import ID not found for partner {order.partner_id.id}")

                    # Then update the base_row dictionary to include partner_external_id
                    pricelist_dict = self.env['product.pricelist'].sudo().search([('id', '=', order.pricelist_id.id)], limit=1)
                    external_pricelist_id = pricelist_dict.external_id
                    base_row = {
                        'order_number': order.id,
                        'date_order': order.date_order.strftime('%Y-%m-%d %H:%M:%S') if order.date_order else '',
                        'partner_id': partner_external_id,  # Use the external ID instead of internal ID
                        'company_id': order.company_id.id if order.company_id else '',
                        'partner_invoice_id': order.partner_invoice_id.id if order.partner_invoice_id else '',
                        'partner_shipping_id': order.partner_shipping_id.id if order.partner_shipping_id else '',
                        # 'pricelist_id': order.pricelist_id.id if order.pricelist_id else ''
                        'pricelist_id': external_pricelist_id

                    }
                    # Log order lines
                    _logger.info(f"Order {order.id} has {len(order.order_line)} order lines")
                    
                    if not order.order_line:
                        # Export the order even if it has no lines
                        writer.writerow(base_row)
                        rows_written += 1
                        continue

                    for line in order.order_line:
                        try:
                            row = base_row.copy()
                            
                            try:
                                
                                product_product = self.env['product.product'].sudo().search([('id', '=', line.product_id.id)], limit=1)
                                product_template = self.env['product.template'].sudo().search([('id', '=', product_product.product_tmpl_id.id)], limit=1)
                                product_external_id = product_template.external_id if hasattr(product_template, 'external_id') else line.product_id.id
                            except Exception as e:
                                product_external_id = line.product_id.id
                                
                            row.update({
                                # 'order_line/product_id': line.product_id.id if line.product_id else '',
                                'order_line/product_id': product_external_id,
                                'order_line/product_uom_qty': line.product_uom_qty,
                                'order_line/price_unit': line.price_unit
                            })
                            writer.writerow(row)
                            rows_written += 1
                        except Exception as line_error:
                            _logger.error(f"Error processing order line {line.id} for order {order.id}: {str(line_error)}")

                _logger.info(f"Wrote {rows_written} rows to {filename}")

            # Verify the file was created and has content
            if os.path.exists(filename):
                file_size = os.path.getsize(filename)
                _logger.info(f"Export file created: {filename}, size: {file_size} bytes")
                if file_size <= len(','.join(fieldnames)) + 2:  # Header only
                    _logger.warning("File contains only headers, no data was written")
            else:
                _logger.error(f"Failed to create export file at {filename}")

            return True

        except Exception as e:
            _logger.error(f"Error in order export cron: {str(e)}")
            import traceback
            _logger.error(traceback.format_exc())
            return False
            
    @api.model
    def run_export(self):
        """Method that can be called from cron job or manually"""
        _logger.info("Manual export triggered")
        return self._export_orders()