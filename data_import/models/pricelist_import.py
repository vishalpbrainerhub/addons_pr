# -*- coding: utf-8 -*-
from odoo import models, fields, api
import csv
import logging
import ast
from contextlib import closing

_logger = logging.getLogger(__name__)

class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'
    external_id = fields.Char('External ID', index=True)
    
    
class DataImporter(models.TransientModel):
    # _name = 'data.importer'
    _inherit = 'data.importer'
    _description = 'Data Import Wizard'
        
        
    def import_pricelist(self):
        try:
            file_path = '/home/dell/Documents/Projects/PrimaPaint/odoo-15.0/primapaint_addons/data_import/models/pricelist_data.csv'
            
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file, delimiter='\t')
                records = [row for row in reader if row.get('id') and row['id'].strip()]
                total_records = len(records)
                _logger.info(f"Starting import of {total_records} pricelist")
                
            
                for row in records:
                    _logger.info(f"Processing pricelist ID: {row['id']}, Name: {row['name']}")
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
                        _logger.info(f"Pricelist with ID {pricelist_external_id} created successfully")
                    
                    # Find product template
                    product_tmpl = self.env['product.template'].search([('external_id', '=', row['item_ids/product_id'])], limit=1)
                    
                    if not product_tmpl:
                        _logger.info(f"Product template with ID {row['item_ids/product_id']} not found. Skipping...")
                        continue
                        
                    # Check if product has variants
                    variants = self.env['product.product'].search([('product_tmpl_id', '=', product_tmpl.id)])
                    
                    try:
                        if len(variants) > 1:
                            # If product has multiple variants, create a rule for the template
                            item_vals = {
                                'pricelist_id': pricelist.id,
                                'product_tmpl_id': product_tmpl.id,
                                'applied_on': row['item_ids/applied_on'],
                                'compute_price': row['item_ids/compute_price'],
                                'min_quantity': float(row['item_ids/min_quantity']) if row['item_ids/min_quantity'] else 0.0,
                                'base': row['item_ids/base'] or 'list_price',
                                'percent_price': float(row['item_ids/percent_price']) if row['item_ids/percent_price'] else 0.0,
                                'date_start': row['item_ids/date_start'] if row['item_ids/date_start'] else False,
                                'date_end': row['item_ids/date_end'] if row['item_ids/date_end'] else False,
                            }
                        else:
                            # If product has no variants or just one variant, create rule for the variant
                            item_vals = {
                                'pricelist_id': pricelist.id,
                                'product_id': variants[0].id if variants else False,
                                'product_tmpl_id': product_tmpl.id,
                                'applied_on': row['item_ids/applied_on'],  # Apply on product variant
                                'compute_price': row['item_ids/compute_price'],
                                'min_quantity': float(row['item_ids/min_quantity']) if row['item_ids/min_quantity'] else 0.0,
                                'base': row['item_ids/base'] or 'list_price',
                                'percent_price': float(row['item_ids/percent_price']) if row['item_ids/percent_price'] else 0.0,
                                'date_start': row['item_ids/date_start'] if row['item_ids/date_start'] else False,
                                'date_end': row['item_ids/date_end'] if row['item_ids/date_end'] else False,
                            }
                        
                        item = self.env['product.pricelist.item'].create(item_vals)
                        _logger.info(f"Pricelist item created successfully for product {product_tmpl.name}")
                
                    except Exception as e:
                        _logger.error(f"Error creating pricelist item: {str(e)}")

            
        except Exception as e:
            _logger.error(f"Error creating pricelist item: {str(e)}")
            self.env.cr.rollback()

    def import_all_data(self):
        _logger.info("Starting pricelist import process...")
        return self.import_pricelist()