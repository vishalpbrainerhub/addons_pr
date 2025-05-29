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

class AgentAuthApis(http.Controller):

    def _handle_options(self):
        headers = SocialMediaAuth.get_cors_headers()
        return request.make_response('', headers=headers)
    
    
    
    @http.route('/agent/get_customer', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def agent_get_customer(self):
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        user_auth = SocialMediaAuth.user_auth(self)
        if 'status' in user_auth and user_auth['status'] == 'error':
            return Response(json.dumps({
                'status': 'error', 
                'message': user_auth['message'],
                'info': 'Authentication failed'
            }), content_type='application/json', status=401)

        agent_auth_id = user_auth.get('user_id')
        if not agent_auth_id:
            return Response(json.dumps({
                'status': 'error',
                'message': 'Authentication failed', 
                'info': 'User ID missing from authentication'
            }), content_type='application/json', status=400)

        # Verify the authenticated user is an agent
        agent = request.env['res.partner'].sudo().search([
            ('id', '=', agent_auth_id),
        ], limit=1)

        if not agent:
            return Response(json.dumps({
                'status': 'error',
                'message': 'Agente non trovato',
                'info': 'Agent not found or user is not an agent'
            }), content_type='application/json', status=404)
            
        try:
            
            print(agent_auth_id,'agent_auth_id')
            # Get the agent's external import record to find their external_import_id
            agent_import_record = request.env['external.import'].sudo().search([
                ('partner_id', '=', agent_auth_id),
                ('is_agent', '=', True)
            ], limit=1)
            
            if not agent_import_record:
                return Response(json.dumps({
                    'status': 'error',
                    'message': 'Record di importazione agente non trovato',
                    'info': 'Agent import record not found'
                }), content_type='application/json', status=404)
            
            agent_external_id = agent_import_record.external_import_id
            print(agent_external_id, "agent_external_id")
            
            # CORRECTED: Get customers directly by agent_id field in res.partner
            # This matches how the relationship import sets customer.agent_id = agent.id
            customers_external_data = request.env['external.import'].sudo().search([
                ('agent_id', '=', agent_external_id),  # Direct relationship in res.partner
                ('is_agent', '=', False)
            ])
            
            print(len(customers_external_data),"customers_external_data")
            

            customer_data = []
            
            for customer in customers_external_data:
                print(customer.partner_id,"customer.partner_id")
                print(customer.agent_id,"customer.agent_id")
                # Get the customer's external import record for additional data
                local_customer = request.env['res.partner'].sudo().search([
                    ('id', '=', customer.partner_id.id)  # Add .id here
                ], limit=1)
                
                print(local_customer,"local_customer")
                # Get custom address if available
                custom_address = request.env['social_media.custom_address'].sudo().search([
                    ('partner_id', '=', customer.partner_id.id),
                    ('default', '=', True)
                ], limit=1)
                
                customer_info = {
                    'id': local_customer.id,
                    'name': local_customer.name,
                    'email': local_customer.email or '',
                    'phone': local_customer.phone or '',
                    'mobile': local_customer.mobile or '',
                    'street': local_customer.street or '',
                    'street2': local_customer.street2 or '',
                    'city': local_customer.city or '',
                    'zip': local_customer.zip or '',
                    'country': local_customer.country_id.name if local_customer.country_id else '',
                    'state': local_customer.state_id.name if local_customer.state_id else '',
                    'vat': local_customer.vat or '',
                    'is_company': local_customer.is_company,
                    'create_date': local_customer.create_date.isoformat() if local_customer.create_date else None,
                    'write_date': local_customer.write_date.isoformat() if local_customer.write_date else None,
                }
                
                # Add custom address information if available
                if custom_address:
                    customer_info.update({
                        'custom_address': {
                            'address': custom_address.address or '',
                            'continued_address': custom_address.continued_address or '',
                            'city': custom_address.city or '',
                            'postal_code': custom_address.postal_code or '',
                            'village': custom_address.village or '',
                            'state': custom_address.state_id.name if custom_address.state_id else '',
                            'country': custom_address.country_id.name if custom_address.country_id else ''
                        }
                    })
                
                customer_data.append(customer_info)
            
            # Sort customers by name for better user experience
            customer_data.sort(key=lambda x: x['name'].lower())
            
            return Response(json.dumps({
                'status': 'success',
                'agent_info': {
                    'id': agent.id,
                    'name': agent.name,
                    'email': agent.email or '',
                    'external_import_id': agent_external_id,
                    'total_customers': len(customer_data)
                },
                'customers': customer_data,
                'total_count': len(customer_data)
            }), content_type='application/json')

        except Exception as e:
            _logger.error('Error retrieving customers for agent', str(e))
            return Response(json.dumps({
                'status': 'error',
                'message': 'Errore durante il recupero dei clienti',
                'info': str(e)
            }), content_type='application/json', status=500)