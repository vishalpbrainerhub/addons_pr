# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime
from odoo import http, models, fields
from odoo.http import request, Response
from .user_authentication import SocialMediaAuth

_logger = logging.getLogger(__name__)

class NotificationController(http.Controller):
    
    def _serialize_datetime(self, dt):
        return dt.strftime('%Y-%m-%d %H:%M:%S') if dt else None
    
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
                ('patner_id', '=', customer_id)
            ])

            data = [{
                'id': notif.id,
                'message': notif.message,
                'title': notif.title,
                'data': notif.data,
                'filter': notif.filter,
                'create_date': self._serialize_datetime(notif.create_date),
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
            
            
    @http.route('/api/notification_status', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def update_notification_status(self, **post):
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        user_auth = SocialMediaAuth.user_auth(self)
        headers = SocialMediaAuth.get_cors_headers()

        if user_auth.get('status') == 'error':
            return Response(json.dumps({
                'status': 'error',
                'message': user_auth['message']
            }), content_type='application/json', headers=headers, status=401)

        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
            customer_id = user_auth['user_id']
            
            status = request.env['notification.status'].sudo().search([
                ('partner_id', '=', customer_id)
            ], limit=1)
            
            values = {
                'community': data.get('community', True),
                'promo': data.get('promo', True),
                'order': data.get('order', True),
                'partner_id': customer_id
            }
            
            if status:
                status.write(values)
            else:
                status = request.env['notification.status'].sudo().create(values)

            return {
                'status': 'success',
                'data': {
                    'id': status.id,
                    'community': status.community,
                    'promo': status.promo,
                    'order': status.order
                }
            }

        except Exception as e:
            _logger.error('Error updating notification status: %s', str(e))
            return{
                'status': 'error',
                'message': str(e)
            }