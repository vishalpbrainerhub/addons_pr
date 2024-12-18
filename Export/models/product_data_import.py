from contextlib import contextmanager
from odoo import api, models, fields
import csv
import logging
import os
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ProductImport(models.Model):
    _name = 'product.import'
    _description = 'Product Import'

    name = fields.Char(string='Import Name')
    last_import_date = fields.Datetime()
    import_count = fields.Integer(default=0)

    @contextmanager
    def _get_new_env(self):
        with self.pool.cursor() as new_cr:
            yield api.Environment(new_cr, self.env.uid, self.env.context)

    def _process_batch(self, env, batch):
        products = []
        existing_ids = set(env['product.template'].search([]).ids)
        
        for row in batch:
            try:
                product_id = int(row['id'])
                if product_id in existing_ids:
                    _logger.info(f"Skipping existing product ID: {product_id}")
                    continue
                    
                product_vals = {
                    'id': product_id,
                    'name': row['name'],
                    'list_price': float(row['list_price']),
                    'sale_ok': row['sale_ok'].lower() == 'true',
                    'purchase_ok': row['purchase_ok'].lower() == 'true',
                    'active': True
                }
                products.append(product_vals)
            except Exception as e:
                _logger.error(f"Error processing product: {str(e)}")
                continue

        if products:
            env['product.template'].with_context(tracking_disable=True).create(products)
            return len(products)
        return 0

    def import_products(self):
        file_path = '/var/lib/odoo/export_data/In/customer-data.csv'
        if not os.path.exists(file_path):
            raise UserError("Product import file not found")

        total_success = 0
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                batch = []
                
                for row in reader:
                    batch.append(row)
                    if len(batch) >= 5:
                        with self._get_new_env() as new_env:
                            success = self._process_batch(new_env, batch)
                            total_success += success
                            new_env.cr.commit()
                        batch = []

                if batch:
                    with self._get_new_env() as new_env:
                        success = self._process_batch(new_env, batch)
                        total_success += success
                        new_env.cr.commit()

            self.write({
                'last_import_date': fields.Datetime.now(),
                'import_count': total_success
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Product Import Complete',
                    'message': f"Imported {total_success} products",
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(str(e))

    @api.model
    def _run_import_cron(self):
        import_record = self.search([], limit=1) or self.create({'name': 'Auto Import Products'})
        return import_record.import_products()