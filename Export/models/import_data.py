from odoo import models, fields, api
import csv
import logging
import os
from contextlib import contextmanager
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class PartnerImport(models.Model):
    _name = 'partner.import'
    _description = 'Partner Import'

    name = fields.Char(string='Import Name')
    last_import_date = fields.Datetime()
    import_count = fields.Integer(default=0)
    skipped_count = fields.Integer(default=0)  # New field to track skipped records

    @contextmanager
    def _get_new_env(self):
        with self.pool.cursor() as new_cr:
            yield api.Environment(new_cr, self.env.uid, self.env.context)

    def _get_country_id(self, env, country_name):
        if not country_name:
            return False
        return env['res.country'].search([('name', '=', country_name)], limit=1).id

    def _check_existing_partner(self, env, partner_data):
        """Check if partner exists based on multiple criteria"""
        domain = ['|', '|', '|']
        if partner_data.get('id'):
            domain.extend([('id', '=', int(partner_data['id']))])
        if partner_data.get('vat'):
            domain.extend([('vat', '=', partner_data['vat'])])
        if partner_data.get('email'):
            domain.extend([('email', '=', partner_data['email'])])
        if partner_data.get('name'):
            domain.extend([('name', '=', partner_data['name'])])
        
        return env['res.partner'].search(domain, limit=1)

    def _process_batch(self, env, batch):
        partners_to_create = []
        created_count = 0
        skipped_count = 0
        
        for row in batch:
            try:
                # Create partner_vals for checking
                partner_vals = {
                    'name': row.get('name'),
                    'email': row.get('email'),
                    'vat': row.get('vat'),
                    'street': row.get('street'),
                    'city': row.get('city'),
                    'zip': row.get('zip'),
                    'country_id': self._get_country_id(env, row.get('country_id')),
                }
                
                if row.get('id'):
                    partner_vals['id'] = int(row['id'])

                # Check if partner exists
                existing_partner = self._check_existing_partner(env, partner_vals)
                
                if existing_partner:
                    _logger.info(f"Skipping existing partner: {partner_vals.get('name')} "
                                f"(ID: {existing_partner.id})")
                    skipped_count += 1
                    continue

                partners_to_create.append(partner_vals)
                
            except Exception as e:
                _logger.error(f"Error processing partner row {row}: {str(e)}")
                continue

        if partners_to_create:
            try:
                env['res.partner'].with_context(tracking_disable=True).create(partners_to_create)
                created_count = len(partners_to_create)
            except Exception as e:
                _logger.error(f"Error creating partners: {str(e)}")
                raise UserError(f"Error creating partners: {str(e)}")

        return created_count, skipped_count

    def import_partners(self):
        file_path = '/var/lib/odoo/export_data/In/customer-data.csv'
        if not os.path.exists(file_path):
            raise UserError(f"Partner import file not found at {file_path}")

        total_created = 0
        total_skipped = 0
        batch_size = 100  # Increased batch size for better performance

        try:
            with open(file_path, 'r', encoding='utf-8-sig') as file:  # Handle BOM if present
                reader = csv.DictReader(file)
                batch = []
                
                for row in reader:
                    batch.append(row)
                    if len(batch) >= batch_size:
                        with self._get_new_env() as new_env:
                            created, skipped = self._process_batch(new_env, batch)
                            total_created += created
                            total_skipped += skipped
                            new_env.cr.commit()
                        batch = []

                if batch:
                    with self._get_new_env() as new_env:
                        created, skipped = self._process_batch(new_env, batch)
                        total_created += created
                        total_skipped += skipped
                        new_env.cr.commit()

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
                    'message': f"Successfully imported {total_created} partners. "
                              f"Skipped {total_skipped} existing partners.",
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(f"Import failed: {str(e)}")

    @api.model
    def _run_import_cron(self):
        import_record = self.search([], limit=1) or self.create({'name': 'Auto Import Partners'})
        return import_record.import_partners()