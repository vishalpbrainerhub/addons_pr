from odoo import http, fields
from odoo.http import request, Response
import json
from .user_authentication import SocialMediaAuth
import math
import os

class MobileEcommerceApiController(http.Controller):

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
            # Get pagination parameters
            page = int(request.params.get('page', 1))
            page_size = int(request.params.get('page_size', 20))
            
            # Get category filter
            category_param = request.params.get('category_id', None)
            category_ids = None
            if category_param:
                category_ids = [int(cat_id) for cat_id in category_param.split(',') if cat_id.strip()]
            
            # Get search parameter
            search_term = request.params.get('search', None)
            
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

            partner_id = user_info['user_id']
            env = request.env
            
            # Get user's pricelist
            partner = env['res.partner'].sudo().browse(partner_id)
            pricelist = partner.property_product_pricelist or env['product.pricelist'].sudo().search([('name', '=', 'Public Pricelist')], limit=1)
            
            # Build product search domain
            domain = [('active', '=', True)]
            
            # Add category filter
            if category_ids:
                domain.append(('categ_id', 'in', category_ids))
            
            # Add search filter
            if search_term:
                domain.append('|')
                domain.append(('name', 'ilike', search_term))
                domain.append(('default_code', 'ilike', search_term))
            
            # Get total count for pagination
            total_items = env['product.template'].sudo().search_count(domain)
            
            # Calculate pagination
            start_idx = (page - 1) * page_size
            pagination_info = {
                'total_items': total_items,
                'total_pages': math.ceil(total_items / page_size) if total_items > 0 else 0,
                'current_page': page,
                'page_size': page_size,
                'has_next': page < math.ceil(total_items / page_size) if total_items > 0 else False,
                'has_previous': page > 1
            }
            
            # Get paginated products
            product_templates = env['product.template'].sudo().search(
                domain, 
                limit=page_size, 
                offset=start_idx
            )
            
            # Get cart lines for current user
            order_lines = env['sale.order.line'].sudo().search([
                ('order_id.partner_id', '=', partner_id),
                ('order_id.state', '=', 'draft')
            ])
            
            cart_lines_map = []
            for line in order_lines:
                cart_lines_map.append({
                    'product_id': line.product_id.id,
                    'cart_line_id': line.id,
                    'product_uom_qty': line.product_uom_qty
                })
            
            # Build product list
            product_list = []
            for template in product_templates:
                # Get product variants
                product_variants = env['product.product'].sudo().search([('product_tmpl_id', '=', template.id)])
                product_variant_id = product_variants[0].id if product_variants else template.id
                
                # Find cart line
                cart_line = None
                for line in cart_lines_map:
                    if line['product_id'] == template.id or line['product_id'] == product_variant_id:
                        cart_line = line
                        break
                
                quantity = cart_line['product_uom_qty'] if cart_line else 0
                cart_line_id = cart_line['cart_line_id'] if cart_line else None
                
                
                # Test different quantities
                # test_quantities = [1, 100, 200, 1000, 2000]
                # for qty in test_quantities:
                #     pricelist_price_test = pricelist.get_product_price(template, qty, partner)
                #     print(f"Quantity {qty}: Pricelist Price = {pricelist_price_test}")
                
                # print("------------------------------------------\n")
                
                # Use quantity 1 for the actual API response
                pricelist_price = pricelist.get_product_price(template, 1, partner)
                
                # Calculate final price (use pricelist price if available, otherwise external_basic_price)
                final_price = pricelist_price if pricelist_price > 0 else template.external_basic_price
                if template.discount:
                    final_price = final_price * (1 - (template.discount / 100))
                    final_price = round(final_price, 2)
                
                # Get min quantity from pricelist items
                min_quantity_items = []
                pricelist_items = env['product.pricelist.item'].sudo().search([
                    ('pricelist_id', '=', pricelist.id),
                    '|', 
                    ('product_tmpl_id', '=', template.id),
                    ('product_id', 'in', [variant.id for variant in product_variants])
                ])
                
                for item in pricelist_items:
                    min_quantity_items.append({
                        'min_quantity': item.min_quantity,
                        'price': item.fixed_price if item.compute_price == 'fixed' else None,
                        'discount': item.percent_price if item.compute_price == 'percentage' else None,
                        'pricelist_item_id': item.id
                    })
                
                product_data = {
                    'name': template.name,
                    'list_price': final_price,
                    'active': template.active,
                    'barcode': template.barcode,
                    'color': template.color,
                    'id': template.id,
                    'quantity': quantity,
                    'cart_line_id': cart_line_id,
                    'discount': template.discount,
                    'is_published': template.is_published,
                    'rewards_score': template.rewards_score,
                    'code': template.default_code if template.default_code else None,
                    'discounted_price': final_price * quantity,
                    'min_quantity': min_quantity_items,
                    'category_id': template.categ_id.id if template.categ_id else False,
                    'external_id': template.external_id,
                    'image': f'/web/image/product.template/{template.id}/image_1920' if template.image_1920 else None,
                }
                product_list.append(product_data)

            response_data = {
                'status': 'success',
                'message': 'Prodotti recuperati con successo',
                'info': f'Products retrieved successfully' + (f' for categories {category_param}' if category_param else f' from page {page}') + (f' matching search: {search_term}' if search_term else ''),
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
                    
                    # final_price = ProductPriceController.calculate_price_product(product.id, quantity, partner_id)
                    final_price = test_product.external_basic_price
                    if test_product.discount:
                        final_price = final_price * (1 - (test_product.discount / 100))
                        final_price = round(final_price, 2)
                    
                    
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
                