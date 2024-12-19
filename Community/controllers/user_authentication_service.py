from odoo import http, tools, _
from odoo.http import request, Response
from .user_authentication import SocialMediaAuth
from .shared_utilities import save_user_image
import os
import json
import random
from odoo.exceptions import AccessDenied
import logging
import base64
import random

_logger = logging.getLogger(__name__)

class UsersAuthApi(http.Controller):

    def _handle_options(self):
        headers = SocialMediaAuth.get_cors_headers()
        return request.make_response('', headers=headers)
    
    @http.route('/user/reset_password', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def reset_password(self):
        """
        Description: Allows a user to reset their password after verifying the old password.
        Parameters: old_password, new_password
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        old_password = request.jsonrequest.get('old_password', False)
        new_password = request.jsonrequest.get('new_password', False)

        if not old_password or not new_password:
            return {'status': 'error', 'message': 'Sono richieste sia la vecchia password che la nuova password'}

        user_auth = SocialMediaAuth.user_auth(self)  # Assuming this is a custom authentication method
        if user_auth['status'] == 'error':
            return {
                'status': 'error',
                'message': user_auth['message'],  # Assuming this message comes already in Italian
                'info': "Both old and new passwords are required",
                'status_code': 401  # Unauthorized
            }

        try:
            # Fetch the user based on the authenticated user ID
            user = request.env['res.users'].sudo().browse(user_auth['user_id'])
            if not user:
                return {'status': 'error', 'message': 'Utente non trovato', 'info': "User not found"}

            # Verify the old password
            try:
                user._check_credentials(old_password)
                user.sudo().write({'password': new_password})
                return {'status': 'success', 'message': 'La password è stata correttamente resettata', 'info': "Password has been successfully reset"}
            except AccessDenied as e:
                _logger.error('Password reset error: %s', str(e))
                return {'status': 'error', 'message': "Accesso negato", 'info': "Access denied", 'status_code': 401}

        except Exception as e:
            _logger.error('General error during password reset: %s', str(e))
            return {'status': 'error', 'message': "Errore nel reset della password", 'info': "Error in password reset", 'status_code': 500}


        
    @http.route('/user/add_address', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def add_address(self):
        """
        Description: Adds or updates the customer's address in the system.
        Parameters: address, continued_address, city, postal_code, village, country_id, state_id
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        address_details = request.jsonrequest.get('address', False)
        continued_address = request.jsonrequest.get('continued_address', False)
        city = request.jsonrequest.get('city', False)
        postal_code = request.jsonrequest.get('postal_code', False)
        village = request.jsonrequest.get('village', False)
        country_id = request.jsonrequest.get('country_id', False)
        state_id = request.jsonrequest.get('state_id', False)
        
        user_auth = SocialMediaAuth.user_auth(self)  # Assuming this is a custom authentication method
        if user_auth['status'] == 'error':
            return {
                'status': 'error',
                'message': user_auth['message'],
                'info': "Authentication failed",
                'status_code': 401
            }

        try:
            partner_id = user_auth['user_id']
            customer_address = request.env['social_media.custom_address'].search([('partner_id', '=', partner_id)])
            _logger.info(f"Customer Address: {customer_address}")
            
            address_action = 'updated'
            # Check if the customer address exists and update or create new
            if not customer_address:
                address_action = 'created'
                customer_address = request.env['social_media.custom_address'].create({
                    'partner_id': partner_id,
                    'address': address_details,
                    'continued_address': continued_address,
                    'city': city,
                    'postal_code': postal_code,
                    'village': village,
                    'country_id': country_id,
                    'state_id': state_id,
                    'default': True
                })

            partner = request.env['res.partner'].sudo().browse(partner_id)
            if not partner:
                return {'status': 'error', 'message': 'Cliente non trovato', 'info': "Customer not found"}

            partner.sudo().write({
                'street': address_details,
                'street2': continued_address + ' ' + village,
                'city': city,
                'zip': postal_code,
                'country_id': country_id,
                'state_id': state_id
            })

            return {'status': 'success', 'message': f'Indirizzo {address_action} con successo', 'info': f'Address {address_action} successfully'}
        
        except Exception as e:
            _logger.error(f"Error in add/update address: {str(e)}")
            return {'status': 'error', 'message': "Errore durante l'aggiornamento dell'indirizzo", 'info': str(e), 'status_code': 500}


    @http.route('/user/get_address', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def get_address(self):
        """
        Description: Retrieves the address information for an authenticated customer.
        Parameters: None
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        customer_auth = SocialMediaAuth.user_auth(self)
        if customer_auth['status'] == 'error':
            return Response(json.dumps({
                'status': 'error',
                'message': customer_auth['message'],
                'info': "Authentication failed",
                'status_code': 401
            }), content_type='application/json', status=401)

        try:
            partner_id = customer_auth['user_id']
            customer_address = request.env['social_media.custom_address'].search([('partner_id', '=', partner_id)])
            if not customer_address:
                return Response(json.dumps({
                    'status': 'error',
                    'message': 'Nessun indirizzo trovato per questo cliente',
                    'info': 'No address found for this customer'
                }), content_type='application/json', status=404)

            customer_address_data = customer_address.read(['address', 'continued_address', 'city', 'postal_code', 'village', 'default', 'state_id', 'country_id'])

            return Response(json.dumps({"result":{
                'status': 'success',
                'address': customer_address_data
            }}), content_type='application/json')

        except Exception as e:
            _logger.error('Error retrieving customer address: %s', str(e))
            return Response(json.dumps({
                'status': 'error',
                'message': "Errore durante il recupero dell'indirizzo",
                'info': str(e),
                'status_code': 500
            }), content_type='application/json', status=500)


    @http.route('/user/change_default_address', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def change_default_address(self):
        """
        Description: Changes the default address for the customer and updates the customer profile.
        Parameters: address_id
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        customer_auth = SocialMediaAuth.user_auth(self)
        if customer_auth['status'] == 'error':
            return {
                'status': 'error',
                'message': customer_auth['message'],
                'info': "Non authorized",
                'status_code': 401
            }

        partner_id = customer_auth['user_id']
        address_id = request.jsonrequest.get('address_id', False)
        if not address_id:
            return {'status': 'error', 'message': 'L\'ID dell\'indirizzo è richiesto', 'info': 'Address ID is required'}

        try:
            customer_address = request.env['social_media.custom_address'].search([('partner_id', '=', partner_id)])
            if not customer_address:
                return {'status': 'error', 'message': 'Nessun indirizzo trovato per questo cliente', 'info': 'No address found for this customer'}

            # Update the default address
            address = customer_address.filtered(lambda a: a.id == address_id)
            if address:
                customer_address.write({'default': False})  # Reset all addresses to not default
                address.write({'default': True})  # Set the selected one as default
            else:
                return {'status': 'error', 'message': 'Indirizzo non trovato', 'info': 'Address not found'}

            # Update the partner model fields
            partner = request.env['res.partner'].sudo().browse(partner_id)
            if not partner:
                return {'status': 'error', 'message': 'Cliente non trovato', 'info': 'Customer not found'}

            partner.sudo().write({
                'street': address.address,
                'street2': address.continued_address + ' ' + address.village,
                'city': address.city,
                'zip': address.postal_code,
                'country_id': address.country_id.id,
                'state_id': address.state_id.id
            })

            return {'status': 'success', 'message': 'Indirizzo predefinito modificato con successo', 'info': 'Default address changed successfully'}

        except Exception as e:
            _logger.error('Error changing default address: %s', str(e))
            return {
                'status': 'error',
                'message': 'Errore durante la modifica dell\'indirizzo predefinito',
                'info': str(e),
                'status_code': 500
            }
    


    # ---------------------- DOne ---------------------
    @http.route('/user/update_details', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def update_details(self):
        """
        Description: Updates customer profile details such as name and last name.
        Parameters: name, last_name
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        user_auth = SocialMediaAuth.user_auth(self)
        if user_auth['status'] == 'error':
            return {
                'status': 'error',
                'message': user_auth['message'],
                'info': "Non authorized",
                'status_code': 401
            }

        customer_id = user_auth['user_id']  # This is now customer_id from the auth
        name = request.jsonrequest.get('name', False)
        last_name = request.jsonrequest.get('last_name', False)

        try:
            customer = request.env['res.partner'].sudo().search([
                ('id', '=', customer_id),
                ('customer_rank', '>', 0)
            ], limit=1)

            if not customer:
                return {
                    'status': 'error', 
                    'message': 'Utente non trovato', 
                    'info': 'User not found'
                }

            # Construct the full name if both name and last name are provided
            if name and last_name:
                full_name = f"{name} {last_name}"
            elif name:
                full_name = name
            else:
                full_name = customer.name  # Keep existing name if no new name provided

            # Update customer details
            customer.sudo().write({
                'name': full_name,
            })

            return {
                'status': 'success',
                'message': 'Profilo aggiornato con successo',
                'info': 'Profile updated successfully'
            }

        except Exception as e:
            _logger.error('Error updating customer profile: %s', str(e))
            return {
                'status': 'error',
                'message': 'Errore durante l\'aggiornamento del profilo',
                'info': str(e),
                'status_code': 500
            }  

    # ---------------------- DOne ---------------------
    @http.route('/user/profile_image', type='http', auth='public', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def profile_image(self):
        """
        Description: Updates the customer's profile image.
        Parameters: image (file upload)
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        user_auth = SocialMediaAuth.user_auth(self)
        if user_auth['status'] == 'error':
            return request.make_response(json.dumps({
                'status': 'error',
                'message': user_auth['message'],
                'info': 'Authentication failed'
            }), content_type='application/json', status=401)

        customer_id = user_auth['user_id']  # This is now customer_id from the auth
        image_file = request.httprequest.files.get('image')

        if not image_file:
            return Response(json.dumps({
                'status': 'error',
                'message': 'È richiesto un file immagine',
                'info': 'Image file is required'
            }), content_type='application/json', status=400)
        
        try:
            # Read the image file and encode it to base64
            image_content = image_file.read()
            image_base64 = base64.b64encode(image_content).decode('utf-8')

            customer = request.env['res.partner'].sudo().search([
                ('id', '=', customer_id),
                ('customer_rank', '>', 0)
            ], limit=1)

            if not customer:
                return Response(json.dumps({
                    'status': 'error',
                    'message': 'Utente non trovato',
                    'info': 'User not found'
                }), content_type='application/json', status=404)

            # Update the customer's profile image
            customer.sudo().write({
                'image_1920': image_base64
            })
            
            return Response(json.dumps({
                'status': 'success',
                'message': 'Immagine del profilo aggiornata con successo',
                'info': 'Profile image updated successfully'
            }), content_type='application/json')

        except Exception as e:
            _logger.error('Error updating profile image: %s', str(e))
            return Response(json.dumps({
                'status': 'error',
                'message': 'Errore durante l\'aggiornamento dell\'immagine del profilo',
                'info': str(e)
            }), content_type='application/json', status=500)
        

    @http.route('/user/details', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def user_details(self):
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        user_auth = SocialMediaAuth.user_auth(self)
        if 'status' in user_auth and user_auth['status'] == 'error':
            return Response(json.dumps({
                'status': 'error',
                'message': user_auth['message'],
                'info': 'Authentication failed'
            }), content_type='application/json', status=401)

        customer_id = user_auth.get('user_id')
        if not customer_id:
            return Response(json.dumps({
                'status': 'error',
                'message': 'Authentication failed',
                'info': 'User ID missing from authentication'
            }), content_type='application/json', status=400)

        customer = request.env['res.partner'].sudo().search([
            ('id', '=', customer_id),
            ('customer_rank', '>', 0)
        ], limit=1)

        if not customer:
            return Response(json.dumps({
                'status': 'error',
                'message': 'Utente non trovato',
                'info': 'User not found'
            }), content_type='application/json', status=404)
        
        try:
            customer_data = customer.read(['name', 'email', 'phone', 'mobile', 
                                        'street', 'city', 'zip', 'country_id', 
                                        'company_id', 'image_1920'])[0]
            
            name_parts = customer_data['name'].split(' ', 1)
            customer_data['name'] = name_parts[0]
            customer_data['x_last_name'] = name_parts[1] if len(name_parts) > 1 else ''


            image = customer_data.pop('image_1920', None)
            base_path = '/mnt/data/images'
            image_path = os.path.join(base_path, 'profilepics', str(customer_id), 
                                    f'profile_{customer_id}.png')
            customer_data['image_path'] = f'/{image_path}'

            return Response(json.dumps({
                'status': 'success',
                'user': customer_data
            }), content_type='application/json')

        except Exception as e:
            _logger.error('Error retrieving customer details: %s', str(e))
            return Response(json.dumps({
                'status': 'error',
                'message': 'Errore durante il recupero dei dettagli dell\'utente',
                'info': str(e)
            }), content_type='application/json', status=500)

    @http.route('/images/profilepics/<path:image>', type='http', auth='public', csrf=False, cors='*')
    def get_image(self, image):
        try:
            base_path = '/mnt/data/images'
            image_path = os.path.join(base_path, 'profilepics', image)
            safe_path = os.path.join(base_path, 'profilepics')
            
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
            else:
                return Response(json.dumps({
                    'error': {'message': 'Image not found'},
                    'status': 'error',
                    'status_code': '404'
                }), content_type='application/json', status=404)
        except Exception as e:
            _logger.error('Error serving image: %s', str(e))
            return Response(json.dumps({
                'error': {'message': 'Server error'},
                'status': 'error',
                'status_code': '500'
            }), content_type='application/json', status=500)

    # ---------------------- DOne ---------------------
    @http.route('/countries_list', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def countries(self):
        """
        Description: Retrieves a list of all countries and their IDs.
        Parameters: None
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            countries = request.env['res.country'].search_read([], ['id', 'name'])
            return Response(json.dumps({
                'status': 'success',
                'countries': countries
            }), content_type='application/json')

        except Exception as e:
            _logger.error('Error retrieving countries: %s', str(e))
            return Response(json.dumps({
                'status': 'error',
                'message': 'Errore durante il recupero dei paesi',
                'info': str(e)
            }), content_type='application/json', status=500)
        
    # ---------------------- DOne ---------------------
    @http.route('/states_list/<int:country_id>', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def states(self, country_id):
        """
        Description: Retrieves a list of states for a given country ID.
        Parameters: country_id (integer)
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()
        
        try:
            states = request.env['res.country.state'].search_read([('country_id', '=', country_id)], ['id', 'name'])
            if not states:
                return Response(json.dumps({
                    'status': 'error',
                    'message': 'Nessuno stato trovato per questo paese',
                    'info': 'No states found for this country'
                }), content_type='application/json', status=404)

            return Response(json.dumps({
                'status': 'success',
                'states': states
            }), content_type='application/json')

        except Exception as e:
            _logger.error('Error retrieving states for country ID %s: %s', country_id, str(e))
            return Response(json.dumps({
                'status': 'error',
                'message': 'Errore durante il recupero degli stati',
                'info': str(e)
            }), content_type='application/json', status=500)