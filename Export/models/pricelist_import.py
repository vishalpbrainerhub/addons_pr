from odoo import api, models, fields
import csv
import logging
import os
from odoo.exceptions import UserError
from datetime import datetime
from pytz import UTC

_logger = logging.getLogger(__name__)

class PricelistImport(models.Model):
    _name = 'pricelist.import'
    _description = 'Pricelist Import'

    name = fields.Char(string='Import Name')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('failed', 'Failed')
    ], default='draft', string='Status')
    last_import_date = fields.Datetime('Last Import Date')

    def _get_pricelist_by_external_id(self, external_id):
        """Get pricelist by external ID with duplicate handling"""
        mapping = self.env['external.import.pricelist'].search([
            ('external_import_id', '=', int(external_id))
        ], limit=1)
        
        if mapping:
            # Check if this pricelist still exists
            if mapping.pricelist_id.exists():
                return mapping.pricelist_id
            else:
                # If pricelist was deleted, remove the mapping
                mapping.unlink()
        return False

    def _get_or_create_pricelist(self, row):
        """Get existing pricelist or create new one with duplicate handling"""
        try:
            external_id = int(row['id'])
            name = row.get('name')
            
            # First try to find by external ID mapping
            pricelist = self._get_pricelist_by_external_id(external_id)
            if pricelist:
                return pricelist
                
            # Then try to find by exact name match
            existing_pricelist = self.env['product.pricelist'].search([
                ('name', '=', name)
            ], limit=1)
            
            if existing_pricelist:
                # Create mapping for future reference
                self.env['external.import.pricelist'].create({
                    'pricelist_id': existing_pricelist.id,
                    'external_import_id': external_id
                })
                return existing_pricelist
            
            # If no existing pricelist found, create new one
            values = self._prepare_pricelist_values(row)
            new_pricelist = self.env['product.pricelist'].create(values)
            
            # Create mapping
            self.env['external.import.pricelist'].create({
                'pricelist_id': new_pricelist.id,
                'external_import_id': external_id
            })
            
            return new_pricelist
            
        except Exception as e:
            _logger.error(f"Error in _get_or_create_pricelist: {str(e)}")
            return False

    def _prepare_pricelist_values(self, row):
        """Prepare pricelist values with additional validation"""
        name = row.get('name', '').strip()
        if not name:
            raise UserError(f"Missing name for pricelist ID {row.get('id')}")
            
        return {
            'name': name,
            'discount_policy': row.get('discount_policy', 'with_discount'),
            'active': True,
        }

    def _find_product_variant(self, product_id, template_id=None):
        """Enhanced product variant search with better error handling"""
        if not product_id:
            return False

        try:
            variant_id = int(float(product_id))
            
            # Direct search by external_product_import_id
            variant = self.env['product.product'].sudo().search([
                ('external_product_import_id', '=', variant_id)
            ], limit=1)
            
            if variant:
                _logger.info(f"Found variant with external_product_import_id: {variant_id}")
                return variant

            # If template_id provided, search within that template
            if template_id:
                template = self.env['product.template'].sudo().search([
                    ('external_import_id', '=', int(float(template_id)))
                ], limit=1)
                if template:
                    variant = self.env['product.product'].sudo().search([
                        ('product_tmpl_id', '=', template.id),
                        '|',
                        ('default_code', '=', str(variant_id)),
                        ('id', '=', variant_id)
                    ], limit=1)
                    if variant:
                        _logger.info(f"Found variant through template: {template.id}")
                        return variant

            # Fallback search
            variant = self.env['product.product'].sudo().search([
                '|',
                ('default_code', '=', str(variant_id)),
                ('id', '=', variant_id)
            ], limit=1)
            
            if variant:
                _logger.info(f"Found variant through fallback search: {variant_id}")
            else:
                _logger.info(f"No variant found for ID: {variant_id}")
            
            return variant

        except Exception as e:
            _logger.error(f"Error finding product variant: {str(e)}")
            return False

    def _prepare_pricelist_item_values(self, row, pricelist_id):
        """Prepare pricelist item values with improved validation"""
        values = {
            'pricelist_id': pricelist_id,
            'min_quantity': float(row.get('item_ids/min_quantity', 0.0) or 0.0),
            'base': row.get('item_ids/base', 'list_price'),
            'compute_price': row.get('item_ids/compute_price', 'fixed'),
        }
        try:
            product_found = False
            template_id = row.get('item_ids/product_tmpl_id')
            product_id = row.get('item_ids/product_id')
            original_applied_on = row.get('item_ids/applied_on', '3_global')

            # Try to find variant first
            if product_id:
                variant = self._find_product_variant(product_id, template_id)
                if variant:
                    values.update({
                        'product_id': variant.id,
                        'applied_on': '0_product_variant',
                        'product_tmpl_id': variant.product_tmpl_id.id
                    })
                    product_found = True
                    _logger.info(f"Set variant {variant.id} for pricelist item")

            # If no variant but template exists
            if not product_found and template_id:
                template = self.env['product.template'].sudo().search([
                    ('external_import_id', '=', int(float(template_id)))
                ], limit=1)
                if template:
                    values.update({
                        'product_tmpl_id': template.id,
                        'applied_on': '1_product'
                    })
                    product_found = True
                    _logger.info(f"Set template {template.id} for pricelist item")

            # Default to global if no product found
            if not product_found:
                values['applied_on'] = '3_global'
                if product_id or template_id:
                    _logger.info(f"""
                        Product not found:
                        Template ID: {template_id}
                        Product ID: {product_id}
                        Original Applied On: {original_applied_on}
                    """)

            # Process dates
            for date_field in ['date_start', 'date_end']:
                if row.get(f'item_ids/{date_field}'):
                    try:
                        date_val = datetime.strptime(row[f'item_ids/{date_field}'], '%Y-%m-%d %H:%M:%S')
                        values[date_field] = date_val.replace(tzinfo=UTC).strftime('%Y-%m-%d %H:%M:%S')
                    except Exception as e:
                        _logger.warning(f"Invalid date format: {row[f'item_ids/{date_field}']}")

            # Process numeric fields
            numeric_fields = [
                'fixed_price', 'percent_price', 'price_discount',
                'price_surcharge', 'price_round', 'price_min_margin', 
                'price_max_margin'
            ]
            for field in numeric_fields:
                field_key = f'item_ids/{field}'
                if row.get(field_key):
                    try:
                        values[field] = float(row[field_key])
                    except (ValueError, TypeError):
                        _logger.warning(f"Invalid numeric value for {field}: {row[field_key]}")
                        continue

            return values

        except Exception as e:
            _logger.error(f"Error preparing pricelist item: {str(e)}, Row: {row}")
            return None

    def import_pricelists(self):
        """Main import function with improved error handling and recovery"""
        self.ensure_one()
        
        self.write({'state': 'running'})
        self.env.cr.commit()

        file_path = os.environ.get("LOCAL_PRICELIST_DATA_PATH")
        if not os.path.exists(file_path):
            self.write({'state': 'failed'})
            self.env.cr.commit()
            raise UserError(f"Import file not found: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                data = list(reader)

            # Group data by pricelist ID
            pricelists_data = {}
            for row in data:
                pricelist_id = row['id']
                if pricelist_id not in pricelists_data:
                    pricelists_data[pricelist_id] = []
                pricelists_data[pricelist_id].append(row)

            successful_imports = 0
            failed_imports = 0
            total_pricelists = len(pricelists_data)
            processed_names = set()  # Track processed pricelist names

            _logger.info(f"Starting import of {total_pricelists} pricelists")

            for pricelist_id, rows in pricelists_data.items():
                try:
                    pricelist_name = rows[0].get('name', '').strip()
                    
                    # Skip if we've already processed this pricelist name
                    if pricelist_name in processed_names:
                        _logger.info(f"Skipping duplicate pricelist name: {pricelist_name}")
                        continue
                        
                    pricelist = self._get_or_create_pricelist(rows[0])
                    if not pricelist:
                        failed_imports += 1
                        continue

                    processed_names.add(pricelist_name)

                    valid_items = []
                    for row in rows:
                        item_values = self._prepare_pricelist_item_values(row, pricelist.id)
                        if item_values:
                            valid_items.append(item_values)

                    if valid_items:
                        # Remove existing items
                        pricelist.item_ids.unlink()
                        # Create new items
                        self.env['product.pricelist.item'].create(valid_items)
                        
                        successful_imports += 1
                        _logger.info(f"Processed pricelist {pricelist_name} with {len(valid_items)} items")
                    else:
                        failed_imports += 1
                        _logger.error(f"No valid items found for pricelist {pricelist_name}")

                    self.env.cr.commit()

                except Exception as e:
                    failed_imports += 1
                    _logger.error(f"Error processing pricelist {pricelist_id}: {str(e)}")
                    self.env.cr.rollback()
                    continue

            final_state = 'done' if successful_imports > 0 else 'failed'
            self.write({
                'state': final_state,
                'last_import_date': fields.Datetime.now()
            })
            self.env.cr.commit()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Import Complete',
                    'message': f'Successfully imported {successful_imports} unique pricelists. Failed: {failed_imports}',
                    'type': 'success' if successful_imports > 0 else 'warning',
                }
            }

        except Exception as e:
            self.write({'state': 'failed'})
            self.env.cr.commit()
            error_msg = f"Import failed: {str(e)}"
            _logger.error(error_msg)
            raise UserError(error_msg)

    @api.model
    def _run_import_cron(self):
        """Cron job entry point"""
        try:
            import_record = self.search([('state', 'in', ['draft', 'failed'])], limit=1)
            if not import_record:
                import_record = self.create({
                    'name': 'Pricelist Import',
                    'state': 'draft'
                })
                self.env.cr.commit()

            return import_record.with_context(tracking_disable=True).import_pricelists()

        except Exception as e:
            _logger.error(f"Cron job failed: {str(e)}")
            return False