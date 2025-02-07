from odoo import api, models, fields, _
import csv
import logging
import os
from odoo.exceptions import UserError
import re
from contextlib import contextmanager

_logger = logging.getLogger(__name__)

class PartnerImport(models.Model):
    _name = 'partner.import'
    _description = 'Partner Import'

    name = fields.Char(string='Import Name', required=True)
    last_import_date = fields.Datetime()
    import_count = fields.Integer(default=0)
    skipped_count = fields.Integer(default=0)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('failed', 'Failed')
    ], default='draft')
    progress = fields.Float(default=0.0)
    total_rows = fields.Integer(default=0)
    processed_rows = fields.Integer(default=0)
    error_log = fields.Text(string='Error Log')
    batch_size = fields.Integer(default=1000, string='Batch Size')

    @contextmanager
    def _get_new_env(self):
        """Create a new environment for transaction management."""
        with api.Environment.manage():
            with self.pool.cursor() as new_cr:
                yield api.Environment(new_cr, self.env.uid, self.env.context)

    def _extract_pricelist_info(self, pricelist_data):
        """Extract pricelist name from string format '(id, name)' and remove (EUR) suffix."""
        try:
            if not pricelist_data or pricelist_data == 'False':
                return False
            
            match = re.match(r"\((\d+),\s*'([^']+)'\)", pricelist_data)
            if match:
                pl_name = match.group(2)
                if pl_name.endswith(' (EUR)'):
                    pl_name = pl_name[:-6]
                return pl_name
            
            return False
        except Exception as e:
            _logger.error(f"Error extracting pricelist info: {str(e)}")
            return False

    def _get_pricelist(self, env, pricelist_data):
        """Get existing pricelist or return public pricelist."""
        try:
            pl_name = self._extract_pricelist_info(pricelist_data)
            if not pl_name:
                return env['product.pricelist'].search([('name', '=', 'Public Pricelist')], limit=1).id

            pricelist = env['product.pricelist'].search([
                ('name', '=', pl_name)
            ], limit=1)

            if not pricelist:
                return env['product.pricelist'].search([('name', '=', 'Public Pricelist')], limit=1).id

            return pricelist.id
        except Exception as e:
            _logger.error(f"Error handling pricelist: {str(e)}")
            return env['product.pricelist'].search([('name', '=', 'Public Pricelist')], limit=1).id

    def _prepare_partner_data(self, env, partner_data):
        """Prepare partner data with pricelist."""
        try:
            vals = {
                'name': partner_data['name'].strip('"'),
                'email': partner_data['email'] if partner_data['email'] != 'False' else False,
                'vat': partner_data['vat'] if partner_data['vat'] != 'False' else False,
                'street': partner_data['street'] if partner_data['street'] != 'False' else False,
                'city': partner_data['city'] if partner_data['city'] != 'False' else False,
                'zip': partner_data['zip'] if partner_data['zip'] != 'False' else False,
                'l10n_it_codice_fiscale': partner_data['l10n_it_codice_fiscale'] if partner_data['l10n_it_codice_fiscale'] != 'False' else False,
            }

            if partner_data.get('country_id') and partner_data['country_id'] != 'False':
                country = env['res.country'].search([('name', '=', partner_data['country_id'])], limit=1)
                if country:
                    vals['country_id'] = country.id

            if partner_data.get('property_product_pricelist'):
                pricelist_id = self._get_pricelist(env, partner_data['property_product_pricelist'])
                if pricelist_id:
                    vals['property_product_pricelist'] = pricelist_id

            return vals
        except Exception as e:
            _logger.error(f"Error preparing partner data: {str(e)}")
            return False

    def _process_batch(self, env, batch_data):
        """Process a batch of partner records."""
        batch_results = {
            'created': 0,
            'updated': 0,
            'errors': []
        }

        for partner_data in batch_data:
            try:
                vals = self._prepare_partner_data(env, partner_data)
                if not vals:
                    batch_results['errors'].append(f"Failed to prepare data for partner {partner_data.get('name')}")
                    continue

                domain = []
                if vals.get('vat'):
                    domain.append(('vat', '=', vals['vat']))
                if vals.get('l10n_it_codice_fiscale'):
                    domain.append(('l10n_it_codice_fiscale', '=', vals['l10n_it_codice_fiscale']))
                
                if domain:
                    domain = ['|'] * (len(domain) - 1) + domain
                    partner = env['res.partner'].search(domain, limit=1)
                else:
                    partner = False

                if partner:
                    partner.write(vals)
                    batch_results['updated'] += 1
                else:
                    env['res.partner'].create(vals)
                    batch_results['created'] += 1

            except Exception as e:
                batch_results['errors'].append(f"Error processing partner {partner_data.get('name')}: {str(e)}")
                _logger.error(f"Batch processing error: {str(e)}", exc_info=True)

        return batch_results

    def import_partners(self):
        """Main import method with batch processing."""
        file_path = os.environ.get("LOCAL_CUSTOMER_DATA_PATH")
        if not file_path or not os.path.exists(file_path):
            raise UserError(_("Partner data file not found"))

        self.write({
            'state': 'in_progress',
            'progress': 0.0,
            'error_log': '',
        })

        try:
            # Count total rows
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                total_rows = sum(1 for row in f) - 1  # Subtract header row
            
            self.write({'total_rows': total_rows})

            # Initialize counters
            processed = 0
            total_created = 0
            total_updated = 0
            all_errors = []
            current_batch = []

            # Process in batches
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    current_batch.append(row)
                    
                    # Process batch when it reaches the batch size
                    if len(current_batch) >= self.batch_size:
                        with self._get_new_env() as new_env:
                            batch_results = self._process_batch(new_env, current_batch)
                            
                            total_created += batch_results['created']
                            total_updated += batch_results['updated']
                            all_errors.extend(batch_results['errors'])
                            
                            processed += len(current_batch)
                            self.write({
                                'processed_rows': processed,
                                'progress': (processed / total_rows * 100) if total_rows else 0
                            })
                            self.env.cr.commit()
                            
                        current_batch = []  # Reset batch

                # Process remaining records
                if current_batch:
                    with self._get_new_env() as new_env:
                        batch_results = self._process_batch(new_env, current_batch)
                        total_created += batch_results['created']
                        total_updated += batch_results['updated']
                        all_errors.extend(batch_results['errors'])
                        processed += len(current_batch)

            # Update final status
            final_state = 'done' if not all_errors else 'failed'
            self.write({
                'state': final_state,
                'last_import_date': fields.Datetime.now(),
                'import_count': total_created + total_updated,
                'skipped_count': len(all_errors),
                'error_log': '\n'.join(all_errors) if all_errors else '',
                'processed_rows': processed,
                'progress': 100.0
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Import Complete'),
                    'message': _(
                        'Processed %(total)d partners: %(created)d created, %(updated)d updated, %(failed)d failed'
                    ) % {
                        'total': processed,
                        'created': total_created,
                        'updated': total_updated,
                        'failed': len(all_errors)
                    },
                    'type': 'success' if not all_errors else 'warning',
                    'sticky': True,
                }
            }

        except Exception as e:
            self.write({
                'state': 'failed',
                'error_log': str(e)
            })
            raise UserError(_("Import failed: %s") % str(e))

    @api.model
    def _run_import_cron(self):
        """Cron job entry point."""
        import_record = self.search([], limit=1) or self.create({'name': 'Auto Import'})
        return import_record.import_partners()