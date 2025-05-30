# -*- coding: utf-8 -*-
from odoo import models, fields, api
import csv
import logging
import os

_logger = logging.getLogger(__name__)


class DataImporter(models.TransientModel):
    _inherit = 'data.importer'
    _description = 'Data Import Wizard'
    
    def import_customer_agent_relationships(self):
        """Import customer-agent relationships from CSV"""
        try:
            _logger.info("Starting customer-agent relationship import process...")
            file_path = os.environ.get('AGENT_CUSTOMER_DATA_PATH')
            
            if not file_path:
                _logger.error("LOCAL_AGENT_CUSTOMER_DATA_PATH environment variable not set")
                return False
                
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                records = [row for row in reader if row.get('customer_id') and row.get('sales_agent_id')]
                _logger.info(f"Found {len(records)} customer-agent relationships in CSV")
                

                
                for row in records:
                    try:
                        customer_external_id = int(row['customer_id'])
                        agent_external_id = int(row['sales_agent_id'])
                        
                        # Find customer by external import ID
                        customer_import = self.env['external.import'].search([
                            ('external_import_id', '=', customer_external_id)
                        ], limit=1)
                        
                        print(customer_import)
                        
                        if not customer_import:
                            _logger.warning(f"Customer not found for external ID: {customer_external_id}")
                            continue
                            
                        # Find agent by external import ID
                        agent_import = self.env['external.import'].search([
                            ('external_import_id', '=', agent_external_id),
                            ('is_agent', '=', True) 
                        ], limit=1)
                        
                        if not agent_import:
                            _logger.warning(f"Agent not found for external ID: {agent_external_id}")
                            continue
                            
                        customer_import.write({
                            'agent_id': agent_external_id
                        })
                        self.env.cr.commit()
                        
                        _logger.info(f"Successfully updated the agent id")
                        
                    except Exception as e:
                        _logger.error(f"Error processing relationship - Customer ID: {customer_external_id}, Agent ID: {agent_external_id}: {e}")
                        continue
                
                return True
                            
        except Exception as e:
            _logger.error(f"File reading error: {e}")
            return False

    def import_all_data(self):
        return self.import_customer_agent_relationships()