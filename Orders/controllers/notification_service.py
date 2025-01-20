# Add these imports at the top
import requests
import json
from odoo import http
from odoo.http import request
import logging
_logger = logging.getLogger(__name__)



class CustomerController(http.Controller):
    
    ONESIGNAL_APP_ID = "1803cfbe-6c0d-4be6-af61-63d649cd324d"
    ONESIGNAL_REST_API_KEY = "os_v2_app_dab47ptmbvf6nl3bmplettjsjvdflb5gfkfeyqmsejilv2xgls2aioyn2escig6jdgbn5hnzj4usqsxtb2g3t2uf6kvnuzfmlmuimoa"
    ONESIGNAL_API_URL = "https://onesignal.com/api/v1"
    
    
   
    
    def send_onesignal_notification(self, device_tokens, message, title="", data=None):
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.ONESIGNAL_REST_API_KEY}",
            "content-type": "application/json"
        }
        
        
        notification_payload = {
            "app_id": self.ONESIGNAL_APP_ID,
            "contents": {"en": message},
            "headings": {"en": title},
            "include_player_ids": [device_tokens],
            "priority": 10,
            "data": {"custom_data": "test_data"}
        }

        try:
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
        
        
    def send_onesignal_notification_to_all(self, message, title="", data=None):
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.ONESIGNAL_REST_API_KEY}",
            "content-type": "application/json"
        }
        
        notification_payload = {
            "app_id": self.ONESIGNAL_APP_ID,
            "contents": {"en": message},
            "headings": {"en": title},
            "included_segments": ["All"],
            "priority": 10,
            "data": {"custom_data": "test_data"}
        }
        
        try:
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