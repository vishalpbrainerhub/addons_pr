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
        """Enhanced product search method using external_import_id"""
        try:
            # Try to convert to integer for external_import_id search
            external_id = int(product_tmpl_id)
            
            # Search by external_import_id first
            product = env['product.template'].search([
                ('external_import_id', '=', external_id)
            ], limit=1)
            
            if product:
                return product
                
            # Fallback to other search methods if not found
            product = env['product.template'].search([
                '|',
                ('code_', '=', str(product_tmpl_id)),
                ('name', '=', str(product_tmpl_id))
            ], limit=1)
            
            return product
            
        except ValueError:
            # If product_tmpl_id is not an integer, search by code or name
            return env['product.template'].search([
                '|',
                ('code_', '=', str(product_tmpl_id)),
                ('name', '=', str(product_tmpl_id))
            ], limit=1)
    
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

                # Use enhanced product search with external_import_id
                product = self._find_product(env, product_tmpl_id)
                if not product:
                    _logger.warning(f"Product with external ID/code/name {product_tmpl_id} not found, skipping")
                    skipped_count += 1
                    continue

                # Create or get pricelist
                pricelist_id = self._create_pricelist(env, {
                    'id': int(row['id']),
                    'name': row['name'],
                    'discount_policy': row['discount_policy']
                })

                # Determine compute_price based on fixed_price field value
                compute_price = 'fixed'
                if row.get('item_idsfixed_price') == 'percentage':
                    compute_price = 'percentage'

                # Parse dates
                date_start = None
                date_end = None
                if row.get('item_idsdate_end'):
                    try:
                        date_end = datetime.strptime(row['item_idsdate_end'], '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        _logger.warning(f"Invalid date_end format: {row['item_idsdate_end']}")

                # Get minimum quantity
                min_quantity = 1.0
                if row.get('item_idsmin_quantity'):
                    try:
                        min_quantity = float(row['item_idsmin_quantity'])
                    except (ValueError, TypeError):
                        _logger.warning(f"Invalid min_quantity: {row['item_idsmin_quantity']}, using default 1.0")

                # Prepare item values
                item_vals = {
                    'pricelist_id': pricelist_id,
                    'product_tmpl_id': product.id,
                    'base': 'list_price',
                    'applied_on': '1_product',
                    'compute_price': compute_price,
                    'min_quantity': min_quantity
                }

                # Add price values based on compute_price type
                if compute_price == 'percentage':
                    # Get percentage from discount1 field
                    if row.get('item_idsdiscount1'):
                        try:
                            item_vals['percent_price'] = -float(row['item_idsdiscount1'])  # Negative because discount
                        except (ValueError, TypeError):
                            _logger.warning(f"Invalid discount percentage: {row['item_idsdiscount1']}")
                            continue
                else:  # fixed
                    if row.get('item_idspercent_price'):
                        try:
                            item_vals['fixed_price'] = float(row['item_idspercent_price'])
                        except (ValueError, TypeError):
                            _logger.warning(f"Invalid fixed price: {row['item_idspercent_price']}")
                            continue

                # Add dates if they exist
                if date_end:
                    item_vals['date_end'] = date_end

                _logger.info(f"Final item values: {item_vals}")
                pricelist_items.append(item_vals)
                
            except Exception as e:
                _logger.error(f"Error processing pricelist item: {str(e)}, Row: {row}")
                skipped_count += 1
                continue

        if pricelist_items:
            try:
                env['product.pricelist.item'].create(pricelist_items)
                _logger.info(f"Successfully created {len(pricelist_items)} pricelist items")
            except Exception as e:
                _logger.error(f"Error creating pricelist items: {str(e)}")
                raise
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