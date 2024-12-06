from odoo import http
from odoo.http import request, Response
import json
from .user_authentication import user_auth



class CatalogApis(http.Controller):

    @http.route('/api/catalog', type='http', auth='user', methods=['GET'], csrf=False, cors='*')
    def get_catalog(self):
        """
        Retrieve catalog data accessible to authenticated users only. This API handles CORS.
        parameters: none
        """
        # Check if user is authenticated
        user = user_auth(self)
        if user['status'] == 'error':
            return Response(
                json.dumps({
                    'status': 'error',
                    'message': 'Autenticazione fallita',  
                    'info': user['message']  
                }),
                content_type='application/json',
                status=401,
                headers={'Access-Control-Allow-Origin': '*'}
            )
        
        try:
            # Retrieve catalog data from the database
            catalogs = request.env['rewards.catalog'].sudo().search([])
            catalog_data = []
            for catalog in catalogs:
                image_url = '/web/image/rewards.catalog/' + str(catalog.id) + '/image' if catalog.image else None
                catalog_data.append({
                    'id': catalog.id,
                    'title': catalog.title,
                    'description': catalog.description,
                    'points': catalog.points,
                    'image': image_url
                })

            # Successful response with catalog data
            response_dict = {
                'status': 'success',
                'message': 'Catalogo recuperato con successo',  
                'info': 'Catalog retrieved successfully',  
                'data': catalog_data
            }
            return Response(
                json.dumps(response_dict),
                content_type='application/json',
                status=200,
                headers={'Access-Control-Allow-Origin': '*'}
            )
        except Exception as e:
            # Handle any unexpected errors
            return Response(
                json.dumps({
                    'status': 'error',
                    'message': 'Errore del server interno',  
                    'info': str(e)  
                }),
                content_type='application/json',
                status=500,
                headers={'Access-Control-Allow-Origin': '*'}
            )