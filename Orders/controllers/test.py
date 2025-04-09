#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xmlrpc.client
import sys
import os

def get_product_details(pricelist_id, product_id, qty, partner_id=False):
    """
    Get product price from Odoo based on pricelist, product, quantity and customer.
    
    Args:
        pricelist_id (int): ID of the pricelist
        product_id (int): ID of the product
        qty (float): Quantity
        partner_id (int, optional): ID of the partner (customer). Defaults to False.
    
    Returns:
        float or None: Product price or None if price couldn't be retrieved
    """
    try:
        url = os.environ.get("ISA_ODOO_URL", "https://isa-primapaint-staging.odoo.com")
        db = os.environ.get("ISA_ODOO_DB", "odoo-isa-isa-odoo-primapaint-14-0-staging-19484011")
        username = os.environ.get("ISA_ODOO_USERNAME", "connectorantea")
        password = os.environ.get("ISA_ODOO_PASSWORD", "connectorantea")
        
        # Ensure all IDs are integers
        pricelist_id = int(pricelist_id)
        product_id = int(product_id)
        if partner_id:
            partner_id = int(partner_id)
        
        # Initialize XML-RPC connections
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
        
        # Authenticate
        uid = common.authenticate(db, username, password, {})
        if not uid:
            print("Authentication failed. Please check your credentials.")
            return None
        
        # Get price directly using product.product and context
        product_context = {
            'pricelist': pricelist_id,
            'quantity': float(qty)  # Ensure quantity is float
        }
        
        if partner_id:
            product_context['partner'] = partner_id
        
        # Use a list with a single integer for product_id
        product_data = models.execute_kw(
            db, uid, password,
            'product.product', 
            'read',
            [[product_id]],  # Note the double brackets to ensure it's a list of ids
            {'fields': ['price', 'lst_price'], 'context': product_context}
        )
        
        price = None
        
        if product_data and len(product_data) > 0:
            # 'price' field contains the computed price with all rules applied
            if 'price' in product_data[0]:
                price = product_data[0]['price']
            elif 'lst_price' in product_data[0]:
                price = product_data[0]['lst_price']
        
        # If we couldn't get the price through the first method, try alternative
        if price is None:
            # Try to call _compute_price_rule directly
            try:
                # Create the arguments needed - using proper tuple format
                products_qty_partner = [(product_id, float(qty), partner_id or False)]
                
                # Call _compute_price_rule directly with proper list format
                result = models.execute_kw(
                    db, uid, password,
                    'product.pricelist', 
                    '_compute_price_rule',
                    [[pricelist_id], products_qty_partner]  # Note the double brackets for pricelist_id
                )
                
                # Result should be a dictionary where key is product_id and value is (price, rule_id)
                if result and product_id in result:
                    price = result[product_id][0]  # Return just the price
            except Exception as internal_error:
                print(f"Alternative method error: {internal_error}")
        
        # If we still don't have the price, get it separately
        if price is None:
            try:
                product_info = models.execute_kw(
                    db, uid, password,
                    'product.product',
                    'search_read',
                    [[['id', '=', product_id]]],
                    {'fields': ['list_price']}
                )
                
                if product_info and len(product_info) > 0 and 'list_price' in product_info[0]:
                    price = product_info[0]['list_price']
            except Exception as info_error:
                print(f"Product info retrieval error: {info_error}")
        
        return price
        
    except Exception as e:
        print(f"Error: {e}")
        return None