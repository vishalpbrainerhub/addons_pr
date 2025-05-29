from odoo import http
from odoo.http import request, Response
import json
from .user_authentication import SocialMediaAuth

class EcommerceCartLine(http.Controller):
    
    @http.route('/api/cart_line', auth='public', type='http', methods=['GET'], csrf=False, cors='*')
    def get_cart_line(self):
        try:
            user = SocialMediaAuth.user_auth(self)
            if user['status'] == 'error':
                return Response(json.dumps({
                    'status': 'error',
                    'message': user['message'],
                    'info': 'Authentication failed.'
                }), content_type='application/json', status=401, headers={'Access-Control-Allow-Origin': '*'})

            partner_id = user['user_id']
            env = request.env
            
            # Get user's pricelist
            partner = env['res.partner'].sudo().browse(partner_id)
            pricelist = partner.property_product_pricelist or env['product.pricelist'].sudo().search([('name', '=', 'Public Pricelist')], limit=1)

            cart_lines = env['sale.order.line'].sudo().search_read([
                ('order_id.partner_id', '=', partner_id),
                ('order_id.state', '=', 'draft')
            ], ['product_id', 'price_unit', 'product_uom_qty', 'order_id'])

            cart = []
            for line in cart_lines:
                
                if line['product_uom_qty'] > 0:
                    
                    product_product = env['product.product'].sudo().browse(line['product_id'][0])
                    product = env['product.template'].sudo().browse(product_product.product_tmpl_id.id)
                    
                    # Get pricelist price based on quantity
                    quantity = line['product_uom_qty']
                    pricelist_price = pricelist.get_product_price(product, quantity, partner)
                    
                    # Calculate final price (use pricelist price if available, otherwise external_basic_price)
                    base_price = pricelist_price if pricelist_price > 0 else product.external_basic_price
                    
                    # Apply product discount if any
                    product_discount = getattr(product, 'discount', 0.0)
                    if product_discount:
                        base_price = base_price * (1 - (product_discount / 100))
                        base_price = round(base_price, 2)
                    
                    test = {
                        'id': line['id'],
                        'product_id': product.id,
                        'name': product.name,
                        'list_price': base_price * quantity,
                        'quantity': quantity,
                        'image': f'/web/image/product.template/{product.id}/image_1920' if product.image_1920 else None,
                        'barcode': product.barcode,
                        'active': product.active,
                        'color': getattr(product, 'color', None),
                        'base_price': base_price,
                        'discount': product_discount,
                        'order_id': line['order_id'][0],
                        'code': getattr(product, 'default_code', None)
                    }
                    cart.append(test)
                else:
                    env['sale.order.line'].sudo().browse(line['id']).unlink()
            
            response_data = {
                'cart': cart,
                'status': 'success',
                'message': 'Dettagli del carrello recuperati con successo.',
                'info': 'Cart details retrieved successfully.'
            }

            return Response(json.dumps(response_data), content_type='application/json', headers={'Access-Control-Allow-Origin': '*'})

        except Exception as e:
            return Response(json.dumps({
                'status': 'error',
                'message': 'Si è verificato un errore nel recupero dei dettagli del carrello.',
                'info': str(e)
            }), content_type='application/json', status=500, headers={'Access-Control-Allow-Origin': '*'})    
            
        
    @http.route('/api/cart_line', auth='public', type='json', methods=['POST'], csrf=False, cors='*')
    def create_cart_line(self):
        """
        description : Create a cart line by adding a product to the authenticated user's current draft order.
        parameters : product_id (int), quantity (float), product_price (float) - NOTE: product_price will now be calculated using pricelist
        """
        if request.httprequest.method == 'OPTIONS':
            headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Authorization, Content-Type',
                'Access-Control-Max-Age': '86400',
            }
            return Response(status=204, headers=headers)

        try:
            user = SocialMediaAuth.user_auth(self)
            if user['status'] == 'error':
                return {
                    'status': 'error',
                    'message': user['message'],
                    'info': 'Authentication failed.'
                }, 401

            partner_id = user['user_id']
            env = request.env
            
            # Get user's pricelist
            partner = env['res.partner'].sudo().browse(partner_id)
            pricelist = partner.property_product_pricelist or env['product.pricelist'].sudo().search([('name', '=', 'Public Pricelist')], limit=1)

            product_id = request.jsonrequest.get('product_id')
            product_uom_qty = request.jsonrequest.get('quantity', False)
            # Note: product_price from frontend is now ignored - we calculate based on pricelist

            if not product_id or not product_uom_qty:
                return {
                    'status': 'error',
                    'message': 'ID del prodotto e quantità sono necessari.',
                    'info': 'Product ID and quantity are required.'
                }, 400

            product = env['product.template'].sudo().browse(product_id)
            if not product.exists():
                return {
                    'status': 'error',
                    'message': 'Il prodotto specificato non esiste o è stato eliminato.',
                    'info': 'The specified product does not exist or has been deleted.'
                }, 400

            # Calculate price using pricelist logic
            pricelist_price = pricelist.get_product_price(product, product_uom_qty, partner)
            price_unit = pricelist_price if pricelist_price > 0 else product.external_basic_price
            
            # Apply product discount if any
            if product.discount:
                price_unit = price_unit * (1 - (product.discount / 100))
                price_unit = round(price_unit, 2)

            shipping_address = env['social_media.custom_address'].sudo().search([
                ('partner_id', '=', partner_id), 
                ("default", "=", True)
            ], limit=1)

            # Check for existing draft order
            sale_order = env['sale.order'].sudo().search([
                ('partner_id', '=', partner_id), 
                ('state', '=', 'draft')
            ], limit=1)
            
            if not sale_order:
                # Create new sale order
                sale_order = env['sale.order'].sudo().with_context(
                    default_partner_id=partner_id
                ).create({
                    'partner_id': partner_id,
                    'shipping_address_id': shipping_address.id if shipping_address else False,
                })

            cart_line_check = env['sale.order.line'].sudo().search([
                ('product_id', '=', product.id), 
                ('order_id', '=', sale_order.id)
            ], limit=1)
            
            if cart_line_check:
                return {
                    'status': 'error',
                    'message': 'Prodotto già nel carrello.',
                    'info': 'Product already in cart.'
                }

            cart_line = env['sale.order.line'].sudo().with_context(
                default_order_id=sale_order.id
            ).create({
                'order_id': sale_order.id,
                'product_id': product.id,
                'price_unit': price_unit,
                'product_uom_qty': product_uom_qty,
            })

            return {
                'cart_line': cart_line.id,
                'status': 'success', 
                'message': 'Articolo aggiunto al carrello con successo.',
                'info': 'Item added to cart successfully.'
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': 'Si è verificato un errore durante la creazione della riga del carrello.',
                'info': str(e)
            }, 500

    @http.route('/api/cart_line/<int:id>', auth='public', type='json', methods=['PUT'], csrf=False, cors='*')
    def update_cart_line(self, id):
        if request.httprequest.method == 'OPTIONS':
            headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'PUT, OPTIONS',
                'Access-Control-Allow-Headers': 'Authorization, Content-Type',
                'Access-Control-Max-Age': '86400',
            }
            return Response(status=204, headers=headers)

        try:
            product_uom_qty = request.jsonrequest.get('quantity', False)
            if not product_uom_qty:
                return {
                    'status': 'error',
                    'message': 'La quantità è richiesta.',
                    'info': 'Quantity is required.'
                }, 400

            user = SocialMediaAuth.user_auth(self)
            if user['status'] == 'error':
                return {
                    'status': 'error',
                    'message': user['message'],
                    'info': 'Authentication failed.'
                }, 401

            partner_id = user['user_id']
            env = request.env
            
            # Get user's pricelist
            partner = env['res.partner'].sudo().browse(partner_id)
            pricelist = partner.property_product_pricelist or env['product.pricelist'].sudo().search([('name', '=', 'Public Pricelist')], limit=1)

            sale_order = env['sale.order'].sudo().search([
                ('partner_id', '=', partner_id),
                ('state', '=', 'draft')
            ], limit=1)
            
            if not sale_order:
                sale_order = env['sale.order'].sudo().create({
                    'partner_id': partner_id,
                })

            cart_line = env['sale.order.line'].sudo().browse(id)
            if not cart_line.exists() or cart_line.order_id.partner_id.id != partner_id:
                return {
                    'status': 'error',
                    'message': 'La riga del carrello non esiste.',
                    'info': 'Cart line does not exist or does not belong to this customer.'
                }, 404

            # Get product and recalculate price based on new quantity
            product_product = env['product.product'].sudo().browse(cart_line.product_id.id)
            product = env['product.template'].sudo().browse(product_product.product_tmpl_id.id)
            
            # Calculate new price using updated quantity
            pricelist_price = pricelist.get_product_price(product, product_uom_qty, partner)
            price_unit = pricelist_price if pricelist_price > 0 else product.external_basic_price
            
            # Apply product discount if any
            if product.discount:
                price_unit = price_unit * (1 - (product.discount / 100))
                price_unit = round(price_unit, 2)

            cart_line.sudo().write({
                'product_uom_qty': product_uom_qty,
                'price_unit': price_unit  # Update price based on new quantity
            })

            return {
                'status': 'success',
                'message': 'Quantità della riga del carrello aggiornata con successo.',
                'info': 'Cart line quantity updated successfully.',
                'cart_line': cart_line.id
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': 'Si è verificato un errore durante l\'aggiornamento della quantità.',
                'info': str(e)
            }, 500

    @http.route('/api/cart_line/<int:id>', auth='public', type='http', methods=['DELETE'], csrf=False, cors='*')
    def delete_cart_line(self, id):
        if request.httprequest.method == 'OPTIONS':
            headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'DELETE, OPTIONS',
                'Access-Control-Allow-Headers': 'Authorization, Content-Type',
                'Access-Control-Max-Age': '86400',
            }
            return Response(status=204, headers=headers)

        try:
            user = SocialMediaAuth.user_auth(self)
            if user['status'] == 'error':
                return Response(json.dumps({
                    'status': 'error',
                    'message': user['message'],
                    'info': 'Authentication failed.'
                }), content_type='application/json', status=401, headers={'Access-Control-Allow-Origin': '*'})

            partner_id = user['user_id']

            cart_line = request.env['sale.order.line'].sudo().browse(id)
            if not cart_line.exists() or cart_line.order_id.partner_id.id != partner_id:
                return Response(json.dumps({
                    'status': 'error',
                    'message': 'La riga del carrello non esiste.',
                    'info': 'Cart line does not exist or does not belong to this customer.'
                }), content_type='application/json', status=404, headers={'Access-Control-Allow-Origin': '*'})

            cart_line.sudo().unlink()

            return Response(json.dumps({
                'status': 'success',
                'message': 'Riga del carrello eliminata con successo.',
                'info': 'Cart line successfully deleted.'
            }), content_type='application/json', headers={'Access-Control-Allow-Origin': '*'})

        except Exception as e:
            return Response(json.dumps({
                'status': 'error',
                'message': 'Si è verificato un errore durante l\'eliminazione della riga del carrello.',
                'info': str(e)
            }), content_type='application/json', status=500, headers={'Access-Control-Allow-Origin': '*'})