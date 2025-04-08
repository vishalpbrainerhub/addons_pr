#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xmlrpc.client
import os

def get_product_price_from_platform(pricelist_id, product_id, qty, partner_id=False):
    """
    Get product price from Odoo based on pricelist, product, quantity and customer.
    
    Args:
        pricelist_id (int): ID of the pricelist
        product_id (int): ID of the product
        qty (float): Quantity
        partner_id (int, optional): ID of the partner (customer). Defaults to False.
    
    Returns:
        float: Product price or None if unable to retrieve
    """
    # Get credentials from environment variables
    # url = os.environ["ISA_ODOO_URL"]
    # db = os.environ["ISA_ODOO_DB"]
    # username = os.environ["ISA_ODOO_USERNAME"]
    # password = os.environ["ISA_ODOO_PASSWORD"]
    url = "https://isa-primapaint-staging.odoo.com"
    db = "odoo-isa-isa-odoo-primapaint-14-0-staging-19484011"
    username = "connectorantea"
    password = "connectorantea"
    
    print(f"Connecting to Odoo at {url} with DB {db} and user {username}")
    try:
        # Initialize XML-RPC connections
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
        
        # Authenticate
        uid = common.authenticate(db, username, password, {})
        if not uid:
            return None
        
        # Set up context with pricelist and quantity
        product_context = {
            'pricelist': pricelist_id,
            'quantity': float(qty)  # Ensure quantity is passed as float
        }
        
        # Add partner to context if provided
        if partner_id:
            product_context['partner'] = partner_id
        
        # Direct approach - get price with all context applied
        product_data = models.execute_kw(
            db, uid, password,
            'product.product', 
            'read',
            [product_id], 
            {'fields': ['price'], 'context': product_context}
        )
        
        # Extract price if available
        if product_data and len(product_data) > 0 and 'price' in product_data[0]:
            return product_data[0]['price']
        
        # Fallback - use price calculation API directly
        products_qty_partner = [(product_id, float(qty), partner_id or False)]
        
        result = models.execute_kw(
            db, uid, password,
            'product.pricelist', 
            '_compute_price_rule',
            [pricelist_id, products_qty_partner]
        )
        
        if result and product_id in result:
            return result[product_id][0]
            
        return None
        
    except Exception as e:
        return None