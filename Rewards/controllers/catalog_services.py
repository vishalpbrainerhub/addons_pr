from odoo import http
from odoo.http import request, Response
import json
from .user_authentication import SocialMediaAuth


class CatalogApis(http.Controller):

    @http.route('/api/catalog', type='http', auth='public', methods=['GET'], csrf=False, cors='*')
    def get_catalog(self):
        try:
            user = SocialMediaAuth.user_auth(self)
            if user['status'] == 'error':
                return Response(json.dumps({
                    'status': 'error',
                    'message': 'Autenticazione fallita',
                    'info': user['message']
                }), content_type='application/json', status=401, headers={'Access-Control-Allow-Origin': '*'})

            partner_id = user['user_id']

            catalogs = request.env['rewards.catalog'].sudo().search([])
            catalog_data = []
            for catalog in catalogs:
                # /web/image?model=rewards.catalog&id=1&field=image
                
                # image_url = '/web/image/rewards.catalog/' + str(catalog.id) + '/image' if catalog.image else None
                image_url = '/web/image?model=rewards.catalog&id=' + str(catalog.id) + '&field=image' if catalog.image else None   
                catalog_data.append({
                    'id': catalog.id,
                    'title': catalog.title, 
                    'description': catalog.description,
                    'points': catalog.points,
                    'image': image_url
                })

            return Response(json.dumps({
                'status': 'success',
                'message': 'Catalogo recuperato con successo',
                'info': 'Catalog retrieved successfully',
                'data': catalog_data
            }), content_type='application/json', status=200, headers={'Access-Control-Allow-Origin': '*'})

        except Exception as e:
            return Response(json.dumps({
                'status': 'error',
                'message': 'Errore del server interno',
                'info': str(e)
            }), content_type='application/json', status=500, headers={'Access-Control-Allow-Origin': '*'})