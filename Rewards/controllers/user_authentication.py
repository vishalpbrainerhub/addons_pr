import jwt
from odoo import http, models, fields, api
from odoo.http import request
import requests
import os
from dotenv import load_dotenv

load_dotenv()


def user_auth(self):
        auth_header = request.httprequest.headers.get('Authorization', False)
        if not auth_header:
            return {
                "status": "error",
                "message": "Token is required."
            }
        token = auth_header.split(' ')[1]
        secret_key =  "testing_enviroment"
        try:
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