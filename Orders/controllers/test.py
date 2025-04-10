#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xmlrpc.client
import sys
import os
import functools
import time
from threading import Lock

# Add caching with TTL
cache = {}
cache_lock = Lock()
CACHE_TTL = 300  # 5 minutes cache validity

# Connection pool for XML-RPC
connection_pool = {}
connection_lock = Lock()

def get_connection(url, type_conn='common'):
    """Get a cached XML-RPC connection or create a new one"""
    conn_key = f"{url}_{type_conn}"
    
    with connection_lock:
        if conn_key not in connection_pool:
            if type_conn == 'common':
                connection_pool[conn_key] = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
            else:  # models
                connection_pool[conn_key] = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
        
        return connection_pool[conn_key]

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
    # Convert input parameters
    pricelist_id = int(pricelist_id)
    product_id = int(product_id)
    qty = float(qty)
    if partner_id:
        partner_id = int(partner_id)
    
    # Generate cache key
    cache_key = f"{pricelist_id}_{product_id}_{qty}_{partner_id}"
    
    # Check cache first
    with cache_lock:
        if cache_key in cache:
            timestamp, price = cache[cache_key]
            if time.time() - timestamp < CACHE_TTL:
                return price
    
    try:
        # Get connection parameters from environment
        url = os.environ.get("ISA_ODOO_URL", "https://isa-primapaint-staging.odoo.com")
        db = os.environ.get("ISA_ODOO_DB", "odoo-isa-isa-odoo-primapaint-14-0-staging-19484011")
        username = os.environ.get("ISA_ODOO_USERNAME", "connectorantea")
        password = os.environ.get("ISA_ODOO_PASSWORD", "connectorantea")
        
        # Get connections from pool
        common = get_connection(url, 'common')
        models = get_connection(url, 'models')
        
        # Authenticate
        uid = common.authenticate(db, username, password, {})
        if not uid:
            print("Authentication failed. Please check your credentials.")
            return None
        
        # Create context with all params for a single API call
        product_context = {
            'pricelist': pricelist_id,
            'quantity': qty
        }
        
        if partner_id:
            product_context['partner'] = partner_id
        
        price = None
        
        # Try method 1: Direct read with proper context
        product_data = models.execute_kw(
            db, uid, password,
            'product.product', 
            'read',
            [[product_id]],
            {'fields': ['price', 'lst_price'], 'context': product_context}
        )
        
        if product_data and len(product_data) > 0:
            # Get price from response
            if 'price' in product_data[0]:
                price = product_data[0]['price']
            elif 'lst_price' in product_data[0]:
                price = product_data[0]['lst_price']
        
        # If price is still None, try alternative method
        if price is None:
            try:
                # Method 2: Try _compute_price_rule directly
                products_qty_partner = [(product_id, qty, partner_id or False)]
                
                result = models.execute_kw(
                    db, uid, password,
                    'product.pricelist', 
                    '_compute_price_rule',
                    [[pricelist_id], products_qty_partner]
                )
                
                if result and product_id in result:
                    price = result[product_id][0]
            except Exception:
                # No need to print every failure
                pass
        
        # Final fallback to list price
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
            except Exception:
                # No need to print every failure
                pass
        
        # Cache the result
        if price is not None:
            with cache_lock:
                cache[cache_key] = (time.time(), price)
                
                # Clean old cache entries (optional)
                current_time = time.time()
                expired_keys = [k for k, (timestamp, _) in cache.items() if current_time - timestamp > CACHE_TTL]
                for k in expired_keys:
                    cache.pop(k, None)
        
        return price
        
    except Exception as e:
        print(f"Error: {e}")
        return None

# Batch price retrieval for multiple products
def get_batch_product_details(pricelist_id, products_data, partner_id=False):
    """
    Get prices for multiple products in one batch
    
    Args:
        pricelist_id (int): ID of the pricelist
        products_data (list): List of dictionaries with product_id and qty
        partner_id (int, optional): ID of the partner (customer). Defaults to False.
    
    Returns:
        dict: Dictionary with product_id as key and price as value
    """
    results = {}
    
    # First check cache for all products
    uncached_products = []
    
    for product in products_data:
        product_id = int(product['product_id'])
        qty = float(product['qty'])
        
        cache_key = f"{pricelist_id}_{product_id}_{qty}_{partner_id}"
        
        with cache_lock:
            if cache_key in cache:
                timestamp, price = cache[cache_key]
                if time.time() - timestamp < CACHE_TTL:
                    results[product_id] = price
                    continue
        
        uncached_products.append((product_id, qty))
    
    if not uncached_products:
        return results
    
    try:
        # Get connection parameters from environment
        url = os.environ.get("ISA_ODOO_URL", "https://isa-primapaint-staging.odoo.com")
        db = os.environ.get("ISA_ODOO_DB", "odoo-isa-isa-odoo-primapaint-14-0-staging-19484011")
        username = os.environ.get("ISA_ODOO_USERNAME", "connectorantea")
        password = os.environ.get("ISA_ODOO_PASSWORD", "connectorantea")
        
        # Get connections from pool
        common = get_connection(url, 'common')
        models = get_connection(url, 'models')
        
        # Authenticate once
        uid = common.authenticate(db, username, password, {})
        if not uid:
            print("Authentication failed. Please check your credentials.")
            return results
        
        # Batch retrieve for all products at once
        product_ids = [p[0] for p in uncached_products]
        
        # Try _compute_price_rule for all products at once
        products_qty_partner = [(prod_id, qty, partner_id or False) for prod_id, qty in uncached_products]
        
        try:
            pricing_result = models.execute_kw(
                db, uid, password,
                'product.pricelist', 
                '_compute_price_rule',
                [[pricelist_id], products_qty_partner]
            )
            
            if pricing_result:
                for product_id, qty in uncached_products:
                    if product_id in pricing_result:
                        price = pricing_result[product_id][0]
                        results[product_id] = price
                        
                        # Cache result
                        cache_key = f"{pricelist_id}_{product_id}_{qty}_{partner_id}"
                        with cache_lock:
                            cache[cache_key] = (time.time(), price)
        except Exception:
            # If batch fails, fall back to individual calls
            for product_id, qty in uncached_products:
                if product_id not in results:
                    price = get_product_details(pricelist_id, product_id, qty, partner_id)
                    if price is not None:
                        results[product_id] = price
        
        return results
        
    except Exception as e:
        print(f"Batch error: {e}")
        return results