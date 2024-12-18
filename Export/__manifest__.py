{
    "name": "Export Service",
    "version": "1.0",
    "summary": "Export Service",
    "sequence": 10,
    "description": "This module enables a Export Service.",

    "category": "Customer Loyalty",
    "depends": ["base", "product", "sale",'contacts'],
    "data": [
        "security/ir.model.access.csv",
        "data/import_data.xml",
        "views/import_views.xml",
        "data/order_export.xml",
        "data/product_data_import.xml",
    ],
    "demo": [],
    "installable": True,
    "application": True,
    "auto_install": False
}
