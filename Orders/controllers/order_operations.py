from odoo import http, _ , fields
from odoo.http import request, Response
import json
from datetime import datetime
from .user_authentication import SocialMediaAuth
from .notification_service import CustomerController
from .helper_functions import ProductPriceController

import logging
_logger = logging.getLogger(__name__)

notification_service = CustomerController()

class Ecommerce_orders(http.Controller):

    def _calculate_vat(self, order):
        """
        Calculate VAT (IVA) for an order by applying a fixed 22% tax rate.
        
        Args:
            order: The sale.order object
            
        Returns:
            dict: Dictionary containing vat percentages and values
        """
        vat_data = {
            'vat_1_percentage': 22.0,
            'vat_2_percentage': 0.0,
            'vat_1_value': 0.0,
            'vat_2_value': 0.0
        }
        
        # Process each order line and apply 22% tax
        for line in order.order_line:
            line_amount = line.price_subtotal
            
            # Calculate and add tax value with 22% rate
            tax_value = round(line_amount * (22.0 / 100.0), 2)
            vat_data['vat_1_value'] += tax_value
        
        # Final rounding
        vat_data['vat_1_value'] = round(vat_data['vat_1_value'], 2)
        
        return vat_data

    @http.route('/api/orders/<int:order_id>', auth='public', type='http', methods=['GET'])
    def get_order_single(self, order_id):
        try:
            user = SocialMediaAuth.user_auth(self)
            if user['status'] == 'error':
                return Response(json.dumps({
                    'status': 'error',
                    'message': user['message'],
                    'info': 'Authentication failed.'
                }), content_type='application/json', status=401)

            partner_id = user['user_id']
            
            # Search for orders where either:
            # 1. User is the direct customer (partner_id = user_id)
            # 2. User is the agent who placed the order (order_agent_id = user_id)
            orders = request.env['sale.order'].sudo().search([
                ('id', '=', order_id),
                '|',
                ('partner_id', '=', partner_id),
                ('order_agent_id', '=', partner_id)
            ])

            if not orders:
                return Response(json.dumps({
                    'status': 'error',
                    'message': 'Ordine non trovato.',
                    'info': 'Order not found.'
                }), content_type='application/json', status=404)

            reward_points_records = request.env['rewards.points'].sudo().search([('order_id', '=', order_id)])
            order_reward_points = sum(reward_points_records.mapped('points')) if reward_points_records else 0
            response_data = []

            for order in orders:
                user_address = request.env['social_media.custom_address'].sudo().search([
                    ('id', '=', order.shipping_address_id)
                ])
                shipping_address = f'{user_address.address}, {user_address.continued_address}, {user_address.city}, {user_address.postal_code}, {user_address.village}, {user_address.state_id.name}, {user_address.country_id.name}' if user_address else None
                vat_data = self._calculate_vat(order)

                # Determine if this is an agent order for the current user
                is_agent_order = order.order_agent_id == partner_id
                agent_info = None
                
                if is_agent_order:
                    # Get agent information
                    agent_partner = request.env['res.partner'].sudo().browse(order.order_agent_id)
                    agent_info = {
                        'agent_id': order.order_agent_id,
                        'agent_name': agent_partner.name,
                        'agent_email': agent_partner.email,
                        'customer_id': order.partner_id.id,
                        'customer_name': order.partner_id.name,
                        'customer_email': order.partner_id.email
                    }

                order_data = {
                    'id': order.id,
                    'name': order.name,
                    'state': order.state,
                    'taxable_amount': order.amount_untaxed,
                    'date_order': order.date_order.strftime('%Y-%m-%d %H:%M:%S') if order.date_order else None,
                    'partner_id': order.partner_id.id,
                    'partner_name': order.partner_id.name,
                    'partner_email': order.partner_id.email,
                    'external_order_state': order.external_order_state,
                    'partner_phone': order.partner_id.phone,
                    'partner_address': shipping_address,
                    'vat_1_percentage': vat_data['vat_1_percentage'],
                    'vat_2_percentage': vat_data['vat_2_percentage'],
                    'shipping_charge': 0,
                    'vat_1_value': vat_data['vat_1_value'],
                    'vat_2_value': vat_data['vat_2_value'],
                    'total_amount': order.amount_total,
                    'reward_points': order_reward_points,
                    'is_agent_order': is_agent_order,
                    'agent_attach': order.agent_attach if hasattr(order, 'agent_attach') else False,
                    'agent_info': agent_info,
                    'note': order.note if order.note else None,
                    'all_products': []
                }

                for line in order.sudo().order_line:
                    print(line.product_id.id, "------------product id from order line")
                    image_url = '/web/image/product.product/' + str(line.product_id.id) + '/image_1920' if line.product_id.image_1920 else None
                    
                    product_data = {
                        'id': line.product_id.id,
                        'name': line.product_id.name,
                        'list_price': line.price_unit * line.product_uom_qty,
                        'active': line.product_id.active,
                        'barcode': line.product_id.barcode,
                        'color': line.product_id.color,
                        'image': image_url,
                        'quantity': line.product_uom_qty,
                        'base_price': line.price_unit,
                        'discount': line.discount or 0,
                        'order_id': line.order_id.id,
                        'code': line.product_id.default_code,
                    }
                    order_data['all_products'].append(product_data)

                response_data.append(order_data)

            return Response(json.dumps(response_data), content_type='application/json')

        except Exception as e:
            return Response(json.dumps({
                'status': 'error',
                'message': 'Si è verificato un errore durante il recupero dei dettagli dell\'ordine.',
                'info': str(e)
            }), content_type='application/json', status=500)

    @http.route('/api/orders', auth='public', type='http', methods=['GET'])
    def get_orders(self):
        try:
            user = SocialMediaAuth.user_auth(self)
            if user['status'] == 'error':
                return Response(json.dumps({
                    'status': 'error', 
                    'message': user['message'],
                    'info': 'Authentication failed.'
                }), content_type='application/json', status=401)

            partner_id = user['user_id']
            
            # Get search parameters from request
            search_query = request.params.get('search', '').strip()
            search_customer = request.params.get('search_customer', '').strip()
            search_order = request.params.get('search_order', '').strip()
            
            # Build base domain for orders
            base_domain = [('state', '!=', 'draft')]
            
            # Add user-specific domain (agent or customer)
            user_domain = [
                '|',
                ('partner_id', '=', partner_id),
                ('order_agent_id', '=', partner_id)
            ]
            
            # Build search domain
            search_domain = []
            
            # If there's a general search query, search in both customer name and order name
            if search_query:
                search_domain.extend([
                    '|',
                    ('partner_id.name', 'ilike', search_query),
                    ('name', 'ilike', search_query)
                ])
            
            # If there's a specific customer search
            if search_customer:
                search_domain.append(('partner_id.name', 'ilike', search_customer))
            
            # If there's a specific order search
            if search_order:
                search_domain.append(('name', 'ilike', search_order))
            
            # Combine all domains
            final_domain = base_domain + user_domain
            if search_domain:
                final_domain.extend(search_domain)
            
            # Search for orders
            orders = request.env['sale.order'].sudo().search(final_domain)
            
            # Additional filtering for agent users searching by customer name
            # This ensures agents can only see orders from their associated customers
            if (search_query or search_customer):
                # Check if current user is an agent
                agent_orders = request.env['sale.order'].sudo().search([
                    ('order_agent_id', '=', partner_id),
                    ('state', '!=', 'draft')
                ])
                
                # Get all customer IDs associated with this agent
                agent_customer_ids = agent_orders.mapped('partner_id.id')
                
                # If user is an agent and searching, filter orders to only show:
                # 1. Orders where user is the direct customer
                # 2. Orders where user is the agent AND the customer is in their associated customers
                if agent_customer_ids:
                    filtered_orders = orders.filtered(lambda o: 
                        o.partner_id.id == partner_id or  # User is direct customer
                        (o.order_agent_id == partner_id and o.partner_id.id in agent_customer_ids)  # User is agent and customer is associated
                    )
                    orders = filtered_orders

            response_data = []
            for order in orders:
                user_address = request.env['social_media.custom_address'].sudo().search([
                    ('id', '=', order.shipping_address_id)
                ])
                shipping_address = f'{user_address.address}, {user_address.continued_address}, {user_address.city}, {user_address.postal_code}, {user_address.village}, {user_address.state_id.name}, {user_address.country_id.name}' if user_address else None
                
                # Using improved VAT calculation
                vat_data = self._calculate_vat(order)

                # Determine if this is an agent order for the current user
                is_agent_order = order.order_agent_id == partner_id
                agent_info = None
                
                if is_agent_order:
                    # Get agent information
                    agent_partner = request.env['res.partner'].sudo().browse(order.order_agent_id)
                    agent_info = {
                        'agent_id': order.order_agent_id,
                        'agent_name': agent_partner.name,
                        'agent_email': agent_partner.email,
                        'customer_id': order.partner_id.id,
                        'customer_name': order.partner_id.name,
                        'customer_email': order.partner_id.email
                    }

                order_data = {
                    'id': order.id,
                    'name': order.name,
                    'state': order.state,
                    'taxable_amount': order.amount_untaxed,
                    'date_order': order.date_order.strftime('%Y-%m-%d %H:%M:%S') if order.date_order else None,
                    'partner_id': order.partner_id.id,
                    'partner_name': order.partner_id.name,
                    'partner_email': order.partner_id.email,
                    'partner_phone': order.partner_id.phone,
                    'partner_address': shipping_address,
                    'vat_1_percentage': vat_data['vat_1_percentage'],
                    'vat_2_percentage': vat_data['vat_2_percentage'],
                    'shipping_charge': 0,
                    'vat_1_value': vat_data['vat_1_value'],
                    'vat_2_value': vat_data['vat_2_value'],
                    'total_amount': order.amount_total,
                    'is_agent_order': is_agent_order,
                    'agent_attach': order.agent_attach if hasattr(order, 'agent_attach') else False,
                    'agent_info': agent_info,
                    'note': order.note if order.note else None
                }
                response_data.append(order_data)

            # Prepare response message
            search_info = []
            if search_query:
                search_info.append(f"general search: '{search_query}'")
            if search_customer:
                search_info.append(f"customer search: '{search_customer}'")
            if search_order:
                search_info.append(f"order search: '{search_order}'")
            
            message = 'Ordini recuperati con successo.'
            info = 'Orders retrieved successfully.'
            if search_info:
                info += f" Applied filters: {', '.join(search_info)}"

            return Response(json.dumps({
                'status': 'success',
                'message': message,
                'info': info,
                'total_orders': len(response_data),
                'search_applied': bool(search_query or search_customer or search_order),
                'orders': response_data
            }), content_type='application/json')

        except Exception as e:
            return Response(json.dumps({
                'status': 'error',
                'message': 'Si è verificato un errore durante il recupero degli ordini.',
                'info': str(e)
            }), content_type='application/json', status=500)

    @http.route('/api/confirm_order', auth='public', type='json', methods=['POST'])
    def confirm_order(self, **post):
        try:
            user = SocialMediaAuth.user_auth(self)
            if user['status'] == 'error':
                return {'status': 'error', 'message': user['message'], 'info': 'Authentication failed.'}

            partner_id = user['user_id']
            order_id = request.jsonrequest.get('order_id')
            agent_attach = request.jsonrequest.get('agent_attach', None)
            order_agent_id = request.jsonrequest.get('order_agent_id', None)
            agent_customer_id = request.jsonrequest.get('agent_customer_id', None)
            note =  request.jsonrequest.get('note', None)

            
            print('order_id',order_id)
            print('agent_attach',agent_attach)
            print('order_agent_id',order_agent_id)
            print('agent_customer_id',agent_customer_id)
            print('note',note)
            
            print("------------------------------------------")
            print("------------------------------------------")
            print("------------------------------------------")
            
            if not order_id:
                return {'status': 'error', 'message': 'ID dell\'ordine non fornito.', 'info': 'Order ID is required.'}, 400

            # For agent orders, search by order_id only since partner_id will change
            if agent_attach and agent_customer_id:
                order = request.env['sale.order'].sudo().search([
                    ('id', '=', order_id),
                    ('state', '=', 'draft')
                ], limit=1)
            else:
                order = request.env['sale.order'].sudo().search([
                    ('id', '=', order_id),
                    ('partner_id', '=', partner_id),
                    ('state', '=', 'draft')
                ], limit=1)

            if not order:
                return {'status': 'error', 'message': 'Ordine non trovato o già confermato.', 
                    'info': 'Order not found or already confirmed.'}, 404

            # Handle agent-placed orders
            if agent_attach and order_agent_id and agent_customer_id:
                # Update order with agent information
                order_data = {
                    'agent_attach': agent_attach,
                    'order_agent_id': order_agent_id,
                    'partner_id': agent_customer_id  # Change order to customer's ID
                }
                
                # Add note if provided
                if note:
                    order_data['note'] = note
                    
                order.sudo().write(order_data)
                
                # Use customer's partner for price calculations and rewards
                partner_id = agent_customer_id
                partner = request.env['res.partner'].sudo().browse(partner_id)
            else:
                if note:
                    order.sudo().write({'note': note})
                partner = request.env['res.partner'].sudo().browse(partner_id)

            order_line = request.env['sale.order.line'].sudo().search([('order_id', '=', order.id)])
            if not order_line:
                return {'status': 'error', 'message': "L'ordine non contiene prodotti.", 
                    'info': 'The order contains no products.'}, 400

            # Get partner's pricelist
            price_list = partner.property_product_pricelist
            
            if not price_list:
                return {'status': 'error', 'message': 'Listino prezzi non trovato.', 
                    'info': 'Price list not found.'}, 400

            # Update prices based on pricelist before confirming
            for line in order_line:
                product_product = request.env['product.product'].sudo().browse(line.product_id.id)
                product_tmpl = request.env['product.template'].sudo().browse(product_product.product_tmpl_id.id)
                
                pricelist_price = price_list.get_product_price(product_tmpl, line.product_uom_qty, partner)
                price = pricelist_price if pricelist_price > 0 else product_tmpl.external_basic_price

                # Apply product discount if any
                if product_tmpl.discount:
                    price = price * (1 - (product_tmpl.discount / 100))
                    price = round(price, 2)
                
                if price:
                    line.sudo().write({'price_unit': price})

            # Confirm order
            order.sudo().action_confirm()

            # Handle rewards points
            total_points = sum(line.product_id.rewards_score * line.product_uom_qty for line in order_line)
            if total_points > 0:
                request.env['rewards.points'].sudo().create({
                    'user_id': agent_customer_id if (agent_attach and agent_customer_id) else partner_id,
                    'order_id': order.id,
                    'points': total_points,
                    'status': 'gain'
                })

                total_points_obj = request.env['rewards.totalpoints'].sudo().search([
                    ('user_id', '=', agent_customer_id if (agent_attach and agent_customer_id) else partner_id)
                ], limit=1)
                
                if total_points_obj:
                    total_points_obj.sudo().write({
                        'total_points': total_points_obj.total_points + total_points
                    })
                else:
                    request.env['rewards.totalpoints'].sudo().create({
                        'user_id': agent_customer_id if (agent_attach and agent_customer_id) else partner_id,
                        'total_points': total_points
                    })

            # Get shipping address
            user_address = request.env['social_media.custom_address'].sudo().search([
                ('id', '=', order.shipping_address_id)
            ])

            shipping_address = f'{user_address.address}, {user_address.continued_address}, {user_address.city}, {user_address.postal_code}, {user_address.village}, {user_address.state_id.name}, {user_address.country_id.name}' if user_address else None

            # Send confirmation email
            template = request.env['mail.template'].sudo().create({
                'name': 'Conferma Ordine',
                'email_from': 'admin@primapaint.com',
                'email_to': f"{order.partner_id.email}, staff@primapaint.it",
                'subject': f'Ordine #{order.name} Confermato',
                'body_html': f'''
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #2C3E50;">Conferma Ordine</h2>
                        
                        <p>Caro/a {order.partner_id.name},</p>
                        
                        <p>Grazie per il tuo ordine. Dettagli dell'ordine:</p>
                        
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">
                            <p><strong>Numero Ordine:</strong> {order.name}</p>
                            <p><strong>Codici Prodotto:</strong> {', '.join([line.product_id.default_code or 'N/A' for line in order.order_line])}</p>
                            <p><strong>Data Ordine:</strong> {order.date_order.strftime('%Y-%m-%d %H:%M')}</p>
                            <p><strong>Importo Totale:</strong> {order.currency_id.symbol}{order.amount_total:.2f}</p>
                            {f'<p><strong>Ordine Agente:</strong> Sì (ID Agente: {order_agent_id})</p>' if agent_attach else ''}
                            {f'<p><strong>Note:</strong> {order.note}</p>' if order.note else ''}
                        </div>

                        <h3 style="color: #2C3E50; margin-top: 20px;">Indirizzo di Spedizione:</h3>
                        <p style="background: #f8f9fa; padding: 15px; border-radius: 5px;">
                            {order.partner_shipping_id.street or ''}<br>
                            {order.partner_shipping_id.city or ''}, {order.partner_shipping_id.state_id.name or ''} {order.partner_shipping_id.zip or ''}<br>
                            {order.partner_shipping_id.country_id.name or ''}
                        </p>

                        <p style="color: #666; margin-top: 30px; font-size: 12px;">
                            Se hai domande, ti preghiamo di contattare il nostro servizio clienti.
                        </p>
                    </div>
                ''',
                'model_id': request.env['ir.model']._get('sale.order').id,
                'auto_delete': True
            })
            template.send_mail(order.id, force_send=True)

            # Handle notifications - send to both customer and agent
            if agent_attach and agent_customer_id:
                # Send notification to CUSTOMER
                customer_filter = request.env['notification.status'].sudo().search([('partner_id', '=', agent_customer_id)], limit=1)
                if customer_filter.order:
                    customer_notification = request.env['customer.notification'].sudo().search([('partner_id', '=', agent_customer_id)], limit=1)
                    if customer_notification.onesignal_player_id:
                        notification_service.send_onesignal_notification(
                            customer_notification.onesignal_player_id,
                            'Il tuo ordine è stato inserito con successo',
                            'Ordine Confermato',
                            {'type': 'order_placed', 'role': 'customer'}
                        )
                        
                        request.env['notification.storage'].sudo().create({
                            'message': 'Il tuo ordine è stato inserito con successo',
                            'patner_id': agent_customer_id,
                            'title': 'Ordine Confermato',
                            'data': {'type': 'order_placed', 'role': 'customer'},
                            'include_player_ids': customer_notification.onesignal_player_id,
                            'filter': 'order'
                        })
                
                # Send notification to AGENT
                agent_filter = request.env['notification.status'].sudo().search([('partner_id', '=', user['user_id'])], limit=1)
                if agent_filter.order:
                    agent_notification = request.env['customer.notification'].sudo().search([('partner_id', '=', user['user_id'])], limit=1)
                    if agent_notification.onesignal_player_id:
                        customer_name = request.env['res.partner'].sudo().browse(agent_customer_id).name
                        notification_service.send_onesignal_notification(
                            agent_notification.onesignal_player_id,
                            f'Ordine confermato per {customer_name}',
                            'Ordine Agente Completato',
                            {'type': 'agent_order_placed', 'role': 'agent', 'customer_id': agent_customer_id}
                        )
                        
                        request.env['notification.storage'].sudo().create({
                            'message': f'Ordine confermato per {customer_name}',
                            'patner_id': user['user_id'],
                            'title': 'Ordine Agente Completato',
                            'data': {'type': 'agent_order_placed', 'role': 'agent', 'customer_id': agent_customer_id},
                            'include_player_ids': agent_notification.onesignal_player_id,
                            'filter': 'order'
                        })

            else:
                # Regular customer order notification
                filter_notification = request.env['notification.status'].sudo().search([('partner_id', '=', partner_id)], limit=1)
                if filter_notification.order:
                    customer = request.env['customer.notification'].sudo().search([('partner_id', '=', partner_id)], limit=1)
                    device_token = customer.onesignal_player_id       
                    if device_token:
                        notification_service.send_onesignal_notification(
                            device_token,
                            'Ordine inserito con successo',
                            'Ordine inserito',
                            {'type': 'order_placed', 'role': 'customer'}
                        )
                        
                        request.env['notification.storage'].sudo().create({
                            'message': 'Ordine inserito con successo',
                            'patner_id': partner_id,
                            'title': 'Ordine inserito',
                            'data': {'type': 'order_placed', 'role': 'customer'},
                            'include_player_ids': device_token,
                            'filter': 'order'
                        })

            return {
                'status': 'success',
                'message': 'Ordine inserito con successo e carrello svuotato.',
                'info': 'Order placed successfully and cart emptied.',
                'order_id': order.id,
                'order_state': order.state,
                'order_amount_total': order.amount_total,
                'order_date_order': order.date_order.strftime('%Y-%m-%d %H:%M:%S') if order.date_order else None,
                'partner_address': shipping_address,
                'reward_points_earned': total_points if total_points > 0 else 0,
                'agent_order': agent_attach,
                'order_agent_id': order_agent_id if agent_attach else None,
                'customer_id': agent_customer_id if agent_attach else partner_id
            }

        except Exception as e:
            return {'status': 'error', 'message': 'Si è verificato un errore durante la conferma dell\'ordine.',
                    'info': str(e)}, 500
        

    @http.route('/api/reorder', auth='public', type='json', methods=['POST'])
    def reorder(self):
        try:
            user = SocialMediaAuth.user_auth(self)
            if user['status'] == 'error':
                return {'status': 'error', 'message': user['message'], 'info': 'Authentication failed.'}

            partner_id = user['user_id']
            order_id = request.jsonrequest.get('order_id')

            # Search for orders where either:
            # 1. User is the direct customer (partner_id = user_id)
            # 2. User is the agent who placed the order (order_agent_id = user_id)  
            order = request.env['sale.order'].sudo().search([
                ('id', '=', order_id),
                ('state', 'in', ['sent', 'sale', 'done']),
                '|',
                ('partner_id', '=', partner_id),
                ('order_agent_id', '=', partner_id)
            ], limit=1)

            if not order:
                return {'status': 'error', 'message': 'Ordine non trovato o non può essere riordinato.',
                    'info': 'Order not found or cannot be reordered.'}, 404

            # Determine if this is an agent reorder
            is_agent_reorder = order.order_agent_id == partner_id
            original_customer_id = order.partner_id.id if is_agent_reorder else partner_id
            
            # Create new order
            new_order = order.sudo().copy()
            
            # If it's an agent reorder, preserve agent information
            if is_agent_reorder:
                new_order.sudo().write({
                    'agent_attach': order.agent_attach,
                    'order_agent_id': order.order_agent_id,
                    'partner_id': original_customer_id  # Keep customer as order owner
                })
            
            # Get the appropriate partner for pricelist (customer, not agent)
            pricing_partner = request.env['res.partner'].sudo().browse(original_customer_id)
            price_list = pricing_partner.property_product_pricelist
            
            if not price_list:
                return {'status': 'error', 'message': 'Listino prezzi non trovato.', 
                    'info': 'Price list not found.'}, 400

            # Update prices based on customer's current pricelist
            for line in new_order.order_line:
                product_product = request.env['product.product'].sudo().browse(line.product_id.id)
                product_tmpl = request.env['product.template'].sudo().browse(product_product.product_tmpl_id.id)
                
                pricelist_price = price_list.get_product_price(product_tmpl, line.product_uom_qty, pricing_partner)
                price = pricelist_price if pricelist_price > 0 else product_tmpl.external_basic_price

                # Apply product discount if any
                if product_tmpl.discount:
                    price = price * (1 - (product_tmpl.discount / 100))
                    price = round(price, 2)

                if price:
                    line.sudo().write({'price_unit': price})

            # Confirm the new order
            new_order.sudo().action_confirm()

            # Handle reward points (always go to the customer, not the agent)
            reward_points_records = request.env['rewards.points'].sudo().search([('order_id', '=', order_id)])
            order_reward_points = sum(reward_points_records.mapped('points')) if reward_points_records else 0
            
            if order_reward_points:
                request.env['rewards.points'].sudo().create({
                    'points': order_reward_points,
                    'user_id': original_customer_id,  # Always assign to customer
                    'order_id': new_order.id,
                    'status': 'gain' 
                })

                total_points_obj = request.env['rewards.totalpoints'].sudo().search([('user_id', '=', original_customer_id)])
                if total_points_obj:
                    total_points_obj.sudo().write({
                        'total_points': total_points_obj.total_points + order_reward_points
                    })

            # Get shipping address
            user_address = request.env['social_media.custom_address'].sudo().search([
                ('id', '=', new_order.shipping_address_id)
            ])

            shipping_address = f'{user_address.address}, {user_address.continued_address}, {user_address.city}, {user_address.postal_code}, {user_address.village}, {user_address.state_id.name}, {user_address.country_id.name}' if user_address else None

            # Create order details HTML for email
            order_lines_html = ""
            for line in new_order.order_line:
                order_lines_html += f"""
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{line.product_id.name}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: center;">{int(line.product_uom_qty)}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: right;">{line.price_unit:.2f} {new_order.currency_id.symbol}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: right;">{line.price_total:.2f} {new_order.currency_id.symbol}</td>
                    </tr>
                """

            # Email template with agent information if applicable
            agent_info_html = ""
            if is_agent_reorder:
                agent_partner = request.env['res.partner'].sudo().browse(partner_id)
                agent_info_html = f"""
                    <div style="background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin-bottom: 20px; border-left: 4px solid #2196f3;">
                        <h3 style="color: #1976d2; margin-bottom: 10px;">Ordine Agente</h3>
                        <p style="margin: 0;"><strong>Agente:</strong> {agent_partner.name}</p>
                        <p style="margin: 0;"><strong>Email Agente:</strong> {agent_partner.email}</p>
                        <p style="margin: 0;"><strong>Cliente:</strong> {new_order.partner_id.name}</p>
                    </div>
                """

            email_template = f'''
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 20px;">
                        <h2 style="color: #2C3E50; margin-bottom: 20px;">Conferma Riordine</h2>
                        
                        <p>Gentile {new_order.partner_id.name},</p>
                        <p>{'Un agente ha effettuato' if is_agent_reorder else 'Hai effettuato'} un riordine per te. Di seguito i dettagli del tuo ordine:</p>
                    </div>

                    {agent_info_html}

                    <div style="background-color: #ffffff; padding: 20px; border-radius: 5px; margin-bottom: 20px; border: 1px solid #e9ecef;">
                        <h3 style="color: #2C3E50; margin-bottom: 15px;">Dettagli Ordine</h3>
                        <table style="width: 100%; border-collapse: collapse; margin-bottom: 15px;">
                            <tr>
                                <td style="padding: 5px;"><strong>Numero Ordine:</strong></td>
                                <td>{new_order.name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px;"><strong>Ordine Originale:</strong></td>
                                <td>{order.name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px;"><strong>Data Ordine:</strong></td>
                                <td>{new_order.date_order.strftime('%Y-%m-%d %H:%M')}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px;"><strong>Punti Premio:</strong></td>
                                <td>{order_reward_points}</td>
                            </tr>
                        </table>

                        <h3 style="color: #2C3E50; margin: 20px 0 15px;">Prodotti Ordinati</h3>
                        <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                            <thead>
                                <tr style="background-color: #f8f9fa;">
                                    <th style="padding: 8px; text-align: left;">Prodotto</th>
                                    <th style="padding: 8px; text-align: center;">Quantità</th>
                                    <th style="padding: 8px; text-align: right;">Prezzo Unit.</th>
                                    <th style="padding: 8px; text-align: right;">Totale</th>
                                </tr>
                            </thead>
                            <tbody>
                                {order_lines_html}
                            </tbody>
                            <tfoot>
                                <tr>
                                    <td colspan="3" style="padding: 8px; text-align: right;"><strong>Totale Ordine:</strong></td>
                                    <td style="padding: 8px; text-align: right;"><strong>{new_order.amount_total:.2f} {new_order.currency_id.symbol}</strong></td>
                                </tr>
                            </tfoot>
                        </table>

                        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
                            <h3 style="color: #2C3E50; margin-bottom: 10px;">Indirizzo di Spedizione</h3>
                            <p style="margin: 0;">
                                {user_address.address or ''}, {user_address.continued_address or ''}<br>
                                {user_address.city or ''}, {user_address.postal_code or ''}<br>
                                {user_address.village or ''}, {user_address.state_id.name or ''}<br>
                                {user_address.country_id.name or ''}
                            </p>
                        </div>
                    </div>

                    <div style="color: #666; font-size: 12px; margin-top: 20px; padding: 20px; background-color: #f8f9fa; border-radius: 5px;">
                        <p>Per qualsiasi domanda o assistenza, non esitare a contattare il nostro servizio clienti.</p>
                        <p>Grazie per aver scelto i nostri prodotti!</p>
                    </div>
                </div>
            '''

            # Send email
            template = request.env['mail.template'].sudo().create({
                'name': 'Conferma Riordine',
                'email_from': 'admin@primapaint.com',
                'email_to': f"{new_order.partner_id.email}, staff@primapaint.it",
                'subject': f'Riordine #{new_order.name} Confermato',
                'body_html': email_template,
                'model_id': request.env['ir.model']._get('sale.order').id,
                'auto_delete': True
            })
            template.send_mail(new_order.id, force_send=True)
            
            # Handle notifications - Send to both customer and agent if applicable
            if is_agent_reorder:
                # Send notification to CUSTOMER
                customer_filter = request.env['notification.status'].sudo().search([('partner_id', '=', original_customer_id)], limit=1)
                if customer_filter.order:
                    customer_notification = request.env['customer.notification'].sudo().search([('partner_id', '=', original_customer_id)], limit=1)
                    if customer_notification.onesignal_player_id:
                        agent_partner = request.env['res.partner'].sudo().browse(partner_id)
                        notification_service.send_onesignal_notification(
                            customer_notification.onesignal_player_id,
                            f'Il tuo ordine è stato riordinato da {agent_partner.name}',
                            'Ordine Riordinato',
                            {'type': 'agent_reorder', 'role': 'customer', 'agent_id': partner_id}
                        )
                        
                        request.env['notification.storage'].sudo().create({
                            'message': f'Il tuo ordine è stato riordinato da {agent_partner.name}',
                            'patner_id': original_customer_id,
                            'title': 'Ordine Riordinato',
                            'data': {'type': 'agent_reorder', 'role': 'customer', 'agent_id': partner_id},
                            'include_player_ids': customer_notification.onesignal_player_id,
                            'filter': 'order'
                        })
                
                # Send notification to AGENT
                agent_filter = request.env['notification.status'].sudo().search([('partner_id', '=', partner_id)], limit=1)
                if agent_filter.order:
                    agent_notification = request.env['customer.notification'].sudo().search([('partner_id', '=', partner_id)], limit=1)
                    if agent_notification.onesignal_player_id:
                        customer_name = request.env['res.partner'].sudo().browse(original_customer_id).name
                        notification_service.send_onesignal_notification(
                            agent_notification.onesignal_player_id,
                            f'Riordine completato per {customer_name}',
                            'Riordine Agente Completato',
                            {'type': 'agent_reorder_completed', 'role': 'agent', 'customer_id': original_customer_id}
                        )
                        
                        request.env['notification.storage'].sudo().create({
                            'message': f'Riordine completato per {customer_name}',
                            'patner_id': partner_id,
                            'title': 'Riordine Agente Completato',
                            'data': {'type': 'agent_reorder_completed', 'role': 'agent', 'customer_id': original_customer_id},
                            'include_player_ids': agent_notification.onesignal_player_id,
                            'filter': 'order'
                        })
            else:
                # Regular customer reorder notification
                filter_notification = request.env['notification.status'].sudo().search([('partner_id', '=', partner_id)], limit=1)
                if filter_notification.order:
                    customer = request.env['customer.notification'].sudo().search([('partner_id', '=', partner_id)], limit=1)
                    device_token = customer.onesignal_player_id       
                    if device_token:
                        notification_service.send_onesignal_notification(
                            device_token,
                            'Ordine riordinato con successo',
                            'Ordine Riordinato',
                            {'type': 'order_reorder'}
                        )
                        
                        request.env['notification.storage'].sudo().create({
                            'message': 'Ordine riordinato con successo',
                            'patner_id': partner_id,
                            'title': 'Ordine Riordinato',
                            'data': {'type': 'order_reorder'},
                            'include_player_ids': device_token,
                            'filter': 'order'
                        })

            return {
                'status': 'success',
                'message': 'Ordine riordinato con successo.',
                'info': 'Order successfully reordered.',
                'order_id': new_order.id,
                'order_state': new_order.state, 
                'order_amount_total': new_order.amount_total,
                'order_date_order': new_order.date_order.strftime('%Y-%m-%d %H:%M:%S') if new_order.date_order else None,
                'order_reward_points': order_reward_points,
                'partner_address': shipping_address,
                'is_agent_reorder': is_agent_reorder,
                'original_customer_id': original_customer_id,
                'agent_id': partner_id if is_agent_reorder else None
            }

        except Exception as e:
            return {'status': 'error', 'message': 'Si è verificato un errore durante il riordino.',
                    'info': str(e)}, 500