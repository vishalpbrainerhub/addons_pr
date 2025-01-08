from odoo import http, _ , fields
from odoo.http import request, Response
import json
from datetime import datetime
from .user_authentication import SocialMediaAuth

class Ecommerce_orders(http.Controller):
    
    def _calculate_vat(self, order):
        vat_1_percentage = 0
        vat_2_percentage = 0
        vat_1_value = 0 
        vat_2_value = 0

        if order.order_line:
            line_taxes = order.order_line[0].tax_id
            if line_taxes:
                sorted_taxes = sorted(line_taxes, key=lambda x: x.amount)
                if len(sorted_taxes) >= 1:
                    vat_1_percentage = sorted_taxes[0].amount
                    vat_1_value = order.amount_untaxed * (vat_1_percentage/100)
                if len(sorted_taxes) >= 2:  
                    vat_2_percentage = sorted_taxes[1].amount
                    vat_2_value = order.amount_untaxed * (vat_2_percentage/100)

        return {
            'vat_1_percentage': vat_1_percentage,
            'vat_2_percentage': vat_2_percentage, 
            'vat_1_value': vat_1_value,
            'vat_2_value': vat_2_value
        }


    def _get_price_from_pricelist(self, product, partner_id, quantity=1.0):
        partner = request.env['res.partner'].sudo().browse(partner_id)
        pricelist = partner.property_product_pricelist
        
        pricelist_items = request.env['product.pricelist.item'].sudo().search([
            ('pricelist_id', '=', pricelist.id),
            ('product_id', '=', product.id),
            '|',
            ('date_start', '<=', fields.Date.today()),
            ('date_start', '=', False),
            '|', 
            ('date_end', '>=', fields.Date.today()),
            ('date_end', '=', False),
            ('min_quantity', '<=', quantity)
        ], order='min_quantity desc')

        if not pricelist_items:
            return product.list_price

        item = pricelist_items[0]
        
        if item.compute_price == 'fixed':
            price = item.fixed_price
        elif item.compute_price == 'percentage':
            price = product.list_price * (1 - item.percent_price / 100)
        else:
            price = product.list_price

        if pricelist.currency_id != product.currency_id:
            price = product.currency_id._convert(
                price,
                pricelist.currency_id,
                product.company_id,
                fields.Date.today()
            )
            
        return price

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
                    price = self._get_price_from_pricelist(line.product_id, partner_id, line.product_uom_qty)
                    image_url = '/web/image/product.product/' + str(line.product_id.id) + '/image_1920' if line.product_id.image_1920 else None
                    
                    product_data = {
                        'id': line.product_id.id,
                        'name': line.product_id.name,
                        'list_price': price * line.product_uom_qty,
                        'active': line.product_id.active,
                        'barcode': line.product_id.barcode,
                        'color': line.product_id.color,
                        'image': image_url,
                        'quantity': line.product_uom_qty,
                        'base_price': line.product_id.list_price,
                        'discount': line.discount or 0,
                        'order_id': line.order_id.id,
                        'code': line.product_id.code_,
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
                ('state', 'in', ['sent', 'sale', 'done'])
            ])

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

            # Update prices based on pricelist before confirming
            for line in order_line:
                price = self._get_price_from_pricelist(
                    line.product_id, 
                    partner_id,
                    line.product_uom_qty
                )
                line.sudo().write({'price_unit': price})

            order.sudo().action_confirm()

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

            user_address = request.env['social_media.custom_address'].sudo().search([
                ('id', '=', order.shipping_address_id)
            ])

            shipping_address = f'{user_address.address}, {user_address.continued_address}, {user_address.city}, {user_address.postal_code}, {user_address.village}, {user_address.state_id.name}, {user_address.country_id.name}' if user_address else None

            template = request.env['mail.template'].sudo().create({
            'name': 'Order Confirmation',
            'email_from': 'admin@primapaint.com',
            'email_to': order.partner_id.email,
            'subject': f'Order #{order.name} Confirmed',
            'body_html': f'''
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #2C3E50;">Order Confirmation</h2>
                    
                    <p>Dear {order.partner_id.name},</p>
                    
                    <p>Thank you for your order. Your order details:</p>
                    
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">
                        <p><strong>Order Number:</strong> {order.name}</p>
                        <p><strong>Order Date:</strong> {order.date_order.strftime('%Y-%m-%d %H:%M')}</p>
                        <p><strong>Total Amount:</strong> {order.currency_id.symbol}{order.amount_total:.2f}</p>
                    </div>

                    <h3 style="color: #2C3E50; margin-top: 20px;">Shipping Address:</h3>
                    <p style="background: #f8f9fa; padding: 15px; border-radius: 5px;">
                        {order.partner_shipping_id.street or ''}<br>
                        {order.partner_shipping_id.city or ''}, {order.partner_shipping_id.state_id.name or ''} {order.partner_shipping_id.zip or ''}<br>
                        {order.partner_shipping_id.country_id.name or ''}
                    </p>

                    <p style="color: #666; margin-top: 30px; font-size: 12px;">
                        If you have any questions, please contact our customer service.
                    </p>
                </div>
            ''',
            'model_id': request.env['ir.model']._get('sale.order').id,
            'auto_delete': True
            })
            template.send_mail(order.id, force_send=True)
                
            return {
                'status': 'success',
                'message': 'Ordine confermato con successo e carrello svuotato.',
                'info': 'Order confirmed successfully and cart emptied.',
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
            
            # Update prices based on current pricelist
            for line in new_order.order_line:
                price = self._get_price_from_pricelist(
                    line.product_id,
                    partner_id,
                    line.product_uom_qty
                )
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

    @http.route('/api/cancel_order', auth='public', type='json', methods=['POST'], csrf=False)
    def cancel_order(self, **post):
        try:
            user = SocialMediaAuth.user_auth(self)
            if user['status'] == 'error':
                return {'status': 'error', 'message': user['message'], 'info': 'Authentication failed.'}

            partner_id = user['user_id']
            order_id = request.jsonrequest.get('order_id')

            if not order_id:
                return {'status': 'error', 'message': 'ID dell\'ordine non fornito.',
                    'info': 'Order ID is required.'}, 400

            order = request.env['sale.order'].sudo().search([
                ('id', '=', order_id),
                ('partner_id', '=', partner_id),
                ('state', '!=', 'draft')
            ], limit=1)

            if not order:
                return {'status': 'error', 'message': 'Ordine non trovato o già confermato.',
                    'info': 'Order not found or already confirmed.'}, 404

            order_line = request.env['sale.order.line'].sudo().search([('order_id', '=', order.id)])
            if not order_line:
                return {'status': 'error', 'message': 'L\'ordine non contiene prodotti.',
                    'info': 'Order has no products.'}, 400

            reward_points = request.env['rewards.points'].sudo().search([
                ('order_id', '=', order.id),
                ('user_id', '=', partner_id),
                ('status', '=', 'gain')
            ])

            if reward_points:
                total_points_obj = request.env['rewards.totalpoints'].sudo().search([
                    ('user_id', '=', partner_id)
                ], limit=1)

                if total_points_obj and total_points_obj.total_points >= reward_points.points:
                    total_points_obj.sudo().write({
                        'total_points': total_points_obj.total_points - reward_points.points
                    })
                    reward_points.sudo().unlink()

            order.sudo().action_cancel()

            return {
                'status': 'success',
                'message': 'Ordine annullato con successo.',
                'info': 'Order cancelled successfully.',
                'order_id': order.id,
                'order_state': order.state,
                'order_amount_total': order.amount_total,
                'order_date_order': order.date_order.strftime('%Y-%m-%d %H:%M:%S') if order.date_order else None,
                'points_deducted': reward_points.points if reward_points else 0
            }

        except Exception as e:
            return {'status': 'error', 'message': 'Si è verificato un errore durante l\'annullamento dell\'ordine.',
                    'info': str(e)}, 500

    