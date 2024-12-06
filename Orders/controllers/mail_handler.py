from odoo import http
from odoo.http import request, Response
import json

class EmailController(http.Controller):

    @http.route('/api/send_email', auth='user', type='json', methods=['POST'])
    def send_email(self):
        # Accessing the JSON data from the request
        email_to = request.jsonrequest.get('email_to')
        subject = request.jsonrequest.get('subject')
        body_html = request.jsonrequest.get('body_html')

        # Basic validation of required fields
        if not email_to or not subject or not body_html:
            return Response(json.dumps({
                'status': 'error',
                'message': 'Missing required fields: email_to, subject, or body_html.'
            }), content_type='application/json', status=400, headers={'Access-Control-Allow-Origin': '*'})

        # Create the email
        mail_values = {
            'subject': subject,
            'email_to': email_to,
            'body_html': body_html,
            'email_from': request.env.user.email or 'no-reply@yourdomain.com',  # Set a default email_from if user email is not available
        }
        mail = request.env['mail.mail'].create(mail_values)

        # Send the email
        try:
            mail.send()
            return {'status': 'success', 'message': 'Email sent successfully!'}
        except Exception as e:
            return Response(json.dumps({
                'status': 'error',
                'message': str(e)
            }), content_type='application/json', status=500, headers={'Access-Control-Allow-Origin': '*'})

