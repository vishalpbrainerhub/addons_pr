# -*- coding: utf-8 -*-

import json
import logging
from odoo import http, models, fields
from odoo.http import request, Response
from .user_authentication import SocialMediaAuth

_logger = logging.getLogger(__name__)

class NotificationController(http.Controller):
    
    @http.route('/api/notifications', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def get_notifications(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        user_auth = SocialMediaAuth.user_auth(self)
        headers = SocialMediaAuth.get_cors_headers()

        if user_auth.get('status') == 'error':
            return Response(json.dumps({
                'status': 'error',
                'message': user_auth['message']
            }), content_type='application/json', headers=headers, status=401)

        customer_id = user_auth['user_id']

        try:
            notifications = request.env['notification.storage'].sudo().search([
                ('patner_id', '=', customer_id)  # Changed from partner_id to patner_id
            ])

            data = [{
                'id': notif.id,
                'message': notif.message,
                'title': notif.title,
                'data': notif.data,
                'filter': notif.filter,
                'create_date': notif.create_date,
            } for notif in notifications]

            return Response(json.dumps({
                'status': 'success',
                'data': data
            }), content_type='application/json', headers=headers)

        except Exception as e:
            _logger.error('Error fetching notifications: %s', str(e))
            return Response(json.dumps({
                'status': 'error',
                'message': str(e)
            }), content_type='application/json', headers=headers, status=500)


