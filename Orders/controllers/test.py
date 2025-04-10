#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xmlrpc.client
import argparse
import os


def get_batch_product_details():
    return 10

def get_product_details():
    return 10

# url = os.environ.get("ISA_ODOO_URL", "https://isa-primapaint-staging.odoo.com")
#         db = os.environ.get("ISA_ODOO_DB", "odoo-isa-isa-odoo-primapaint-14-0-staging-19484011")
#         username = os.environ.get("ISA_ODOO_USERNAME", "connectorantea")
#         password = os.environ.get("ISA_ODOO_PASSWORD", "connectorantea")


#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xmlrpc.client
import sys
import argparse

def get_product_details( pricelist_id, product_id, qty, partner_id=False):
    """
    Get product details from Odoo based on pricelist, product, quantity and customer.
    
    Args:
        url (str): Odoo URL
        db (str): Database name
        username (str): Odoo username
        password (str): Odoo password
        pricelist_id (int): ID of the pricelist
        product_id (int): ID of the product
        qty (float): Quantity
        partner_id (int, optional): ID of the partner (customer). Defaults to False.
    
    Returns:
        tuple: (price, name, default_code) - Product price, name and default code
    """
    try:
        url = os.environ.get("ISA_ODOO_URL", "https://isa-primapaint-staging.odoo.com")
        db = os.environ.get("ISA_ODOO_DB", "odoo-isa-isa-odoo-primapaint-14-0-staging-19484011")
        username = os.environ.get("ISA_ODOO_USERNAME", "connectorantea")
        password = os.environ.get("ISA_ODOO_PASSWORD", "connectorantea")
        # Initialize XML-RPC connections
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
        
        # Authenticate
        uid = common.authenticate(db, username, password, {})
        if not uid:
            print("Authentication failed. Please check your credentials.")
            return None, None, None
        
        # Get price directly using product.product and context
        product_context = {
            'pricelist': pricelist_id,
            'quantity': qty
        }
        
        if partner_id:
            product_context['partner'] = partner_id
            
        product_data = models.execute_kw(
            db, uid, password,
            'product.product', 
            'read',
            [product_id], 
            {'fields': ['lst_price', 'price', 'name', 'display_name', 'default_code'], 'context': product_context}
        )
        
        price = None

        
        if product_data and len(product_data) > 0:
            if 'price' in product_data[0]:
                price = product_data[0]['price']
                print(price,"------------------price--------------------")
            elif 'lst_price' in product_data[0]:
                price = product_data[0]['lst_price']
                print(price,"------------------list price--------------------")


        if price is None:
            # Try to call _compute_price_rule directly
            try:
                # Create the arguments needed
                products_qty_partner = [(product_id, qty, partner_id or False)]
                
                # Call _compute_price_rule directly
                result = models.execute_kw(
                    db, uid, password,
                    'product.pricelist', 
                    '_compute_price_rule',
                    [pricelist_id, products_qty_partner]
                )
                
                # Result should be a dictionary where key is product_id and value is (price, rule_id)
                if result and product_id in result:
                    price = result[product_id][0]  # Return just the price
            except Exception as internal_error:
                print(f"Alternative method error: {internal_error}")
        
        # If we still don't have detailed info, get it separately
        if price is None :
            try:
                product_info = models.execute_kw(
                    db, uid, password,
                    'product.product',
                    'search_read',
                    [[['id', '=', product_id]]],
                    {'fields': ['list_price', 'name', 'display_name', 'default_code']}
                )
                
                if product_info and len(product_info) > 0:
                    # Set price if not already set
                    if price is None and 'list_price' in product_info[0]:
                        price = product_info[0]['list_price']
                    
                
            except Exception as info_error:
                print(f"Product info retrieval error: {info_error}")
        
        return price
        
    except Exception as e:
        print(f"Error: {e}")
        return None

