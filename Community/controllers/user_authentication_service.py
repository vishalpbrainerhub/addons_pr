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


        


    # update the user's address
    @http.route('/user/add_address', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def add_address(self):
        """
        Description: Adds or updates the user's address in the system.
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
                'status_code': 401  # Unauthorized
            }

        try:
            user_id = user_auth['user_id']
            user_address = request.env['social_media.custom_address'].search([('user_id', '=', user_id)])
            _logger.info(f"User Address: {user_address}")
            
            address_action = 'updated'
            # Check if the user address exists and update or create new
            if not user_address:
                address_action = 'created'
                user_address = request.env['social_media.custom_address'].create({
                    'user_id': user_id,
                    'address': address_details,
                    'continued_address': continued_address,
                    'city': city,
                    'postal_code': postal_code,
                    'village': village,
                    'country_id': country_id,
                    'state_id': state_id,
                    'default': True
                })

            user = request.env['res.users'].sudo().browse(user_id)
            if not user:
                return {'status': 'error', 'message': 'Utente non trovato', 'info': "User not found"}

            user.sudo().write({
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
        Description: Retrieves the address information for an authenticated user.
        Parameters: None
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        user_auth = SocialMediaAuth.user_auth(self)  # Assuming this is a custom authentication method
        if user_auth['status'] == 'error':
            return Response(json.dumps({
                'status': 'error',
                'message': user_auth['message'],  # Assuming the message is already in Italian
                'info': "Authentication failed",
                'status_code': 401  # Unauthorized
            }), content_type='application/json', status=401)

        try:
            user_id = user_auth['user_id']
            user_address = request.env['social_media.custom_address'].search([('user_id', '=', user_id)])
            if not user_address:
                return Response(json.dumps({
                    'status': 'error',
                    'message': 'Nessun indirizzo trovato per questo utente',
                    'info': 'No address found for this user'
                }), content_type='application/json', status=404)

            user_address_data = user_address.read(['address', 'continued_address', 'city', 'postal_code', 'village', 'default', 'state_id', 'country_id'])

            return Response(json.dumps({"result":{
                'status': 'success',
                'address': user_address_data
            }}), content_type='application/json')

        except Exception as e:
            _logger.error('Error retrieving user address: %s', str(e))
            return Response(json.dumps({
                'status': 'error',
                'message': "Errore durante il recupero dell'indirizzo",
                'info': str(e),
                'status_code': 500  # Internal Server Error
            }), content_type='application/json', status=500)
        

        

    @http.route('/user/change_default_address', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def change_default_address(self):
        """
        Description: Changes the default address for the user and updates the user profile.
        Parameters: address_id
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        user_auth = SocialMediaAuth.user_auth(self)  # Assuming this is a custom authentication method
        if user_auth['status'] == 'error':
            return {
                'status': 'error',
                'message': user_auth['message'],
                'info': "Non authorized",
                'status_code': 401  # Unauthorized
            }

        user_id = user_auth['user_id']
        address_id = request.jsonrequest.get('address_id', False)
        if not address_id:
            return {'status': 'error', 'message': 'L\'ID dell\'indirizzo è richiesto', 'info': 'Address ID is required'}

        try:
            user_address = request.env['social_media.custom_address'].search([('user_id', '=', user_id)])
            if not user_address:
                return {'status': 'error', 'message': 'Nessun indirizzo trovato per questo utente', 'info': 'No address found for this user'}

            # Update the default address
            address = user_address.filtered(lambda a: a.id == address_id)
            if address:
                user_address.write({'default': False})  # Reset all addresses to not default
                address.write({'default': True})  # Set the selected one as default
            else:
                return {'status': 'error', 'message': 'Indirizzo non trovato', 'info': 'Address not found'}

            # Update the user model fields
            user = request.env['res.users'].sudo().browse(user_id)
            if not user:
                return {'status': 'error', 'message': 'Utente non trovato', 'info': 'User not found'}

            user.sudo().write({
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



    @http.route('/user/update_details', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def update_details(self):
        """
        Description: Updates user profile details such as name and last name.
        Parameters: name, last_name
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        user_auth = SocialMediaAuth.user_auth(self)  # Assuming this is a custom authentication method
        if user_auth['status'] == 'error':
            return {
                'status': 'error',
                'message': user_auth['message'],
                'info': "Non authorized",
                'status_code': 401  # Unauthorized
            }

        user_id = user_auth['user_id']
        name = request.jsonrequest.get('name', False)
        last_name = request.jsonrequest.get('last_name', False)

        try:
            user = request.env['res.users'].sudo().browse(user_id)
            if not user:
                return {'status': 'error', 'message': 'Utente non trovato', 'info': 'User not found'}

            # Update user details
            user.sudo().write({
                'name': name,  # Update if provided, otherwise keep existing
                'x_last_name': last_name  # Custom field: ensure it exists
            })

            return {'status': 'success', 'message': 'Profilo aggiornato con successo', 'info': 'Profile updated successfully'}

        except Exception as e:
            _logger.error('Error updating user profile: %s', str(e))
            return {
                'status': 'error',
                'message': 'Errore durante l\'aggiornamento del profilo',
                'info': str(e),
                'status_code': 500
            }
        

    @http.route('/user/profile_image', type='http', auth='public', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def profile_image(self):
        """
        Description: Updates the user's profile image.
        Parameters: image (file upload)
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        user_auth = SocialMediaAuth.user_auth(self)  # Assuming this is a custom authentication method
        if user_auth['status'] == 'error':
            return request.make_response(json.dumps({
                'status': 'error',
                'message': user_auth['message'],
                'info': 'Authentication failed'
            }), content_type='application/json', status=401)

        user_id = user_auth['user_id']
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

            user = request.env['res.users'].sudo().browse(user_id)
            if not user:
                return Response(json.dumps({
                    'status': 'error',
                    'message': 'Utente non trovato',
                    'info': 'User not found'
                }), content_type='application/json', status=404)

            # Update the user's profile image
            user.sudo().write({
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

        user_id = user_auth.get('user_id')
        if not user_id:
            return Response(json.dumps({
                'status': 'error',
                'message': 'Authentication failed',
                'info': 'User ID missing from authentication'
            }), content_type='application/json', status=400)

        user = request.env['res.users'].sudo().browse(user_id)
        if not user:
            return Response(json.dumps({
                'status': 'error',
                'message': 'Utente non trovato',
                'info': 'User not found'
            }), content_type='application/json', status=404)
        
        try:
            user_data = user.read(['name', 'login', 'email', 'phone', 'company_id', 'blocked_users', 'x_last_name', 'image_1920'])[0]
            image = user_data.pop('image_1920', None)  
            
            image_path = save_user_image(user_id, image)
            user_data['image_path'] = image_path

            return Response(json.dumps({
                'status': 'success',
                'user': user_data
            }), content_type='application/json')

        except Exception as e:
            _logger.error('Error retrieving user details: %s', str(e))
            return Response(json.dumps({
                'status': 'error',
                'message': 'Errore durante il recupero dei dettagli dell\'utente',
                'info': str(e)
            }), content_type='application/json', status=500)
    


    @http.route('/images/profilepics/<path:image>', type='http', auth='public', csrf=False,cors='*')
    def get_image(self, image):
        image_path = os.path.join('/mnt/extra-addons/images/profilepics', image)
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