# -*- coding: utf-8 -*-
from odoo import models, fields, api
import csv
import logging
import ast
from contextlib import closing
import os
import xmlrpc.client
import time

_logger = logging.getLogger(__name__)

class DataImporter(models.TransientModel):
    _inherit = 'data.importer'
    _description = 'Data Import Wizard'
        
    def import_price_xmlrpc(self):
        try:
            start_time = time.time()
            _logger.info("Starting XMLRPC price import...")
            
            # Get credentials from environment variables
            url = os.environ.get("ISA_ODOO_URL", "")
            db = os.environ.get("ISA_ODOO_DB", "")
            username = os.environ.get("ISA_ODOO_USERNAME", "")
            password = os.environ.get("ISA_ODOO_PASSWORD", "")
            
            _logger.info(f"Connecting to: {url}, Database: {db}, Username: {username}")

            # Initialize XML-RPC connections
            common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
            models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
            
            # Authenticate
            uid = common.authenticate(db, username, password, {})
            if not uid:
                _logger.error("Authentication failed. Please check your credentials.")
                return
            
            # Use pagination to efficiently retrieve all products
            offset = 0
            limit = 1000  # Fetch 100 records at a time
            total_products = 0
            updated_products = 0
            
            while True:
                # Get all products from ISA platform with pagination
                _logger.info(f"Fetching products batch - offset: {offset}, limit: {limit}")
                product_data = models.execute_kw(
                    db, uid, password,
                    'product.product',
                    'search_read',
                    [[]],  # Empty domain to get all products
                    {
                        'fields': ['id', 'list_price', 'default_code'],  # Only fetch needed fields
                        'limit': limit,
                        'offset': offset
                    }
                )
                
                # Break if no more products
                if not product_data:
                    _logger.info("No more products to process")
                    break
                
                # Process the batch
                for product in product_data:
                    total_products += 1
                    price = product['list_price']
                    product_code = product.get('default_code', '')
                    
                    _logger.debug(f"Processing external product - ID, Code: {product_code}, Price: {price}")
                    
                    # Find matching product in current instance by external_id
                    matching_product = self.env['product.template'].search([
                        ('external_id', '=',  product['id'])
                    ], limit=1)
                    
                    if matching_product:
                        # Update external basic price
                        matching_product.write({
                            'external_basic_price': price,
                             'list_price': price
                        })
                        updated_products += 1
                        _logger.debug(f"Updated product: {matching_product.display_name} with price: {price}")
                
                # Move to next batch
                offset += limit
            
            end_time = time.time()
            duration = end_time - start_time
            _logger.info(f"Price import completed: Processed {total_products} products, Updated {updated_products} products in {duration:.2f} seconds")
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Price Import Complete',
                    'message': f'Processed {total_products} products, Updated {updated_products} products in {duration:.2f} seconds',
                    'sticky': False,
                    'type': 'success',
                }
            }
                    
        except Exception as e:
            _logger.error(f"Error in pricelist import: {str(e)}")
            self.env.cr.rollback()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Failed to import prices: {str(e)}',
                    'sticky': False,
                    'type': 'danger',
                }
            }
            
    def import_all_data(self):
        _logger.info("Starting price import process...")
        return self.import_price_xmlrpc()