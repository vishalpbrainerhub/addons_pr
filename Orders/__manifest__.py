{
    "name": "Products and Orders Management",
    "version": "1.0",
    "license": "LGPL-3",
    "summary": "Comprehensive management of products and orders within Odoo 15",
    "sequence": 10,
    "description": "This module facilitates streamlined management of products and orders, integrating seamlessly with Odoo 15. It offers advanced features to enhance the handling of sales and product inventories.",
    "category": "Sales Management",
    "depends": ["base", "product", "sale"],
    "data": [
        "security/ir.model.access.csv",
        "views/orders_view.xml",
        "views/product_view.xml",
    ],
    "demo": [],
    "installable": True,
    "application": True,
    "auto_install": False
}
