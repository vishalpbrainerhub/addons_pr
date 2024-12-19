from odoo import _,http, tools
from odoo.http import request, Response
import jwt
import json
from dotenv import load_dotenv
import os
import logging
import csv
import os
import datetime

load_dotenv()
_logger = logging.getLogger(__name__)


class Users(http.Controller):

    # ---------------------- Done --------------------------------
    @http.route('/user/login', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False)
    def login(self):
        try:
            email = request.jsonrequest.get('email')
            password = request.jsonrequest.get('password')

            if not email or not password:
                return {
                    "status": "error",
                    "message": "Email e password sono richieste",
                    "info": "Email and password are required"
                }

            customer = request.env['res.partner'].sudo().search([
                ('email', '=', email),
                ('customer_rank', '>', 0),
            ], limit=1)

            if not customer:
                return {
                    "status": "error", 
                    "message": "Credenziali non valide",
                    "info": "Invalid credentials"
                }

            payload = {
                'user_id': customer.id,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=2)
            }

            token = jwt.encode(payload, 'testing', algorithm='HS256')

            return {
                "status": "success",
                "message": "Accesso eseguito con successo",
                "info": "Login successful",
                "user": {
                    'name': customer.name,
                    'email': customer.email,
                    'phone': customer.phone,
                    'company_id': customer.company_id.id if customer.company_id else False,
                    'lang': customer.lang or 'en_US'
                },
                "token": token if isinstance(token, str) else token.decode('utf-8')
            }

        except Exception as e:
            _logger.error('Login error: %s', str(e))
            return {
                "status": "error",
                "message": "Errore del server",
                "info": str(e)
            }


    
     # ---------------------- Done --------------------------------
    

    @http.route('/api/banners', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    def banners(self):
        banners = []
        try:
            base_path = '/mnt/data/images'
            banner_dir = os.path.join(base_path, 'banners')
            for root, dirs, files in os.walk(banner_dir):
                for file in files:
                    if file.endswith((".jpg", ".png")):
                        path = os.path.join(root, file)
                        relative_path = os.path.relpath(path, base_path)
                        banners.append(f'/images/{relative_path}')
        
            data = {
                "status": "success",
                "info": "Banner images retrieved successfully",
                "banners": banners
            }
        except Exception as e:
            _logger.error('Error retrieving banners: %s', str(e))
            data = {
                "status": "error", 
                "message": "Errore nel recupero dei banner",
                "info": str(e)
            }
        return request.make_response(json.dumps(data), [('Content-Type', 'application/json')])

    @http.route('/images/banners/<path:image>', type='http', auth='public', csrf=False)
    def get_image(self, image):
        base_path = '/mnt/data/images'
        image_path = os.path.join(base_path, 'banners', image)
        safe_path = os.path.join(base_path, 'banners')

        if not os.path.abspath(image_path).startswith(os.path.abspath(safe_path)):
            return Response(json.dumps({
                'error': {'message': 'Invalid image path'},
                'status': 'error',
                'status_code': '403'
            }), content_type='application/json', status=403)

        if os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                image_data = f.read()
            return Response(image_data, content_type='image/png')
        return Response(json.dumps({
            'error': {'message': 'Image not found'},
            'status': 'error',
            'status_code': '404'
        }), content_type='application/json', status=404)