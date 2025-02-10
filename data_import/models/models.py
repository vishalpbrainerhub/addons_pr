# -*- coding: utf-8 -*-
from odoo import models, fields, api
import csv
import logging
import ast
from contextlib import closing

_logger = logging.getLogger(__name__)

class ProductCategory(models.Model):
    _inherit = 'product.category'
    external_id = fields.Char('External ID', index=True)

class ProductTemplate(models.Model):
    _inherit = 'product.template'
    external_id = fields.Char('External ID', index=True)

class DataImporter(models.TransientModel):
    _name = 'data.importer'
    _description = 'Data Import Wizard'
        
    def _create_or_get_external_id(self, record_id, model, external_id, module='__import__'):
        """Create external ID if it doesn't exist, or get existing one"""
        existing = self.env['ir.model.data'].search([
            ('name', '=', external_id),
            ('model', '=', model),
            ('module', '=', module)
        ], limit=1)
        
        if existing:
            return existing
            
        return self.env['ir.model.data'].create({
            'name': external_id,
            'model': model,
            'module': module,
            'res_id': record_id,
            'noupdate': True
        })
        
    def import_products(self):
        try:
            file_path = '/home/dell/Documents/Projects/PrimaPaint/odoo-15.0/primapaint_addons/data_import/models/product-data.csv'
            
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file, delimiter='\t')
                records = [row for row in reader if row.get('id') and row['id'].strip()]
                total_records = len(records)
                _logger.info(f"Starting import of {total_records} products")
                
                for row in records:
                    try:
                        external_product_id = row.get('id')
                        product_exists = self.env['product.template'].search([
                            ('external_id', '=', external_product_id)
                        ], limit=1)
                        
                        if product_exists:
                            _logger.info(f"Product with ID {external_product_id} already exists. Skipping creation...")
                            continue
                        
                        
                        
                        # Parse category data
                        category = ast.literal_eval(row['categ_id'])
                        category_id, category_name = category if isinstance(category, tuple) else ast.literal_eval(category)
                        category_path = category_name.split(' / ')

                        _logger.info(f"Processing category ID: {category_id}, Name: {category_name}")

                        # Find or create categories
                        parent_id = False
                        final_category = None
                        path_external_id = None
                        
                        # Process each level of the category path
                        for path in category_path:
                            category = self.env['product.category'].search([
                                ('name', '=', path),
                                ('parent_id', '=', parent_id)
                            ], limit=1)
                            
                            if not category:
                                category = self.env['product.category'].create({
                                    'name': path,
                                    'parent_id': parent_id,
                                    'external_id': str(category_id) if path == category_path[-1] else None
                                })
                            
                            parent_id = category.id
                            final_category = category
                            
                            # Only create external ID for the leaf category
                            if path == category_path[-1]:
                                path_external_id = f'product_category_{category_id}'
                                self._create_or_get_external_id(
                                    category.id,
                                    'product.category',
                                    path_external_id
                                )

                        # Create product with improved error handling
                        try:
                            product_vals = {
                                'name': row.get('name', '').strip(),
                                'default_code': row.get('default_code', '').strip(),
                                'categ_id': final_category.id,
                                'type': 'product',
                                'list_price': float(row.get('list_price', 0) or 0),
                                'sale_ok': bool(row.get('sale_ok', False)),
                                'purchase_ok': bool(row.get('purchase_ok', False)),
                                'external_id': row.get('id')  # Store the original ID
                            }

                            product = self.env['product.template'].create(product_vals)
                            _logger.info(f"Created product: {product.name}")
                            
                            # Create external ID for product if ID exists
                            if row.get('id'):
                                product_external_id = f'product_template_{row["id"]}'
                                self._create_or_get_external_id(
                                    product.id,
                                    'product.template',
                                    product_external_id
                                )
                            
                            self.env.cr.commit()

                        except Exception as product_error:
                            _logger.error(f"Error creating product: {product_error}")
                            self.env.cr.rollback()
                            continue

                    except Exception as row_error:
                        _logger.error(f"Error processing row: {row_error}")
                        self.env.cr.rollback()
                        continue

                return {'type': 'ir.actions.client', 'tag': 'reload'}
                        
        except Exception as e:
            _logger.error(f"Error reading file: {e}")
            return False

    def import_all_data(self):
        _logger.info("Starting product import process...")
        return self.import_products()