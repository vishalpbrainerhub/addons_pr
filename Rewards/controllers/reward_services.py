from odoo import http
from odoo.http import request, Response
import json
from .user_authentication import user_auth


class RewardAPIs(http.Controller):

    @http.route('/api/rewards', type='http', auth='user', methods=['GET'], csrf=False, cors='*')
    def get_rewards(self):
        """
        Retrieve all reward points and their details for an authenticated user.
        parameters: none
        """
        # Check if user is authenticated
        user = user_auth(self)
        if user['status'] == 'error':
            return Response(
                json.dumps({
                    'status': 'error',
                    'message': 'Autenticazione fallita',  # Italian
                    'info': user['message']  # English
                }),
                content_type='application/json',
                status=401,
                headers={'Access-Control-Allow-Origin': '*'}
            )
        
        try:
            user_id = user['user_id']
            rewards = request.env['rewards.points'].sudo().search([('user_id', '=', user_id)])
            total_points = request.env['rewards.totalpoints'].sudo().search([('user_id', '=', user_id)])
            rewards_data = []
            for reward in rewards:
                rewards_data.append({
                    'id': reward.id,
                    'user_id': reward.user_id.id,
                    'order_id': reward.order_id.id,
                    'points': reward.points,
                    'date': reward.date.strftime('%Y-%m-%d %H:%M:%S'),  # Convert datetime to string
                    'status': reward.status,
                    'catalog_id': reward.catalog_id.id,
                    'catalog_title': reward.catalog_id.title if reward.status == 'redeem' else None,
                    'order_total': reward.order_id.amount_total if reward.status == 'gain' else None
                })

            # Sort rewards data in descending order by date
            rewards_data = sorted(rewards_data, key=lambda x: x['date'], reverse=True)

            response_dict = {
                'status': 'success',
                'message': 'Premi recuperati con successo',  # Italian
                'info': 'Rewards retrieved successfully',  # English
                'data': rewards_data,
                'total_points': total_points.total_points,
            }
            return Response(
                json.dumps(response_dict),
                content_type='application/json',
                status=200,
                headers={'Access-Control-Allow-Origin': '*'}
            )
        except Exception as e:
            return Response(
                json.dumps({
                    'status': 'error',
                    'message': 'Errore del server interno',  # Italian
                    'info': str(e)  # English
                }),
                content_type='application/json',
                status=500,
                headers={'Access-Control-Allow-Origin': '*'}
            )

    @http.route('/api/rewards', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def create_reward(self, **post):
        """
        Create a reward based on a user's purchase.
        parameters: order_id (int) - ID of the order based on which rewards are calculated
        """
        # Check if user is authenticated
        user = user_auth(self)
        if user['status'] == 'error':
            return {
                'status': 'error',
                'message': 'Autenticazione fallita',  # Italian
                'info': user['message']  # English
            }, 401
        
        try:
            user_id = user['user_id']
            order_id = request.jsonrequest.get('order_id')
            if not order_id:
                return {'status': 'error', 'message': 'ID dell\'ordine è richiesto'}, 400  # Italian

            order = request.env['sale.order'].sudo().search([('id', '=', order_id)])
            if not order:
                return {'status': 'error', 'message': 'Ordine non trovato'}, 404  # Italian

            points = sum(line.product_id.rewards_score * line.product_uom_qty for line in order.order_line)
            if points == 0:
                return {'status': 'error', 'message': 'Nessun punto da guadagnare'}, 400  # Italian

            total_points_obj = request.env['rewards.totalpoints'].sudo().search([('user_id', '=', user_id)])
            total_points = points + (total_points_obj.total_points if total_points_obj else 0)
            
            if total_points_obj:
                total_points_obj.write({'total_points': total_points})
            else:
                request.env['rewards.totalpoints'].sudo().create({
                    'total_points': total_points,
                    'user_id': user_id
                })

            create_reward = request.env['rewards.points'].sudo().create({
                'user_id': user_id,
                'order_id': order_id,
                'points': points,
                'status': 'gain'
            })

            return {
                'status': 'success',
                'message': 'Premio creato con successo',  # Italian
                'info': 'Reward created successfully',  # English
                'data': create_reward.id
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': 'Errore durante la creazione del premio',  # Italian
                'info': str(e)  # English
            }, 500
        
        

    @http.route('/api/claim_catalog', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def claim_catalog(self):
        """
        Claim a catalog item using reward points.
        parameters: catalog_id (int) - ID of the catalog item to claim
        """
        # Check if user is authenticated
        user = user_auth(self)
        if user['status'] == 'error':
            return {
                'status': 'error',
                'message': 'Autenticazione fallita',  # Italian
                'info': user['message']  # English
            }, 401
        
        try:
            user_id = user['user_id']
            catalog_id = request.jsonrequest.get('catalog_id')
            if not catalog_id:
                return {'status': 'error', 'message': 'ID del catalogo è richiesto'}, 400  # Italian

            catalog = request.env['rewards.catalog'].sudo().search([('id', '=', catalog_id)])
            if not catalog:
                return {'status': 'error', 'message': 'Catalogo non trovato'}, 404  # Italian

            total_points_obj = request.env['rewards.totalpoints'].sudo().search([('user_id', '=', user_id)])
            if total_points_obj.total_points < catalog.points:
                return {'status': 'error', 'message': 'Punti insufficienti'}, 400  # Italian

            total_points_obj.write({'total_points': total_points_obj.total_points - catalog.points})

            create_reward = request.env['rewards.points'].sudo().create({
                'user_id': user_id,
                'catalog_id': catalog_id,
                'points': catalog.points,
                'status': 'redeem'
            })

            return {
                'status': 'success',
                'message': 'Catalogo richiesto con successo',  # Italian
                'info': 'Catalog claimed successfully',  # English
                'data': create_reward.id
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': 'Errore durante la richiesta del catalogo',  # Italian
                'info': str(e)  # English
            }, 500
