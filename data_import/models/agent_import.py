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
        password_record = self.env['agent.password'].sudo().create({
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
        
    def import_agents(self):
        try:
            _logger.info("Starting agent import process...")
            file_path = os.environ.get('LOCAL_AGENT_DATA_PATH')
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                records = [row for row in reader if row.get('id')]
                _logger.info(f"Found {len(records)} agents in CSV")
                
                success_count = 0
                error_count = 0
                
                for row in records:
                    try:
                        agent_id = row['id']
                        agent_name = row.get('name', 'Unknown')
                        agent_email = row.get('email', '').strip()
                        
                        # Helper function to clean and validate field values
                        def clean_field(value, field_name=''):
                            """Clean field values, converting False/None/empty to proper values"""
                            if value in [False, None, 'False', 'None', '']:
                                return False if field_name in ['vat', 'l10n_it_codice_fiscale'] else ''
                            return str(value).strip() if value else ''
                        
                        # Clean and prepare data
                        cleaned_data = {
                            'name': clean_field(row.get('name')) or 'Unknown Agent',
                            'email': clean_field(agent_email),
                            'street': clean_field(row.get('street')),
                            'city': clean_field(row.get('city')),
                            'zip': clean_field(row.get('zip')),
                            'vat': clean_field(row.get('vat'), 'vat'),
                            'l10n_it_codice_fiscale': clean_field(row.get('l10n_it_codice_fiscale'), 'l10n_it_codice_fiscale'),
                            'state_id': row.get('state_id') if row.get('state_id') and row.get('state_id') != 'False' else False,
                            'street2': clean_field(row.get('street2'))
                        }
                        
                        # Additional validation for VAT
                        if cleaned_data['vat'] and cleaned_data['vat'] not in ['False', 'false', '']:
                            # Basic VAT format validation - adjust regex as needed for your requirements
                            import re
                            if not re.match(r'^[A-Z]{2}[0-9A-Z]{2,}$', cleaned_data['vat'].upper()):
                                _logger.warning(f"Invalid VAT format for {agent_name}: {cleaned_data['vat']}. Setting to empty.")
                                cleaned_data['vat'] = False
                        else:
                            cleaned_data['vat'] = False
                        
                        # Check if agent already exists based on external import ID
                        existing_import = self.env['external.import'].search([('external_import_id', '=', agent_id)], limit=1)
                        
                        existing_agent = None
                        
                        if existing_import:
                            # Update existing agent found by external import ID
                            existing_agent = existing_import.partner_id
                            _logger.info(f"Found agent by external ID - Updating {existing_agent.name} (ID: {agent_id})")
                            
                            # Update the external import record to ensure is_agent is True and agent_id is None
                            external_import_update_data = {
                                'is_agent': True,
                                'agent_id': None
                            }
                            
                            # Only add codice fiscale if it's valid
                            if cleaned_data['l10n_it_codice_fiscale']:
                                external_import_update_data['l10n_it_codice_fiscale'] = cleaned_data['l10n_it_codice_fiscale']
                            
                            existing_import.write(external_import_update_data)
                            _logger.info(f"Updated external import record for agent {existing_agent.name} - set is_agent=True, agent_id=None")
                            
                        else:
                            # Check if agent exists by email (only if email is provided and valid)
                            if agent_email and agent_email.lower() not in ['false', 'none', '']:
                                existing_agent = self.env['res.partner'].search([('email', '=', agent_email)], limit=1)
                                if existing_agent:
                                    _logger.info(f"Found agent by email - Updating {existing_agent.name} (Email: {agent_email})")
                                    
                                    # update all fields of it in res.partner
                            else:
                                _logger.info(f"No valid email provided for agent {agent_name} (ID: {agent_id}) - will create new record if not found by external ID")
                        
                        if existing_agent:
                            # Prepare update data (exclude False VAT to avoid validation issues)
                            update_data = {
                                'name': cleaned_data['name'],
                                'email': cleaned_data['email'] or False,
                                'street': cleaned_data['street'] or False,
                                'city': cleaned_data['city'] or False,
                                'zip': cleaned_data['zip'] or False,
                                'supplier_rank': 1
                            }
                            
                            # Only update VAT if it's a valid value
                            if cleaned_data['vat']:
                                update_data['vat'] = cleaned_data['vat']
                            
                            # Update agent information
                            existing_agent.write(update_data)
                            
                            # Update or create the custom address
                            existing_address = self.env['social_media.custom_address'].search([
                                ('partner_id', '=', existing_agent.id),
                                ('default', '=', True)
                            ], limit=1)
                            
                            address_data = {
                                'address': cleaned_data['street'] or '',
                                'continued_address': cleaned_data['street2'] or '',
                                'city': cleaned_data['city'] or '',
                                'postal_code': cleaned_data['zip'] or '',
                                'state_id': cleaned_data['state_id']
                            }
                            
                            if existing_address:
                                existing_address.write(address_data)
                            else:
                                # Create new address if none exists
                                address_data.update({
                                    'partner_id': existing_agent.id,
                                    'village': '',
                                    'default': True,
                                    'country_id': 109,
                                })
                                self.env['social_media.custom_address'].create(address_data)
                                
                        else:
                            # Create new agent - no existing record found by ID or email
                            create_data = {
                                'name': cleaned_data['name'],
                                'email': cleaned_data['email'] or False,
                                'street': cleaned_data['street'] or False,
                                'city': cleaned_data['city'] or False,
                                'zip': cleaned_data['zip'] or False,
                                'country_id': 109,
                                'company_id': 1,
                                'supplier_rank': 1
                            }
                            
                            # Only add VAT if it's a valid value
                            if cleaned_data['vat']:
                                create_data['vat'] = cleaned_data['vat']
                            
                            agent = self.env['res.partner'].create(create_data)
                            
                            # Create external import record
                            external_import_data = {
                                'external_import_id': agent_id,
                                'partner_id': agent.id,
                                'is_agent': True,
                                'agent_id': None
                            }
                            
                            # Only add codice fiscale if it's valid
                            if cleaned_data['l10n_it_codice_fiscale']:
                                external_import_data['l10n_it_codice_fiscale'] = cleaned_data['l10n_it_codice_fiscale']
                            
                            self.env['external.import'].create(external_import_data)
                            
                            # Create custom address
                            self.env['social_media.custom_address'].create({
                                'partner_id': agent.id,
                                'address': cleaned_data['street'] or '',
                                'continued_address': cleaned_data['street2'] or '',
                                'city': cleaned_data['city'] or '',
                                'postal_code': cleaned_data['zip'] or '',
                                'village': '',
                                'default': True,
                                'country_id': 109,
                                'state_id': cleaned_data['state_id']
                            })
                            
                            # Send welcome email (commented out in original code)
                            # if agent.email:
                            #     try:
                            #         self._send_welcome_email(agent, agent.email)
                            #         _logger.info(f"Welcome email sent to {agent.email}")
                            #     except Exception as email_error:
                            #         _logger.error(f"Error sending welcome email to {agent.email}: {email_error}")
                            
                            _logger.info(f"Created new agent {agent.name} (ID: {agent_id})")
                        
                        success_count += 1
                    
                    except Exception as e:
                        error_count += 1
                        _logger.error(f"Error processing agent {agent_name} (ID: {agent_id}): {e}")
                        continue
                
                _logger.info(f"Agent import completed. Success: {success_count}, Errors: {error_count}")
                return True
                            
        except Exception as e:
            _logger.error(f"File reading error: {e}")
            return False

    def import_all_data(self):
        _logger.info("Starting agent import process...")
        return self.import_agents()