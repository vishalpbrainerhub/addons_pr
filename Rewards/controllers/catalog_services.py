from odoo import http
from odoo.http import request, Response
import json
from .user_authentication import SocialMediaAuth
import base64
import os
import random

import logging
_logger = logging.getLogger(__name__)


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
                }), content_type='application/json', status=401)

            catalogs = request.env['rewards.catalog'].sudo().search([])
            catalog_data = []
            
            for catalog in catalogs:
                image_path = None
                if catalog.image:
                    filename = f'catalog_{random.randint(1,5000)}_{catalog.id}.png'
                    save_dir = os.path.join('/mnt/data/images', 'catalog', str(catalog.id))
                    os.makedirs(save_dir, exist_ok=True)
                    
                    # Save image
                    image_path = f'/images/catalog/{catalog.id}/{filename}'
                    with open(os.path.join(save_dir, filename), 'wb') as f:
                        f.write(base64.b64decode(catalog.image))

                catalog_data.append({
                    'id': catalog.id,
                    'title': catalog.title,
                    'description': catalog.description, 
                    'points': catalog.points,
                    'image': image_path
                })

            return Response(json.dumps({
                'status': 'success',
                'message': 'Catalogo recuperato con successo',
                'info': 'Catalog retrieved successfully',
                'data': catalog_data
            }), content_type='application/json', status=200)

        except Exception as e:
            return Response(json.dumps({
                'status': 'error',
                'message': 'Errore del server interno',
                'info': str(e)
            }), content_type='application/json', status=500)

    @http.route('/images/catalog/<int:catalog_id>/<path:image>', type='http', auth='public', csrf=False, cors='*')
    def get_catalog_image(self, catalog_id, image):
        try:
            base_path = '/mnt/data/images'
            image_path = os.path.join(base_path, 'catalog', str(catalog_id), image.lstrip('/'))
            safe_path = os.path.join(base_path, 'catalog', str(catalog_id))
            
            if not os.path.abspath(image_path).startswith(os.path.abspath(safe_path)):
                return Response(json.dumps({
                    'error': {'message': 'Invalid path'}
                }), content_type='application/json', status=403)

            if os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    return Response(f.read(), content_type='image/png')

            return Response(json.dumps({
                'error': {'message': 'Image not found'}
            }), content_type='application/json', status=404)

        except Exception as e:
            _logger.error('Error serving catalog image: %s', str(e))
            return Response(json.dumps({
                'error': {'message': 'Server error'}
            }), content_type='application/json', status=500)