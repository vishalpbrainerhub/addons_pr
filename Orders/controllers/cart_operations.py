from odoo import http
from odoo.http import request, Response
import json
from .user_authentication import user_auth


class EcommerceCartLine(http.Controller):

    #get cart lines
    @http.route('/api/cart_line', auth='user', type='http', methods=['GET'], csrf=False, cors='*')
    def get_cart_line(self):
        """
        description : Retrieve the cart line details for the authenticated user's current draft order.
        parameters : None
        """
        if request.httprequest.method == 'OPTIONS':
            headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Authorization, Content-Type',
                'Access-Control-Max-Age': '86400',  # 24 hours
            }
            return Response(status=204, headers=headers)

        try:
            # Authenticate user
            user = user_auth(self)
            if user['status'] == 'error':
                return Response(json.dumps({
                    'status': 'error',
                    'message': user['message'],  # Error message in Italian
                    'info': 'Authentication failed.'  # English description
                }), content_type='application/json', status=401, headers={'Access-Control-Allow-Origin': '*'})

            user_id = user['user_id']
            partner_id = request.env['res.users'].sudo().search([('id', '=', user_id)]).partner_id.id

            # Fetch cart lines for the draft order
            cart_lines = request.env['sale.order.line'].search_read([
                ('order_id.partner_id', '=', partner_id),
                ('order_id.state', '=', 'draft')  # Filter by draft state
            ], ['product_id', 'price_unit', 'product_uom_qty', 'order_id'])

            cart = []
            for line in cart_lines:
                if line['product_uom_qty'] > 0:
                    product = request.env['product.product'].browse(line['product_id'][0])
                    test = {
                        'id': line['id'],
                        'name': product.name,
                        'list_price': line['price_unit'],
                        'quantity': line['product_uom_qty'],
                        'image': f'/web/image/product.product/{product.id}/image_1920' if product.image_1920 else None,
                        'barcode': product.barcode,
                        'active': product.active,
                        'color': getattr(product, 'color', None),
                        'base_price': product.list_price,
                        'discount': getattr(product, 'discount', 0.0),
                        'order_id': line['order_id'][0],
                        'code': getattr(product, 'code_', None)
                    }
                    cart.append(test)
                    test = None
                else:
                    request.env['sale.order.line'].browse(line['id']).unlink()
            
            response_data = {
                'cart': cart,
                'status': 'success',
                'message': 'Dettagli del carrello recuperati con successo.',  # Success message in Italian
                'info': 'Cart details retrieved successfully.'  # English description
            }

            # Success response
            return Response(json.dumps(response_data), content_type='application/json', headers={'Access-Control-Allow-Origin': '*'})

        except Exception as e:
            # Error response
            return Response(json.dumps({
                'status': 'error',
                'message': 'Si è verificato un errore nel recupero dei dettagli del carrello.',  # Error message in Italian
                'info': str(e)  # English error description
            }), content_type='application/json', status=500, headers={'Access-Control-Allow-Origin': '*'})


    

    @http.route('/api/cart_line', auth='user', type='json', methods=['POST'], csrf=False, cors='*')
    def create_cart_line(self):
        """
        description : Create a cart line by adding a product to the authenticated user's current draft order.
        parameters : product_id (int), quantity (float), product_price (float)
        """
        if request.httprequest.method == 'OPTIONS':
            headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Authorization, Content-Type',
                'Access-Control-Max-Age': '86400',  # 24 hours
            }
            return Response(status=204, headers=headers)

        try:
            # Authenticate the user
            user = user_auth(self)
            if user['status'] == 'error':
                return Response(json.dumps({
                    'status': 'error',
                    'message': user['message'],  # Error message in Italian
                    'info': 'Authentication failed.'  # English description
                }), content_type='application/json', status=401, headers={'Access-Control-Allow-Origin': '*'})

            user_id = user['user_id']

            # Get required fields from the request
            product_id = request.jsonrequest.get('product_id')
            product_uom_qty = request.jsonrequest.get('quantity', False)
            price_unit = request.jsonrequest.get('product_price', False)

            # Validate required fields
            if not product_id or not product_uom_qty or not price_unit:
                return {
                    'status': 'error',
                    'message': 'ID del prodotto, quantità e prezzo sono necessari.',  # Error message in Italian
                    'info': 'Product ID, quantity, and price are required.'  # English description
                }, 400

            # Check if the product exists as a product or product template
            product = request.env['product.product'].sudo().browse(product_id)
            if not product.exists():
                # Try checking if it's a product template ID and get the first variant
                template = request.env['product.template'].sudo().browse(product_id)
                if template.exists():
                    # Get the first variant of the template
                    product = template.product_variant_ids[0]
                    if not product:
                        return {
                            'status': 'error',
                            'message': 'La variante del prodotto specificata non esiste o è stata eliminata.',  # Error message in Italian
                            'info': 'The specified product variant does not exist or has been deleted.'  # English description
                        }, 400
                else:
                    return {
                        'status': 'error',
                        'message': 'Il prodotto specificato non esiste o è stato eliminato.',  # Error message in Italian
                        'info': 'The specified product does not exist or has been deleted.'  # English description
                    }, 400

            # Apply discount on the product price
            price_unit = price_unit - (price_unit * product.discount / 100)

            # Get the partner (customer) associated with the user
            partner = request.env['res.users'].browse(user_id).partner_id
            if not partner:
                return {
                    'status': 'error',
                    'message': 'Nessun partner trovato per l\'utente.',  # Error message in Italian
                    'info': 'No partner found for the user.'  # English description
                }

            # Get the user's default shipping address
            shipping_address = request.env['social_media.custom_address'].search([('user_id', '=', user_id), ("default", "=", True)], limit=1)

            # Check if there is an existing draft order for the partner
            sale_order = request.env['sale.order'].search([('partner_id', '=', partner.id), ('state', '=', 'draft')], limit=1)
            if not sale_order:
                # Create a new sale order if no draft order exists
                sale_order = request.env['sale.order'].create({
                    'partner_id': partner.id,
                    'user_id': user_id,
                    'shipping_address_id': shipping_address.id
                })

            # Check if the product is already in the cart
            cart_line_check = request.env['sale.order.line'].search([('product_id', '=', product.id), ('order_id', '=', sale_order.id)], limit=1)
            if cart_line_check:
                return {
                    'status': 'error',
                    'message': 'Prodotto già nel carrello.',  # Error message in Italian
                    'info': 'Product already in cart.'  # English description
                }

            # Create the new cart line
            cart_line = request.env['sale.order.line'].create({
                'product_id': product.id,
                'price_unit': price_unit,
                'product_uom_qty': product_uom_qty,
                'order_id': sale_order.id
            })

            # Success response
            return {
                'cart_line': cart_line.id,
                'status': 'success',
                'message': 'Articolo aggiunto al carrello con successo.',  # Success message in Italian
                'info': 'Item added to cart successfully.'  # English description
            }

        except Exception as e:
            # Error response
            return {
                'status': 'error',
                'message': 'Si è verificato un errore durante la creazione della riga del carrello.',  # Error message in Italian
                'info': str(e)  # English error description
            }



    #update cart line quantity
    @http.route('/api/cart_line/<int:id>', auth='user', type='json', methods=['PUT'], csrf=False, cors='*')
    def update_cart_line(self, id):
        """
        description : Update the quantity of a specific cart line.
        parameters : id (int), quantity (float)
        """
        if request.httprequest.method == 'OPTIONS':
            headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'PUT, OPTIONS',
                'Access-Control-Allow-Headers': 'Authorization, Content-Type',
                'Access-Control-Max-Age': '86400',  # 24 hours
            }
            return Response(status=204, headers=headers)

        try:
            # Get quantity from the request
            product_uom_qty = request.jsonrequest.get('quantity', False)

            # Validate that quantity is provided
            if not product_uom_qty:
                return Response(json.dumps({
                    'status': 'error',
                    'message': 'La quantità è richiesta.',  # Error message in Italian
                    'info': 'Quantity is required.'  # English description
                }), content_type='application/json', status=400, headers={'Access-Control-Allow-Origin': '*'})

            # Authenticate the user
            user = user_auth(self)
            if user['status'] == 'error':
                return Response(json.dumps({
                    'status': 'error',
                    'message': user['message'],  # Error message in Italian
                    'info': 'Authentication failed.'  # English description
                }), content_type='application/json', status=401, headers={'Access-Control-Allow-Origin': '*'})

            user_id = user['user_id']

            # Retrieve the partner associated with the user
            partner = request.env['res.users'].browse(user_id).partner_id
            if not partner:
                return Response(json.dumps({
                    'status': 'error',
                    'message': 'Nessun partner trovato per l\'utente.',  # Error message in Italian
                    'info': 'No partner found for the user.'  # English description
                }), content_type='application/json', status=400, headers={'Access-Control-Allow-Origin': '*'})

            # Check if there's an existing sale order for this user
            sale_order = request.env['sale.order'].search([('partner_id', '=', partner.id)], limit=1)
            if not sale_order:
                # Create a new sale order if it doesn't exist
                sale_order = request.env['sale.order'].create({
                    'partner_id': partner.id,
                    'user_id': user_id,
                    # Additional necessary fields for sale.order creation
                })

            # Attempt to retrieve the order line safely
            cart_line = request.env['sale.order.line'].browse(id)
            if not cart_line.exists():
                return Response(json.dumps({
                    'status': 'error',
                    'message': 'La riga del carrello non esiste.',  # Error message in Italian
                    'info': 'Cart line does not exist.'  # English description
                }), content_type='application/json', status=404, headers={'Access-Control-Allow-Origin': '*'})

            # Update the cart line quantity
            cart_line.write({
                'product_uom_qty': product_uom_qty
            })

            # Success response
            return Response(json.dumps({
                'status': 'success',
                'message': 'Quantità della riga del carrello aggiornata con successo.',  # Success message in Italian
                'info': 'Cart line quantity updated successfully.',  # English description
                'cart_line': cart_line.id
            }), content_type='application/json', headers={'Access-Control-Allow-Origin': '*'})

        except Exception as e:
            # Error response
            return Response(json.dumps({
                'status': 'error',
                'message': 'Si è verificato un errore durante l\'aggiornamento della quantità.',  # Error message in Italian
                'info': str(e)  # English error description
            }), content_type='application/json', status=500, headers={'Access-Control-Allow-Origin': '*'})
            


    # delete cart line
    @http.route('/api/cart_line/<int:id>', auth='user', type='http', methods=['DELETE'], csrf=False, cors='*')
    def delete_cart_line(self, id):
        """
        description : Delete a specific cart line from the user's draft order.
        parameters : id (int)
        """
        if request.httprequest.method == 'OPTIONS':
            headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'DELETE, OPTIONS',
                'Access-Control-Allow-Headers': 'Authorization, Content-Type',
                'Access-Control-Max-Age': '86400',  # 24 hours
            }
            return Response(status=204, headers=headers)

        try:
            # Authenticate the user
            user = user_auth(self)
            if user['status'] == 'error':
                return Response(json.dumps({
                    'status': 'error',
                    'message': user['message'],  # Assuming the message from user_auth is already in Italian
                    'info': 'Authentication failed.'  # English description
                }), content_type='application/json', status=401, headers={'Access-Control-Allow-Origin': '*'})

            user_id = user['user_id']

            # Retrieve the partner associated with the user
            partner = request.env['res.users'].browse(user_id).partner_id
            if not partner:
                return Response(json.dumps({
                    'status': 'error',
                    'message': "Nessun partner trovato per l'utente.",  # Error message in Italian
                    'info': 'No partner found for the user.'  # English description
                }), content_type='application/json', status=400, headers={'Access-Control-Allow-Origin': '*'})

            # Check if there's an existing sale order for this user
            sale_order = request.env['sale.order'].search([('partner_id', '=', partner.id)], limit=1)
            if not sale_order:
                # Create a new sale order if it doesn't exist
                sale_order = request.env['sale.order'].create({
                    'partner_id': partner.id,
                    'user_id': user_id,
                    # Additional necessary fields for sale.order creation
                })

            # Retrieve and delete the order line
            cart_line = request.env['sale.order.line'].browse(id)
            if not cart_line.exists():
                return Response(json.dumps({
                    'status': 'error',
                    'message': 'La riga del carrello non esiste.',  # Error message in Italian
                    'info': 'Cart line does not exist.'  # English description
                }), content_type='application/json', status=404, headers={'Access-Control-Allow-Origin': '*'})

            cart_line.unlink()

            # Success response
            return Response(json.dumps({
                'status': 'success',
                'message': 'Riga del carrello eliminata con successo.',  # Success message in Italian
                'info': 'Cart line successfully deleted.'  # English description
            }), content_type='application/json', headers={'Access-Control-Allow-Origin': '*'})

        except Exception as e:
            # Error response
            return Response(json.dumps({
                'status': 'error',
                'message': 'Si è verificato un errore durante l\'eliminazione della riga del carrello.',  # Error message in Italian
                'info': str(e)  # English error description
            }), content_type='application/json', status=500, headers={'Access-Control-Allow-Origin': '*'})


