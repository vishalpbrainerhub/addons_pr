from odoo import http
from odoo.http import request, Response
import json
from .user_authentication import SocialMediaAuth
from .test import get_batch_product_details, get_product_details


class EcommerceCartLine(http.Controller):
    
    @http.route('/api/cart_line', auth='public', type='http', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def get_cart_line(self):
        if request.httprequest.method == 'OPTIONS':
            headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS', 
                'Access-Control-Allow-Headers': 'Authorization, Content-Type',
                'Access-Control-Max-Age': '86400',
            }
            return Response(status=204, headers=headers)
            
        try:
            user_info = SocialMediaAuth.user_auth(self)
            if user_info['status'] == 'error':
                return Response(json.dumps({
                    'status': 'error',
                    'message': 'Autenticazione fallita',
                    'info': user_info['message']
                }), content_type='application/json', status=401, headers={'Access-Control-Allow-Origin': '*'})

            partner_id = user_info['user_id']
                
            pricelist_id = request.env['res.partner'].sudo().browse(partner_id).property_product_pricelist.id
            if not pricelist_id:
                return Response(json.dumps({
                    'status': 'error',
                    'message': 'Nessun listino trovato per questo partner.',
                    'info': 'No pricelist found for this partner.'
                }), content_type='application/json', status=404, headers={'Access-Control-Allow-Origin': '*'})

            # Get active cart lines
            cart_lines = request.env['sale.order.line'].sudo().search_read([
                ('order_id.partner_id', '=', partner_id),
                ('order_id.state', '=', 'draft')
            ], ['product_id', 'price_unit', 'product_uom_qty', 'order_id'])

            # Prepare batch price requests
            batch_price_requests = []
            product_map = {}
            
            for line in cart_lines:
                if line['product_uom_qty'] <= 0:
                    # Remove lines with zero quantity
                    request.env['sale.order.line'].sudo().browse(line['id']).unlink()
                    continue
                    
                product_product = request.env['product.product'].sudo().browse(line['product_id'][0])
                product = request.env['product.template'].sudo().browse(product_product.product_tmpl_id.id)
                
                # Get external_id for the product
                external_id = product.external_id if hasattr(product, 'external_id') else product.id
                
                product_map[str(external_id)] = {
                    'line_id': line['id'],
                    'product': product,
                    'product_id': product.id,
                    'quantity': line['product_uom_qty'],
                    'order_id': line['order_id'][0]
                }
                
                batch_price_requests.append({
                    'product_id': external_id,
                    'qty': line['product_uom_qty']
                })
            
            # Get all prices in batch
            all_prices = get_batch_product_details(pricelist_id, batch_price_requests, partner_id)
            
            # Process results
            cart = []
            
            for product_ext_id, product_info in product_map.items():
                product = product_info['product']
                quantity = product_info['quantity']
                
                # Get price from batch results, or fallback to individual call if missing
                final_price = all_prices.get(int(product_ext_id), 
                                          get_product_details(pricelist_id, product_ext_id, 
                                                             quantity, partner_id))
                
                # Apply discount if needed
                product_discount = getattr(product, 'discount', 0.0)
                if product_discount:
                    final_price = final_price * (1 - (product_discount / 100))
                    final_price = round(final_price, 2)
                
                cart_item = {
                    'id': product_info['line_id'],
                    'product_id': product.id,
                    'name': product.name,
                    'list_price': final_price * quantity,
                    'quantity': quantity,
                    'image': f'/web/image/product.template/{product.id}/image_1920' if product.image_1920 else None,
                    'barcode': product.barcode,
                    'active': product.active,
                    'color': getattr(product, 'color', None),
                    'base_price': final_price,
                    'discount': product_discount,
                    'order_id': product_info['order_id'],
                    'code': getattr(product, 'default_code', None),
                    'external_id': external_id
                }
                cart.append(cart_item)
            
            # Calculate cart totals
            total_price = sum(item['list_price'] for item in cart)
            
            response_data = {
                'cart': cart,
                'total_items': len(cart),
                'total_price': total_price,
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
        parameters : product_id (int), quantity (float), product_price (float)
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

            partner_id = user['user_id']  # This is partner_id from token

            product_id = request.jsonrequest.get('product_id')
            product_uom_qty = request.jsonrequest.get('quantity', False)
            price_unit = request.jsonrequest.get('product_price', False)

            if not product_id or not product_uom_qty or not price_unit:
                return {
                    'status': 'error',
                    'message': 'ID del prodotto, quantità e prezzo sono necessari.',
                    'info': 'Product ID, quantity, and price are required.'
                }, 400

            product = request.env['product.template'].sudo().browse(product_id)
            if not product.exists():
                return {
                    'status': 'error',
                    'message': 'Il prodotto specificato non esiste o è stato eliminato.',
                    'info': 'The specified product does not exist or has been deleted.'
                }, 400
            # if not product.exists():
            #     template = request.env['product.template'].sudo().browse(product_id)
            #     if template.exists():
            #         product = template.product_variant_ids[0]   
            #         if not product:
            #             return {
            #                 'status': 'error',
            #                 'message': 'La variante del prodotto specificata non esiste o è stata eliminata.',
            #                 'info': 'The specified product variant does not exist or has been deleted.'
            #             }, 400
            #     else:
            #         return {
            #             'status': 'error',
            #             'message': 'Il prodotto specificato non esiste o è stato eliminato.',
            #             'info': 'The specified product does not exist or has been deleted.'
            #         }, 400

            price_unit = price_unit - (price_unit * product.discount / 100)

            shipping_address = request.env['social_media.custom_address'].sudo().search([
                ('partner_id', '=', partner_id), 
                ("default", "=", True)
            ], limit=1)

            # Check for existing draft order with sudo
            sale_order = request.env['sale.order'].sudo().search([
                ('partner_id', '=', partner_id), 
                ('state', '=', 'draft')
            ], limit=1)
            
            if not sale_order:
                # Create new sale order with sudo
                sale_order = request.env['sale.order'].sudo().with_context(
                    default_partner_id=partner_id
                ).create({
                    'partner_id': partner_id,
                    'shipping_address_id': shipping_address.id if shipping_address else False,
                })

            cart_line_check = request.env['sale.order.line'].sudo().search([
                ('product_id', '=', product.id), 
                ('order_id', '=', sale_order.id)
            ], limit=1)
            
            if cart_line_check:
                return {
                    'status': 'error',
                    'message': 'Prodotto già nel carrello.',
                    'info': 'Product already in cart.'
                }

            cart_line = request.env['sale.order.line'].sudo().with_context(
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

            sale_order = request.env['sale.order'].sudo().search([
                ('partner_id', '=', partner_id),
                ('state', '=', 'draft')
            ], limit=1)
            
            if not sale_order:
                sale_order = request.env['sale.order'].sudo().create({
                    'partner_id': partner_id,
                })

            cart_line = request.env['sale.order.line'].sudo().browse(id)
            if not cart_line.exists() or cart_line.order_id.partner_id.id != partner_id:
                return {
                    'status': 'error',
                    'message': 'La riga del carrello non esiste.',
                    'info': 'Cart line does not exist or does not belong to this customer.'
                }, 404

            cart_line.sudo().write({
                'product_uom_qty': product_uom_qty
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