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
        """
        Description: Authenticates a customer and generates a session token.
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

            # Find customer instead of user
            customer = request.env['res.partner'].sudo().search([
                ('email', '=', email),
                ('customer_rank', '>', 0)  # Ensure it's a customer
            ], limit=1)

            if not customer:
                return {
                    "status": "error",
                    "message": "Utente non trovato",
                    "info": "User not found"
                }

           

            # Create JWT token
            payload = {
                'user_id': customer.id,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=2)
            }

            # Fix for JWT secret key
            secret_key = 'testing'
            if not secret_key:
                return {
                    "status": "error",
                    "message": "Chiave segreta JWT non configurata",
                    "info": "JWT secret key not configured"
                }

            token = jwt.encode(payload, str(secret_key), algorithm='HS256')

            # Prepare user data from customer
            user_data = {
                'name': customer.name,
                'login': customer.email,  
                'email': customer.email,
                'phone': customer.phone,
                'company_id': customer.company_id.id if customer.company_id else False,
                'lang': customer.lang or 'en_US'
            }

            return {
                "status": "success",
                "message": "Accesso utente eseguito con successo, procedi con il completamento",
                "info": "User login successful, proceed to completion",
                "user": user_data,
                "token": token.decode('utf-8') if isinstance(token, bytes) else token,
            }

        except Exception as e:
            _logger.error('Login error: %s', str(e))
            return {
                "status": "error",
                "message": "Errore del server",
                "info": "Server error occurred"
            }


     # ---------------------- Done --------------------------------
    
    
    @http.route('/api/banners', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    def banners(self):
        banners = []
        try:
            banner_dir = 'images/banners'
            for root, dirs, files in os.walk(banner_dir):
                for file in files:
                    if file.endswith((".jpg", ".png")):
                        path = os.path.join(root, file)
                        banners.append(f'/{path}')
        
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
    
    # ---------------------- Done --------------------------------
    @http.route('/images/banners/<path:image>', type='http', auth='public', csrf=False)
    def get_image(self, image):
        image_path = os.path.join('images/banners', image)
        if os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                image_data = f.read()
            return Response(image_data, content_type='image/png')
        return Response(json.dumps({
            'error': {'message': 'Image not found'},
            'status': 'error',
            'status_code': '404'
        }), content_type='application/json', status=404)
    

    @http.route('/api/export/customers', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def export_customers(self):
        """
        Export customer data to CSV file
        Fields: id, name, vat, l10n_it_codice_fiscale (if available), property_product_pricelist
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            # Create OUT directory if it doesn't exist
            os.makedirs('OUT', exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'OUT/customers_export_{timestamp}.csv'

            # Get all customers
            Partner = request.env['res.partner'].sudo()
            
            # Check if l10n_it_codice_fiscale field exists
            has_codice_fiscale = 'l10n_it_codice_fiscale' in Partner._fields
            
            # Define fields based on availability
            fieldnames = ['id', 'name', 'vat']
            if has_codice_fiscale:
                fieldnames.append('l10n_it_codice_fiscale')
            fieldnames.append('property_product_pricelist')

            # Get all customers
            customers = Partner.search([('customer_rank', '>', 0)])

            # Write to CSV
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Write headers
                writer.writeheader()
                
                # Write customer data
                for customer in customers:
                    # Prepare row data
                    row = {
                        'id': customer.id,
                        'name': customer.name or '',
                        'vat': customer.vat or '',
                    }
                    
                    # Add codice fiscale if field exists
                    if has_codice_fiscale:
                        row['l10n_it_codice_fiscale'] = getattr(customer, 'l10n_it_codice_fiscale', '') or ''
                    
                    # Add pricelist
                    row['property_product_pricelist'] = customer.property_product_pricelist.name if customer.property_product_pricelist else ''
                    
                    writer.writerow(row)

            # Return success response with file path
            return Response(json.dumps({
                'status': 'success',
                'message': 'File esportato con successo',
                'info': 'File exported successfully',
                'file_path': filename
            }), content_type='application/json')

        except Exception as e:
            _logger.error('Error exporting customers: %s', str(e))
            return Response(json.dumps({
                'status': 'error',
                'message': 'Errore durante l\'esportazione dei clienti',
                'info': str(e)
            }), content_type='application/json', status=500)