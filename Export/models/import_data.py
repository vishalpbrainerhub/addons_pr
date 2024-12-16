import csv
import os
from datetime import datetime
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class CustomerImportCron(models.Model):
    _name = 'customer.import.cron'
    _description = 'Customer Import Cron Job'

    def _import_customers(self):
        try:
            file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'In', 'customers_2_12_2024_8_34.csv')
            _logger.info(f"Attempting to read file from: {file_path}")
            
            if not os.path.exists(file_path):
                _logger.error(f"File not found at path: {file_path}")
                return

            Partner = self.env['res.partner'].sudo()
            count = 0
            
            with open(file_path, 'r', encoding='utf-8') as csvfile:
                content = csvfile.readlines()
                _logger.info(f"Found {len(content)} lines in customer file")
                
                for line in content[1:]:  # Skip header
                    line = line.strip()
                    if not line:
                        continue

                    parts = line.split('\t')
                    if len(parts) < 5:
                        _logger.warning(f"Invalid line format: {line}")
                        continue

                    try:
                        record_id = parts[0].strip('"').split(',')[0]
                        name = parts[0].strip('"').split(',')[-1].strip()
                        
                        vals = {
                            'name': name,
                            'vat': parts[1].strip('"') if parts[1] != 'False' else False,
                            'l10n_it_codice_fiscale': parts[2].strip('"') if parts[2] != 'False' else False,
                            'customer_rank': 1,
                            'company_type': 'company'
                        }

                        if parts[4] != 'False':
                            pricelist_data = eval(parts[4].strip())
                            vals['property_product_pricelist'] = pricelist_data[0]

                        self.env.cr.execute("SELECT id FROM res_partner WHERE id = %s", (int(record_id),))
                        exists = self.env.cr.fetchone()
                        
                        if exists:
                            Partner.browse(int(record_id)).write(vals)
                        else:
                            Partner.create(vals)
                        
                        self.env.cr.commit()
                        count += 1
                        _logger.info(f"Processed customer: {name} (ID: {record_id})")
                    
                    except Exception as e:
                        self.env.cr.rollback()
                        _logger.error(f"Error processing line: {line}\nError: {str(e)}")

            _logger.info(f"Successfully imported {count} customers")
        except Exception as e:
            self.env.cr.rollback()
            _logger.error(f"Customer import error: {str(e)}")

class ProductImportCron(models.Model):
    _name = 'product.import.cron'
    _description = 'Product Import Cron Job'

    def _import_products(self):
        try:
            file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'In', 'product_2_12_2024_8_34.csv')
            _logger.info(f"Attempting to read file from: {file_path}")
            
            if not os.path.exists(file_path):
                _logger.error(f"File not found at path: {file_path}")
                return

            Product = self.env['product.template'].sudo()
            count = 0
            
            with open(file_path, 'r', encoding='utf-8') as csvfile:
                content = csvfile.readlines()
                _logger.info(f"Found {len(content)} lines in product file")
                
                for line in content[1:]:
                    line = line.strip()
                    if not line:
                        continue

                    parts = line.split('\t')
                    if len(parts) < 6:
                        _logger.warning(f"Invalid line format: {line}")
                        continue

                    try:
                        record_id = parts[0].strip('"').split(',')[0]
                        name = parts[0].strip('"').split(',')[-1].strip()

                        vals = {
                            'name': name,
                            'type': 'product',  # Changed from 'consu'
                            'detailed_type': 'product',  # Changed from 'consu'
                            'sale_ok': parts[4].strip() == 'True',
                            'purchase_ok': parts[5].strip() == 'True',
                            'uom_id': 1,
                            'uom_po_id': 1,
                            'lst_price': 1.0,
                            'active': True
                        }

                        if parts[3]:
                            categ_data = eval(parts[3].strip())
                            vals['categ_id'] = categ_data[0]

                        self.env.cr.execute("SELECT id FROM product_template WHERE id = %s", (int(record_id),))
                        exists = self.env.cr.fetchone()
                        
                        if exists:
                            Product.browse(int(record_id)).write(vals)
                        else:
                            Product.create(vals)
                            
                        self.env.cr.commit()
                        count += 1
                        _logger.info(f"Processed product: {name} (ID: {record_id})")
                        
                    except Exception as e:
                        self.env.cr.rollback()
                        _logger.error(f"Error processing line: {line}\nError: {str(e)}")

            _logger.info(f"Successfully imported {count} products")
        except Exception as e:
            self.env.cr.rollback()
            _logger.error(f"Product import error: {str(e)}")

class DataImportScheduler(models.Model):
    _name = 'data.import.scheduler'
    _description = 'Data Import Scheduler'

    @api.model
    def run_imports(self):
        self.env['customer.import.cron']._import_customers()
        self.env['product.import.cron']._import_products()