import csv
import os
from datetime import datetime
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class CustomerExportCron(models.Model):
    _name = 'customer.export.cron'
    _description = 'Customer Export Cron Job'

    def _export_customers(self):
        try:
            # Create OUT directory if it doesn't exist
            os.makedirs('OUT', exist_ok=True)

            # Use a fixed filename since we're updating the same file
            filename = 'OUT/customers_export.csv'

            # Get all customers
            Partner = self.env['res.partner'].sudo()
            
            # Check if l10n_it_codice_fiscale field exists
            has_codice_fiscale = 'l10n_it_codice_fiscale' in Partner._fields
            
            # Define fields based on availability
            fieldnames = ['id', 'name', 'vat']
            if has_codice_fiscale:
                fieldnames.append('l10n_it_codice_fiscale')
            fieldnames.append('property_product_pricelist')

            # Get all customers
            customers = Partner.search([('customer_rank', '>', 0)])

            # Write to CSV
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Write headers
                writer.writeheader()
                
                # Write customer data
                for customer in customers:
                    # Prepare row data
                    row = {
                        'id': customer.id,
                        'name': customer.name or '',
                        'vat': customer.vat or '',
                    }
                    
                    # Add codice fiscale if field exists
                    if has_codice_fiscale:
                        row['l10n_it_codice_fiscale'] = getattr(customer, 'l10n_it_codice_fiscale', '') or ''
                    
                    # Add pricelist
                    row['property_product_pricelist'] = customer.property_product_pricelist.name if customer.property_product_pricelist else ''
                    
                    writer.writerow(row)

            _logger.info(f"Customer export completed successfully at {datetime.now()}")

        except Exception as e:
            _logger.error(f"Error in customer export cron: {str(e)}")