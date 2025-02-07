

from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Add fiscal code field only if it doesn't exist
    if not hasattr(models.Model, 'l10n_it_codice_fiscale'):
        l10n_it_codice_fiscale = fields.Char(
            string='Fiscal Code',
            size=16,
            help="Italian Fiscal Code (Codice Fiscale)"
        )

    @api.model
    def create(self, vals):
        """Override create to handle fiscal code formatting"""
        if vals.get('l10n_it_codice_fiscale'):
            vals['l10n_it_codice_fiscale'] = vals['l10n_it_codice_fiscale'].upper()
        return super(ResPartner, self).create(vals)

    def write(self, vals):
        """Override write to handle fiscal code formatting"""
        if vals.get('l10n_it_codice_fiscale'):
            vals['l10n_it_codice_fiscale'] = vals['l10n_it_codice_fiscale'].upper()
        return super(ResPartner, self).write(vals)
    


class Partner_External_import_id(models.Model):
    _name = 'external.import'
    _description = 'External Import ID'
    
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, ondelete='cascade')
    external_import_id = fields.Integer(string='External Import ID', required=True)
    


    
class PricelistExternalImport(models.Model):
    _name = 'external.import.pricelist'
    _description = 'External Import ID for Pricelist'
    
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist', required=True, ondelete='cascade')
    external_import_id = fields.Integer(string='External Import ID', required=True)
    _sql_constraints = [
        ('unique_pricelist_external_id', 'unique(external_import_id)', 'External Import ID must be unique!')
    ]
    
    
class ProductPricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Update domain for product_id field"""
        domain = []
        if self.product_tmpl_id:
            domain = [('product_tmpl_id', '=', self.product_tmpl_id.id)]
        return {'domain': {'product_id': domain}}