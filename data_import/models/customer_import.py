# -*- coding: utf-8 -*-
from odoo import models, fields, api
import csv
import logging
import ast
from contextlib import closing

_logger = logging.getLogger(__name__)

class Partner_External_import_id(models.Model):
    _name = 'external.import'
    _description = 'External Import ID'
    
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, ondelete='cascade')
    external_import_id = fields.Integer(string='External Import ID', required=True)
    
    

class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'
    external_id = fields.Char('External ID', index=True)
    
    

class DataImporter(models.TransientModel):
    # _name = 'data.importer'
    _inherit = 'data.importer'
    _description = 'Data Import Wizard'
        
  
    def import_cutomers(self):
        try:
            _logger.info("Starting customer import process...")
            file_path = '/home/dell/Documents/Projects/PrimaPaint/odoo-15.0/primapaint_addons/data_import/models/customer-data.csv'
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)  # Remove delimiter='\t'
                records = [row for row in reader if row.get('id')]
                _logger.info(f"Found {len(records)} customers in CSV")
                for row in records:
                    try:
                        customer_id = row['id']
                        price_list = ast.literal_eval(row['property_product_pricelist'])
                        category_id = int(price_list[0]) if isinstance(price_list, tuple) else int(ast.literal_eval(price_list)[0])
                        
                        if not self.env['external.import'].search_count([('external_import_id', '=', customer_id)]):
                            pricelist = self.env['product.pricelist'].search([('external_id', '=', category_id)], limit=1)
                            if not pricelist:
                                _logger.error(f"Pricelist not found for category_id: {category_id}")
                                continue
                                
                            customer = self.env['res.partner'].create({
                                'name': row['name'],
                                'email': row['email'],
                                'street': row['street'],
                                'city': row['city'],
                                'zip': row['zip'],
                                'country_id': 110,
                                'property_product_pricelist': pricelist.id
                            })
                            
                            self.env['external.import'].create({
                                'external_import_id': customer_id,
                                'partner_id': customer.id
                            })
                            
                            _logger.info(f"Created customer {customer.name} (ID: {customer_id})")
                    
                    except Exception as e:
                        _logger.error(f"Error processing customer {row.get('name', 'Unknown')}: {e}")
                        continue
                        
        except Exception as e:
            _logger.error(f"File reading error: {e}")
            return False
            
        return True

    def import_all_data(self):
        _logger.info("Starting customer import process...")
        return self.import_cutomers()
        