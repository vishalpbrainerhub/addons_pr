from odoo import models, fields, api
import csv
import logging
import os
from odoo.exceptions import UserError
import random

_logger = logging.getLogger(__name__)

class PartnerImport(models.Model):
    _name = 'partner.import'
    _description = 'Partner Import'

    name = fields.Char(string='Import Name')
    last_import_date = fields.Datetime()
    import_count = fields.Integer(default=0)
    skipped_count = fields.Integer(default=0)

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

    def _get_country_id(self, country_name):
        if not country_name:
            return False
        return self.env['res.country'].search([('name', '=', country_name)], limit=1).id

    def _check_external_id(self, external_id):
        return self.env['external.import'].search([('external_import_id', '=', external_id)], limit=1)

    def _process_batch(self, batch):
        created_count = 0
        skipped_count = 0
        
        for row in batch:
            try:
                external_id = int(row.get('id', 0))
                if self._check_external_id(external_id):
                    _logger.info(f"Skipping partner with existing external ID: {external_id}")
                    skipped_count += 1
                    continue

                partner_vals = {
                    'name': row.get('name'),
                    'email': row.get('email'),
                    'customer_rank': 1,
                    'vat': row.get('vat'),
                    'street': row.get('street'),
                    'city': row.get('city'),
                    'zip': row.get('zip'),
                    'country_id': self._get_country_id(row.get('country_id')),
                }

                partner = self.env['res.partner'].with_context(tracking_disable=True).create(partner_vals)
                
                self.env['external.import'].create({
                    'partner_id': partner.id,
                    'external_import_id': external_id
                })

                if row.get('email'):
                    self._send_welcome_email(partner, row['email'])
                
                created_count += 1
                self.env.cr.commit()
                
            except Exception as e:
                _logger.error(f"Error processing partner row {row}: {str(e)}")
                continue

        return created_count, skipped_count

    def import_partners(self):
        file_path = '/var/lib/odoo/export_data/In/customer-data.csv'
        if not os.path.exists(file_path):
            raise UserError(f"Partner import file not found at {file_path}")

        total_created = 0
        total_skipped = 0
        batch_size = 100

        try:
            with open(file_path, 'r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                batch = []
                
                for row in reader:
                    batch.append(row)
                    if len(batch) >= batch_size:
                        created, skipped = self._process_batch(batch)
                        total_created += created
                        total_skipped += skipped
                        batch = []

                if batch:
                    created, skipped = self._process_batch(batch)
                    total_created += created
                    total_skipped += skipped

            self.write({
                'last_import_date': fields.Datetime.now(),
                'import_count': total_created,
                'skipped_count': total_skipped
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Partner Import Complete',
                    'message': f"Successfully imported {total_created} partners. Skipped {total_skipped} existing partners.",
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(f"Import failed: {str(e)}")

    @api.model
    def _run_import_cron(self):
        import_record = self.search([], limit=1) or self.create({'name': 'Auto Import Partners'})
        return import_record.import_partners()