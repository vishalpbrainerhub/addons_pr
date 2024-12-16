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
        Authenticate the customer by verifying the JWT token from the request headers.

        Returns:
            dict: A dictionary containing the status of the authentication, 
                 potentially with the customer ID if successful or an error message if not.
        """
        auth_header = request.httprequest.headers.get('Authorization', False)
        if not auth_header:
            return {
                "status": "error",
                "message": "Token is required."
            }

        # Extract the actual token part following the 'Bearer' keyword
        try:
            token = auth_header.split(' ')[1]
        except IndexError:
            return {
                "status": "error",
                "message": "Invalid authorization header format."
            }

        secret_key = "testing"

        try:
            # Decode the JWT token to extract customer information
            payload = jwt.decode(token, secret_key, algorithms=['HS256'])
            
            # Search for customer instead of user
            customer = request.env['res.partner'].sudo().search([
                ('id', '=', payload['user_id']),
                ('customer_rank', '>', 0)  # Ensure it's a customer
            ])
            
            if customer:
                return {
                    "status": "success",
                    "user_id": customer.id,  # Keeping user_id in response for compatibility
                }
            else:
                return {
                    "status": "error",
                    "message": "Invalid token or customer not found."
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