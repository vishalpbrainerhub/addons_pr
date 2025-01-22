from odoo import api, models, fields
import csv
import logging
import os
from odoo.exceptions import UserError
from datetime import datetime
from psycopg2.extras import execute_values

_logger = logging.getLogger(__name__)


class PricelistImport(models.Model):
    _name = 'pricelist.import'
    _description = 'Pricelist Import'

    name = fields.Char(string='Import Name')
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
    last_processed_id = fields.Integer(default=0)
    error_log = fields.Text(string='Error Log')

    def _check_existing_external_ids(self, external_ids):
        if not external_ids:
            return set()
        
        self.env.cr.execute("""
            SELECT external_import_id 
            FROM external_import_pricelist 
            WHERE external_import_id = ANY(%s)
        """, (list(external_ids),))
        
        return {r[0] for r in self.env.cr.fetchall()}

    def _bulk_insert_pricelists(self, pricelist_vals):
        query = """
            INSERT INTO product_pricelist 
            (name, discount_policy, currency_id, active, create_date, write_date)
            VALUES %s RETURNING id
        """
        params = [(
            p['name'], 
            p.get('discount_policy', 'without_discount'),
            p.get('currency_id', self.env.ref('base.EUR').id),
            True,
            datetime.now(), 
            datetime.now()
        ) for p in pricelist_vals]
        
        execute_values(self.env.cr, query, params, page_size=100)
        return [r[0] for r in self.env.cr.fetchall()]

    def _bulk_insert_pricelist_items(self, item_vals):
        query = """
            INSERT INTO product_pricelist_item
            (pricelist_id, product_tmpl_id, base, applied_on, compute_price, 
             min_quantity, fixed_price, percent_price, date_end, create_date, write_date)
            VALUES %s
        """
        params = [(
            item['pricelist_id'],
            item['product_tmpl_id'],
            'list_price',
            '1_product',
            item['compute_price'],
            item.get('min_quantity', 1.0),
            item.get('fixed_price', 0.0),
            item.get('percent_price', 0.0),
            item.get('date_end'),
            datetime.now(),
            datetime.now()
        ) for item in item_vals]
        
        execute_values(self.env.cr, query, params, page_size=100)

    def _bulk_insert_external_ids(self, pricelist_ids, external_ids):
        query = """
            INSERT INTO external_import_pricelist (pricelist_id, external_import_id)
            VALUES %s
        """
        params = list(zip(pricelist_ids, external_ids))
        execute_values(self.env.cr, query, params, page_size=100)

    def _process_batch(self, batch, existing_external_ids):
        created_pricelists = []
        pricelist_items = []
        new_external_records = []
        
        for row in batch:
            try:
                external_id = int(row.get('id', 0))
                if external_id in existing_external_ids:
                    continue

                pricelist_vals = {
                    'name': row['name'],
                    'discount_policy': row.get('discount_policy', 'without_discount'),
                }
                
                product = self._find_product(row.get('item_idsproduct_tmpl_id'))
                if not product:
                    continue

                created_pricelists.append(pricelist_vals)
                new_external_records.append(external_id)

                compute_price = 'fixed' if row.get('item_idsfixed_price') != 'percentage' else 'percentage'
                
                item_vals = {
                    'compute_price': compute_price,
                    'product_tmpl_id': product.id,
                    'min_quantity': float(row.get('item_idsmin_quantity', 1.0))
                }

                if compute_price == 'percentage' and row.get('item_idsdiscount1'):
                    item_vals['percent_price'] = -float(row['item_idsdiscount1'])
                elif row.get('item_idspercent_price'):
                    item_vals['fixed_price'] = float(row['item_idspercent_price'])

                if row.get('item_idsdate_end'):
                    item_vals['date_end'] = datetime.strptime(row['item_idsdate_end'], '%Y-%m-%d %H:%M:%S')

                pricelist_items.append(item_vals)
                
            except Exception as e:
                _logger.error(f"Error processing pricelist row {row}: {str(e)}")
                continue

        if created_pricelists:
            try:
                pricelist_ids = self._bulk_insert_pricelists(created_pricelists)
                
                for item, pricelist_id in zip(pricelist_items, pricelist_ids):
                    item['pricelist_id'] = pricelist_id
                
                self._bulk_insert_pricelist_items(pricelist_items)
                self._bulk_insert_external_ids(pricelist_ids, new_external_records)
                
                return len(created_pricelists), len(batch) - len(created_pricelists)
            except Exception as e:
                _logger.error(f"Error in batch processing: {str(e)}")
                raise

        return 0, len(batch)

    def _find_product(self, product_tmpl_id):
        if not product_tmpl_id:
            return False
            
        try:
            external_id = int(product_tmpl_id)
            product = self.env['product.template'].search([
                ('external_import_id', '=', external_id)
            ], limit=1)
            
            if not product:
                product = self.env['product.template'].search([
                    '|',
                    ('code_', '=', str(product_tmpl_id)),
                    ('name', '=', str(product_tmpl_id))
                ], limit=1)
            
            return product
            
        except ValueError:
            return self.env['product.template'].search([
                '|',
                ('code_', '=', str(product_tmpl_id)),
                ('name', '=', str(product_tmpl_id))
            ], limit=1)

    def _count_total_rows(self, file_path):
        with open(file_path, 'r', encoding='utf-8-sig') as file:
            return sum(1 for _ in file) - 1

    def import_pricelists(self):
        file_path = os.environ["PRICELIST_DATA_PATH"]
        if not os.path.exists(file_path):
            raise UserError("Pricelist import file not found")

        self.write({
            'state': 'in_progress',
            'total_rows': self._count_total_rows(file_path),
            'processed_rows': 0,
            'progress': 0.0,
            'error_log': ''
        })

        total_created = 0
        total_skipped = 0
        batch_size = 1000
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                batch = []
                external_ids = set()
                
                for row in reader:
                    batch.append(row)
                    external_ids.add(int(row.get('id', 0)))
                    
                    if len(batch) >= batch_size:
                        existing_ids = self._check_existing_external_ids(external_ids)
                        created, skipped = self._process_batch(batch, existing_ids)
                        
                        total_created += created
                        total_skipped += skipped
                        self.processed_rows += len(batch)
                        self.progress = (self.processed_rows / self.total_rows) * 100
                        
                        self.env.cr.commit()
                        
                        batch = []
                        external_ids = set()

                if batch:
                    existing_ids = self._check_existing_external_ids(external_ids)
                    created, skipped = self._process_batch(batch, existing_ids)
                    total_created += created
                    total_skipped += skipped
                    self.processed_rows += len(batch)
                    self.progress = 100.0

            self.write({
                'last_import_date': fields.Datetime.now(),
                'import_count': total_created,
                'skipped_count': total_skipped,
                'state': 'done'
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Pricelist Import Complete',
                    'message': f"Successfully imported {total_created} pricelists. Skipped {total_skipped} existing pricelists.",
                    'type': 'success',
                }
            }

        except Exception as e:
            error_message = f"Import failed: {str(e)}"
            _logger.error(error_message)
            self.write({
                'state': 'failed',
                'error_log': error_message
            })
            raise UserError(error_message)

    @api.model
    def _run_import_cron(self):
        import_record = self.search([], limit=1) or self.create({'name': 'Auto Import Pricelists'})
        return import_record.import_pricelists()