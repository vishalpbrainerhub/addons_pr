{
    "name": "Customer Rewards Program",
    "version": "1.0",
    "summary": "Earn rewards with each purchase",
    "sequence": 10,
    "description": "This module enables a rewards program within Odoo 15, allowing customers to collect points on each order which can be redeemed for discounts or special offers. Enhance customer loyalty and engagement with seamless integration.",

    "category": "Customer Loyalty",
    "depends": ["base", "product", "sale"],
    "data": [
        "security/ir.model.access.csv",
        "views/rewards.xml"
    ],
    "demo": [],
    "installable": True,
    "application": True,
    "auto_install": False
}
