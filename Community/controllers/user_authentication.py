from odoo import http, models, fields, api
from odoo.http import request
import jwt
import requests
import os
from dotenv import load_dotenv

load_dotenv()

class SocialMediaAuth(http.Controller):
    

    def get_cors_headers():
        """
        Define and return the necessary CORS headers for the response.
        
        Returns:
            list of tuples: Each tuple contains a header key and its corresponding value.
        """
        return [
            ('Content-Type', 'application/json'),
            ('Access-Control-Allow-Origin', '*'),
            ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
            ('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept')
        ]

    
    def user_auth(self):
        """
        Authenticate the user by verifying the JWT token from the request headers.

        Returns:
            dict: A dictionary containing the status of the authentication, potentially with the user ID if successful or an error message if not.
        """
        token = request.httprequest.headers.get('Authorization', False)
        if not token:
            return {
                "status": "error",
                "message": "Token is required."
            }

        # Extract the actual token part following the 'Bearer' keyword
        token = token.split(' ')[1]
        secret_key = "testing_enviroment"

        try:
            # Decode the JWT token to extract user information
            payload = jwt.decode(token, secret_key, algorithms=['HS256'])
            user = request.env['res.users'].sudo().search([('id', '=', payload['user_id'])])
            if user:
                return {
                    "status": "success",
                    "user_id": user.id,
                }
            else:
                return {
                    "status": "error",
                    "message": "Invalid token."
                }
        except jwt.ExpiredSignatureError:
            return {
                "status": "error",
                "message": "Token is expired."
            }
        except jwt.InvalidTokenError:
            return {
                "status": "error",
                "message": "Invalid token."
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
        