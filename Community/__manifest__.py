{
    "name": "Community Application",
    "version": "1.0",
    "license": "LGPL-3",
    "summary": "A comprehensive Social Media Module for posting images and videos",
    "sequence": 10,
    "description": "This module enhances Odoo 15 by introducing advanced social media functionalities, allowing users to engage by posting images seamlessly.",
    "category": "Social Media Tools",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "views/post_views.xml"
    ],
    "i18n": [
        "i18n/it.po" 
    ],
    "demo": [],
    "installable": True,
    "application": True,
    "auto_install": False
}
