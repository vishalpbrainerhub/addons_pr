#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xmlrpc.client
import sys
import os
import time
import threading
from threading import Lock
import concurrent.futures
from functools import lru_cache
import random

# Enhanced caching with TTL and better efficiency
CACHE_TTL = 300  # 5 minutes cache validity
cache = {}
cache_lock = Lock()

# Global auth token to minimize authentication requests
# This is safer than trying to maintain multiple connections
global_auth_token = None
auth_token_timestamp = 0
auth_lock = Lock()

# Maximum number of concurrent workers
MAX_WORKERS = 5

# Semaphore to limit concurrent API requests
request_semaphore = threading.Semaphore(MAX_WORKERS)

def get_connection(url, type_conn='common'):
    """Get a connection to Odoo XML-RPC endpoint"""
    try:
        transport = xmlrpc.client.Transport()
        # Set reasonable timeout to prevent hanging threads
        transport.timeout = 20 if type_conn == 'models' else 10
        
        if type_conn == 'common':
            return xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", transport=transport)
        else:  # models
            return xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", transport=transport)
    except Exception as e:
        print(f"Connection error ({type_conn}): {e}")
        return None

def generate_cache_key(pricelist_id, product_id, qty, partner_id):
    """Generate a consistent cache key for price lookup"""
    try:
        # Convert all parameters to ensure consistency
        pricelist_id = int(pricelist_id) if pricelist_id else 0
        product_id = int(product_id) if product_id else 0
        qty = float(qty) if qty else 0.0
        partner_id = int(partner_id) if partner_id else 0
        
        return f"{pricelist_id}_{product_id}_{qty}_{partner_id}"
    except (ValueError, TypeError):
        # If conversion fails, create a fallback key
        return f"fallback_{str(pricelist_id)}_{str(product_id)}_{str(qty)}_{str(partner_id)}"

def get_auth_token(url, db, username, password):
    """Get a cached authentication token or create a new one"""
    global global_auth_token, auth_token_timestamp
    
    # Use a lock to prevent multiple threads from authenticating at the same time
    with auth_lock:
        current_time = time.time()
        
        # If we have a valid token, return it
        if global_auth_token and (current_time - auth_token_timestamp) < 1800:  # 30 minutes
            return global_auth_token
        
        # Otherwise, authenticate
        try:
            common = get_connection(url, 'common')
            if not common:
                return None
                
            uid = common.authenticate(db, username, password, {})
            if uid:
                global_auth_token = uid
                auth_token_timestamp = current_time
                return uid
        except Exception as e:
            print(f"Authentication error: {e}")
            return None

# Simplified product price getter with error handling and caching
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
    # Validate and convert input parameters
    try:
        pricelist_id = int(pricelist_id)
        product_id = int(product_id)
        qty = float(qty)
        if partner_id:
            partner_id = int(partner_id)
    except (ValueError, TypeError):
        return None
    
    # Generate cache key
    cache_key = generate_cache_key(pricelist_id, product_id, qty, partner_id)
    
    # Check cache first
    with cache_lock:
        if cache_key in cache:
            timestamp, price = cache[cache_key]
            if time.time() - timestamp < CACHE_TTL:
                return price
    
    # Use a semaphore to limit concurrent requests
    with request_semaphore:
        try:
            # Get connection parameters from environment
            url = os.environ.get("ISA_ODOO_URL", "https://isa-primapaint-staging.odoo.com")
            db = os.environ.get("ISA_ODOO_DB", "odoo-isa-isa-odoo-primapaint-14-0-staging-19484011")
            username = os.environ.get("ISA_ODOO_USERNAME", "connectorantea")
            password = os.environ.get("ISA_ODOO_PASSWORD", "connectorantea")
            
            # Get auth token (using global cache)
            uid = get_auth_token(url, db, username, password)
            if not uid:
                return None
            
            # Get connection to models
            models = get_connection(url, 'models')
            if not models:
                return None
            
            # Start with the most direct price retrieval method
            price = None
            
            # Method 1: Direct read with price context (preferred)
            try:
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
                    [[product_id]],
                    {'fields': ['price', 'lst_price'], 'context': product_context}
                )
                
                if product_data and len(product_data) > 0:
                    if 'price' in product_data[0]:
                        price = product_data[0]['price']
                    elif 'lst_price' in product_data[0]:
                        price = product_data[0]['lst_price']
            except Exception as e:
                # Don't print every error, just proceed to next method
                pass
            
            # Method 2: Get price from product with pricing context
            if price is None:
                try:
                    # Try to get product price through get_product_price public method
                    price_data = models.execute_kw(
                        db, uid, password,
                        'product.pricelist', 
                        'get_product_price',
                        [pricelist_id, product_id, qty, partner_id or False]
                    )
                    
                    if price_data:
                        price = float(price_data)
                except Exception:
                    pass
            
            # Method 3: Fallback to list price if needed
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
                    pass
            
            # Cache the result if we got a price
            if price is not None:
                with cache_lock:
                    cache[cache_key] = (time.time(), price)
                    
                    # Clean old cache entries periodically
                    if random.random() < 0.01:  # 1% chance to clean
                        current_time = time.time()
                        expired_keys = [k for k, (timestamp, _) in cache.items() if current_time - timestamp > CACHE_TTL]
                        for k in expired_keys:
                            cache.pop(k, None)
            
            return price
            
        except Exception as e:
            print(f"Error getting product price: {e}")
            return None

def get_batch_product_details(pricelist_id, products_data, partner_id=False):
    """
    Get prices for multiple products efficiently
    
    Args:
        pricelist_id (int): ID of the pricelist
        products_data (list): List of dictionaries with product_id and qty
        partner_id (int, optional): ID of the partner (customer). Defaults to False.
    
    Returns:
        dict: Dictionary with product_id as key and price as value
    """
    # Start with empty results
    results = {}
    
    # Handle empty input
    if not products_data:
        return results
    
    try:
        # Convert pricelist_id to int
        pricelist_id = int(pricelist_id)
        
        # First check cache for all products
        uncached_products = []
        for product in products_data:
            product_id = int(product['product_id'])
            qty = float(product['qty'])
            
            # Check cache
            cache_key = generate_cache_key(pricelist_id, product_id, qty, partner_id)
            with cache_lock:
                if cache_key in cache:
                    timestamp, price = cache[cache_key]
                    if time.time() - timestamp < CACHE_TTL:
                        results[product_id] = price
                        continue
            
            # If not in cache, add to list for processing
            uncached_products.append((pricelist_id, product_id, qty, partner_id))
        
        # If everything was cached, return immediately
        if not uncached_products:
            return results
        
        # Process uncached products in parallel using a reasonable number of workers
        worker_count = min(MAX_WORKERS, len(uncached_products))
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
            # Create futures for each product
            future_to_product = {}
            for args in uncached_products:
                _, product_id, qty, _ = args
                future = executor.submit(get_product_details, *args)
                future_to_product[future] = product_id
            
            # Process completed futures as they complete
            for future in concurrent.futures.as_completed(future_to_product):
                product_id = future_to_product[future]
                try:
                    price = future.result()
                    if price is not None:
                        results[product_id] = price
                except Exception as e:
                    print(f"Error processing product {product_id}: {e}")
        
        return results
        
    except Exception as e:
        print(f"Batch processing error: {e}")
        # Fallback to sequential processing
        for product in products_data:
            try:
                product_id = int(product['product_id'])
                if product_id not in results:
                    price = get_product_details(
                        pricelist_id, 
                        product_id, 
                        float(product['qty']), 
                        partner_id
                    )
                    if price is not None:
                        results[product_id] = price
            except Exception:
                pass
                
        return results