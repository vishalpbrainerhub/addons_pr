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

    @contextmanager
    def _get_new_env(self):
        with self.pool.cursor() as new_cr:
            yield api.Environment(new_cr, self.env.uid, self.env.context)

    def _get_country_id(self, env, country_name):
        return env['res.country'].search([('name', '=', country_name)], limit=1).id

    def _process_batch(self, env, batch):
        partners = []
        existing_ids = set(env['res.partner'].search([]).ids)
        
        for row in batch:
            try:
                partner_id = int(row['id'])
                if partner_id in existing_ids:
                    _logger.info(f"Skipping existing partner ID: {partner_id}")
                    continue
                    
                partner_vals = {
                    'id': partner_id,
                    'name': row['name'],
                    'email': row['email'],
                    'vat': row['vat'],
                    'street': row['street'],
                    'city': row['city'],
                    'zip': row['zip'],
                    'country_id': self._get_country_id(env, row['country_id'])
                }
                partners.append(partner_vals)
            except Exception as e:
                _logger.error(f"Error processing partner: {str(e)}")
                continue

        if partners:
            env['res.partner'].with_context(tracking_disable=True).create(partners)
            return len(partners)
        return 0

    def import_partners(self):
        file_path = '/var/lib/odoo/export_data/In/customer-data.csv'
        if not os.path.exists(file_path):
            _logger.error(f"File not found at {file_path}")
            raise UserError(f"Partner import file not found. Please ensure file exists in {file_path}")

        total_success = 0
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                batch = []
                
                for row in reader:
                    batch.append(row)
                    if len(batch) >= 5:
                        with self._get_new_env() as new_env:
                            success = self._process_batch(new_env, batch)
                            total_success += success
                            new_env.cr.commit()
                        batch = []

                if batch:
                    with self._get_new_env() as new_env:
                        success = self._process_batch(new_env, batch)
                        total_success += success
                        new_env.cr.commit()

            self.write({
                'last_import_date': fields.Datetime.now(),
                'import_count': total_success
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Partner Import Complete',
                    'message': f"Imported {total_success} partners",
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(str(e))

    @api.model
    def _run_import_cron(self):
        import_record = self.search([], limit=1) or self.create({'name': 'Auto Import Partners'})
        return import_record.import_partners()