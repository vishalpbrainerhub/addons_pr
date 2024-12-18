from contextlib import contextmanager
from odoo import api, models, fields
import csv
import logging
import os
from odoo.exceptions import UserError
from datetime import datetime

_logger = logging.getLogger(__name__)

class PricelistImport(models.Model):
    _name = 'pricelist.import'
    _description = 'Pricelist Import'

    name = fields.Char(string='Import Name')
    last_import_date = fields.Datetime()
    import_count = fields.Integer(default=0)

    @contextmanager
    def _get_new_env(self):
        with self.pool.cursor() as new_cr:
            yield api.Environment(new_cr, self.env.uid, self.env.context)

    def _create_pricelist(self, env, pricelist_data):
        existing_pricelist = env['product.pricelist'].search([('id', '=', pricelist_data['id'])])
        if existing_pricelist:
            return existing_pricelist.id
            
        vals = {
            'id': pricelist_data['id'],
            'name': pricelist_data['name'],
            'discount_policy': pricelist_data['discount_policy'] or 'without_discount',
            'currency_id': env.ref('base.EUR').id,  # Default to EUR, adjust as needed
            'active': True
        }
        return env['product.pricelist'].create(vals).id

    def _process_batch(self, env, batch):
        pricelist_items = []
        
        for row in batch:
            try:
                pricelist_id = self._create_pricelist(env, {
                    'id': int(row['id']),
                    'name': row['name'],
                    'discount_policy': row['discount_policy']
                })
                
                # Verify product template exists
                product_tmpl_id = row.get('item_idsproduct_tmpl_id')
                if product_tmpl_id:
                    product = env['product.template'].search([('id', '=', int(product_tmpl_id))])
                    if not product:
                        _logger.warning(f"Product template {product_tmpl_id} not found, skipping")
                        continue
                
                item_vals = {
                    'pricelist_id': pricelist_id,
                    'base': 'list_price',
                    'applied_on': '0_product_variant',
                    'compute_price': row['item_idsfixed_price'].lower(),
                }
                
                # Only add product_tmpl_id if product exists
                if product_tmpl_id and product:
                    item_vals['product_tmpl_id'] = int(product_tmpl_id)
                
                if row.get('item_idsmin_quantity'):
                    item_vals['min_quantity'] = float(row['item_idsmin_quantity'])
                    
                if row['item_idsfixed_price'] == 'percentage' and row.get('item_idsdiscount1'):
                    item_vals['percent_price'] = float(row['item_idsdiscount1'])
                elif row['item_idsfixed_price'] == 'fixed' and row.get('item_idspercent_price'):
                    item_vals['fixed_price'] = float(row['item_idspercent_price'])
                
                for date_field, csv_field in [('date_start', 'item_idsdate_start'), 
                                            ('date_end', 'item_idsdate_end')]:
                    if row.get(csv_field):
                        item_vals[date_field] = datetime.strptime(row[csv_field], 
                                                                '%Y-%m-%d %H:%M:%S')

                pricelist_items.append(item_vals)
                
            except Exception as e:
                _logger.error(f"Error processing pricelist item: {str(e)}, Row: {row}")
                continue

        if pricelist_items:
            env['product.pricelist.item'].create(pricelist_items)
            return len(pricelist_items)
        return 0

    def import_pricelists(self):
        file_path = '/var/lib/odoo/export_data/In/pricelist_data.csv'
        if not os.path.exists(file_path):
            raise UserError("Pricelist import file not found")

        total_success = 0
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)  # Remove tab delimiter
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
                    'title': 'Pricelist Import Complete',
                    'message': f"Imported {total_success} pricelist items",
                    'type': 'success'
                }
            }
        except Exception as e:
            raise UserError(str(e))

    @api.model
    def _run_import_cron(self):
        import_record = self.search([], limit=1) or self.create({'name': 'Auto Import Pricelists'})
        return import_record.import_pricelists()