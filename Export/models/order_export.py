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
            out_dir = '/var/lib/odoo/export_data/Out'
            os.makedirs(out_dir, exist_ok=True)
            filename = f'{out_dir}/orders_export.csv'
            

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

            orders = SaleOrder.search([('state', 'in', ['sent', 'sale', 'done'])])

            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for order in orders:
                    base_row = {
                        'order_number': order.id,
                        'date_order': order.date_order.strftime('%Y-%m-%d %H:%M:%S') if order.date_order else '',
                        'partner_id': order.partner_id.id if order.partner_id else '',
                        'company_id': order.company_id.id if order.company_id else '',
                        'partner_invoice_id': order.partner_invoice_id.id if order.partner_invoice_id else '',
                        'partner_shipping_id': order.partner_shipping_id.id if order.partner_shipping_id else '',
                        'pricelist_id': order.pricelist_id.id if order.pricelist_id else ''
                    }

                    for line in order.order_line:
                        row = base_row.copy()
                        row.update({
                            'order_line/product_id': line.product_id.id,
                            'order_line/product_uom_qty': line.product_uom_qty,
                            'order_line/price_unit': line.price_unit
                        })
                        writer.writerow(row)

            _logger.info(f"Order export completed successfully at {datetime.now()}")

        except Exception as e:
            _logger.error(f"Error in order export cron: {str(e)}")