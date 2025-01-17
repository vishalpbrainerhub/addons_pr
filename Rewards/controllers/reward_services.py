from odoo import http
from odoo.http import request, Response
import json
from .user_authentication import SocialMediaAuth
from .notification_service import CustomerController

notification_service = CustomerController()

class RewardAPIs(http.Controller):

    @http.route('/api/rewards', type='http', auth='public', methods=['GET'], csrf=False, cors='*')
    def get_rewards(self):
        try:
            user = SocialMediaAuth.user_auth(self)
            if user['status'] == 'error':
                return Response(json.dumps({
                    'status': 'error',
                    'message': 'Autenticazione fallita',
                    'info': user['message']
                }), content_type='application/json', status=401, headers={'Access-Control-Allow-Origin': '*'})

            partner_id = user['user_id']

            rewards = request.env['rewards.points'].sudo().search([('user_id', '=', partner_id)])
            total_points = request.env['rewards.totalpoints'].sudo().search([('user_id', '=', partner_id)])

            rewards_data = []
            for reward in rewards:
                rewards_data.append({
                    'id': reward.id,
                    'user_id': reward.user_id.id,
                    'order_id': reward.order_id.id,
                    'points': reward.points,
                    'date': reward.date.strftime('%Y-%m-%d %H:%M:%S'),
                    'status': reward.status,
                    'catalog_id': reward.catalog_id.id,
                    'catalog_title': reward.catalog_id.title if reward.status == 'redeem' else None,
                    'order_total': reward.order_id.amount_total if reward.status == 'gain' else None
                })

            rewards_data = sorted(rewards_data, key=lambda x: x['date'], reverse=True)

            return Response(json.dumps({
                'status': 'success',
                'message': 'Premi recuperati con successo',
                'info': 'Rewards retrieved successfully', 
                'data': rewards_data,
                'total_points': total_points.total_points,
            }), content_type='application/json', status=200, headers={'Access-Control-Allow-Origin': '*'})

        except Exception as e:
            return Response(json.dumps({
                'status': 'error', 
                'message': 'Errore del server interno',
                'info': str(e)
            }), content_type='application/json', status=500, headers={'Access-Control-Allow-Origin': '*'})

    @http.route('/api/rewards', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def create_reward(self, **post):
        user = SocialMediaAuth.user_auth(self)
        if user['status'] == 'error':
            return {'status': 'error', 'message': 'Autenticazione fallita', 
                    'info': user['message']}, 401
        
        try:
            partner_id = user['user_id']
            order_id = request.jsonrequest.get('order_id')
            if not order_id:
                return {'status': 'error', 'message': 'ID dell\'ordine è richiesto'}, 400

            order = request.env['sale.order'].sudo().search([('id', '=', order_id)])
            if not order:
                return {'status': 'error', 'message': 'Ordine non trovato'}, 404

            points = sum(line.product_id.rewards_score * line.product_uom_qty for line in order.order_line)
            if points == 0:
                return {'status': 'error', 'message': 'Nessun punto da guadagnare'}, 400

            total_points_obj = request.env['rewards.totalpoints'].sudo().search([('user_id', '=', partner_id)])
            total_points = points + (total_points_obj.total_points if total_points_obj else 0)
            
            if total_points_obj:
                total_points_obj.sudo().write({'total_points': total_points})
            else:
                request.env['rewards.totalpoints'].sudo().create({
                    'total_points': total_points,
                    'user_id': partner_id
                })

            create_reward = request.env['rewards.points'].sudo().create({
                'user_id': partner_id,
                'order_id': order_id,
                'points': points,
                'status': 'gain'
            })
            
            filter_notification = request.env['notification.status'].sudo().search([('partner_id', '=', partner_id)], limit=1)
            if filter_notification.order:
                customer = request.env['customer.notification'].sudo().search([('partner_id', '=', partner_id)], limit=1)
                device_token = customer.onesignal_player_id       
                if device_token:
                    
                    notification_service.send_onesignal_notification(
                        device_token,
                        f'{points} Punti guadagnati con successo',
                        'Punti Guadagnati',
                        {'type': 'points_earned'}
                    )
                    
                    request.env['notification.storage'].sudo().create({
                        'message': f'{points} Punti guadagnati con successo',
                        'patner_id': partner_id,
                        'title': 'Punti Guadagnati',
                        'data': {'type': 'points_earned'},
                        'include_player_ids': device_token,
                        'filter': 'promo'
                    })

            return {
                'status': 'success',
                'message': 'Premio creato con successo',
                'info': 'Reward created successfully',
                'data': create_reward.id
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': 'Errore durante la creazione del premio',
                'info': str(e)
            }, 500

    @http.route('/api/claim_catalog', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def claim_catalog(self):
        user = SocialMediaAuth.user_auth(self)
        if user['status'] == 'error':
            return {'status': 'error', 'message': 'Autenticazione fallita',
                    'info': user['message']}, 401
        
        try:
            partner_id = user['user_id']
            catalog_id = request.jsonrequest.get('catalog_id')
            if not catalog_id:
                return {'status': 'error', 'message': 'ID del catalogo è richiesto'}, 400

            catalog = request.env['rewards.catalog'].sudo().search([('id', '=', catalog_id)])
            if not catalog:
                return {'status': 'error', 'message': 'Catalogo non trovato'}, 404

            total_points_obj = request.env['rewards.totalpoints'].sudo().search([('user_id', '=', partner_id)])
            if total_points_obj.total_points < catalog.points:
                return {'status': 'error', 'message': 'Punti insufficienti'}, 400

            total_points_obj.sudo().write({'total_points': total_points_obj.total_points - catalog.points})

            create_reward = request.env['rewards.points'].sudo().create({
                'user_id': partner_id,
                'catalog_id': catalog_id,
                'points': catalog.points,
                'status': 'redeem'
            })
            
            filter_notification = request.env['notification.status'].sudo().search([('partner_id', '=', partner_id)], limit=1)
            if filter_notification.order:
                customer = request.env['customer.notification'].sudo().search([('partner_id', '=', partner_id)], limit=1)
                device_token = customer.onesignal_player_id       
                if device_token:
                    
                    notification_service.send_onesignal_notification(
                        device_token,
                        'Catalogo richiesto con successo',
                        'Catalogo Richiesto',
                        {'type': 'catalog_claimed'}
                    )
                    
                    request.env['notification.storage'].sudo().create({
                        'message': 'Catalogo richiesto con successo',
                        'patner_id': partner_id,
                        'title': 'Catalogo Richiesto',
                        'data': {'type': 'catalog_claimed'},
                        'include_player_ids': device_token,
                        'filter': 'promo'
                    })
                    
            return {
                'status': 'success',
                'message': 'Catalogo richiesto con successo',
                'info': 'Catalog claimed successfully', 
                'data': create_reward.id
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': 'Errore durante la richiesta del catalogo',
                'info': str(e)
            }, 500