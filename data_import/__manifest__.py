{
    'name': 'Data Import Tool',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Import products, categories, pricelists and customers',
    'description': """
        This module provides a tool to import:
        - Products with categories
        - Pricelists and pricelist items
        - Customers
        with external ID mapping
    """,
    'depends': [
        'base',
        'product',
        'sale',
        'l10n_it',
          'contacts', 
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/import_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    
}