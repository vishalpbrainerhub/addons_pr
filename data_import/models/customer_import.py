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
            file_path = '/home/dell/Documents/Projects/PrimaPaint/odoo-15.0/primapaint_addons/data_import/models/customer-data.csv'
            
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file, delimiter='\t')
                records = [row for row in reader if row.get('id') and row['id'].strip()]
                total_records = len(records)
                _logger.info(f"Starting import of {total_records} customers")
                

                    # id	name	email	vat	street	city	zip	country_id	l10n_it_codice_fiscale	property_product_pricelist
                for row in records:
                    
                    customer_id = row['id']
                    property_product_pricelist = row['property_product_pricelist']
                    
                    category = ast.literal_eval(property_product_pricelist)
                    category_id, category_name = category if isinstance(category, tuple) else ast.literal_eval(category)
                    
                    
                    customer = self.env['external.import'].search([('external_import_id', '=', customer_id)], limit=1)
                    if customer:
                        _logger.info(f"Customer with ID {customer_id} already exists. Skipping creation...")
                    else:
                        category_id = int(category_id)
                        _logger.info(f"Processing category ID: {category_id}, Name: {category_name}")
                        pricelist = self.env['product.pricelist'].search([('external_id', '=', category_id)], limit=1)
                        
                        _logger.info(f"Processing pricelist ID: {pricelist.id}, Name: {pricelist.name}")
                        
                        customer = self.env['res.partner'].create({
                            'name': row['name'],
                            'email': row['email'],
                            # 'vat': row['vat'],
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
                        
                        _logger.info(f"Customer with ID {customer_id} created successfully")
                    
                

                        
        except Exception as e:
            _logger.error(f"Error reading file: {e}")
            return False

    def import_all_data(self):
        _logger.info("Starting customer import process...")
        return self.import_cutomers()