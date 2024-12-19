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
    skipped_count = fields.Integer(default=0)

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
            'currency_id': env.ref('base.EUR').id,
            'active': True
        }
        return env['product.pricelist'].create(vals).id

    def _check_existing_pricelist_item(self, env, pricelist_id, product_tmpl_id, date_start, date_end):
        domain = [
            ('pricelist_id', '=', pricelist_id),
            ('product_tmpl_id', '=', product_tmpl_id),
        ]
        
        if date_start:
            domain.append(('date_start', '=', date_start))
        if date_end:
            domain.append(('date_end', '=', date_end))
            
        return env['product.pricelist.item'].search(domain, limit=1)

    def _find_product(self, env, product_tmpl_id):
        """Enhanced product search method"""
        # Try direct ID search first
        product = env['product.template'].browse(int(product_tmpl_id))
        if product.exists():
            return product

        # If direct search fails, try searching with various fields
        product = env['product.template'].search([
            '|',
            ('id', '=', int(product_tmpl_id)),
            '|',
            ('default_code', '=', str(product_tmpl_id)),
            ('name', '=', str(product_tmpl_id))
        ], limit=1)

        return product

    def _process_batch(self, env, batch):
        pricelist_items = []
        skipped_count = 0
        
        for row in batch:
            try:
                # Verify product exists first
                product_tmpl_id = row.get('item_idsproduct_tmpl_id')
                if not product_tmpl_id:
                    _logger.warning(f"No product template ID specified, skipping row")
                    skipped_count += 1
                    continue

                # Use enhanced product search
                product = self._find_product(env, product_tmpl_id)
                if not product:
                    _logger.warning(f"Product template {product_tmpl_id} not found, skipping")
                    skipped_count += 1
                    continue

                # Create or get pricelist
                pricelist_id = self._create_pricelist(env, {
                    'id': int(row['id']),
                    'name': row['name'],
                    'discount_policy': row['discount_policy']
                })

                # Parse dates
                date_start = None
                date_end = None
                if row.get('item_idsdate_start'):
                    date_start = datetime.strptime(row['item_idsdate_start'], '%Y-%m-%d %H:%M:%S')
                if row.get('item_idsdate_end'):
                    date_end = datetime.strptime(row['item_idsdate_end'], '%Y-%m-%d %H:%M:%S')

                # Check for existing pricelist item
                existing_item = self._check_existing_pricelist_item(
                    env, pricelist_id, product.id, date_start, date_end
                )
                
                if existing_item:
                    _logger.info(f"Pricelist item already exists for product {product.name} (ID: {product.id}), skipping")
                    skipped_count += 1
                    continue

                # Prepare item values
                item_vals = {
                    'pricelist_id': pricelist_id,
                    'product_tmpl_id': product.id,
                    'base': 'list_price',
                    'applied_on': '0_product_variant',
                    'compute_price': row['item_idscompute_price'].lower(),
                }
                
                if row.get('item_idsmin_quantity'):
                    item_vals['min_quantity'] = float(row['item_idsmin_quantity'])
                    
                if row['item_idscompute_price'] == 'percentage':
                    if row.get('item_idspercent_price'):
                        item_vals['percent_price'] = float(row['item_idspercent_price'])
                elif row['item_idscompute_price'] == 'fixed':
                    if row.get('item_idsfixed_price'):
                        item_vals['fixed_price'] = float(row['item_idsfixed_price'])

                if date_start:
                    item_vals['date_start'] = date_start
                if date_end:
                    item_vals['date_end'] = date_end

                pricelist_items.append(item_vals)
                _logger.info(f"Successfully prepared pricelist item for product {product.name} (ID: {product.id})")
                
            except Exception as e:
                _logger.error(f"Error processing pricelist item: {str(e)}, Row: {row}")
                skipped_count += 1
                continue

        if pricelist_items:
            env['product.pricelist.item'].create(pricelist_items)
            _logger.info(f"Successfully created {len(pricelist_items)} pricelist items")
        return len(pricelist_items), skipped_count

    def import_pricelists(self):
        file_path = '/var/lib/odoo/export_data/In/pricelist_data.csv'
        if not os.path.exists(file_path):
            raise UserError("Pricelist import file not found")

        total_success = 0
        total_skipped = 0
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                batch = []
                
                for row in reader:
                    batch.append(row)
                    if len(batch) >= 5:
                        with self._get_new_env() as new_env:
                            success, skipped = self._process_batch(new_env, batch)
                            total_success += success
                            total_skipped += skipped
                            new_env.cr.commit()
                        batch = []

                if batch:
                    with self._get_new_env() as new_env:
                        success, skipped = self._process_batch(new_env, batch)
                        total_success += success
                        total_skipped += skipped
                        new_env.cr.commit()

            self.write({
                'last_import_date': fields.Datetime.now(),
                'import_count': total_success,
                'skipped_count': total_skipped
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Pricelist Import Complete',
                    'message': f"Successfully imported {total_success} pricelist items, skipped {total_skipped} items",
                    'type': 'success'
                }
            }
        except Exception as e:
            raise UserError(str(e))

    @api.model
    def _run_import_cron(self):
        import_record = self.search([], limit=1) or self.create({'name': 'Auto Import Pricelists'})
        return import_record.import_pricelists()