from odoo import api, models, fields
import csv
import logging
import os
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ProductImport(models.Model):
    _name = 'product.import'
    _description = 'Product Import'

    name = fields.Char(string='Import Name')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('failed', 'Failed')
    ], default='draft', string='Status')
    last_import_date = fields.Datetime('Last Import Date')

    def _get_category_id(self, env, category_str):
        """Get category ID from name, create if doesn't exist"""
        try:
            if not category_str:
                return 1

            # Extract category path from string
            clean_str = category_str.replace("(", "").replace(")", "").replace("'", "")
            parts = clean_str.split(",", 1)
            
            category_path = ['All']
            if len(parts) > 1:
                category_names = [x.strip() for x in parts[1].split('/')]
                category_path.extend([x for x in category_names if x])

            # Create category hierarchy
            parent_id = 1
            for category_name in category_path:
                if not category_name:
                    continue

                category = env['product.category'].search([
                    ('name', '=', category_name),
                    ('parent_id', '=', parent_id)
                ], limit=1)

                if not category:
                    category = env['product.category'].create({
                        'name': category_name,
                        'parent_id': parent_id
                    })
                    _logger.info(f"Created category: {category_name}")

                parent_id = category.id

            return parent_id
        except Exception as e:
            _logger.error(f"Error creating category {category_str}: {str(e)}")
            return 1

    def _prepare_product_values(self, row, category_id):
        """Prepare product values dictionary"""
        values = {
            'name': row.get('name'),
            'default_code': str(row.get('id', '')),
            'code_': str(row.get('id', '')),
            'list_price': float(row.get('list_price', 0)),
            'categ_id': category_id,
            'external_import_id': int(row.get('id', 0)),
            'sale_ok': True if row.get('sale_ok', '').lower() == 'true' else False,
            'purchase_ok': True if row.get('purchase_ok', '').lower() == 'true' else False,
            'active': True
        }

        # Handle image if present in base64 format
        # image_data = row.get('image_1920')
        # if image_data:
        #     try:
        #         # Clean up the base64 string if needed
        #         if isinstance(image_data, str):
        #             values['image_1920'] = image_data
        #     except Exception as e:
        #         _logger.error(f"Error processing image for product {row.get('name')}: {str(e)}")

        return values

    def import_products(self):
        """Main import function"""
        self.ensure_one()
        
        # Set initial state
        self.write({'state': 'running'})
        self.env.cr.commit()

        file_path = os.environ.get("LOCAL_PRODUCT_DATA_PATH")
        if not os.path.exists(file_path):
            self.write({'state': 'failed'})
            self.env.cr.commit()
            raise UserError(f"Import file not found: {file_path}")

        try:
            # Read all data first
            with open(file_path, 'r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                data = list(reader)

            total_count = len(data)
            processed_count = 0
            _logger.info(f"Starting import of {total_count} products")

            # Pre-fetch existing products
            product_template = self.env['product.template'].with_context(active_test=False)
            existing_products = product_template.search([('default_code', '!=', False)])
            existing_dict = {str(p.default_code): p.id for p in existing_products if p.default_code}

            # Process in batches
            batch_size = 1000
            for i in range(0, total_count, batch_size):
                batch = data[i:i + batch_size]
                products_to_create = []
                
                for row in batch:
                    try:
                        if not row.get('name'):
                            continue

                        category_id = self._get_category_id(self.env, row.get('categ_id'))
                        values = self._prepare_product_values(row, category_id)
                        code = str(row.get('id', ''))

                        if code in existing_dict:
                            product_template.browse(existing_dict[code]).write(values)
                        else:
                            products_to_create.append(values)

                    except Exception as e:
                        _logger.error(f"Error processing product {row.get('name')}: {str(e)}")
                        continue

                # Create new products
                if products_to_create:
                    product_template.with_context(
                        mail_create_nosubscribe=True,
                        mail_create_nolog=True,
                        tracking_disable=True,
                        import_file=True
                    ).create(products_to_create)

                processed_count += len(batch)
                _logger.info(f"Processed {processed_count} of {total_count} products")
                
                # Commit after each batch
                self.write({'last_import_date': fields.Datetime.now()})
                self.env.cr.commit()

            # Final update
            self.write({
                'state': 'done',
                'last_import_date': fields.Datetime.now()
            })
            self.env.cr.commit()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Import Complete',
                    'message': f'Successfully processed {processed_count} products',
                    'type': 'success',
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
                    'name': 'Product Import',
                    'state': 'draft'
                })
                self.env.cr.commit()

            return import_record.with_context(tracking_disable=True).import_products()

        except Exception as e:
            _logger.error(f"Cron job failed: {str(e)}")
            return False