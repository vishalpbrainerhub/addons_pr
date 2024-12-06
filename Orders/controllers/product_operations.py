from odoo import http
from odoo.http import request, Response
import json
from .user_authentication import user_auth



class MobileEcommerceApiController(http.Controller):


    @http.route('/api/products', auth='none', type='http', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def get_products(self):
        """
        Retrieve all available products. This API supports CORS and can handle preflight requests.
        parameters: none
        """
        # Handle OPTIONS request for CORS preflight
        if request.httprequest.method == 'OPTIONS':
            headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Authorization, Content-Type',
                'Access-Control-Max-Age': '86400',  # 24 hours
            }
            return Response(status=204, headers=headers)

        try:
            # Authenticate user and handle error in authentication
            user_info = user_auth(self)
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
            user_id = user_info['user_id']
            users_dict = request.env['res.users'].sudo().search([('id', '=', user_id)])
            partner_id = users_dict.partner_id.id

            # Retrieve product data
            products_data = request.env['product.template'].search_read([], [
                'id', 'name', 'list_price', 'active', 'barcode', 'color', 'image_1920', 
                'discount', 'is_published', 'rewards_score', 'default_code', 'code_'
            ])
            product_list = []

            # Handle draft orders to fetch product quantities
            order_lines = request.env['sale.order.line'].sudo().search([
                ('order_partner_id', '=', partner_id), ('state', '=', 'draft')
            ])
            product_ids = [line.product_id.id for line in order_lines]

            for product in products_data:
                # Handle the image (convert to URL if needed)
                image_url = '/web/image/product.template/' + str(product['id']) + '/image_1920' if product['image_1920'] else None
                product_data = {
                    'name': product['name'],
                    'list_price': product['list_price'],
                    'active': product['active'],
                    'barcode': product['barcode'],
                    'color': product['color'],
                    'image': image_url,
                    'id': product['id'],
                    'quantity': 0,
                    'discount': product["discount"],
                    'is_published': product["is_published"],
                    'rewards_score': product["rewards_score"],
                    'default_code': product["default_code"],
                    'code': product["code_"],
                    'discounted_price': product['list_price'] - (product['list_price'] * product["discount"] / 100),
                }
                if product['id'] in product_ids:
                    # Update the quantity of the product in the cart
                    for line in order_lines:
                        if line.product_id.id == product['id']:
                            product_data['quantity'] = line.product_uom_qty
                            product_data['discounted_price'] *= line.product_uom_qty
                            break
                product_list.append(product_data)

            # Successful response
            response_data = {
                'status': 'success',
                'message': 'Prodotti recuperati con successo', 
                'info': 'Products retrieved successfully',  
                'products': product_list,
                'total_products': len(product_list)
            }
            return Response(json.dumps(response_data), content_type='application/json', headers={'Access-Control-Allow-Origin': '*'})

        except Exception as e:
            # Handle unexpected errors
            return Response(json.dumps({
                'status': 'error',
                'message': 'Errore del server interno', 
                'info': str(e)  
            }), content_type='application/json', status=500, headers={'Access-Control-Allow-Origin': '*'})



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
            user_info = user_auth(self)
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
            user_id = user_info['user_id']
            users_dict = request.env['res.users'].sudo().search([('id', '=', user_id)])
            partner_id = users_dict.partner_id.id

            # Retrieve the product data based on code
            product_data = request.env['product.template'].search_read([('code_', '=', product_code)], [
                'id', 'name', 'list_price', 'active', 'barcode', 'color', 'image_1920', 'discount', 
                'is_published', 'rewards_score', 'default_code', 'code_'
            ])
            product_list = []

            # Fetch draft order lines to check quantities in the cart
            order_lines = request.env['sale.order.line'].sudo().search([
                ('order_partner_id', '=', partner_id), ('state', '=', 'draft')
            ])
            product_ids = [line.product_id.id for line in order_lines]

            for product in product_data:
                # Handle image conversion to URL if needed
                image_url = '/web/image/product.template/' + str(product['id']) + '/image_1920' if product['image_1920'] else None
                product_details = {
                    'name': product['name'],
                    'list_price': product['list_price'],
                    'active': product['active'],
                    'barcode': product['barcode'],
                    'color': product['color'],
                    'image': image_url,
                    'id': product['id'],
                    'quantity': 0,
                    'discount': product["discount"],
                    'is_published': product["is_published"],
                    'rewards_score': product["rewards_score"],
                    'default_code': product["default_code"],
                    'code': product["code_"],
                    'discounted_price': product['list_price'] - (product['list_price'] * product["discount"] / 100),
                }
                if product['id'] in product_ids:
                    # Update the quantity of the product in the cart
                    for line in order_lines:
                        if line.product_id.id == product['id']:
                            product_details['quantity'] = line.product_uom_qty
                            product_details['discounted_price'] *= line.product_uom_qty
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
    
        

    @http.route('/api/products/<int:product_id>', auth='none', type='json', methods=['PUT', 'OPTIONS'], csrf=False, cors='*')
    def update_product_quantity(self, product_id):
        """
        Update the quantity of a specific product in the user's cart. Supports CORS and handles preflight requests.
        parameters: product_id (int) - Unique identifier for the product
        """
        if request.httprequest.method == 'OPTIONS':
            headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'PUT, OPTIONS',
                'Access-Control-Allow-Headers': 'Authorization, Content-Type',
                'Access-Control-Max-Age': '86400'  # 24 hours
            }
            return Response(status=204, headers=headers)

        try:
            # Authenticate user and handle errors
            user_info = user_auth(self)
            if user_info['status'] == 'error':
                return {
                    'status': 'error',
                    'message': 'Autenticazione fallita', 
                    'info': user_info['message']  
                }, 401

            user_id = user_info['user_id']
            user_record = request.env['res.users'].sudo().search([('id', '=', user_id)], limit=1)
            if not user_record:
                return {
                    'status': 'error',
                    'message': 'Utente non trovato', 
                    'info': 'User not found'  
                }, 404

            partner_id = user_record.partner_id.id
            product = request.env['product.template'].sudo().search([('id', '=', product_id)])
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

            # Search for an existing draft sale order for the user
            sale_order = request.env['sale.order'].sudo().search([('partner_id', '=', partner_id), ('state', '=', 'draft')], limit=1)
            if not sale_order:
                return {
                    'status': 'error',
                    'message': 'Nessun ordine di vendita trovato per questo utente', 
                    'info': 'Sale order not found for this user'  
                }, 404

            # Setting the correct company context for the sale order line
            env = request.env['sale.order.line'].with_company(sale_order.company_id)

            order_line = env.sudo().search([('product_id', '=', product.id), ('order_id', '=', sale_order.id)])
            if order_line:
                if quantity == 0:
                    order_line.unlink()
                    return {
                        'status': 'success',
                        'message': 'Prodotto rimosso dal carrello con successo', 
                        'info': 'Product removed from cart successfully'  
                    }
                else:
                    order_line.write({'product_uom_qty': quantity})
                    return {
                        'status': 'success',
                        'message': 'Quantità del prodotto aggiornata con successo', 
                        'info': 'Product quantity updated successfully'  
                    }
            else:
                if quantity > 0:
                    env.sudo().create({
                        'order_id': sale_order.id,
                        'product_id': product.id,
                        'product_uom_qty': quantity,
                        'price_unit': product.list_price,
                    })
                    return {
                        'status': 'success',
                        'message': 'Prodotto aggiunto al carrello con successo', 
                        'info': 'Product added to cart successfully'  
                    }
                return {
                    'status': 'error',
                    'message': 'Nessuna quantità specificata', 
                    'info': 'No quantity specified'  
                }

        except Exception as e:
            # Handle any unexpected errors
            return {
                'status': 'error',
                'message': 'Errore del server interno', 
                'info': str(e)  
            }, 500
