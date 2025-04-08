from odoo import http, fields
from odoo.http import request, Response
from odoo.osv import expression
import json
from .user_authentication import SocialMediaAuth
import random
import math
from .helper_functions import ProductPriceController
import os
import base64


class MobileEcommerceApiController(http.Controller):    
    
    def get_product_list_price(self, partner_id, page=1, page_size=20, category_ids=None, search_term=None):
        """
        Get paginated product list with prices
        
        Args:
            partner_id: ID of the partner
            page: Page number (default: 1)
            page_size: Number of items per page (default: 20)
            category_ids: List of category IDs to filter by (optional)
            search_term: Search term to filter products by code or name (optional)
        """
        cr = request.env.cr
        env = request.env
        
        cr.execute("""
            SELECT 
                rp.id as partner_id,
                rp.name as partner_name,
                pp.id as pricelist_id,
                pp.name as pricelist_name
            FROM res_partner rp
            LEFT JOIN ir_property ip ON ip.res_id = CONCAT('res.partner,', rp.id)
            LEFT JOIN product_pricelist pp ON pp.id = CAST(SUBSTRING(ip.value_reference FROM 'product.pricelist,(.*)') AS INTEGER)
            WHERE ip.name = 'property_product_pricelist'
            AND rp.id = %s
        """, (partner_id,))
        
        result = cr.fetchone()
        data = []
        total_items = 0
        
        if result and result[2]:  # if pricelist_id exists
            pricelist_id = result[2]
            pricelist = env['product.pricelist'].sudo().browse(pricelist_id)
            
            # Get all pricelist items first to calculate total
            all_pricelist_items = pricelist.item_ids
            
            # If we're filtering by category or search term, don't apply pagination initially
            if category_ids or search_term:
                pricelist_items = all_pricelist_items
            else:
                total_items = len(all_pricelist_items)
                # Calculate pagination
                start_idx = (page - 1) * page_size
                end_idx = start_idx + page_size
                # Get paginated items
                pricelist_items = all_pricelist_items[start_idx:end_idx]
            
            count = 0
            for item in pricelist_items:
                count += 1
                if item.product_tmpl_id.id:
                    domain = [
                        ('id', '=', item.product_tmpl_id.id)
                    ]
                    
                    # Add category filter if specified
                    if category_ids:
                        domain.append(('categ_id', 'in', category_ids))

                    # Add search term filter if specified
                    if search_term:
                        search_domain = ['|',
                            ('name', 'ilike', search_term),
                            ('default_code', 'ilike', search_term)
                        ]
                        domain = expression.AND([domain, search_domain])

                    product_info = env['product.template'].sudo().search_read(domain, [
                        'name', 'list_price', 'active', 'barcode', 'color', 'discount', 
                        'is_published', 'rewards_score' ,'categ_id', 'code_','image_1920','default_code','external_id'
                    ])
                    
                    # Skip if no product found
                    if not product_info:
                        continue
                    
                    price = 0
                    if item.compute_price == 'percentage':
                        price = item.percent_price
                    elif item.compute_price == 'fixed':
                        price = item.fixed_price
                    elif item.compute_price == 'formula':
                        price = product_info[0]['list_price'] * (1 - (item.price_discount / 100))
                        
                    product_dict = {
                        'name': product_info[0]['name'],
                        'list_price': price,
                        'active': product_info[0]['active'],
                        'barcode': product_info[0]['barcode'],
                        'color': product_info[0]['color'],
                        'id': item.product_tmpl_id.id,
                        'discount': product_info[0].get('discount', 0),
                        'is_published': product_info[0].get('is_published', False),
                        'rewards_score': product_info[0].get('rewards_score', 0),
                        'code_': product_info[0].get('default_code', False),
                        'min_quantity': [{"min_quantity": item.min_quantity, "price": price}],
                        'category_id': product_info[0]['categ_id'][0],
                        'image_1920': product_info[0]['image_1920'] or '',
                        'external_id': product_info[0]['external_id']
                    }
                    if item.product_tmpl_id.id not in [p['id'] for p in data]:
                        data.append(product_dict)
                    else:                    
                        for p in data:
                            if p['id'] == item.product_tmpl_id.id:
                                dict = {
                                    'min_quantity': item.min_quantity,
                                    'price': price
                                }
                                p['min_quantity'].append(dict)
                                break
                            
                elif item.categ_id.id:
                    # If filtering by category_ids, check if this item's category is in the list
                    if category_ids and item.categ_id.id not in category_ids:
                        continue
                        
                    domain = [('categ_id', '=', item.categ_id.id)]
                    
                    # If filtering by category_ids, add the filter to the domain
                    if category_ids:
                        domain = [('categ_id', 'in', category_ids)]
                    
                    # Add search term filter if specified
                    if search_term:
                        search_domain = ['|',
                            ('name', 'ilike', search_term),
                            ('default_code', 'ilike', search_term)
                        ]
                        domain = expression.AND([domain, search_domain])
                    
                    products_in_category = env['product.template'].sudo().search_read(domain, [
                        'name', 'list_price', 'active', 'barcode', 'color', 'discount', 
                        'is_published', 'rewards_score', 'code_', 'categ_id','image_1920','default_code','external_id'
                    ])
                    
                    # Process each product in the category
                    for product_info in products_in_category:
                        price = 0
                        if item.compute_price == 'percentage':
                            price = item.percent_price
                        elif item.compute_price == 'fixed':
                            price = item.fixed_price
                        elif item.compute_price == 'formula':
                            price = product_info['list_price'] * (1 - (item.price_discount / 100))
                            
                        # FIX: Initialize min_quantity as a list instead of an integer
                        product_dict = {
                            'name': product_info['name'],
                            'list_price': price,
                            'active': product_info['active'],
                            'barcode': product_info['barcode'],
                            'color': product_info['color'],
                            'id': product_info['id'],
                            'discount': product_info.get('discount', 0),
                            'is_published': product_info.get('is_published', False),
                            'rewards_score': product_info.get('rewards_score', 0),
                            'code_': product_info.get('default_code', False),
                            'min_quantity': [],  # Changed from 0 to an empty list
                            'category_id': product_info['categ_id'][0],
                            'image_1920': product_info['image_1920'] or '',
                            'external_id': product_info['external_id']
                        }
                        if product_info['id'] not in [p['id'] for p in data]:
                            data.append(product_dict)
                        else:
                            for p in data:
                                if p['id'] == product_info['id']:
                                    dict = {
                                        'min_quantity': 0,
                                        'price': price
                                    }
                                    p['min_quantity'].append(dict)
                                    break
                        
                else:
                    print("Global Price:", item.fixed_price)
            print("Count:", count)
            
        # If we're filtering by category or search term, calculate total_items after filtering
        if category_ids or search_term:
            total_items = len(data)
        
        # Apply pagination to the filtered data if search term is provided
        if search_term and page_size > 0:
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            data = data[start_idx:end_idx]
        
        pagination_info = {
            'total_items': total_items,
            'total_pages': math.ceil(total_items / page_size) if total_items > 0 and page_size > 0 else 0,
            'current_page': page,
            'page_size': page_size,
            'has_next': page < math.ceil(total_items / page_size) if total_items > 0 and page_size > 0 else False,
            'has_previous': page > 1
        }
        return data, pagination_info

    @http.route('/api/products', auth='public', type='http', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def get_products(self):
        if request.httprequest.method == 'OPTIONS':
            headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS', 
                'Access-Control-Allow-Headers': 'Authorization, Content-Type',
                'Access-Control-Max-Age': '86400',
            }
            return Response(status=204, headers=headers)

        try:
            # Get pagination parameters from request
            page = int(request.params.get('page', 1))
            page_size = int(request.params.get('page_size', 20))
            
            # Get category_id parameter, if provided
            category_param = request.params.get('category_id', None)
            category_ids = None
            
            if category_param:
                # Split by comma and convert to integers
                category_ids = [int(cat_id) for cat_id in category_param.split(',') if cat_id.strip()]
            
            # Get search term parameter, if provided
            search_term = request.params.get('search', None)
            
            user_info = SocialMediaAuth.user_auth(self)
            if user_info['status'] == 'error':
                return Response(
                    json.dumps({
                        'status': 'error',
                        'message': 'Autenticazione fallita',
                        'info': user_info['message']
                    }),
                    content_type='application/json',
                    status=401,
                    headers={'Access-Control-Allow-Origin': '*'}
                )

            partner_id = user_info['user_id']
            
            products_data, pagination_info = self.get_product_list_price(
                partner_id, 
                page, 
                page_size, 
                category_ids,
                search_term
            )

            order_lines = request.env['sale.order.line'].sudo().search([
                ('order_id.partner_id', '=', partner_id),
                ('order_id.state', '=', 'draft')
            ])

            cart_lines_map = []
            for line in order_lines:
                dict = {}
                dict['product_id'] = line.product_id.id
                dict['cart_line_id'] = line.id
                dict['product_uom_qty'] = line.product_uom_qty
                cart_lines_map.append(dict)

            product_list = []
            
            for product in products_data:
                product_template = request.env['product.product'].sudo().search([('product_tmpl_id', '=', product['id'])])
                cart_line = None
                for line in cart_lines_map:
                    if line['product_id'] == product['id'] or line['product_id'] == product_template.id:
                        cart_line = line
                        break
                
                quantity = cart_line['product_uom_qty'] if cart_line else 0
                cart_line_id = cart_line['cart_line_id'] if cart_line else None
                
                
                final_price = ProductPriceController.calculate_price_product(product["id"], quantity, partner_id)
                if product['discount']:
                    final_price = final_price * (1 - (product['discount'] / 100))
                
                pr_id = product['id']
                
                product_data = {
                    'name': product['name'],
                    'list_price': final_price,
                    'active': product['active'], 
                    'barcode': product['barcode'],
                    'color': product['color'],
                    'image': "/web/image?model=res.users&field=avatar_128&id=2",
                    'id': product['id'],
                    'quantity': quantity,
                    'cart_line_id': cart_line_id,
                    'discount': product["discount"],
                    'is_published': product["is_published"],
                    'rewards_score': product["rewards_score"],
                    'code': product["code_"] if product["code_"] else None,
                    'discounted_price': final_price*quantity,
                    'min_quantity': product.get('min_quantity'),
                    'category_id': product['category_id'],
                    'external_id': product['external_id'],
                    'image': f'/web/image/product.template/{pr_id}/image_1920' if product['image_1920'] else None,
                }
                product_list.append(product_data)

            response_data = {
                'status': 'success',
                'message': 'Prodotti recuperati con successo',
                'info': f'Products retrieved successfully' + 
                    (f' for categories {category_param}' if category_param else '') +
                    (f' matching search: {search_term}' if search_term else '') +
                    (f' from page {page}' if not search_term else ''),
                'pagination': pagination_info,
                'total_products': len(product_list),
                'products': product_list
            }
            
            return Response(
                json.dumps(response_data), 
                content_type='application/json',
                headers={'Access-Control-Allow-Origin': '*'}
            )

        except Exception as e:
            return Response(
                json.dumps({
                    'status': 'error',
                    'message': 'Errore del server interno',
                    'info': str(e)
                }),
                content_type='application/json', 
                status=500,
                headers={'Access-Control-Allow-Origin': '*'}
            )
             
    @http.route('/images/products/<int:product_id>/<path:image>', type='http', auth='public', csrf=False, cors='*')
    def get_product_image(self, product_id, image):
        try:
            base_path = '/mnt/data/images'
            image_path = os.path.join(base_path, 'products', str(product_id), image.lstrip('/'))
            safe_path = os.path.join(base_path, 'products', str(product_id))
            
            # Security check to prevent directory traversal
            if not os.path.abspath(image_path).startswith(os.path.abspath(safe_path)):
                return Response(json.dumps({
                    'error': {'message': 'Invalid image path'},
                    'status': 'error',
                    'status_code': '403'
                }), content_type='application/json', status=403)

            if os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    return Response(f.read(), content_type='image/png')

            return Response(json.dumps({
                'error': {'message': 'Product image not found'},
                'status': 'error',
                'status_code': '404'
            }), content_type='application/json', status=404)

        except Exception as e:
            return Response(json.dumps({
                'error': {'message': 'Server error'},
                'status': 'error', 
                'status_code': '500'
            }), content_type='application/json', status=500)
    
    
    @http.route('/api/products/<int:product_code>', auth='none', type='http', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def get_product(self, product_code):
        """
        Retrieve a specific product by its code. Supports CORS and can handle preflight requests.
        parameters: product_code (int) - Unique identifier for the product
        """
        # Handle OPTIONS request for CORS preflight
        if request.httprequest.method == 'OPTIONS':
            headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Authorization, Content-Type',
                'Access-Control-Max-Age': '86400',  # 24 hours
            }
            return Response(status=204, headers=headers)

        try:
            # Authenticate user and handle errors
            user_info = SocialMediaAuth.user_auth(self)
            if user_info['status'] == 'error':
                return Response(
                    json.dumps({
                        'status': 'error',
                        'message': 'Autenticazione fallita', 
                        'info': user_info['message']  
                    }),
                    content_type='application/json',
                    status=401,
                    headers={'Access-Control-Allow-Origin': '*'}
                )
            partner_id = user_info['user_id']

            # Retrieve the product data based on code
            product_data = request.env['product.template'].search_read([('default_code', '=', product_code)], [
                'id', 'name', 'list_price', 'active', 'barcode', 'color', 'image_1920', 'discount', 
                'is_published', 'rewards_score', 'default_code', 'code_'
            ])
            product_list = []

            # Fetch draft order lines to check quantities in the cart
            order_lines = request.env['sale.order.line'].sudo().search([
                ('order_partner_id', '=', partner_id), ('state', '=', 'draft')
            ])
            
            # Create a mapping of product IDs to their corresponding order lines
            cart_lines_map = []
            for line in order_lines:
                cart_lines_map.append({
                    'product_id': line.product_id.id,
                    'cart_line_id': line.id,
                    'product_uom_qty': line.product_uom_qty
                })

            # Retrieve product pricelist for the partner
            cr = request.env.cr
            cr.execute("""
                SELECT 
                    rp.id as partner_id,
                    pp.id as pricelist_id
                FROM res_partner rp
                LEFT JOIN ir_property ip ON ip.res_id = CONCAT('res.partner,', rp.id)
                LEFT JOIN product_pricelist pp ON pp.id = CAST(SUBSTRING(ip.value_reference FROM 'product.pricelist,(.*)') AS INTEGER)
                WHERE ip.name = 'property_product_pricelist'
                AND rp.id = %s
            """, (partner_id,))
            
            result = cr.fetchone()
            pricelist_id = result[1] if result and result[1] else False
            
            for product in product_data:
                # Handle image conversion to URL if needed
                image_url = '/web/image/product.template/' + str(product['id']) + '/image_1920' if product['image_1920'] else None
                
                # Calculate the price based on pricelist if available
                price = product['list_price']
                if pricelist_id:
                    pricelist = request.env['product.pricelist'].sudo().browse(pricelist_id)
                    pricelist_items = pricelist.item_ids.filtered(
                        lambda item: (item.product_tmpl_id.id == product['id']) or 
                                    (item.categ_id and item.categ_id.id == product.get('categ_id', [False])[0])
                    )
                    
                    if pricelist_items:
                        for item in pricelist_items:
                            if item.compute_price == 'percentage':
                                price = product['list_price'] * (1 - (item.percent_price / 100))
                            elif item.compute_price == 'fixed':
                                price = item.fixed_price
                            elif item.compute_price == 'formula':
                                price = product['list_price'] * (1 - (item.price_discount / 100))
                
                # Apply discount if present
                discounted_price = price
                if product["discount"]:
                    discounted_price = price * (1 - (product["discount"] / 100))
                
                product_details = {
                    'name': product['name'],
                    'list_price': price,
                    'active': product['active'],
                    'barcode': product['barcode'],
                    'color': product['color'],
                    'image': image_url,
                    'id': product['id'],
                    'quantity': 0,
                    'cart_line_id': None,
                    'discount': product["discount"],
                    'is_published': product["is_published"],
                    'rewards_score': product["rewards_score"],
                    'code': product["default_code"],
                    'discounted_price': discounted_price,
                }
                
                # Check if the product is in cart
                for line in cart_lines_map:
                    if line['product_id'] == product['id']:
                        product_details['quantity'] = line['product_uom_qty']
                        product_details['cart_line_id'] = line['cart_line_id']
                        break
                
                product_list.append(product_details)

            # Successful response with product data
            response_data = {
                'status': 'success',
                'message': 'Prodotto recuperato con successo', 
                'info': 'Product retrieved successfully',  
                'products': product_list,
                'total_products': len(product_list)
            }
            return Response(json.dumps(response_data), content_type='application/json', headers={'Access-Control-Allow-Origin': '*'})

        except Exception as e:
            # Handle any unexpected errors
            return Response(json.dumps({
                'status': 'error',
                'message': 'Errore del server interno', 
                'info': str(e)  
            }), content_type='application/json', status=500, headers={'Access-Control-Allow-Origin': '*'})
    
        

    @http.route('/api/products/<int:product_id>', auth='public', type='json', methods=['PUT', 'OPTIONS'], csrf=False, cors='*')
    def update_product_quantity(self, product_id):
        if request.httprequest.method == 'OPTIONS':
            headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'PUT, OPTIONS',
                'Access-Control-Allow-Headers': 'Authorization, Content-Type',
                'Access-Control-Max-Age': '86400'
            }
            return Response(status=204, headers=headers)
        try:
            user_info = SocialMediaAuth.user_auth(self)
            if user_info['status'] == 'error':
                return {
                    'status': 'error',
                    'message': 'Autenticazione fallita',
                    'info': user_info['message']
                }, 401

            partner_id = user_info['user_id']
            test_product = request.env['product.template'].sudo().search([('id', '=', product_id)], limit=1)
            product = request.env['product.product'].sudo().search([('product_tmpl_id', '=', test_product.id)], limit=1)
            if not product:
                return {
                    'status': 'error',
                    'message': 'Prodotto non trovato',
                    'info': 'Product not found'
                }, 404

            quantity = request.jsonrequest.get('quantity', 0)
            if quantity < 0:
                return {
                    'status': 'error',
                    'message': 'La quantità deve essere un numero non negativo',
                    'info': 'Quantity must be a non-negative number'
                }, 400

            sale_order = request.env['sale.order'].sudo().search([
                ('partner_id', '=', partner_id), 
                ('state', '=', 'draft')
            ], limit=1)

            if not sale_order:
                # create sale order
                partner_pricelist = request.env['res.partner'].sudo().browse(partner_id).property_product_pricelist
                sale_order = request.env['sale.order'].sudo().create({
                    'partner_id': partner_id,
                    'partner_invoice_id': partner_id,
                    'partner_shipping_id': partner_id,
                    'pricelist_id': partner_pricelist.id,
                    'company_id': 1
                })
            

            env = request.env['sale.order.line'].with_company(sale_order.company_id)
            order_line = env.sudo().search([('product_id', '=', product.id), ('order_id', '=', sale_order.id)])
            
            if order_line:
                if quantity == 0:
                    order_line.sudo().unlink()
                    return {
                        'status': 'success',
                        'message': 'Prodotto rimosso dal carrello con successo',
                        'info': 'Product removed from cart successfully',
                        'quantity': 0,
                        'cart_line_id': None
                    }
                else:
                    order_line.sudo().write({'product_uom_qty': quantity})
                    return {
                        'status': 'success',
                        'message': 'Quantità del prodotto aggiornata con successo',
                        'info': 'Product quantity updated successfully',
                        'quantity': quantity,
                        'cart_line_id': order_line.id
                    }
            else:
                # find the product id in pricelist items for price based on customer pricelist
                
                if quantity > 0:
                    
                    # new_line = env.sudo().create({
                    #     'order_id': sale_order.id,
                    #     'product_id': product.id,
                    #     'product_uom_qty': quantity,
                    #     'price_unit': product.list_price,
                    # })
                    
                    final_price = ProductPriceController.calculate_price_product(product.id, quantity, partner_id)
                    
                    new_line = env.sudo().create({
                                            'order_id': sale_order.id,
                                            'product_id': product.id,
                                            'product_uom_qty': quantity,
                                            'price_unit': final_price,
                                        })

                    return {
                        'status': 'success',
                        'message': 'Prodotto aggiunto al carrello con successo',
                        'info': 'Product added to cart successfully',
                        'quantity': quantity,
                        'cart_line_id': new_line.id
                    }
                return {
                    'status': 'error',
                    'message': 'Nessuna quantità specificata',
                    'info': 'No quantity specified'
                }

        except Exception as e:
            return {
                'status': 'error',
                'message': 'Errore del server interno',
                'info': str(e)
            }, 500



    @http.route('/api/categories', auth='none', type='http', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def get_categories(self):
        if request.httprequest.method == 'OPTIONS':
            headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Authorization, Content-Type',
                'Access-Control-Max-Age': '86400',
            }
            return Response(status=204, headers=headers)

        try:
            # Authenticate user
            user_info = SocialMediaAuth.user_auth(self)
            if user_info['status'] == 'error':
                return Response(
                    json.dumps({
                        'status': 'error',
                        'message': 'Autenticazione fallita',
                        'info': user_info['message']
                    }),
                    content_type='application/json',
                    status=401,
                    headers={'Access-Control-Allow-Origin': '*'}
                )

            # Get categories with non-null external_id
            # Using order to ensure consistent results when taking first record per external_id
            categories = request.env['product.category'].sudo().search([
                ('external_id', '!=', False)
            ], order='external_id, id')

            # Dictionary to keep track of unique external_ids
            unique_categories = {}

            for category in categories:
                # Only keep the first occurrence of each external_id
                if category.external_id not in unique_categories:
                    # Get complete name and remove "All / Saleable / " prefix if it exists
                    modified_complete_name = category.complete_name
                    if modified_complete_name.startswith("All / Saleable / "):
                        modified_complete_name = modified_complete_name[16:]  # Skip the "All / Saleable / " part
                    
                    unique_categories[category.external_id] = {
                        'id': category.id,
                        'name': category.name,
                        'external_id': category.external_id,
                        'complete_name': modified_complete_name  # Store the modified name directly in complete_name
                    }

            # Convert dictionary values to list
            category_list = list(unique_categories.values())
            
            # loop over the category list and hide the All/Sealable/ part from complete name show the other part
            

            response_data = {
                'status': 'success',
                'message': 'Categorie uniche recuperate con successo',
                'categories': category_list,
                'count': len(category_list)
            }

            return Response(
                json.dumps(response_data),
                content_type='application/json',
                headers={'Access-Control-Allow-Origin': '*'}
            )

        except Exception as e:
            return Response(
                json.dumps({
                    'status': 'error',
                    'message': 'Errore del server interno',
                    'info': str(e)
                }),
                content_type='application/json',
                status=500,
                headers={'Access-Control-Allow-Origin': '*'}
            )
                