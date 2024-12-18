from contextlib import contextmanager
from odoo import api, models, fields
import csv
import logging
import os
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ProductImport(models.Model):
    _name = 'product.import'
    _description = 'Product Import Model'

    name = fields.Char(string='Import Name')
    last_import_date = fields.Datetime(string='Last Import Date')
    import_count = fields.Integer(string='Import Count', default=0)

    @contextmanager
    def _get_new_env(self):
        with api.Environment.manage():
            with self.pool.cursor() as new_cr:
                yield api.Environment(new_cr, self.env.uid, self.env.context)

    def _validate_csv_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.reader(file, delimiter=',', quotechar='"')
                header = next(reader)
                required_columns = {'id', 'name', 'categ_id', 'sale_ok', 'purchase_ok'}
                found_columns = {col.lower().strip() for col in header}
                missing_columns = required_columns - found_columns
                
                if missing_columns:
                    raise UserError(f"Missing columns: {', '.join(missing_columns)}")
                    
                return {col.lower().strip(): idx for idx, col in enumerate(header)}
        except Exception as e:
            raise UserError(f"CSV validation error: {str(e)}")

    def _process_batch(self, rows, column_mapping, env):
        success_count = 0
        errors = []
        
        for row in rows:
            try:
                if len(row) < len(column_mapping):
                    continue

                product_id = int(row[column_mapping['id']])
                product_vals = {
                    'id': product_id,
                    'name': row[column_mapping['name']],
                    'categ_id': self._create_category_hierarchy(env, row[column_mapping['categ_id']]),
                    'sale_ok': row[column_mapping['sale_ok']].lower() == 'true',
                    'purchase_ok': row[column_mapping['purchase_ok']].lower() == 'true',
                    'active': True,
                }

                existing_product = env['product.template'].search([('id', '=', product_id)])
                if existing_product:
                    existing_product.write(product_vals)
                else:
                    env['product.template'].create(product_vals)
                
                success_count += 1
                _logger.info(f"Imported product ID: {product_id}")

            except Exception as e:
                errors.append(f"Error processing product {row[column_mapping['id']]}: {str(e)}")
                continue
                
        return success_count, errors

    def _parse_category(self, categ_string):
        try:
            categ_id, path = eval(categ_string)
            return categ_id, path.split(' / ')[1:]
        except Exception as e:
            raise UserError(f"Invalid category format: {categ_string}")

    def _create_category_hierarchy(self, env, categ_string):
        categ_id, path_parts = self._parse_category(categ_string)
        try:
            existing_category = env['product.category'].browse(categ_id)
            if existing_category.exists():
                return categ_id

            parent_id = 1
            for name in path_parts:
                category = env['product.category'].search([
                    ('name', '=', name),
                    ('parent_id', '=', parent_id)
                ], limit=1)
                
                if category:
                    parent_id = category.id
                else:
                    new_category = env['product.category'].create({
                        'name': name,
                        'parent_id': parent_id,
                    })
                    parent_id = new_category.id
            
            return parent_id
        except Exception as e:
            _logger.error(f"Error creating category: {str(e)}")
            return False

    def import_products(self):
        # file path
        file_path = ''
        if not os.path.exists(file_path):
            raise UserError("Import file not found")

        try:
            column_mapping = self._validate_csv_file(file_path)
            total_success = 0
            all_errors = []
            
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.reader(file, delimiter=',', quotechar='"')
                next(reader)  # Skip header
                current_batch = []
                
                for row in reader:
                    current_batch.append(row)
                    if len(current_batch) >= 10:
                        with self._get_new_env() as new_env:
                            success, errors = self._process_batch(current_batch, column_mapping, new_env)
                            total_success += success
                            all_errors.extend(errors)
                            new_env.cr.commit()
                        current_batch = []

                if current_batch:
                    with self._get_new_env() as new_env:
                        success, errors = self._process_batch(current_batch, column_mapping, new_env)
                        total_success += success
                        all_errors.extend(errors)
                        new_env.cr.commit()

            self.write({
                'last_import_date': fields.Datetime.now(),
                'import_count': total_success
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Import Complete',
                    'message': f"Imported {total_success} products" + 
                              (f" with {len(all_errors)} errors" if all_errors else ""),
                    'type': 'warning' if all_errors else 'success',
                    'sticky': bool(all_errors)
                }
            }
            
        except Exception as e:
            raise UserError(str(e))
        
    @api.model
    def _run_import_cron(self):
        import_record = self.search([], limit=1) or self.create({'name': 'Auto Import'})
        return import_record.import_products()