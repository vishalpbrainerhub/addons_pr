# -*- coding: utf-8 -*-
from odoo import models, fields, api
import csv
import logging
import ast
import random
from contextlib import closing
import os

_logger = logging.getLogger(__name__)


class DataImporter(models.TransientModel):
    # _name = 'data.importer'
    _inherit = 'data.importer'
    _description = 'Data Import Wizard'
    
    def _send_welcome_email(self, partner, email):
        """Send welcome email with password"""
        password = ''.join(random.choices('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz', k=8))
        password_record = self.env['customer.password'].sudo().create({
            'partner_id': partner.id
        })
        password_record.set_password(password)
        
        template = self.env['mail.template'].sudo().create({
                    'name': 'Credenziali Cliente',
                    'email_from': 'admin@primapaint.com',
                    'email_to': email,
                    'subject': 'Benvenuto a PrimaPaint - Le tue Credenziali di Accesso',
                    'body_html': f'''
                        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
                            
                            <h1 style="color: #333333; text-align: center; margin-bottom: 20px;">Benvenuto in <span style="color: #007bff;">PrimaPaint</span>!</h1>
                            
                            <p style="color: #555555; font-size: 16px; line-height: 1.6;">Gentile <strong>{partner.name}</strong>,</p>
                            
                            <p style="color: #555555; font-size: 16px; line-height: 1.6;">Grazie per esserti registrato. Ecco le tue credenziali di accesso:</p>
                            
                            <div style="background-color: #ffffff; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; margin: 20px 0;">
                                <p style="margin: 10px 0; color: #333333;"><strong>Email:</strong> {partner.email}</p>
                                <p style="margin: 10px 0; color: #333333;"><strong>Password:</strong> {password}</p>
                            </div>
                            
                            <div style="text-align: center; margin: 30px 0;">
                                <a href="#" style="display: inline-block; background-color: #28a745; color: #ffffff; text-decoration: none; padding: 12px 40px; border-radius: 5px; font-size: 16px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">Scarica la nostra App</a>
                            </div>
                            
                            <p style="color: #777777; font-size: 14px; text-align: center; margin-top: 30px;">
                                Per qualsiasi domanda, non esitare a contattarci.<br>
                                <strong>Il team di PrimaPaint</strong>
                            </p>
                        </div>
                    ''',
                    'model_id': self.env['ir.model']._get('res.partner').id
                })
        template.send_mail(partner.id, force_send=True)
        
    def import_cutomers(self):
        try:
            _logger.info("Starting customer import process...")
            file_path = os.environ.get('LOCAL_CUSTOMER_DATA_PATH')
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                records = [row for row in reader if row.get('id')]
                _logger.info(f"Found {len(records)} customers in CSV")
                for row in records:
                    try:
                        customer_id = row['id']
                        customer_email = row.get('email', '').strip()
                        price_list = ast.literal_eval(row['property_product_pricelist'])
                        category_id = int(price_list[0]) if isinstance(price_list, tuple) else int(ast.literal_eval(price_list)[0])
                        
                        # Skip if no email provided
                        if not customer_email:
                            _logger.warning(f"Skipping customer {row.get('name', 'Unknown')} - no email provided")
                            continue
                        
                        # Check if customer already exists based on external import ID
                        existing_import = self.env['external.import'].search([('external_import_id', '=', customer_id)], limit=1)
                        
                        # Find the pricelist
                        pricelist = self.env['product.pricelist'].search([('external_id', '=', category_id)], limit=1)
                        if not pricelist:
                            _logger.error(f"Pricelist not found for category_id: {category_id}")
                            continue
                        
                        existing_customer = None
                        
                        if existing_import:
                            # Update existing customer found by external import ID
                            existing_customer = existing_import.partner_id
                            _logger.info(f"Found customer by external ID - Updating {existing_customer.name} (ID: {customer_id})")
                        else:
                            # Check if customer exists by email
                            existing_customer = self.env['res.partner'].search([('email', '=', customer_email)], limit=1)
                            if existing_customer:
                                _logger.info(f"Found customer by email - Updating {existing_customer.name} (Email: {customer_email})")
                                
                        
                        if existing_customer:
                            continue
                            # Update existing customer information
                            existing_customer.write({
                                'name': row['name'],
                                'email': customer_email,
                                'street': row['street'],
                                'city': row['city'],
                                'zip': row['zip'],
                                'vat': row['vat'],
                                'property_product_pricelist': pricelist.id,
                            })
                            
                            # Update or create the custom address
                            existing_address = self.env['social_media.custom_address'].search([
                                ('partner_id', '=', existing_customer.id),
                                ('default', '=', True)
                            ], limit=1)
                            
                            if existing_address:
                                existing_address.write({
                                    'address': row['street'],
                                    'continued_address': row.get('street2', ''),
                                    'city': row['city'],
                                    'postal_code': row['zip'],
                                    'state_id': row.get('state_id', False)
                                })
                            else:
                                # Create new address if none exists
                                self.env['social_media.custom_address'].create({
                                    'partner_id': existing_customer.id,
                                    'address': row['street'],
                                    'continued_address': row.get('street2', ''),
                                    'city': row['city'],
                                    'postal_code': row['zip'],
                                    'village': '',
                                    'default': True,
                                    'country_id': 109,
                                    'state_id': row.get('state_id', False)
                                })
                                
                        else:
                            # Create new customer - no existing record found by ID or email
                            customer = self.env['res.partner'].create({
                                'name': row['name'],
                                'email': customer_email,
                                'street': row['street'],
                                'city': row['city'],
                                'zip': row['zip'],
                                'country_id': 109,
                                'vat': row['vat'],
                                # 'l10n_it_codice_fiscale': row['l10n_it_codice_fiscale'],
                                'property_product_pricelist': pricelist.id,
                                'company_id': 1,
                            })
                            
                            # Create external import record
                            self.env['external.import'].create({
                                'external_import_id': customer_id,
                                'partner_id': customer.id
                            })
                            
                            # Create custom address
                            self.env['social_media.custom_address'].create({
                                'partner_id': customer.id,
                                'address': row['street'],
                                'continued_address': row.get('street2', ''),
                                'city': row['city'],
                                'postal_code': row['zip'],
                                'village': '',
                                'default': True,
                                'country_id': 109,
                                'state_id': row.get('state_id', False)
                            })
                            
                            # Send welcome email commented out in original code
                            # if customer.email:
                            #     try:
                            #         self._send_welcome_email(customer, customer.email)
                            #         _logger.info(f"Welcome email sent to {customer.email}")
                            #     except Exception as email_error:
                            #         _logger.error(f"Error sending welcome email to {customer.email}: {email_error}")
                            
                            _logger.info(f"Created new customer {customer.name} (ID: {customer_id})")
                    
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