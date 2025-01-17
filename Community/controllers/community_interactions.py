from odoo import http
from odoo.http import request, Response
from .user_authentication import SocialMediaAuth
from .shared_utilities import Upload_image, get_user_profile_image_path
import os
import json
import random
from .notification_service import CustomerController
import logging

_logger = logging.getLogger(__name__)
notification_service = CustomerController()

class SocialMedia(http.Controller):

    def _handle_options(self):
        headers = SocialMediaAuth.get_cors_headers()
        return request.make_response('', headers=headers)
    

    @http.route('/social_media/create_post', type='http', auth='public', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def create_post(self, **post):
        """
        Description: Creates a new social media post with an optional image.
        Parameters: description (string), image (file)
        """
        
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        user_auth = SocialMediaAuth.user_auth(self)  # Assuming custom auth method
        headers = SocialMediaAuth.get_cors_headers()  # Assuming custom method to get CORS headers

        if user_auth.get('status') == 'error':
            return Response(json.dumps({
                'status': 'error',
                'message': user_auth['message'],
                'info': 'Authentication failed'
            }), content_type='application/json', headers=headers, status=401)

        image_file = request.httprequest.files.get('image')
        description = post.get('description', '')

        if not image_file:
            return Response(json.dumps({
                'status': 'error',
                'message': 'Image file is required',
                'info': 'No image provided'
            }), content_type='application/json', headers=headers, status=400)

        try:
            # Ensure the directory exists
            file_path = Upload_image(image_file)
            
            # Get customer from auth
            customer_id = user_auth['user_id']  # Assuming this is now customer_id from auth
            
            # Verify this is a valid customer
            customer = request.env['res.partner'].sudo().search([
                ('id', '=', customer_id),
                ('customer_rank', '>', 0)
            ], limit=1)
            
            if not customer:
                return Response(json.dumps({
                    'status': 'error',
                    'message': 'Invalid customer',
                    'info': 'Customer not found or not authorized'
                }), content_type='application/json', headers=headers, status=403)

            # Create the post in the database, storing the image path
            post = request.env['social_media.post'].sudo().create({
                'image': file_path,
                'description': description,
                'partner_id': customer_id
            })
            

            customer = request.env['customer.notification'].sudo().search([('partner_id', '=', customer_id)], limit=1)
            device_token = customer.onesignal_player_id
            if device_token:
                print(customer.onesignal_player_id,"-----------customer.onesignal_player_id---------------")
            
                notification_service.send_onesignal_notification(
                    device_token,
                    'Post creato con successo',
                    'Nuovo post',
                    {'type': 'new_post'}
                )
                            
            return Response(json.dumps({
                'status': 'success',
                'post_id': post.id,
                'image_path': file_path
            }), content_type='application/json', headers=headers)

        except Exception as e:
            _logger.error('Error creating social media post: %s', str(e))
            return Response(json.dumps({
                'status': 'error',
                'message': 'Failed to create post',
                'info': str(e)
            }), content_type='application/json', headers=headers, status=500)
            

    @http.route('/social_media/get_posts', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def get_posts(self):
        """
        Retrieve posts from social media model. It filters out posts from blocked customers and formats the response.
        Parameters: None
        """
        # Handle OPTIONS request for CORS preflight
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            user_auth = SocialMediaAuth.user_auth(self)
            if user_auth['status'] == 'error':
                return Response(json.dumps({
                    "status": "error",
                    "message": "Non autorizzato",  # Italian for 'Unauthorized'
                    "info": "The user authentication failed"
                }), content_type='application/json', status=401, headers={'Access-Control-Allow-Origin': '*'})

            # Get all posts
            posts = request.env['social_media.post'].search([])
            
            # Get current customer's data including blocked customers
            user_data = request.env['res.partner'].sudo().search([
                ('id', '=', user_auth['user_id']),
                ('customer_rank', '>', 0)
            ])
            user_data = user_data.read(['blocked_customers'])
            blocked_customers = user_data[0]['blocked_customers']

            # Filter posts and get basic data
            posts_data = [post for post in posts.read(['id', 'image', 'description', 'timestamp', 'partner_id'])
                        if post['partner_id'][0] not in blocked_customers]

            overall_data = []
            for post in posts_data:
                if post['partner_id'][0] in blocked_customers:
                    continue

                # Get customer info
                user_info = request.env['res.partner'].sudo().search([
                    ('id', '=', post['partner_id'][0]),
                    ('customer_rank', '>', 0)
                ])
                
                profile_image = get_user_profile_image_path(user_info.id)

                post.update({
                    'profile_image': profile_image,
                    'user_name': user_info.name,
                    
                    'image': post['image'].replace('/mnt/data', '') if post['image'] else None,
                    'timestamp': post['timestamp'].isoformat() if post['timestamp'] else None,
                    'is_liked': bool(request.env['social_media.like'].search([
                        ('partner_id', '=', user_auth['user_id']), 
                        ('post_id', '=', post['id'])
                    ])),
                    'likes': request.env['social_media.like'].search_count([
                        ('post_id', '=', post['id'])
                    ]),
                    'comments_count': request.env['social_media.comment'].search_count([
                        ('post_id', '=', post['id'])
                    ]),
                    'owner': post['partner_id'][0] == user_auth['user_id'],
                    'user_id': [post['partner_id'][0], post['partner_id'][1]]
                })

                overall_data.append(post)

            overall_data.reverse()

            return Response(json.dumps({
                "result": {
                    "status": "success",
                    "message": "Operazione riuscita", 
                    "posts": overall_data,
                    "info": f"Retrieved {len(overall_data)} posts"
                }
            }), content_type='application/json', headers={'Access-Control-Allow-Origin': '*'})
        
        except Exception as e:
            return Response(json.dumps({
                "status": "error",
                "message": "Errore del server interno",  # Italian for 'Internal Server Error'
                "info": str(e)
            }), content_type='application/json', status=500, headers={'Access-Control-Allow-Origin': '*'})
            
        
    @http.route('/images/community/<path:image>', type='http', auth='public', csrf=False, cors='*')
    def get_image(self, image):
        """
        Retrieve an image from the community images directory with security checks.
        Parameters: image - The path of the image to retrieve.
        """
        try:
            base_path = '/mnt/data/images'
            image_path = os.path.join(base_path, 'community', image)
            safe_path = os.path.join(base_path, 'community')
            
            # Basic path traversal protection
            if not os.path.abspath(image_path).startswith(os.path.abspath(safe_path)):
                return Response(json.dumps({
                    'status': 'error',
                    'message': 'Percorso immagine non valido',  # Italian for 'Invalid image path'
                    'info': 'Invalid image path detected'
                }), content_type='application/json', status=403)

            if os.path.exists(image_path) and os.path.isfile(image_path):
                with open(image_path, 'rb') as f:
                    image_data = f.read()
                return Response(image_data, content_type='image/png')
            else:
                return Response(json.dumps({
                    'status': 'error',
                    'message': 'Immagine non trovata',  # Italian for 'Image not found'
                    'info': 'The requested image was not found'
                }), content_type='application/json', status=404)
                
        except Exception as e:
            _logger.error('Error serving community image: %s', str(e))
            return Response(json.dumps({
                'status': 'error',
                'message': 'Errore del server',  # Italian for 'Server error'
                'info': str(e)
            }), content_type='application/json', status=500)

    @http.route('/social_media/delete_post/<int:post_id>', type='http', auth='public', methods=['DELETE', 'OPTIONS'], csrf=False, cors='*')
    def delete_post(self, post_id):
        """
        Delete a post based on its ID if the authenticated customer is the owner.
        Parameters: post_id - The ID of the post to delete.
        """
        # Handle OPTIONS request for CORS preflight
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            user_auth = SocialMediaAuth.user_auth(self)
            if user_auth['status'] == 'error':
                return Response(json.dumps({
                    "status": "error",
                    "message": "Non autorizzato",  # Italian for 'Unauthorized'
                    "info": "User authentication failed"
                }), content_type='application/json', status=401)

            # Verify customer
            customer = request.env['res.partner'].sudo().search([
                ('id', '=', user_auth['user_id']),
                ('customer_rank', '>', 0)
            ], limit=1)

            if not customer:
                return Response(json.dumps({
                    "status": "error",
                    "message": "Cliente non valido",  # Italian for 'Invalid customer'
                    "info": "Invalid customer credentials"
                }), content_type='application/json', status=403)

            # Find the post
            post = request.env['social_media.post'].search([('id', '=', post_id)])
            if not post:
                return Response(json.dumps({
                    "status": "error",
                    "message": "Post non esiste",  # Italian for 'Post does not exist'
                    "info": "The post with the specified ID does not exist"
                }), content_type='application/json', status=404)

            # Check ownership
            if post.partner_id.id != customer.id:
                return Response(json.dumps({
                    "status": "error",
                    "message": "Non autorizzato a eliminare questo post",  # Italian for 'Not authorized to delete this post'
                    "info": "You are not authorized to delete this post"
                }), content_type='application/json', status=403)
            
            # Remove the image if it exists
            if post.image:
                image_path = post.image
                full_path = os.path.join(os.path.abspath(''), image_path)
                
                # Security check for path
                if os.path.exists(full_path) and os.path.abspath(full_path).startswith(os.path.abspath('images')):
                    try:
                        os.remove(full_path)
                    except OSError as e:
                        _logger.error(f"Error removing image file: {str(e)}")

            # Delete the post
            post.sudo().unlink()
            
            return Response(json.dumps({
                "status": "success",
                "message": "Post eliminato con successo",  # Italian for 'Post deleted successfully'
                "info": "The post was successfully deleted"
            }), content_type='application/json')

        except Exception as e:
            _logger.error(f"Error deleting post: {str(e)}")
            return Response(json.dumps({
                "status": "error",
                "message": "Errore del server interno",  # Italian for 'Internal Server Error'
                "info": str(e)
            }), content_type='application/json', status=500)

        

    @http.route('/social_media/like', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def like_dislike_post(self):
        """
        Toggle the like status of a post for the authenticated customer.
        Parameters: None - Post ID is expected in the JSON request.
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            user_auth = SocialMediaAuth.user_auth(self)
            if user_auth['status'] == 'error':
                return {
                    "status": "error",
                    "message": "Non autorizzato",
                    "info": "Customer authentication failed"
                }, 401

            # Verify customer
            customer = request.env['res.partner'].sudo().search([
                ('id', '=', user_auth['user_id']),
                ('customer_rank', '>', 0)
            ], limit=1)

            if not customer:
                return {
                    "status": "error",
                    "message": "Cliente non valido",
                    "info": "Invalid customer credentials"
                }, 403

            post_id = request.jsonrequest.get('post_id')
            if not post_id:
                return {
                    "status": "error",
                    "message": "ID del post richiesto",
                    "info": "The post ID is required for this operation"
                }, 400

            # Check if already liked
            already_like = request.env['social_media.like'].search([
                ('partner_id', '=', customer.id),
                ('post_id', '=', post_id)
            ])

            if already_like:
                already_like.unlink()
                return {
                    "status": "success",
                    "message": "Mi piace rimosso",
                    "info": "Post disliked successfully"
                }

            # Create new like
            like = request.env['social_media.like'].create({
                'partner_id': customer.id,
                'post_id': post_id
            })
            return {
                "status": "success",
                "message": "Mi piace aggiunto",
                "info": "Post liked successfully",
                "like_id": like.id
            }

        except Exception as e:
            return {
                "status": "error",
                "message": "Errore del server interno",
                "info": str(e)
            }, 500


    @http.route('/social_media/get_likes/<int:post_id>', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def get_likes(self, post_id):
        """
        Retrieve all likes for a given post along with customer information.
        Parameters: post_id - The ID of the post for which likes are being retrieved.
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            user_auth = SocialMediaAuth.user_auth(self)
            if user_auth['status'] == 'error':
                return Response(json.dumps({
                    "status": "error",
                    "message": "Non autorizzato",
                    "info": "Customer authentication failed"
                }), content_type='application/json', status=401)

            likes = request.env['social_media.like'].search([('post_id', '=', post_id)])
            likes_data = likes.read(['partner_id', 'timestamp'])

            # Convert timestamp to ISO 8601 format if present
            for like in likes_data:
                customer_info = request.env['res.partner'].sudo().search([
                    ('id', '=', like['partner_id'][0]),
                    ('customer_rank', '>', 0)
                ])
                profile_image = get_user_profile_image_path(customer_info.id)

                like.update({
                    'profile_image': profile_image,
                    'user_name': customer_info.name,
                    'timestamp': like['timestamp'].isoformat() if like['timestamp'] else None
                })

            result = {
                "status": "success",
                "message": "Mi piace recuperati con successo",
                "info": f"Retrieved likes for post ID {post_id}",
                "likes": likes_data
            }
            return Response(json.dumps({"result": result}), content_type='application/json')

        except Exception as e:
            return Response(json.dumps({
                "status": "error",
                "message": "Errore del server interno",
                "info": str(e)
            }), content_type='application/json', status=500)


    @http.route('/social_media/add_comment', type='json', auth='public', methods=['POST', 'OPTIONS'])
    def create_comment(self):
        """
        Create a comment on a post for the authenticated customer.
        Parameters: None - Post ID and content are expected in the JSON request.
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            user_auth = SocialMediaAuth.user_auth(self)
            if user_auth['status'] == 'error':
                return {
                    "status": "error",
                    "message": "Non autorizzato",
                    "info": "Customer authentication failed"
                }, 401

            # Verify customer
            customer = request.env['res.partner'].sudo().search([
                ('id', '=', user_auth['user_id']),
                ('customer_rank', '>', 0)
            ], limit=1)

            if not customer:
                return {
                    "status": "error",
                    "message": "Cliente non valido",
                    "info": "Invalid customer credentials"
                }, 403

            post_id = request.jsonrequest.get('post_id')
            content = request.jsonrequest.get('content')
            if not post_id or not content:
                return {
                    "status": "error",
                    "message": "ID del post e contenuto sono richiesti",
                    "info": "Both post ID and content must be provided for comment creation"
                }, 400

            comment = request.env['social_media.comment'].create({
                'partner_id': customer.id,
                'post_id': int(post_id),
                'content': content
            })
            return {
                "status": "success",
                "message": "Commento creato con successo",
                "info": f"Comment ID {comment.id} added to post ID {post_id}"
            }

        except Exception as e:
            return {
                "status": "error",
                "message": "Errore del server interno",
                "info": str(e)
            }, 500

    @http.route('/social_media/report_comment', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def report_comment(self):
        """
        Report a comment as inappropriate by the authenticated customer.
        Parameters: None - Comment ID is expected in the JSON request.
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            user_auth = SocialMediaAuth.user_auth(self)
            if user_auth['status'] == 'error':
                return {
                    "status": "error",
                    "message": "Non autorizzato",
                    "info": "Customer authentication failed, unable to report the comment"
                }, 401

            # Verify customer
            customer = request.env['res.partner'].sudo().search([
                ('id', '=', user_auth['user_id']),
                ('customer_rank', '>', 0)
            ], limit=1)

            if not customer:
                return {
                    "status": "error",
                    "message": "Cliente non valido",
                    "info": "Invalid customer credentials"
                }, 403

            comment_id = request.jsonrequest.get('comment_id')
            if not comment_id:
                return {
                    "status": "error",
                    "message": "ID del commento richiesto",
                    "info": "Comment ID is required for reporting"
                }, 400

            # Check if comment exists
            comment = request.env['social_media.comment'].sudo().browse(comment_id)
            if not comment.exists():
                return {
                    "status": "error",
                    "message": "Commento non trovato",
                    "info": "Comment not found"
                }, 404

            # Check if already reported
            already_reported = request.env['social_media.comment_report'].search([
                ('partner_id', '=', customer.id),
                ('comment_id', '=', comment_id)
            ])

            if already_reported:
                already_reported.unlink()
                return {
                    "status": "success",
                    "message": "Segnalazione commento annullata con successo",
                    "info": "Report for the comment has been successfully removed"
                }

            report = request.env['social_media.comment_report'].create({
                'partner_id': customer.id,
                'comment_id': comment_id
            })
            return {
                "status": "success",
                "message": "Commento segnalato con successo",
                "info": f"Comment report ID {report.id} has been successfully created"
            }

        except Exception as e:
            return {
                "status": "error",
                "message": "Errore del server interno",
                "info": str(e)
            }, 500

    
    @http.route('/social_media/get_comments/<int:post_id>', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def get_comments(self, post_id):
        """
        Retrieve all comments for a given post along with customer information, like status, and total likes for each comment.
        Parameters: post_id - The ID of the post for which comments are being retrieved.
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            user_auth = SocialMediaAuth.user_auth(self)
            if user_auth['status'] == 'error':
                return Response(json.dumps({
                    "status": "error",
                    "message": "Non autorizzato",
                    "info": "Customer authentication failed"
                }), content_type='application/json', status=401)

            # Verify customer
            customer = request.env['res.partner'].sudo().search([
                ('id', '=', user_auth['user_id']),
                ('customer_rank', '>', 0)
            ], limit=1)

            if not customer:
                return Response(json.dumps({
                    "status": "error",
                    "message": "Cliente non valido",
                    "info": "Invalid customer credentials"
                }), content_type='application/json', status=403)

            if not post_id:
                return Response(json.dumps({
                    "status": "error",
                    "message": "ID del post richiesto",
                    "info": "The post ID is required for retrieving comments"
                }), content_type='application/json', status=400)

            comments = request.env['social_media.comment'].search([('post_id', '=', post_id)])
            comments_data = comments.read(['partner_id', 'content', 'timestamp'])

            for comment in comments_data:
                customer_info = request.env['res.partner'].sudo().search([
                    ('id', '=', comment['partner_id'][0]),
                    ('customer_rank', '>', 0)
                ])

                profile_image = get_user_profile_image_path(customer_info.id)

                comment.update({
                    'profile_image':f'/{profile_image}',
                    'user_name': customer_info.name,
                    'timestamp': comment['timestamp'].isoformat() if 'timestamp' in comment and comment['timestamp'] else None,
                    'is_liked': bool(request.env['social_media.comment_like'].search([
                        ('partner_id', '=', user_auth['user_id']),
                        ('comment_id', '=', comment['id'])
                    ])),
                    'likes_count': request.env['social_media.comment_like'].search_count([
                        ('comment_id', '=', comment['id'])
                    ]),
                    'user_id' : [comment['partner_id'][0], comment['partner_id'][1] ]

                })

            final_data = {
                "status": "success",
                "message": "Commenti recuperati con successo",
                "info": f"Retrieved comments for post ID {post_id}",
                "comments": comments_data
            }
            return Response(json.dumps({"result": final_data}), content_type='application/json')

        except Exception as e:
            return Response(json.dumps({
                "status": "error",
                "message": "Errore del server interno",
                "info": str(e)
            }), content_type='application/json', status=500)

    @http.route('/social_media/delete_comment/<int:comment_id>', type='http', auth='public', methods=['DELETE', 'OPTIONS'], csrf=False, cors='*')
    def delete_comments(self, comment_id):
        """
        Delete a comment based on its ID if the authenticated customer is the owner of the comment.
        Parameters: comment_id - The ID of the comment to delete.
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            user_auth = SocialMediaAuth.user_auth(self)
            if user_auth['status'] == 'error':
                return Response(json.dumps({
                    "status": "error",
                    "message": user_auth.get('message', 'Non autorizzato'),
                    "info": "Customer authentication failed"
                }), content_type='application/json', status=401)

            # Verify customer
            customer = request.env['res.partner'].sudo().search([
                ('id', '=', user_auth['user_id']),
                ('customer_rank', '>', 0)
            ], limit=1)

            if not customer:
                return Response(json.dumps({
                    "status": "error",
                    "message": "Cliente non valido",
                    "info": "Invalid customer credentials"
                }), content_type='application/json', status=403)

            if not comment_id:
                return Response(json.dumps({
                    "status": "error",
                    "message": "comment_id è richiesto",
                    "info": "The comment ID is required for deletion"
                }), content_type='application/json', status=400)

            comment = request.env['social_media.comment'].search([('id', '=', comment_id)])
            if not comment:
                return Response(json.dumps({
                    "status": "error",
                    "message": "Il commento non esiste",
                    "info": "No comment found with the provided ID"
                }), content_type='application/json', status=404)

            if comment.partner_id.id != customer.id:
                return Response(json.dumps({
                    "status": "error",
                    "message": "Non sei autorizzato a eliminare questo commento",
                    "info": "Only the owner of the comment can delete it"
                }), content_type='application/json', status=403)

            comment.sudo().unlink()
            final_resp = {
                "status": "success",
                "message": "Commento eliminato con successo",
                "info": "The comment has been successfully deleted"
            }
            return Response(json.dumps({"result": final_resp}), content_type='application/json')

        except Exception as e:
            return Response(json.dumps({
                "status": "error",
                "message": "Errore durante l'eliminazione del commento",
                "info": str(e)
            }), content_type='application/json', status=500)   

        

    @http.route('/social_media/like_comment', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def like_comment(self):
        """
        Toggle the like status of a comment for the authenticated customer.
        Parameters: None - Comment ID is expected in the JSON request.
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            user_auth = SocialMediaAuth.user_auth(self)
            if user_auth['status'] == 'error':
                return {
                    "status": "error",
                    "message": "Non autorizzato",
                    "info": "Customer authentication failed"
                }, 401

            # Verify customer
            customer = request.env['res.partner'].sudo().search([
                ('id', '=', user_auth['user_id']),
                ('customer_rank', '>', 0)
            ], limit=1)

            if not customer:
                return {
                    "status": "error",
                    "message": "Cliente non valido",
                    "info": "Invalid customer credentials"
                }, 403

            comment_id = request.jsonrequest.get('comment_id')
            if not comment_id:
                return {
                    "status": "error",
                    "message": "ID del commento richiesto",
                    "info": "Comment ID is required for this operation"
                }, 400

            # Check if already liked
            already_like = request.env['social_media.comment_like'].search([
                ('partner_id', '=', customer.id),
                ('comment_id', '=', comment_id)
            ])
            
            if already_like:
                already_like.unlink()
                return {
                    "status": "success",
                    "message": "Mi piace al commento rimosso",
                    "info": "Comment disliked successfully"
                }

            like = request.env['social_media.comment_like'].create({
                'partner_id': customer.id,
                'comment_id': comment_id
            })
            return {
                "status": "success",
                "message": "Mi piace al commento aggiunto",
                "info": f"Comment liked successfully, like ID {like.id}"
            }

        except Exception as e:
            return {
                "status": "error",
                "message": "Errore del server interno",
                "info": str(e)
            }, 500


    @http.route('/social_media/get_comment_likes/<int:comment_id>', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def get_comment_likes(self, comment_id):
        """
        Retrieve all likes for a given comment, including the customer who liked and the timestamp.
        Parameters: comment_id - The ID of the comment for which likes are being retrieved.
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            user_auth = SocialMediaAuth.user_auth(self)
            if user_auth['status'] == 'error':
                return Response(json.dumps({
                    "status": "error",
                    "message": "Non autorizzato",
                    "info": "Customer authentication failed"
                }), content_type='application/json', status=401)

            # Verify customer
            customer = request.env['res.partner'].sudo().search([
                ('id', '=', user_auth['user_id']),
                ('customer_rank', '>', 0)
            ], limit=1)

            if not customer:
                return Response(json.dumps({
                    "status": "error",
                    "message": "Cliente non valido",
                    "info": "Invalid customer credentials"
                }), content_type='application/json', status=403)

            if not comment_id:
                return Response(json.dumps({
                    "status": "error",
                    "message": "ID del commento richiesto",
                    "info": "Comment ID is required to retrieve likes"
                }), content_type='application/json', status=400)

            # Get likes
            likes = request.env['social_media.comment_like'].search([('comment_id', '=', comment_id)])
            likes_data = likes.read(['partner_id', 'timestamp'])

            # Enhance like data with customer information
            for like in likes_data:
                customer_info = request.env['res.partner'].sudo().search([
                    ('id', '=', like['partner_id'][0]),
                    ('customer_rank', '>', 0)
                ])
                like.update({
                    'customer_name': customer_info.name,
                    'timestamp': like['timestamp'].isoformat() if like['timestamp'] else None
                })

            final_resp = {
                "status": "success",
                "message": "Mi piace al commento recuperati con successo",
                "info": f"Retrieved likes for comment ID {comment_id}",
                "likes": likes_data
            }
            return Response(json.dumps({"result": final_resp}), content_type='application/json')

        except Exception as e:
            return Response(json.dumps({
                "status": "error",
                "message": "Errore del server interno",
                "info": str(e)
            }), content_type='application/json', status=500)
        

    # Block or unblock a user
    @http.route('/social_media/block_user', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def block_user(self):
        """
        Block or unblock a customer. If the customer is currently blocked, they will be unblocked, and vice versa.
        Parameters: None - Blocked customer ID is expected in the JSON request.
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            user_auth = SocialMediaAuth.user_auth(self)
            if user_auth['status'] == 'error':
                return {
                    "status": "error",
                    "message": "Non autorizzato",
                    "info": "Customer authentication failed"
                }, 401

            # Verify customer
            customer = request.env['res.partner'].sudo().search([
                ('id', '=', user_auth['user_id']),
                ('customer_rank', '>', 0)
            ], limit=1)

            if not customer:
                return {
                    "status": "error",
                    "message": "Cliente non valido",
                    "info": "Invalid customer credentials"
                }, 403

            blocked_customer_id = request.jsonrequest.get('blocked_customer_id')
            if not blocked_customer_id:
                return {
                    "status": "error",
                    "message": "ID del cliente da bloccare richiesto",
                    "info": "The blocked customer ID is required for this operation"
                }, 400

            if int(blocked_customer_id) == customer.id:
                return {
                    "status": "error",
                    "message": "Non puoi bloccare o sbloccare te stesso",
                    "info": "A customer cannot block or unblock themselves"
                }, 400

            # Fetch the customer to block
            blocked_customer = request.env['res.partner'].sudo().search([
                ('id', '=', blocked_customer_id),
                ('customer_rank', '>', 0)
            ], limit=1)

            if not blocked_customer:
                return {
                    "status": "error",
                    "message": "Il cliente da bloccare non esiste",
                    "info": "No customer found with the provided ID"
                }, 404

            # Check if the customer is already blocked
            already_blocked = request.env['social_media.blocked_customer'].search([
                ('customer_id', '=', customer.id),
                ('blocked_customer_id', '=', blocked_customer.id)
            ])

            if already_blocked:
                already_blocked.unlink()
                return {
                    "status": "success",
                    "message": "Cliente sbloccato con successo",
                    "info": "The customer has been successfully unblocked"
                }

            # Create new block record
            request.env['social_media.blocked_customer'].create({
                'customer_id': customer.id,
                'blocked_customer_id': blocked_customer.id
            })

            return {
                "status": "success",
                "message": "Cliente bloccato con successo",
                "info": "The customer has been successfully blocked"
            }

        except Exception as e:
            return {
                "status": "error",
                "message": "Errore del server interno",
                "info": str(e)
            }, 500
        

    @http.route('/social_media/report_post', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def report_post(self):
        """
        Report a post for review. Prevents duplicate reports by the same customer on the same post.
        Parameters: None - Post ID is expected in the JSON request.
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            user_auth = SocialMediaAuth.user_auth(self)
            if user_auth['status'] == 'error':
                return {
                    "status": "error",
                    "message": "Non autorizzato",
                    "info": "Customer authentication failed"
                }, 401

            # Verify customer
            customer = request.env['res.partner'].sudo().search([
                ('id', '=', user_auth['user_id']),
                ('customer_rank', '>', 0)
            ], limit=1)

            if not customer:
                return {
                    "status": "error",
                    "message": "Cliente non valido",
                    "info": "Invalid customer credentials"
                }, 403

            post_id = request.jsonrequest.get('post_id')
            if not post_id:
                return {
                    "status": "error",
                    "message": "ID del post richiesto",
                    "info": "The post ID is required to report the post"
                }, 400

            # Check if already reported
            report = request.env['social_media.report'].search([
                ('post_id', '=', post_id), 
                ('partner_id', '=', customer.id)
            ])

            if report:
                return {
                    "status": "error",
                    "message": "Post già segnalato",
                    "info": "You have already reported this post"
                }, 400

            # Create new report
            report = request.env['social_media.report'].create({
                'post_id': post_id,
                'partner_id': customer.id
            })

            return {
                "status": "success",
                "message": "Post segnalato con successo",
                "info": f"Report ID {report.id} has been successfully created"
            }

        except Exception as e:
            return {
                "status": "error",
                "message": "Errore del server interno",
                "info": str(e)
            }, 500
        
        