

from odoo import models, fields, api




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