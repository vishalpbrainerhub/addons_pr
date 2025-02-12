# -*- coding: utf-8 -*-
from odoo import models, fields, api
import csv
import logging
import ast
from contextlib import closing

_logger = logging.getLogger(__name__)  # Fixed logger name

class ProductCategory(models.Model):
    _inherit = 'product.category'
    external_id = fields.Char('External ID', index=True)

class ProductTemplate(models.Model):
    _inherit = 'product.template'
    external_id = fields.Char('External ID', index=True)

class DataImporter(models.TransientModel):
    _name = 'data.importer'
    _description = 'Data Import Wizard'
    
    CHUNK_SIZE = 1000  # Added chunk size constant

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

    def _process_category(self, category_data):
        """Process category data safely"""
        try:
            if not category_data or category_data == 'False':
                return self.env.ref('product.product_category_all')

            # Handle different category data formats
            try:
                category = ast.literal_eval(category_data)
            except (ValueError, SyntaxError):
                # If literal_eval fails, try direct string splitting
                return self._process_category_by_name(category_data)

            category_id, category_name = category if isinstance(category, tuple) else (None, category)
            
            if not category_name:
                return self.env.ref('product.product_category_all')

            return self._process_category_path(category_id, category_name)
        except Exception as e:
            _logger.error(f"Error processing category data: {str(e)}")
            return self.env.ref('product.product_category_all')

    def _process_category_path(self, category_id, category_name):
        """Process category hierarchy and return final category"""
        category_path = category_name.split(' / ')
        parent_id = False
        final_category = None

        for path in category_path:
            path = path.strip()
            if not path:
                continue

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

        if final_category and category_id:
            # Create external ID for leaf category
            self._create_or_get_external_id(
                final_category.id,
                'product.category',
                f'product_category_{category_id}'
            )

        return final_category

    def _prepare_product_vals(self, row, category_id):
        """Prepare product values with safe conversions"""
        return {
            'name': row.get('name', '').strip(),
            'default_code': row.get('default_code', '').strip(),
            'categ_id': category_id,
            'type': 'product',
            'list_price': float(row.get('list_price', 0) or 0),
            'sale_ok': bool(row.get('sale_ok', True)),
            'purchase_ok': bool(row.get('purchase_ok', True)),
            'external_id': row.get('id')
        }
    
    def import_products(self):
        try:
            file_path = '/home/dell/Documents/Projects/PrimaPaint/odoo-15.0/primapaint_addons/data_import/models/product-data.csv'
            
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                records = [row for row in reader if row.get('id')]
                
            total_records = len(records)
            _logger.info(f"Starting import of {total_records} products")
            
            # Process in chunks
            for i in range(0, total_records, self.CHUNK_SIZE):
                chunk = records[i:i + self.CHUNK_SIZE]
                product_vals_list = []
                
                # Process chunk
                for row in chunk:
                    try:
                        # Skip if product already exists
                        if self.env['product.template'].search_count([
                            ('external_id', '=', row.get('id'))
                        ]):
                            _logger.info(f"Skipping existing product with ID: {row.get('id')}")
                            continue
                        
                        # Process category
                        category = self._process_category(row.get('categ_id'))
                        if category:
                            product_vals = self._prepare_product_vals(row, category.id)
                            product_vals_list.append(product_vals)
                            
                    except Exception as row_error:
                        _logger.error(f"Error processing row {row.get('id')}: {str(row_error)}")
                        continue
                
                # Create products in batch
                if product_vals_list:
                    try:
                        products = self.env['product.template'].create(product_vals_list)
                        
                        # Create external IDs in batch
                        for product, vals in zip(products, product_vals_list):
                            if vals.get('external_id'):
                                self._create_or_get_external_id(
                                    product.id,
                                    'product.template',
                                    f"product_template_{vals['external_id']}"
                                )
                        
                        self.env.cr.commit()
                        _logger.info(f"Successfully imported chunk of {len(product_vals_list)} products")
                        
                    except Exception as batch_error:
                        _logger.error(f"Error creating products in batch: {str(batch_error)}")
                        self.env.cr.rollback()
                        continue
                
                _logger.info(f"Processed {min(i + self.CHUNK_SIZE, total_records)}/{total_records} records")
            
            return {'type': 'ir.actions.client', 'tag': 'reload'}
                        
        except Exception as e:
            _logger.error(f"Error in import process: {str(e)}")
            return False

    def import_all_data(self):
        _logger.info("Starting product import process...")
        return self.import_products()