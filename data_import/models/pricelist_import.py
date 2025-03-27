# -*- coding: utf-8 -*-
from odoo import models, fields, api
import csv
import logging
import ast
from contextlib import closing
import os

_logger = logging.getLogger(__name__)

class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'
    external_id = fields.Char('External ID', index=True)
    
    
class DataImporter(models.TransientModel):
    _inherit = 'data.importer'
    _description = 'Data Import Wizard'
        
        
    def import_pricelist(self):
        try:
            file_path = os.environ.get('PRICELIST_DATA_PATH')
            
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                if not content.strip():
                    _logger.error("CSV file is empty")
                    return
                    
                file.seek(0)
                dialect = csv.Sniffer().sniff(content[:1024])
                reader = csv.DictReader(file, dialect=dialect)
                
                required_fields = ['id', 'name', 'discount_policy']
                header = reader.fieldnames
                if not all(field in header for field in required_fields):
                    _logger.error(f"Missing required columns. Required: {required_fields}, Found: {header}")
                    return
                    
                records = [row for row in reader if row.get('id') and row['id'].strip()]
                total_records = len(records)
                
                if total_records == 0:
                    _logger.error("No valid records found in CSV")
                    return
                
                for row in records:
                    pricelist_external_id = row['id']
                    
                    # Find or create pricelist
                    pricelist = self.env['product.pricelist'].search([('external_id', '=', pricelist_external_id)], limit=1)
                    if pricelist:
                        _logger.info(f"Pricelist with ID {pricelist_external_id} already exists. Skipping creation...")
                    else:
                        pricelist = self.env['product.pricelist'].create({
                            'name': row['name'],
                            'discount_policy': row['discount_policy'],
                            'external_id': pricelist_external_id
                        })
                    
                    try:
                        # Base item values that are common for all types
                        item_vals = {
                            'pricelist_id': pricelist.id,
                            'compute_price': row['item_ids/compute_price'],
                            'min_quantity': float(row['item_ids/min_quantity']) if row['item_ids/min_quantity'] else 0.0,
                            'base': row['item_ids/base'] if row['item_ids/base'] else 0.0,
                            'percent_price': float(row['item_ids/percent_price']) if row['item_ids/percent_price'] else 0.0,
                            'date_start': row['item_ids/date_start'] if row['item_ids/date_start'] else False,
                            'date_end': row['item_ids/date_end'] if row['item_ids/date_end'] else False,
                            'base_pricelist_id': self.env['product.pricelist'].search([('external_id', '=', row['item_ids/base_pricelist_id'])], limit=1).id if row['item_ids/base_pricelist_id'] else False,
                            'price_discount': float(row['item_ids/price_discount']) if row['item_ids/price_discount'] else 0.0,
                            # Add missing fields
                            'fixed_price': float(row['item_ids/fixed_price']) if row.get('item_ids/fixed_price') else 0.0,
                            'price_surcharge': float(row['item_ids/price_surcharge']) if row.get('item_ids/price_surcharge') else 0.0,
                            'price_round': float(row['item_ids/price_round']) if row.get('item_ids/price_round') else 0.0,
                            'price_min_margin': float(row['item_ids/price_min_margin']) if row.get('item_ids/price_min_margin') else 0.0,
                            'price_max_margin': float(row['item_ids/price_max_margin']) if row.get('item_ids/price_max_margin') else 0.0,
                        }

                        # Handle category-based rules
                        if row.get('item_ids/categ_id'):
                            category_details = self.env['product.category'].search([('external_id', '=', row['item_ids/categ_id'])], limit=1)
                            if not category_details:
                                _logger.info(f"Category with ID {row['item_ids/categ_id']} not found. Skipping...")
                                continue
                            
                            # For category rules, only set category-specific fields
                            item_vals.update({
                                'applied_on': '2_product_category',
                                'categ_id': category_details.id
                            })
                            _logger.info(f"Creating category-based rule for category ID: {category_details.id}")
                            
                        # Handle product-based rules
                        elif row.get('item_ids/product_id'):
                            product_tmpl = self.env['product.template'].search([('external_id', '=', row['item_ids/product_id'])], limit=1)
                            if not product_tmpl:
                                _logger.info(f"Product template with ID {row['item_ids/product_id']} not found. Skipping...")
                                continue
                                
                            variants = self.env['product.product'].search([('product_tmpl_id', '=', product_tmpl.id)])
                            
                            if len(variants) > 1:
                                item_vals.update({
                                    'applied_on': '1_product',
                                    'product_tmpl_id': product_tmpl.id
                                })
                            else:
                                item_vals.update({
                                    'applied_on': '0_product_variant',
                                    'product_id': variants[0].id if variants else False,
                                    'product_tmpl_id': product_tmpl.id
                                })
                        else:
                            # Global rule (applies to all products)
                            item_vals.update({
                                'applied_on': '3_global'
                            })
                            _logger.info("Creating global pricing rule")

                        # Create the pricelist item
                        _logger.info(f"Creating pricelist item with values: {item_vals}")
                        item = self.env['product.pricelist.item'].create(item_vals)
                        _logger.info(f"Successfully created pricelist item")
                    
                    except Exception as e:
                        _logger.error(f"Error creating pricelist item: {str(e)}")
                        continue

            _logger.info("Pricelist import completed")
            
        except Exception as e:
            _logger.error(f"Error in pricelist import: {str(e)}")
            self.env.cr.rollback()
            
    def import_all_data(self):
        _logger.info("Starting pricelist import process...")
        return self.import_pricelist()