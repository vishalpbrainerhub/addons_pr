from odoo import models, fields, api
import csv
import logging
import os
from contextlib import contextmanager
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class CustomerImport(models.Model):
    _name = 'customer.import'
    _description = 'Customer Import Model'

    name = fields.Char(string='Import Name')
    last_import_date = fields.Datetime(string='Last Import Date')
    import_count = fields.Integer(string='Import Count', default=0)

    @contextmanager
    def _get_new_env(self):
        with api.Environment.manage():
            with self.pool.cursor() as new_cr:
                yield api.Environment(new_cr, self.env.uid, self.env.context)

    def _process_batch(self, batch, env):
        success_count = 0
        for row in batch:
            if not row[0].isdigit():
                continue
                
            try:
                partner_id = int(row[0])
                
                env.cr.execute("""
                    SELECT id FROM res_partner 
                    WHERE id = %s
                    FOR UPDATE SKIP LOCKED
                """, (partner_id,))
                
                if env.cr.fetchone():
                    continue

                partner_vals = {
                    'id': partner_id,
                    'name': row[1],
                    'vat': False if row[2] == 'False' else row[2],
                    'l10n_it_codice_fiscale': False if row[3] == 'False' else row[3],
                    'company_type': 'company',
                    'country_id': env.ref('base.it').id,
                }

                if len(row) > 4 and '(' in row[4]:
                    try:
                        pricelist_id = int(row[4].split(',')[0].strip('( )'))
                        partner_vals['property_product_pricelist'] = pricelist_id
                    except (ValueError, IndexError):
                        pass

                env['res.partner'].with_context(tracking_disable=True).create(partner_vals)
                success_count += 1
                _logger.info(f"Imported partner ID: {partner_id}")

            except Exception as e:
                _logger.error(f"Error processing partner {row[0]}: {str(e)}")
                continue
                
        return success_count

    def import_customers(self):
        BATCH_SIZE = 50
        # file path to import
        file_path = ''
        total_success = 0
        
        if not os.path.exists(file_path):
            raise UserError(f"Import file not found: {file_path}")

        try:
            with open(file_path, 'r') as file:
                next(file)
                csv_reader = csv.reader(file, delimiter=',', quotechar='"')
                current_batch = []
                
                for row in csv_reader:
                    current_batch.append(row)
                    
                    if len(current_batch) >= BATCH_SIZE:
                        with self._get_new_env() as new_env:
                            batch_success = self._process_batch(current_batch, new_env)
                            new_env.cr.commit()
                            total_success += batch_success
                        current_batch = []

                if current_batch:
                    with self._get_new_env() as new_env:
                        batch_success = self._process_batch(current_batch, new_env)
                        new_env.cr.commit()
                        total_success += batch_success

            with self._get_new_env() as final_env:
                import_record = final_env[self._name].browse(self.id)
                import_record.write({
                    'last_import_date': fields.Datetime.now(),
                    'import_count': total_success
                })
                final_env.cr.commit()
            
        except Exception as e:
            _logger.error(f"Import error: {str(e)}")
            raise UserError(str(e))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Import Complete',
                'message': f'Successfully imported: {total_success}',
                'type': 'success',
            }
        }

    @api.model
    def _run_import_cron(self):
        import_record = self.search([], limit=1) or self.create({'name': 'Auto Import'})
        return import_record.import_customers()