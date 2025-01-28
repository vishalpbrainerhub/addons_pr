from contextlib import contextmanager
from odoo import api, models, fields
import csv
import logging
import os
from odoo.exceptions import UserError
import re
import random

_logger = logging.getLogger(__name__)

class ProductImport(models.Model):
    _name = 'product.import'
    _description = 'Product Import'

    name = fields.Char(string='Import Name')
    last_import_date = fields.Datetime()
    import_count = fields.Integer(default=0)
    skipped_count = fields.Integer(default=0)

    @contextmanager
    def _get_new_env(self):
        with self.pool.cursor() as new_cr:
            yield api.Environment(new_cr, self.env.uid, self.env.context)

    def _validate_code(self, code):
        """Validate the 13-digit code format"""
        if not code:
            return False
        return bool(re.match(r'^\d{13}$', str(code)))

    def _get_category_id(self, env, category_name):
        """Get category ID from name, create if doesn't exist"""
        if not category_name:
            return 1  # Default to "All" category
            
        # Split category path (e.g., "Electronics/Computers")
        category_path = [cat.strip() for cat in category_name.split('/')]
        
        parent_id = 1  # Start from root category
        category_id = parent_id
        
        for category in category_path:
            if not category:
                continue
                
            domain = [('name', '=', category), ('parent_id', '=', parent_id)]
            category_obj = env['product.category'].search(domain, limit=1)
            
            if not category_obj:
                # Create new category
                category_obj = env['product.category'].create({
                    'name': category,
                    'parent_id': parent_id
                })
                _logger.info(f"Created new product category: {category}")
                
            category_id = category_obj.id
            parent_id = category_id
            
        return category_id

    def _check_existing_product(self, env, external_import_id):
        """Check if product exists based on external_import_id"""
        if external_import_id:
            return env['product.template'].search([
                ('external_import_id', '=', external_import_id)
            ], limit=1)
        return False

    def _process_batch(self, env, batch):
        products_to_create = []
        created_count = 0
        skipped_count = 0
        
        for row in batch:
            try:
                # Convert external_import_id to integer
                external_import_id = False
                if row.get('id'):
                    try:
                        external_import_id = int(row['id'])
                    except (ValueError, TypeError):
                        _logger.error(f"Invalid external_import_id format for product {row.get('name')}: {row.get('id')}")
                        continue

                # Validate code_ format
                if 'code_' in row and not self._validate_code(row['code_']):
                    _logger.error(f"Invalid code_ format for product {row.get('name')}: {row.get('code_')}")
                    continue

                # Get category ID from category name
                category_id = self._get_category_id(env, row.get('category'))

                # Prepare product values
                code_id_value = random.randint(1000000000000, 9999999999999)
                product_vals = {
                    'name': row.get('name'),
                    'code_': row.get('code_', code_id_value),
                    'list_price': float(row.get('list_price', 0.0)),
                    'sale_ok': str(row.get('sale_ok', 'true')).lower() == 'true',
                    'purchase_ok': str(row.get('purchase_ok', 'true')).lower() == 'true',
                    'categ_id': category_id,
                    'active': True,
                    'external_import_id': external_import_id
                }

                # Handle image if present
                if row.get('image_1920'):
                    product_vals['image_1920'] = row['image_1920']

                # Add optional fields if present
                optional_fields = ['standard_price', 'weight', 'volume', 'description', 'description_sale']
                for field in optional_fields:
                    if row.get(field):
                        if field in ['standard_price', 'weight', 'volume']:
                            product_vals[field] = float(row[field])
                        else:
                            product_vals[field] = row[field]

                # Check if product exists based on external_import_id
                existing_product = self._check_existing_product(env, external_import_id)
                
                if existing_product:
                    _logger.info(f"Updating existing product: {product_vals.get('name')} "
                               f"(ID: {existing_product.id}, External ID: {external_import_id})")
                    existing_product.write(product_vals)
                    skipped_count += 1
                else:
                    products_to_create.append(product_vals)
                
            except Exception as e:
                _logger.error(f"Error processing product row {row}: {str(e)}")
                continue

        if products_to_create:
            try:
                env['product.template'].with_context(tracking_disable=True).create(products_to_create)
                created_count = len(products_to_create)
            except Exception as e:
                _logger.error(f"Error creating products: {str(e)}")
                raise UserError(f"Error creating products: {str(e)}")

        return created_count, skipped_count

    def import_products(self):
        file_path = os.environ["PRODUCT_DATA_PATH"]
        if not os.path.exists(file_path):
            raise UserError(f"Product import file not found at {file_path}")

        total_created = 0
        total_skipped = 0
        batch_size = 100

        try:
            with open(file_path, 'r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                batch = []
                
                for row in reader:
                    batch.append(row)
                    if len(batch) >= batch_size:
                        with self._get_new_env() as new_env:
                            created, skipped = self._process_batch(new_env, batch)
                            total_created += created
                            total_skipped += skipped
                            new_env.cr.commit()
                        batch = []

                if batch:
                    with self._get_new_env() as new_env:
                        created, skipped = self._process_batch(new_env, batch)
                        total_created += created
                        total_skipped += skipped
                        new_env.cr.commit()

            self.write({
                'last_import_date': fields.Datetime.now(),
                'import_count': total_created,
                'skipped_count': total_skipped
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Product Import Complete',
                    'message': f"Successfully imported {total_created} products. "
                              f"Updated {total_skipped} existing products.",
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(f"Import failed: {str(e)}")

    @api.model
    def _run_import_cron(self):
        import_record = self.search([], limit=1) or self.create({'name': 'Auto Import Products'})
        return import_record.import_products()