from odoo import http, _
from odoo.http import request, Response
import json
from datetime import datetime
from .user_authentication import user_auth

class Ecommerce_orders(http.Controller):

    # get order details
    @http.route('/api/orders/<int:order_id>', auth='public', type='http', methods=['GET'])
    def get_order_single(self, order_id):
        """
        description : Retrieve the order details based on the provided order ID.
        parameters : order_id (int)
        """
        try:
            # Check if order ID is provided
            if not order_id:
                return Response(
                    json.dumps({
                        'status': 'error',
                        'message': 'ID dell\'ordine non fornito.',  # Error message in Italian
                        'info': 'No order ID provided.'  # English description
                    }),
                    content_type='application/json',
                    status=400,
                    headers={'Access-Control-Allow-Origin': '*'}
                )

            # Search for the order with the given ID
            orders = request.env['sale.order'].sudo().search([
                ('id', '=', order_id)
            ])

            if not orders:
                return Response(
                    json.dumps({
                        'status': 'error',
                        'message': 'Ordine non trovato.',  # Error message in Italian
                        'info': 'Order not found.'  # English description
                    }),
                    content_type='application/json',
                    status=404,
                    headers={'Access-Control-Allow-Origin': '*'}
                )

            # Fetch reward points associated with the order
            order_reward_points = request.env['rewards.points'].sudo().search([('order_id', '=', order_id)]).points
            response_data = []

            for order in orders:
                # Retrieve shipping address
                user_address = request.env['social_media.custom_address'].sudo().search([
                    ('id', '=', order.shipping_address_id)
                ])

                shipping_address = f'{user_address.address}, {user_address.continued_address}, {user_address.city}, {user_address.postal_code}, {user_address.village}, {user_address.state_id.name}, {user_address.country_id.name}' if user_address else None

                # Prepare order data
                order_data = {
                    'id': order.id,
                    'name': order.name,
                    'state': order.state,
                    'taxable_amount': order.amount_total,
                    'date_order': order.date_order.strftime('%Y-%m-%d %H:%M:%S') if order.date_order else None,
                    'partner_id': order.partner_id.id,
                    'partner_name': order.partner_id.name,
                    'partner_email': order.partner_id.email,
                    'partner_phone': order.partner_id.phone,
                    'partner_address': shipping_address, 

                    # I have set the VAT percentages to 0 as they are not provided in the scope.
                    'vat_1_percentage': 0,
                    'vat_2_percentage': 0,
                    'shipping_charge': 450,
                    'vat_1_value': 0,
                    'vat_2_value': 0,
                    'total_amount': order.amount_total + 450 + (order.amount_total * 0) + (order.amount_total * 0),
                    'reward_points': order_reward_points,
                    'all_products': []
                }

                # Loop through order lines to get product details
                for line in order.order_line:
                    image_url = '/web/image/product.product/' + str(line.product_id.id) + '/image_1920' if line.product_id.image_1920 else None
                    discount_percentage = request.env['product.template'].sudo().search([('id', '=', line.product_id.id)]).discount

                    product_data = {
                        'id': line.product_id.id,
                        'name': line.product_id.name,
                        'list_price': line.price_unit * line.product_uom_qty,
                        'active': line.product_id.active,
                        'barcode': line.product_id.barcode,
                        'color': line.product_id.color,
                        'image': image_url,
                        'quantity': line.product_uom_qty,
                        'base_price': line.product_id.list_price,
                        'discount': discount_percentage,
                        'order_id': line.order_id.id,
                        'code': line.product_id.code_,
                    }

                    order_data['all_products'].append(product_data)

                response_data.append(order_data)

            # Success response
            return Response(
                json.dumps(response_data),
                content_type='application/json',
                headers={'Access-Control-Allow-Origin': '*'}
            )

        except Exception as e:
            # Error response
            return Response(
                json.dumps({
                    'status': 'error',
                    'message': 'Si è verificato un errore durante il recupero dei dettagli dell\'ordine.',  # Error message in Italian
                    'info': str(e)  # English error description
                }),
                content_type='application/json',
                status=500,
                headers={'Access-Control-Allow-Origin': '*'}
            )



    @http.route('/api/orders', auth='user', type='http', methods=['GET'], csrf=False, cors='*')
    def get_orders(self):
        """
        description : Retrieve all orders for the authenticated user that are in sent, sale, or done state.
        parameters : None
        """
        try:
            # Authenticate the user
            user = user_auth(self)
            if user['status'] == 'error':
                return Response(
                    json.dumps({
                        'status': 'error',
                        'message': user['message'],  # Assuming the message is already in Italian
                        'info': 'Authentication failed.'  # English description
                    }),
                    content_type='application/json',
                    status=401,
                    headers={'Access-Control-Allow-Origin': '*'}
                )

            user_id = user['user_id']

            # Retrieve the partner associated with the user
            partner = request.env['res.users'].browse(user_id).partner_id
            if not partner:
                return Response(json.dumps({
                    'status': 'error',
                    'message': 'Nessun partner trovato per l\'utente.',  # Error message in Italian
                    'info': 'No partner found for the user.'  # English description
                }), content_type='application/json', status=400, headers={'Access-Control-Allow-Origin': '*'})

            # Search for the orders in sent, sale, or done state
            orders = request.env['sale.order'].sudo().search([
                ('partner_id', '=', partner.id),
                ('state', 'in', ['sent', 'sale', 'done'])
            ])

            response_data = []
            for order in orders:

                # Retrieve the shipping address for the order
                user_address = request.env['social_media.custom_address'].sudo().search([
                    ('id', '=', order.shipping_address_id)
                ])

                shipping_address = f'{user_address.address}, {user_address.continued_address}, {user_address.city}, {user_address.postal_code}, {user_address.village}, {user_address.state_id.name}, {user_address.country_id.name}' if user_address else None
                



                # Prepare order data
                order_data = {
                    'id': order.id,
                    'name': order.name,
                    'state': order.state,
                    'taxable_amount': order.amount_total,
                    'date_order': order.date_order.strftime('%Y-%m-%d %H:%M:%S') if order.date_order else None,
                    'partner_id': order.partner_id.id,
                    'partner_name': order.partner_id.name,
                    'partner_email': order.partner_id.email,
                    'partner_phone': order.partner_id.phone,
                    'partner_address': shipping_address,

                    # I have set the VAT percentages to 0 as they are not provided in the scope.
                    'vat_1_percentage': 0,
                    'vat_2_percentage': 0,
                    'shipping_charge': 450,
                    'vat_1_value': 0,
                    'vat_2_value': 0,
                    'total_amount': order.amount_total + 450 + (order.amount_total * 0) + (order.amount_total * 0)
                }

                response_data.append(order_data)

            final_response = {
                'status': 'success',
                'message': 'Ordini recuperati con successo.',  # Success message in Italian
                'info': 'Orders retrieved successfully.',  # English description
                'orders': response_data
            }

            # Success response
            return Response(
                json.dumps(final_response),
                content_type='application/json',
                headers={'Access-Control-Allow-Origin': '*'}
            )

        except Exception as e:
            # Error response
            return Response(
                json.dumps({
                    'status': 'error',
                    'message': 'Si è verificato un errore durante il recupero degli ordini.',  # Error message in Italian
                    'info': str(e)  # English error description
                }),
                content_type='application/json',
                status=500,
                headers={'Access-Control-Allow-Origin': '*'}
            )


    @http.route('/api/confirm_order', auth='user', type='json', methods=['POST'])
    def confirm_order(self, **post):
        """
        description : Confirm the user's order and empty the cart.
        parameters : order_id (int)
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
                return {
                    'status': 'error',  
                    'message': user['message'],  # Assuming the message is already in Italian
                    'info': 'Authentication failed.'  # English description
                }
            
            user_id = user['user_id']
            order_id = request.jsonrequest.get('order_id')

            # Retrieve the partner associated with the user
            partner = request.env['res.users'].browse(user_id).partner_id
            if not partner:
                return {
                    'status': 'error',
                    'message': 'Nessun partner trovato per l\'utente.',  # Error message in Italian
                    'info': 'No partner found for the user.'  # English description
                }
            
            # Search for the order
            order = request.env['sale.order'].sudo().search([
                    ('id', '=', order_id),
                    ('partner_id', '=', partner.id),
                    ('state', '=', 'draft')
                ], limit=1)

            if not order:
                return {
                    'status': 'error',
                    'message': 'Ordine non trovato o già confermato.',  # Error message in Italian
                    'info': 'Order not found or already confirmed.'  # English description
                }, 404
            
            order_line = request.env['sale.order.line'].sudo().search([
                ('order_id', '=', order.id)
            ])

            if not order_line:
                return {
                    'status': 'error',
                    'message': "L'ordine non contiene prodotti.",  # Error message in Italian
                    'info': 'The order contains no products.'  # English description
                }, 400

            # Confirm the order
            order.action_confirm()

            # Retrieve the shipping address
            user_address = request.env['social_media.custom_address'].sudo().search([
                    ('id', '=', order.shipping_address_id)
                ])

            shipping_address =  f'{user_address.address}, {user_address.continued_address}, {user_address.city}, {user_address.postal_code}, {user_address.village}, {user_address.state_id.name}, {user_address.country_id.name}' if user_address else None

            # Success response
            return {
                'status': 'success',
                'message': 'Ordine confermato con successo e carrello svuotato.',  # Success message in Italian
                'info': 'Order confirmed successfully and cart emptied.',  # English description
                'order_id': order.id,
                'order_state': order.state,
                'order_amount_total': order.amount_total,
                'order_date_order': order.date_order,
                'partner_address': shipping_address
            }

        except Exception as e:
            # Error response
            return {
                'status': 'error',
                'message': 'Si è verificato un errore durante la conferma dell\'ordine.',  # Error message in Italian
                'info': str(e)  # English error description
            }, 500
        
        
    @http.route('/api/reorder', auth='user', type='json', methods=['POST'])
    def reorder(self):
        """
        description : Reorder a previously confirmed order.
        parameters : order_id (int)
        """
        try:
            # Authenticate the user
            user = user_auth(self)
            if user['status'] == 'error':
                return {
                    'status': 'error',
                    'message': user['message'],  # Assuming the message is already in Italian
                    'info': 'Authentication failed.'  # English description
                }
            
            user_id = user['user_id']
            order_id = request.jsonrequest.get('order_id')

            # Retrieve the partner associated with the user
            partner = request.env['res.users'].browse(user_id).partner_id
            if not partner:
                return {
                    'status': 'error',
                    'message': "Nessun partner trovato per l'utente.",  # Error message in Italian
                    'info': 'No partner found for the user.'  # English description
                }
            
            # Search for the order
            order = request.env['sale.order'].sudo().search([
                    ('id', '=', order_id),
                    ('partner_id', '=', partner.id),
                    ('state', 'in', ['sent', 'sale', 'done'])
                ], limit=1)

            if not order:
                return {
                    'status': 'error',
                    'message': 'Ordine non trovato o non può essere riordinato.',  # Error message in Italian
                    'info': 'Order not found or cannot be reordered.'  # English description
                }, 404
            
            # Create a new order from the existing one
            new_order = order.copy()
            new_order.action_confirm()

            # Check if the order has reward points
            order_reward_points = request.env['rewards.points'].sudo().search([('order_id', '=', order_id)]).points
            if order_reward_points:
                request.env['rewards.points'].sudo().create({
                    'points': order_reward_points,
                    'user_id': user_id,
                    'order_id': new_order.id,
                    'status': 'gain'
                })

                # Update the total points
                total_points_obj = request.env['rewards.totalpoints'].sudo().search([('user_id', '=', user_id)])
                if total_points_obj:
                    total_points = total_points_obj.total_points + order_reward_points
                    total_points_obj.write({'total_points': total_points})

            # Retrieve the shipping address
            user_address = request.env['social_media.custom_address'].sudo().search([
                    ('id', '=', new_order.shipping_address_id)
                ])

            shipping_address = f'{user_address.address}, {user_address.continued_address}, {user_address.city}, {user_address.postal_code}, {user_address.village}, {user_address.state_id.name}, {user_address.country_id.name}' if user_address else None

            # Success response
            return {
                'status': 'success',
                'message': 'Ordine riordinato con successo.',  # Success message in Italian
                'info': 'Order successfully reordered.',  # English description
                'order_id': new_order.id,
                'order_state': new_order.state,
                'order_amount_total': new_order.amount_total,
                'order_date_order': new_order.date_order,
                'order_reward_points': order_reward_points,
                'partner_address': shipping_address
            }

        except Exception as e:
            # Error response
            return {
                'status': 'error',
                'message': 'Si è verificato un errore durante il riordino.',  # Error message in Italian
                'info': str(e)  # English error description
            }, 500


    
    @http.route('/api/cancel_order', auth='user', type='json', methods=['POST'], csrf=False)
    def cancel_order(self, **post):
        """
        description : Cancel a specific order for the authenticated user.
        parameters : order_id (int)
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
                return {
                    'status': 'error',
                    'message': user['message'],  # Assuming the message is already in Italian
                    'info': 'Authentication failed.'  # English description
                }

            user_id = user['user_id']
            order_id = request.jsonrequest.get('order_id')

            # Retrieve the partner associated with the user
            partner = request.env['res.users'].browse(user_id).partner_id
            if not partner:
                return {
                    'status': 'error',
                    'message': 'Nessun partner trovato per l\'utente.',  # Error message in Italian
                    'info': 'No partner found for the user.'  # English description
                }

            # Search for the order
            order = request.env['sale.order'].sudo().search([
                    ('id', '=', order_id),
                    ('partner_id', '=', partner.id),
                    ('state', '!=', 'draft')
                ], limit=1)

            if not order:
                return {
                    'status': 'error',
                    'message': 'Ordine non trovato o già confermato.',  # Error message in Italian
                    'info': 'Order not found or already confirmed.'  # English description
                }, 404

            # Check if the order has any products
            order_line = request.env['sale.order.line'].search([
                ('order_id', '=', order.id)
            ])

            if not order_line:
                return {
                    'status': 'error',
                    'message': 'L\'ordine non contiene prodotti.',  # Error message in Italian
                    'info': 'Order has no products.'  # English description
                }, 400

            # Cancel the order
            order.action_cancel()

            # Success response
            return {
                'status': 'success',
                'message': 'Ordine annullato con successo.',  # Success message in Italian
                'info': 'Order cancelled successfully.',  # English description
                'order_id': order.id,
                'order_state': order.state,
                'order_amount_total': order.amount_total,
                'order_date_order': order.date_order,
            }

        except Exception as e:
            # Error response
            return {
                'status': 'error',
                'message': 'Si è verificato un errore durante l\'annullamento dell\'ordine.',  # Error message in Italian
                'info': str(e)  # English error description
            }, 500

        
    @http.route('/api/delete_order/<int:order_id>', auth='user', type='http', methods=['DELETE'], csrf=False)
    def delete_order(self, order_id):
        """
        description : Delete a specific order if it's in draft or canceled state.
        parameters : order_id (int)
        """
        try:
            # Authenticate the user
            user = user_auth(self)
            if user['status'] == 'error':
                return Response(
                    json.dumps({
                        'status': 'error',
                        'message': user['message'],  # Assuming the message is already in Italian
                        'info': 'Authentication failed.'  # English description
                    }),
                    content_type='application/json',
                    status=401,
                    headers={'Access-Control-Allow-Origin': '*'}
                )

            user_id = user['user_id']

            # Retrieve the partner associated with the user
            partner = request.env['res.users'].browse(user_id).partner_id
            if not partner:
                return Response(json.dumps({
                    'status': 'error',
                    'message': 'Nessun partner trovato per l\'utente.',  # Error message in Italian
                    'info': 'No partner found for the user.'  # English description
                }), content_type='application/json', status=400, headers={'Access-Control-Allow-Origin': '*'})

            # Search for the order
            order = request.env['sale.order'].sudo().search([
                    ('id', '=', order_id),
                    ('partner_id', '=', partner.id),
                    ('state', 'in', ['draft', 'cancel'])
                ], limit=1)

            if not order:
                return Response(
                    json.dumps({
                        'status': 'error',
                        'message': 'Ordine non trovato o non può essere eliminato.',  # Error message in Italian
                        'info': 'Order not found or cannot be deleted.'  # English description
                    }),
                    content_type='application/json',
                    status=404,
                    headers={'Access-Control-Allow-Origin': '*'}
                )

            # Delete the order
            order.unlink()

            return Response(
                json.dumps({
                    'status': 'success',
                    'message': 'Ordine eliminato con successo.',  # Success message in Italian
                    'info': 'Order deleted successfully.'  # English description
                }),
                content_type='application/json',
                headers={'Access-Control-Allow-Origin': '*'}
            )
        except Exception as e:
            # Error response
            return Response(
                json.dumps({
                    'status': 'error',
                    'message': 'Si è verificato un errore durante l\'eliminazione dell\'ordine.',  # Error message in Italian
                    'info': str(e)  # English error description
                }),
                content_type='application/json',
                status=500,
                headers={'Access-Control-Allow-Origin': '*'}
            )


    @http.route('/api/create_invoice', auth='user', type='json', methods=['POST'])
    def create_invoice(self, **post):
        """
        description : Create an invoice for a confirmed order and send it via email.
        parameters : order_id (int)
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
                return {
                    'status': 'error',
                    'message': user['message'],  # Assuming the message is already in Italian
                    'info': 'Authentication failed.'  # English description
                }

            user_id = user['user_id']
            order_id = request.jsonrequest.get('order_id')

            # Retrieve the partner associated with the user
            partner = request.env['res.users'].browse(user_id).partner_id
            if not partner:
                return Response(json.dumps({
                    'status': 'error',
                    'message': 'Nessun partner trovato per l\'utente.',  # Error message in Italian
                    'info': 'No partner found for the user.'  # English description
                }), content_type='application/json', status=400, headers={'Access-Control-Allow-Origin': '*'})

            # Search for the order
            order = request.env['sale.order'].sudo().search([
                    ('id', '=', order_id),
                    ('partner_id', '=', partner.id),
                    ('state', '=', 'sale')
                ], limit=1)

            if not order:
                return {
                    'status': 'error',
                    'message': 'Ordine non trovato o non confermato.',  # Error message in Italian
                    'info': 'Order not found or not confirmed.'  # English description
                }, 404

            # Create the invoice
            invoice = order._create_invoices()

            # Send the invoice email
            mail_values = {
                'subject': 'Fattura per Ordine %s' % order.name,  # Italian subject
                'email_to': partner.email,
                'body_html': 'Trova in allegato la fattura per il tuo ordine.',  # Italian email body
                'email_from': request.env.user.email or 'admin@gmail.com'
            }

            mail = request.env['mail.mail'].create(mail_values)
            mail.send()

            # Success response
            return {
                'status': 'success',
                'message': 'Fattura creata e inviata con successo.',  # Success message in Italian
                'info': 'Invoice created and sent successfully.',  # English description
                'invoice_id': invoice.id,
                'invoice_state': invoice.state,
                'invoice_amount_total': invoice.amount_total,
                'invoice_date_invoice': invoice.date_invoice,
            }

        except Exception as e:
            # Error response
            return {
                'status': 'error',
                'message': 'Si è verificato un errore durante la creazione della fattura.',  # Error message in Italian
                'info': str(e)  # English error description
            }, 500
        
    