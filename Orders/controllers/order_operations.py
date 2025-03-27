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
        tax_groups = {}
        
        for line in order.order_line:
            line_amount = line.price_subtotal
            for tax in line.tax_id:
                if tax.amount not in tax_groups:
                    tax_groups[tax.amount] = {
                        'percentage': tax.amount,
                        'value': line_amount * (tax.amount / 100)
                    }
                else:
                    tax_groups[tax.amount]['value'] += line_amount * (tax.amount / 100)

        # Sort tax rates and get the first two if they exist
        sorted_taxes = sorted(tax_groups.items())
        vat_data = {
            'vat_1_percentage': 0,
            'vat_2_percentage': 0,
            'vat_1_value': 0,
            'vat_2_value': 0
        }

        if sorted_taxes:
            vat_data['vat_1_percentage'] = sorted_taxes[0][0]
            vat_data['vat_1_value'] = sorted_taxes[0][1]['value']
            
            if len(sorted_taxes) > 1:
                vat_data['vat_2_percentage'] = sorted_taxes[1][0]
                vat_data['vat_2_value'] = sorted_taxes[1][1]['value']

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
            orders = request.env['sale.order'].sudo().search([
                ('id', '=', order_id),
                ('partner_id', '=', partner_id)
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
                    'reward_points': order_reward_points,
                    'all_products': []
                }

                for line in order.sudo().order_line:
                    print(line.product_id.id,"------------prodyct id from order line")
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
            orders = request.env['sale.order'].sudo().search([
                ('partner_id', '=', partner_id),
                # ('state', 'in', ['sent', 'sale', 'done'])
            ])

            response_data = []
            for order in orders:
                user_address = request.env['social_media.custom_address'].sudo().search([
                    ('id', '=', order.shipping_address_id)
                ])
                shipping_address = f'{user_address.address}, {user_address.continued_address}, {user_address.city}, {user_address.postal_code}, {user_address.village}, {user_address.state_id.name}, {user_address.country_id.name}' if user_address else None
                
                # Using improved VAT calculation
                vat_data = self._calculate_vat(order)

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
                    'total_amount': order.amount_total
                }
                response_data.append(order_data)

            return Response(json.dumps({
                'status': 'success',
                'message': 'Ordini recuperati con successo.',
                'info': 'Orders retrieved successfully.',
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

            if not order_id:
                return {'status': 'error', 'message': 'ID dell\'ordine non fornito.', 'info': 'Order ID is required.'}, 400

            order = request.env['sale.order'].sudo().search([
                ('id', '=', order_id),
                ('partner_id', '=', partner_id),
                ('state', '=', 'draft')
            ], limit=1)

            if not order:
                return {'status': 'error', 'message': 'Ordine non trovato o già confermato.', 
                    'info': 'Order not found or already confirmed.'}, 404

            order_line = request.env['sale.order.line'].sudo().search([('order_id', '=', order.id)])
            if not order_line:
                return {'status': 'error', 'message': "L'ordine non contiene prodotti.", 
                    'info': 'The order contains no products.'}, 400

            # Get partner's pricelist
            partner = request.env['res.partner'].sudo().browse(partner_id)
            price_list = partner.property_product_pricelist
            
            if not price_list:
                return {'status': 'error', 'message': 'Listino prezzi non trovato.', 
                    'info': 'Price list not found.'}, 400

            # Check quantities and collect errors
            invalid_quantities = []
            
            for line in order_line:
                # Find matching pricelist items for this product
                matching_items = price_list.item_ids.filtered(
                    lambda x: x.product_tmpl_id.id == line.product_id.product_tmpl_id.id 
                            or x.product_id.id == line.product_id.id
                )
                
                if matching_items:
                    # Get minimum required quantity (lowest min_quantity from rules)
                    min_required = min(matching_items.mapped('min_quantity'))
                    
                    if line.product_uom_qty < min_required:
                        invalid_quantities.append({
                            'product_name': line.product_id.name,
                            'current_quantity': line.product_uom_qty,
                            'min_required': min_required
                        })

            # If there are invalid quantities, return error
            if invalid_quantities:
                return {
                    'status': 'error',
                    'message': f'Quantità minima non raggiunta per alcuni prodotti. Minimo {min_required} richiesto.',
                    'info': f'Minimum quantity not met for some products. Minimum {min_required} required.',
                    'invalid_items': invalid_quantities
                }, 400
            else:

                # Update prices based on pricelist before confirming
                for line in order_line:
                    product_product = request.env['product.product'].sudo().browse(line.product_id.id)
                    product_tmpl = request.env['product.template'].sudo().browse(product_product.product_tmpl_id.id)
                    price = ProductPriceController.calculate_price_product(
                        product_tmpl.id, 
                        line.product_uom_qty,
                        partner_id
                    )
                    if price:
                        line.sudo().write({'price_unit': price})

                # Confirm order
                order.sudo().action_confirm()

                # Handle rewards points
                total_points = sum(line.product_id.rewards_score * line.product_uom_qty for line in order_line)
                if total_points > 0:
                    request.env['rewards.points'].sudo().create({
                        'user_id': partner_id,
                        'order_id': order.id,
                        'points': total_points,
                        'status': 'gain'
                    })

                    total_points_obj = request.env['rewards.totalpoints'].sudo().search([
                        ('user_id', '=', partner_id)
                    ], limit=1)
                    
                    if total_points_obj:
                        total_points_obj.sudo().write({
                            'total_points': total_points_obj.total_points + total_points
                        })
                    else:
                        request.env['rewards.totalpoints'].sudo().create({
                            'user_id': partner_id,
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
                                <p><strong>Data Ordine:</strong> {order.date_order.strftime('%Y-%m-%d %H:%M')}</p>
                                <p><strong>Importo Totale:</strong> {order.currency_id.symbol}{order.amount_total:.2f}</p>
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

                # Handle notifications
                filter_notification = request.env['notification.status'].sudo().search([('partner_id', '=', partner_id)], limit=1)
                if filter_notification.order:
                    customer = request.env['customer.notification'].sudo().search([('partner_id', '=', partner_id)], limit=1)
                    device_token = customer.onesignal_player_id       
                    if device_token:
                        notification_service.send_onesignal_notification(
                            device_token,
                            'Ordine inserito con successo',
                            'Ordine inserito',
                            {'type': 'order_placed'}
                        )
                        
                        request.env['notification.storage'].sudo().create({
                            'message': 'Ordine inserito con successo',
                            'patner_id': partner_id,
                            'title': 'Ordine inserito',
                            'data': {'type': 'order_placed'},
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
                    'reward_points_earned': total_points if total_points > 0 else 0
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

            order = request.env['sale.order'].sudo().search([
                ('id', '=', order_id),
                ('partner_id', '=', partner_id), 
                ('state', 'in', ['sent', 'sale', 'done'])
            ], limit=1)

            if not order:
                return {'status': 'error', 'message': 'Ordine non trovato o non può essere riordinato.',
                    'info': 'Order not found or cannot be reordered.'}, 404

            new_order = order.sudo().copy()
            
            # Get partner's pricelist
            partner = request.env['res.partner'].sudo().browse(partner_id)
            price_list = partner.property_product_pricelist
            
            if not price_list:
                return {'status': 'error', 'message': 'Listino prezzi non trovato.', 
                    'info': 'Price list not found.'}, 400

            # Check quantities and collect errors
            invalid_quantities = []
            
            for line in new_order.order_line:
                # Find matching pricelist items for this product
                matching_items = price_list.item_ids.filtered(
                    lambda x: x.product_tmpl_id.id == line.product_id.product_tmpl_id.id 
                            or x.product_id.id == line.product_id.id
                )
                
                if matching_items:
                    # Get minimum required quantity (lowest min_quantity from rules)
                    min_required = min(matching_items.mapped('min_quantity'))
                    
                    if line.product_uom_qty < min_required:
                        invalid_quantities.append({
                            'product_name': line.product_id.name,
                            'current_quantity': line.product_uom_qty,
                            'min_required': min_required
                        })

            # If there are invalid quantities, return error
            if invalid_quantities:
                return {
                    'status': 'error',
                    'message': 'Quantità minima non raggiunta per alcuni prodotti.',
                    'info': 'Minimum quantity not met for some products.',
                    'invalid_items': invalid_quantities
                }, 400

            # Update prices based on current pricelist
            for line in new_order.order_line:
                product_product = request.env['product.product'].sudo().browse(line.product_id.id)
                product_tmpl = request.env['product.template'].sudo().browse(product_product.product_tmpl_id.id)
                price = ProductPriceController.calculate_price_product(
                    product_tmpl.id,
                    line.product_uom_qty,
                    partner_id
                )
                if price:
                    line.sudo().write({'price_unit': price})

            new_order.sudo().action_confirm()

            reward_points_records = request.env['rewards.points'].sudo().search([('order_id', '=', order_id)])
            order_reward_points = sum(reward_points_records.mapped('points')) if reward_points_records else 0
            if order_reward_points:
                request.env['rewards.points'].sudo().create({
                    'points': order_reward_points,
                    'user_id': partner_id,
                    'order_id': new_order.id,
                    'status': 'gain' 
                })

                total_points_obj = request.env['rewards.totalpoints'].sudo().search([('user_id', '=', partner_id)])
                if total_points_obj:
                    total_points_obj.sudo().write({
                        'total_points': total_points_obj.total_points + order_reward_points
                    })

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

            email_template = f'''
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 20px;">
                        <h2 style="color: #2C3E50; margin-bottom: 20px;">Conferma Riordine</h2>
                        
                        <p>Gentile {new_order.partner_id.name},</p>
                        <p>Grazie per il tuo riordine. Di seguito i dettagli del tuo ordine:</p>
                    </div>

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
            
            # Handle notifications
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
                'partner_address': shipping_address
            }

        except Exception as e:
            return {'status': 'error', 'message': 'Si è verificato un errore durante il riordino.',
                    'info': str(e)}, 500

    