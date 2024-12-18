# /home/dell/Documents/Projects/PrimaPaint/odoo-15.0/primapaint_addons/Export/models/res_partner.py

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