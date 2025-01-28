# Add these imports at the top
import requests
import json
from odoo import http
from odoo.http import request
import logging
import os
_logger = logging.getLogger(__name__)



class CustomerController(http.Controller):
    
    ONESIGNAL_APP_ID = os.environ["ONESIGNAL_APP_ID"]
    ONESIGNAL_REST_API_KEY = os.environ["ONESIGNAL_REST_API_KEY"]
    ONESIGNAL_API_URL = os.environ["ONESIGNAL_API_URL"]
    
    def send_onesignal_notification(self, device_tokens, message, title="", data=None):
        headers = {
            "accept": "application/json",
            "Authorization": f"Basic {self.ONESIGNAL_REST_API_KEY}",
            "content-type": "application/json"
        }
        
        notification_payload = {
            "app_id": self.ONESIGNAL_APP_ID,
            "contents": {"en": message},
            "headings": {"en": title},
            "include_player_ids": [device_tokens] if isinstance(device_tokens, str) else device_tokens,
            "priority": 10,
            "data": data or {"custom_data": "test_data"}
        }

        try:
            _logger.info('Sending OneSignal notification: %s', notification_payload)
            response = requests.post(
                f"{self.ONESIGNAL_API_URL}/notifications",
                headers=headers,
                json=notification_payload
            )
            _logger.info(f"OneSignal API Response: {response.text}")
            response.raise_for_status()
            try:
                return {'status': 'success', 'data': response.json()}
            except json.JSONDecodeError:
                return {'status': 'error', 'message': 'Invalid JSON response from OneSignal API'}
        except requests.exceptions.RequestException as e:
            _logger.error(f"OneSignal API error: {str(e)}")
            return {'status': 'error', 'message': str(e)}