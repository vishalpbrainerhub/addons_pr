from odoo import _,http, tools
from odoo.http import request, Response
import jwt
import datetime
import json
from dotenv import load_dotenv
import os
from .shared_utilities import  generate_password, forgot_password
import logging

load_dotenv()
_logger = logging.getLogger(__name__)


class Users(http.Controller):

    @http.route('/user/login', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False)
    def login(self):
        """
        Description: Authenticates a user and generates a session token.
        Parameters: email, password
        """
        try:
            email = request.jsonrequest.get('email', False)
            password = request.jsonrequest.get('password', False)

            if not email or not password:
                return {
                    "status": "error",
                    "message": "Email e password sono richieste",
                    "info": "Email and password are required"
                }

            user = request.env['res.users'].sudo().search([('email', '=', email)], limit=1)

            if not user:
                return {
                    "status": "error",
                    "message": "Utente non trovato",
                    "info": "User not found"
                }

            login = user.login
            db = request.env.cr.dbname

            # Authenticate the user to create a new session
            uid = request.session.authenticate(db, login, password)
            if uid:
                # A new session ID has been generated
                new_session_id = request.session.sid
                payload = {
                    'user_id': user.id,
                    'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=2)
                }

                # Fix for JWT secret key
                secret_key = os.getenv("JWT_SECRET_KEY")
                if not secret_key:
                    secret_key = "testing_enviroment"  # Replace with your actual default secret key

                token = jwt.encode(payload, str(secret_key), algorithm='HS256')

                user_data = user.read(['name', 'login', 'email', 'phone', 'company_id', 'lang'])[0]

                return {
                    "status": "success",
                    "message": "Accesso utente eseguito con successo, procedi con il completamento",
                    "info": "User login successful, proceed to completion",
                    "user": user_data,
                    "token": token.decode('utf-8') if isinstance(token, bytes) else token,
                    "session_id": new_session_id
                }
            else:
                return {
                    "status": "error",
                    "message": "Credenziali di accesso non valide",
                    "info": "Invalid login credentials"
                }

        except Exception as e:
            _logger.error('Login error: %s', str(e))
            return {
                "status": "error",
                "message": "Errore del server",
                "info": "Server error occurred"
            }   



    # create user
    @http.route('/user/create', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False)
    def create(self):
        """
        Description: Creates a new user with the provided details.
        Parameters: name, login, email, phone, company_id, password
        """
        name = request.jsonrequest.get('name', False)
        login = request.jsonrequest.get('login', False)
        email = request.jsonrequest.get('email', False)
        phone = request.jsonrequest.get('phone', False)
        company_id = request.jsonrequest.get('company_id', False)
        password = request.jsonrequest.get('password', False)
        
        try:
            if not email or not password or not login:
                return {
                    "status": "error",
                    "message": "Alcuni campi sono richiesti",
                    "info": "Some fields are required"
                }
        
            existing_user = request.env['res.users'].sudo().search([('email', '=', email)], limit=1)
            if existing_user:
                return {
                    "status": "error",
                    "message": "Utente già esistente",
                    "info": "User already exists"
                }

            # Create the user with basic information
            user = request.env['res.users'].sudo().create({
                'name': name,
                'login': login,
                'password': password,
                'email': email,
                'phone': phone,
                'company_id': company_id,
            })

            # ADD 35,10,24 GROUPS
            groups = request.env['res.groups'].sudo().search([('id', 'in', [35,10,24])])
            user.write({
                'groups_id': [(6, 0, groups.ids)]
            })

            return {
                "status": "success",
                "message": "Utente creato con successo",
                "info": "Email sent to user with login credentials"
            }
        except Exception as e:
            _logger.error('User creation error: %s', str(e))
            return {
                "status": "error",
                "message": "Errore del server",
                "info": "Server error occurred"
            }
    


    @http.route('/user/delete', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False)
    def delete(self):
        """
        Description: Deletes a user based on the provided user ID.
        Parameters: user_id
        """
        user_id = request.jsonrequest.get('user_id', False)
        if not user_id:
            return {
                "status": "error",
                "message": "user_id è richiesto",
                "info": "user_id is required"
            }
        try:
            user = request.env['res.users'].sudo().search([('id', '=', user_id)], limit=1)
            if user:
                user.unlink()
                return {
                    "status": "success",
                    "message": "Utente eliminato con successo",
                    "info": "User deleted successfully"
                }
            else:
                return {
                    "status": "error",
                    "message": "Utente non trovato",
                    "info": "User not found"
                }
        except Exception as e:
            _logger.error('User deletion error: %s', str(e))
            return {
                "status": "error",
                "message": "Errore del server",
                "info": "Server error occurred"
            }


    # forgot password
    @http.route('/user/forgot_password', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False)
    def forgot_password(self):
        """
        Description: Resets the user's password and sends an email with the new credentials.
        Parameters: email
        """
        email = request.jsonrequest.get('email', False)
        if not email:
            return {
                "status": "error",
                "message": "Email è richiesto",
                "info": "Email is required"
            }

        try:
            user = request.env['res.users'].sudo().search([('email', '=', email)], limit=1)
            if not user:
                return {
                    "status": "error",
                    "message": "Utente non trovato",
                    "info": "User not found"
                }

            password = generate_password(email)  # Assumes the existence of a function to generate passwords
            user.sudo().write({
                'password': password
            })

            # Attempt to send email
            if not forgot_password(email, password, email):  # Assumes the existence of a function to send emails
                return {
                    "status": "error",
                    "message": "Invio email fallito",
                    "info": "Email sending failed"
                }

            return {
                "status": "success",
                "message": "Password reimpostata con successo",
                "info": "Email sent to user with new login credentials"
            }
        except Exception as e:
            _logger.error('Password reset error: %s', str(e))
            return {
                "status": "error",
                "message": "Errore del server",
                "info": "Server error occurred"
            }



    @http.route('/user/logout', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False)
    def logout(self):
        """
        Description: Logs out the user by terminating the current session.
        Parameters: None
        """
        try:
            data = request.session.logout(keep_db=True)
            _logger.info('Logout successful: %s', data)

            return {
                "status": "success",
                "message": "Disconnesso con successo",
                "info": "Logged out successfully"
            }
        except Exception as e:
            _logger.error('Logout error: %s', str(e))
            return {
                "status": "error",
                "message": "Errore durante la disconnessione",
                "info": "Error during logout"
            }
    

    # get all the banner form the Banners folder and return the image path of all the banners
    @http.route('/api/banners', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    def banners(self):
        """
        Description: Fetches all banner images from the 'images/banners' directory and returns their paths.
        Parameters: None
        """
        banners = []
        try:
            # read the images/banners directory
            for root, dirs, files in os.walk("images/banners"):
                for file in files:
                    if file.endswith(".jpg") or file.endswith(".png"):
                        banners.append(os.path.join(root, file))
        
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
                "info": "Error retrieving banner images"
            }

        return request.make_response(json.dumps(data), [('Content-Type', 'application/json')])
    
    
    @http.route('/images/banners/<path:image>', type='http', auth='public', csrf=False)
    def get_image(self, image):
        image_path = os.path.join('images/banners', image)
        if os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                image_data = f.read()
            return Response(image_data, content_type='image/png')
        else:
            return Response(json.dumps({
                'error': {'message': 'Image not found'},
                'status': 'error',
                'status_code': '404'  # Not Found
            }), content_type='application/json', status=404)
        

