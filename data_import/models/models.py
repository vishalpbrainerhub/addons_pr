# -*- coding: utf-8 -*-
from odoo import models, fields, api
import csv
import logging
import ast
from contextlib import closing
from threading import Thread, Lock
from queue import Queue

_logger = logging.getLogger(__name__)

class ImportCounter:
    def __init__(self):
        self.lock = Lock()
        self.count = 0

    def increment(self):
        with self.lock:
            self.count += 1
            if self.count % 10 == 0:
                _logger.info(f"Processed {self.count} products")

    def get_count(self):
        with self.lock:
            return self.count

    def reset(self):
        with self.lock:
            self.count = 0

import_counter = ImportCounter()

class ProductCategory(models.Model):
    _inherit = 'product.category'
    external_id = fields.Char('External ID', index=True)

class ProductTemplate(models.Model):
    _inherit = 'product.template'
    external_id = fields.Char('External ID', index=True)

class DataImporter(models.TransientModel):
    _name = 'data.importer'
    _description = 'Data Import Wizard'
    
    WORKER_THREADS = 4
    QUEUE_SIZE = 1000
    BATCH_SIZE = 100
        
    def _create_or_get_external_id(self, env, record_id, model, external_id, module='__import__'):
        """Create external ID if it doesn't exist, or get existing one"""
        existing = env['ir.model.data'].search([
            ('name', '=', external_id),
            ('model', '=', model),
            ('module', '=', module)
        ], limit=1)
        
        if existing:
            return existing
            
        return env['ir.model.data'].create({
            'name': external_id,
            'model': model,
            'module': module,
            'res_id': record_id,
            'noupdate': True
        })

    def process_batch(self, env, batch):
        """Process a batch of records with a single cursor"""
        for row in batch:
            try:
                external_product_id = row.get('id')
                if not external_product_id:
                    _logger.warning("Skipping row with no ID")
                    continue
                    
                _logger.info(f"Processing product ID: {external_product_id}")
                
                product_exists = env['product.template'].search([
                    ('external_id', '=', external_product_id)
                ], limit=1)
                
                if product_exists:
                    _logger.info(f"Product with ID {external_product_id} already exists. Skipping creation...")
                    continue
                
                categ_id = row.get('categ_id', '')
                if not categ_id:
                    _logger.warning(f"No category data for product {external_product_id}")
                    continue
                    
                try:
                    categ_id = categ_id.strip('()')
                    category_parts = categ_id.split(', ', 1)
                    if len(category_parts) != 2:
                        _logger.error(f"Invalid category format for product {external_product_id}: {categ_id}")
                        continue
                        
                    category_id = int(category_parts[0])
                    category_name = category_parts[1].strip("'")
                    
                    _logger.info(f"Processing category ID: {category_id}, Name: {category_name}")
                    category_path = category_name.split(' / ')
                    
                    parent_id = False
                    final_category = None
                    
                    for path in category_path:
                        if not path:
                            continue
                            
                        category = env['product.category'].search([
                            ('name', '=', path),
                            ('parent_id', '=', parent_id)
                        ], limit=1)
                        
                        if not category:
                            category = env['product.category'].create({
                                'name': path,
                                'parent_id': parent_id,
                                'external_id': str(category_id) if path == category_path[-1] else None
                            })
                        
                        parent_id = category.id
                        final_category = category
                    
                    if final_category:
                        product_vals = {
                            'name': row.get('name', '').strip(),
                            'default_code': row.get('default_code', '').strip(),
                            'categ_id': final_category.id,
                            'type': 'product',
                            'sale_ok': str(row.get('sale_ok', '')).lower() == 'true',
                            'purchase_ok': str(row.get('purchase_ok', '')).lower() == 'true',
                            'external_id': external_product_id
                        }
                        
                        product = env['product.template'].create(product_vals)
                        _logger.info(f"Created product: {product.name}")
                        
                        product_external_id = f'product_template_{external_product_id}'
                        self._create_or_get_external_id(
                            env,
                            product.id,
                            'product.template',
                            product_external_id
                        )
                        
                        import_counter.increment()
                        
                except ValueError as ve:
                    _logger.error(f"Value error processing category for product {external_product_id}: {ve}")
                    continue
                except Exception as category_error:
                    _logger.error(f"Error processing category for product {external_product_id}: {category_error}")
                    continue
                    
            except Exception as row_error:
                _logger.error(f"Error processing row: {row_error}")
                continue

    def worker(self, queue, registry, uid, context):
        """Worker thread function"""
        while True:
            batch = queue.get()
            if batch is None:
                break
                
            try:
                with registry.cursor() as cr:
                    env = api.Environment(cr, uid, context)
                    self.process_batch(env, batch)
                    cr.commit()
            except Exception as e:
                _logger.error(f"Error processing batch: {e}")
            finally:
                queue.task_done()
        
    def import_products(self):
        try:
            file_path = '/home/dell/Documents/Projects/PrimaPaint/odoo-15.0/primapaint_addons/data_import/models/product-data.csv'
            
            _logger.info(f"Attempting to open file at: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as file:
                _logger.info("Successfully opened file")
                first_lines = file.read(500)
                _logger.info(f"First 500 characters of file:\n{first_lines}")
                file.seek(0)
                
                reader = csv.DictReader(
                    file,
                    delimiter=',',
                    quotechar='"',
                    quoting=csv.QUOTE_ALL
                )
                
                clean_fieldnames = [field.strip('"') if field else '' for field in reader.fieldnames] if reader.fieldnames else []
                _logger.info(f"Clean CSV headers: {clean_fieldnames}")
                
                queue = Queue(maxsize=self.QUEUE_SIZE)
                threads = []
                registry = self.pool
                
                import_counter.reset()
                
                for _ in range(self.WORKER_THREADS):
                    t = Thread(target=self.worker, args=(queue, registry, self.env.uid, self.env.context))
                    t.daemon = True
                    t.start()
                    threads.append(t)
                
                current_batch = []
                record_count = 0
                
                for row in reader:
                    clean_row = {}
                    for k, v in row.items():
                        key = k.strip('"') if k else ''
                        if v is None:
                            clean_row[key] = ''
                        else:
                            clean_row[key] = v.strip('"') if isinstance(v, str) else v
                    
                    if clean_row.get('id'):
                        current_batch.append(clean_row)
                        record_count += 1
                        
                        if len(current_batch) >= self.BATCH_SIZE:
                            queue.put(current_batch)
                            current_batch = []
                
                if current_batch:
                    queue.put(current_batch)
                
                _logger.info(f"Queued {record_count} records for processing")
                
                for _ in range(self.WORKER_THREADS):
                    queue.put(None)
                
                queue.join()
                for t in threads:
                    t.join()
                
                _logger.info(f"Import completed. Processed {import_counter.get_count()} products")
                return {'type': 'ir.actions.client', 'tag': 'reload'}
                
        except Exception as e:
            _logger.error(f"Error reading file: {e}")
            return False

    def import_all_data(self):
        _logger.info("Starting product import process...")
        return self.import_products()