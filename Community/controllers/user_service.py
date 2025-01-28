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
import random
import string
from odoo.exceptions import UserError
from .notification_service import CustomerController

load_dotenv()
_logger = logging.getLogger(__name__)


class Users(http.Controller):

    
    
    @http.route('/user/login', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False)
    def login(self):
        try:
            email = request.jsonrequest.get('email')
            password = request.jsonrequest.get('password')
            device_token = request.jsonrequest.get('device_token')
            
            print(email, password, device_token, '-----------------Login request-----------------')

            if not email or not password:
                return {"status": "error", "message": "Email e password sono richieste"}

            customer = request.env['res.partner'].sudo().search([
                ('email', '=', email)
                # ('customer_rank', '>', 0),
            ], limit=1)
            if not customer:
                return {"status": "error", "info": "Credenziali non valide"}

            password_record = request.env['customer.password'].sudo().search([
                ('partner_id', '=', customer.id)
            ], limit=1)

            if not password_record:
                # Generate random password
                random_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
                
                # Create password record
                password_record = request.env['customer.password'].sudo().create({
                    'partner_id': customer.id
                })
                password_record.set_password(random_password)

                # Send email with credentials
                template = request.env['mail.template'].sudo().create({
                    'name': 'Credenziali Cliente',
                    'email_from': 'admin@primapaint.com', 
                    'email_to': customer.email,
                    'subject': 'Le tue Credenziali di Accesso',
                    'body_html': f'''
                        <p>Salve {customer.name},</p>
                        <p>Le tue credenziali di accesso:</p>
                        <p>Email: {customer.email}<br/>
                        Password: {random_password}</p>
                    ''',
                    'model_id': request.env['ir.model']._get('res.partner').id
                })
                template.send_mail(customer.id, force_send=True)
                print('Email sent')
                                
                return {"status": "error", "message": "Credenziali inviate via email"}
            

            if not password_record.verify_password(password):
                print('Password not verified')  
                return {"status": "error", "info": "Credenziali non valide", "message": "Password verification failed"}

            payload = {
                'user_id': customer.id,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
            }
            
            secret_key = os.environ["JWT_SECRET_KEY"]
            print(secret_key, '-----------------Secret Key-----------------')
            token = jwt.encode(payload, secret_key, algorithm='HS256')
            
            
            if device_token:
                notification_record = request.env['customer.notification'].sudo().search([
                    ('partner_id', '=', customer.id)
                ], limit=1)
                # update the token
                if notification_record:
                    notification_record.write({
                        'onesignal_player_id': device_token
                    })
                if not notification_record:
                    request.env['customer.notification'].sudo().create({
                        'partner_id': customer.id,
                        'onesignal_player_id': device_token
                    })
                
                
            notification = CustomerController()
            if device_token:
                
                response = notification.send_onesignal_notification(
                    device_token, 
                    'Accesso eseguito con successo', 
                    'Login', 
                    {'type': 'login'}
                )
                _logger.info('Login notification result: %s', notification)
            
            return {
                "status": "success",
                "message": "Accesso eseguito con successo",
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
            return {"status": "error", "message": "Errore del server", "info": str(e)}

    
     # ---------------------- Done --------------------------------
    
    @http.route('/user/register', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False)
    def register(self):
        try:
            name = request.jsonrequest.get('name')
            email = request.jsonrequest.get('email')
            password = request.jsonrequest.get('password')
            phone = request.jsonrequest.get('phone')
            company_id = request.jsonrequest.get('company_id')

            if not name or not email or not password or not phone:
                return {"status": "error", "message": "Tutti i campi sono richiesti"}

            customer = request.env['res.partner'].sudo().search([
                ('email', '=', email)
            ], limit=1)
            if customer:
                return {"status": "error", "message": "Utente già registrato"}

            customer = request.env['res.partner'].sudo().create({
                'name': name,
                'email': email,
                'phone': phone,
                'company_id': company_id
            })

            password_record = request.env['customer.password'].sudo().create({
                'partner_id': customer.id
            })
            password_record.set_password(password)

            return {"status": "success", "message": "Registrazione effettuata con successo"}

        except Exception as e:
            _logger.error('Registration error: %s', str(e))
            return {"status": "error", "message": "Errore del server", "info": str(e)}
    
    
    @http.route('/user/forgot-password', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False)
    def forgot_password(self):
        try:
            email = request.jsonrequest.get('email')
            if not email:
                return {"status": "error", "message": "Email è richiesta"}

            customer = request.env['res.partner'].sudo().search([
                ('email', '=', email)
            ], limit=1)

            if not customer:
                return {"status": "error", "message": "Utente non trovato"}

            # Generate new random password regardless of existing record
            random_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
            
            # Get or create password record
            password_record = request.env['customer.password'].sudo().search([
                ('partner_id', '=', customer.id)
            ], limit=1)
            
            if password_record:
                password_record.set_password(random_password)
            else:
                password_record = request.env['customer.password'].sudo().create({
                    'partner_id': customer.id
                })
                password_record.set_password(random_password)

            # Send email template
            template = request.env['mail.template'].sudo().create({
                'name': 'Credenziali Cliente',
                'email_from': 'admin@gmail.com',
                'email_to': customer.email,
                'subject': 'Le tue Credenziali di Accesso',
                'body_html': f'''
                    <p>Salve {customer.name},</p>
                    <p>Le tue credenziali di accesso:</p>
                    <p>Email: {customer.email}<br/>
                    Password: {random_password}</p>
                ''',
                'model_id': request.env['ir.model']._get('res.partner').id
            })
            template.send_mail(customer.id, force_send=True)
            
            return {"status": "success", "message": "Credenziali inviate via email"}

        except Exception as e:
            _logger.error('Forgot password error: %s', str(e))
            return {"status": "error", "message": "Errore del server", "info": str(e)}

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