{
    "name": "Export Service",
    "version": "1.0",
    "summary": "Export Service",
    "sequence": 10,
    "description": "This module enables a Export Service.",

    "category": "Customer Loyalty",
    "depends": ["base", "product", "sale"],
    "data": [
        "security/ir.model.access.csv",
        "data/customer_export.xml",
        "data/order_export.xml",
        # "data/cron_data.xml",
    ],
    "demo": [],
    "installable": True,
    "application": True,
    "auto_install": False
}
